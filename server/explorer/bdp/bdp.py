import json
import os
import re
import zipfile
from typing import Dict, List, Optional

import numpy as np
from rtree import index
from saas.core.helpers import write_json_to_file, get_timestamp_now
from saas.core.logging import Logging
from saas.sdk.base import SDKContext
from shapely.geometry import shape

from explorer.dots.duct_ahprofile import AnthropogenicHeatProfile
from explorer.dots.duct_lcz import LocalClimateZoneMap
from explorer.dots.duct_urban_geometries import UrbanGeometries
from explorer.bdp.base import BaseDataPackageDB
from explorer.geodb import GeometryType
from explorer.schemas import BaseDataPackage, ExplorerRuntimeError

from geopandas import gpd

logger = Logging.get('explorer.bdp.bdp')

bdp_spec = {
    'city-admin-zones': {
        'type': 'DUCT.GeoVectorData',
        'format': 'geojson'
    },
    'building-footprints': {
        'type': 'DUCT.GeoVectorData',
        'format': 'geojson'
    },
    'land-use': {
        'type': 'DUCT.GeoVectorData',
        'format': 'geojson'
    },
    'vegetation': {
        'type': 'DUCT.GeoVectorData',
        'format': 'geojson'
    },
    # 'land-cover': {
    #     'type': 'DUCT.GeoRasterData',
    #     'format': 'tiff'
    # },
    'lcz-baseline': {
        'type': LocalClimateZoneMap.DATA_TYPE,
        'format': 'tiff'
    },
    'sh-traffic-baseline': {
        'type': AnthropogenicHeatProfile.DATA_TYPE,
        'format': 'geojson'
    },
    'sh-traffic-ev100': {
        'type': AnthropogenicHeatProfile.DATA_TYPE,
        'format': 'geojson'
    },
    'sh-power-baseline': {
        'type': AnthropogenicHeatProfile.DATA_TYPE,
        'format': 'geojson'
    },
    'lh-power-baseline': {
        'type': AnthropogenicHeatProfile.DATA_TYPE,
        'format': 'geojson'
    },
    'description': {
        'type': '*.BDPDescription',
        'format': 'markdown'
    }
}


def fix_feature_geometry(feature: dict) -> Optional[dict]:
    def ensure_2d_polygons(polygons) -> None:
        for j, polygon in enumerate(polygons):
            polygons[j] = [
                [point[0], point[1]] for point in polygon
            ]

    # ensure only 2D coordinates are used
    if feature['geometry']['type'] == 'Polygon':
        ensure_2d_polygons(feature['geometry']['coordinates'])
    elif feature['geometry']['type'] == 'MultiPolygon':
        for i, multipolygon in enumerate(feature['geometry']['coordinates']):
            ensure_2d_polygons(multipolygon)
    else:
        raise ExplorerRuntimeError(f"Unsupported geometry type {feature['geometry']['type']}")

    # check feature geometry
    geom = shape(feature['geometry'])
    if not geom.is_valid:
        try:
            # try buffering with zero distance
            fixed_geom = geom.buffer(0)
            if not fixed_geom.is_valid:
                # try to simplify the geometry
                fixed_geom = geom.simplify(tolerance=0.01, preserve_topology=True)
                if not fixed_geom.is_valid:
                    raise ExplorerRuntimeError(f"Cannot fix geometry")

            # use the fixed geometry
            feature['geometry'] = fixed_geom.__geo_interface__

        except Exception as e:
            logger.warning(f"unfixable feature ({e}): {feature}")
            return None

    return feature


class DUCTBaseDataPackageDB(BaseDataPackageDB):
    building_type_by_lu_desc = {
        'road': 'commercial:12',
        'waterbody': 'commercial:12',
        'beach area': 'commercial:12',
        'port / airport': 'commercial:1',
        'open space': 'commercial:12',
        'park': 'commercial:12',
        'residential': 'residential:1',
        'residential / institution': 'residential:1',
        'residential with commercial at 1st storey': 'residential:1',
        'commercial & residential': 'residential:1',
        'commercial': 'commercial:3',
        'commercial / institution': 'commercial:1',
        'business 1': 'industrial:1',
        'business 1 - white': 'industrial:1',
        'business 2': 'industrial:1',
        'business 2 - white': 'industrial:1',
        'business park': 'commercial:1',
        'business park - white': 'commercial:1',
        'place of worship': 'commercial:1',
        'hotel': 'commercial:2',
        'utility': 'industrial:1',
        'transport facilities': 'commercial:1',
        'civic & community institution': 'commercial:1',
        'mass rapid transit': 'commercial:1',
        'light rapid transit': 'commercial:1',
        'educational institution': 'commercial:7',
        'health & medical care': 'commercial:9',
        'special use': 'commercial:12',
        'reserve site': 'commercial:12',
        'sports & recreation': 'commercial:11',
        'agriculture': 'industrial:1',
        'white': 'commercial:12',
        'cemetery': 'commercial:12'
    }

    landcover_type_by_lu_desc = {
        'road': 'pavement:2',  # asphalt (asphalt concrete)
        'waterbody': 'water:1',  # lake
        'beach area': 'soil:4',  # fine
        'port / airport': 'pavement:1',  # asphalt/concrete mix
        'open space': 'vegetation:7',  # deciduous broadleaf trees
        'park': 'vegetation:7',  # deciduous broadleaf trees
        'residential': 'pavement:1',  # asphalt/concrete mix
        'residential / institution': 'pavement:1',  # asphalt/concrete mix
        'residential with commercial at 1st storey': 'pavement:1',  # asphalt/concrete mix
        'commercial & residential': 'pavement:1',  # asphalt/concrete mix
        'commercial': 'pavement:1',  # asphalt/concrete mix
        'commercial / institution': 'pavement:1',  # asphalt/concrete mix
        'business 1': 'pavement:1',  # asphalt/concrete mix
        'business 1 - white': 'pavement:1',  # asphalt/concrete mix
        'business 2': 'pavement:1',  # asphalt/concrete mix
        'business 2 - white': 'pavement:1',  # asphalt/concrete mix
        'business park': 'pavement:1',  # asphalt/concrete mix
        'business park - white': 'pavement:1',  # asphalt/concrete mix
        'place of worship': 'pavement:1',  # asphalt/concrete mix
        'hotel': 'pavement:1',  # asphalt/concrete mix
        'utility': 'pavement:1',  # asphalt/concrete mix
        'transport facilities': 'pavement:1',  # asphalt/concrete mix
        'civic & community institution': 'pavement:1',  # asphalt/concrete mix
        'mass rapid transit': 'pavement:1',  # asphalt/concrete mix
        'light rapid transit': 'pavement:1',  # asphalt/concrete mix
        'educational institution': 'pavement:1',  # asphalt/concrete mix
        'health & medical care': 'pavement:1',  # asphalt/concrete mix
        'special use': 'vegetation:1',  # bare soil
        'reserve site': 'vegetation:1',  # bare soil
        'sports & recreation': 'vegetation:3',  # short grass
        'agriculture': 'vegetation:2',  # crops, mixed farming
        'white': 'vegetation:1',  # bare soil
        'cemetery': 'vegetation:3'  # short grass
    }

    @classmethod
    def prepare_city_admin_zones(cls, input_path: str) -> (index.Index, Dict[int, dict]):
        caz_index = index.Index()
        caz_features = {}
        with open(input_path, 'r') as f_in:
            content = json.load(f_in)
            next_feature_id = 0
            for feature in content['features']:
                properties = feature['properties']

                # fix geometry
                feature = fix_feature_geometry(feature)
                if feature is None:
                    logger.warning(f"Feature geometry not valid: {feature}")
                    continue

                # extract subzone code
                description: str = properties['Description']
                i0 = description.index('<th>SUBZONE_C</th>')
                description = description[i0+18:]
                i0 = description.index('<td>')
                i1 = description.index('</td>')
                subzone_code = description[i0+4:i1]

                # extract planning area name
                description: str = properties['Description']
                i0 = description.index('<th>PLN_AREA_N</th>')
                description = description[i0+19:]
                i0 = description.index('<td>')
                i1 = description.index('</td>')
                planning_area_name = description[i0+4:i1].lower().title()

                # create new properties
                feature['properties'] = {
                    'id': next_feature_id,
                    'name': subzone_code,
                    'subzone_code': subzone_code,
                    'planning_area_name': planning_area_name
                }

                # set id for feature and add to index
                feature['id'] = next_feature_id
                caz_index.insert(next_feature_id, shape(feature['geometry']).bounds)
                caz_features[next_feature_id] = feature

                next_feature_id += 1

        return caz_index, caz_features

    @classmethod
    def prepare_building_footprints(cls, input_path: str, landuse_index: index.Index,
                                    landuse_features: Dict[int, dict]) -> List[dict]:
        gdf = gpd.read_file(input_path)

        # check duplicated geometry
        duplicated_geometries = gdf[gdf.duplicated(subset='geometry', keep=False)]
        duplicated_ids = duplicated_geometries['id'].astype('str').tolist()
        if duplicated_ids:
            duplicated_ids_str = ', '.join(duplicated_ids)
            logger.warning(f'Feature IDs with duplicated geometries: {duplicated_ids_str}')

        # check non-polygon geometry
        non_polygons = gdf[~gdf.geometry.geom_type.isin(['Polygon'])]
        non_polygons_ids = non_polygons['id'].astype('str').tolist()
        if non_polygons_ids:
            non_polygon_ids_str = ', '.join(non_polygons_ids)
            logger.warning(f'Feature IDs with non-polygon geometries: {non_polygon_ids_str}')

        # load the GeoJSON features
        with open(input_path, 'r') as f:
            content = json.load(f)
            features = content['features']

        # determine the highest 'unknown' count for building name AND remove invalid geometries
        next_noname_id = 0
        filtered_features = []
        for feature in features:
            # do we have a name property that starts with 'unknown'?
            properties = feature['properties']
            if 'name' in properties:
                name = properties['name']
                if name.lower().startswith('unknown:'):
                    temp = name.split(':')
                    next_noname_id = max(next_noname_id, int(temp[1]))

            # does the feature have an invalid geometry or is it a duplicate? if yes, skip it
            feature_id = str(feature['properties']['id'])
            if feature_id in duplicated_ids or feature_id in non_polygons_ids:
                continue

            # fix geometry
            feature = fix_feature_geometry(feature)
            if feature is None:
                logger.warning(f"Feature geometry not valid: {feature}")
                continue

            filtered_features.append(feature)

        # next id is -> (the highest number found + 1)
        next_noname_id += 1

        # ensure all remaining features have a name, building_type, and valid height attributes
        for feature in filtered_features:
            properties = feature['properties']

            # fix the name (if necessary)
            if 'name' not in properties or properties['name'] is None or properties['name'] == 'Unknown':
                properties['name'] = f"Unknown:{next_noname_id}"
                next_noname_id += 1

            # fix the building type based on the land-use information provided by an overlapping land-use feature
            building_geometry = shape(feature['geometry'])
            for lu_candidate_id in landuse_index.intersection(building_geometry.bounds):
                # does the building overlap with the land-use geometry?
                lu_feature = landuse_features[lu_candidate_id]
                if building_geometry.intersection(shape(lu_feature['geometry'])).area > 0:
                    properties['building_type'] = lu_feature['properties']['bld_type']
                    break

            # fix building height information
            if 'height' not in properties or properties['height'] is None or \
                    not isinstance(properties['height'], (float, int)) or properties['height'] <= 0:
                # FIXME: there should be something to fix missing building height information
                properties['height'] = UrbanGeometries.DEFAULT_BUILDING_HEIGHT
                logger.warning(f"Feature with ID {properties['id']} has invalid height value")

        return filtered_features

    @classmethod
    def prepare_vegetation(cls, input_path: str) -> List[dict]:
        # read the zip file
        with zipfile.ZipFile(input_path, 'r') as zip:
            # read the tree species information
            with zip.open('data/species.json', 'r') as f:
                species = json.load(f)

            # read the tree list
            features = []
            with zip.open('data/trees.csv') as f:
                # read the CSV header
                f.readline().decode('utf-8')

                # read data and convert into GeoJSON features
                next_feature_id = 0
                while line := f.readline().decode('utf-8'):
                    line = line.split(',')
                    line = [field.strip() for field in line]

                    # extract lon lat
                    lon = float(line[8])
                    lat = float(line[9])

                    # extract species information
                    s = species.get(line[2])

                    # extract height
                    try:
                        height = float(line[6])
                    except ValueError:
                        height = UrbanGeometries.DEFAULT_VEGETATION_HEIGHT

                    # extract girth
                    numbers = re.sub(r'[^\d.]+', ' ', line[3])
                    numbers = numbers.split(' ')
                    numbers = [float(number) for number in numbers if number != '']
                    if len(numbers) > 0:
                        girth = float(np.average(numbers))
                        if girth == 0:
                            girth = UrbanGeometries.DEFAULT_VEGETATION_GIRTH
                    else:
                        girth = UrbanGeometries.DEFAULT_VEGETATION_GIRTH

                    # extract age
                    try:
                        age = float(line[7])
                    except ValueError:
                        age = -1

                    features.append({
                        "type": "Feature",
                        "id": str(next_feature_id),
                        "properties": {
                            "id": str(next_feature_id),
                            "girth": girth,
                            "height": height,
                            "age": age,
                            "species": s['name'] if s else "unknown",
                            "vegetation_type": 'tree:1'
                        },
                        "geometry": {
                            "type": "Point",
                            "coordinates": [lon, lat]
                        }
                    })

                    next_feature_id += 1

            return features

    @classmethod
    def prepare_land_use_zoning(cls, input_path: str) -> (index.Index, Dict[int, dict], List[dict]):
        landuse_index = index.Index()
        landuse_features = {}
        landcover_features = []
        with open(input_path, 'r') as f_in:
            content = json.load(f_in)
            next_feature_id = 0
            for feature in content['features']:
                properties = feature['properties']

                # fix geometry
                feature = fix_feature_geometry(feature)
                if feature is None:
                    logger.warning(f"Feature geometry not valid: {feature}")
                    continue

                # extract LU_DESC
                description: str = properties['Description']
                i0 = description.index('<th>LU_DESC</th>')
                description = description[i0+16:]
                i0 = description.index('<td>')
                i1 = description.index('</td>')
                lu_desc = description[i0+4:i1].lower()

                # guess the landcover and building types
                lc_type = cls.landcover_type_by_lu_desc[lu_desc]
                bld_type = cls.building_type_by_lu_desc[lu_desc]
                lc_type_label = UrbanGeometries.lc_type_label(lc_type)
                bld_type_label = UrbanGeometries.bld_type_label(bld_type)

                # create new properties
                feature['properties'] = {
                    'id': next_feature_id,
                    'name': 'unknown',
                    'lu_desc': lu_desc,
                    'lc_type': lc_type,
                    'lc_type_label': lc_type_label,
                    'bld_type': bld_type,
                    'bld_type_label': bld_type_label
                }

                # set id for feature and add to index
                feature['id'] = next_feature_id
                landuse_index.insert(next_feature_id, shape(feature['geometry']).bounds)
                landuse_features[next_feature_id] = feature

                # add land-cover feature
                landcover_features.append({
                    'type': 'Feature',
                    'id': next_feature_id,
                    'properties': {
                        'id': next_feature_id,
                        'landcover_type': lc_type
                    },
                    'geometry': feature['geometry']
                })

                next_feature_id += 1

        return landuse_index, landuse_features, landcover_features

    # @classmethod
    # def prepare_land_cover(cls, input_path: str, processed_content_path) -> None:
    #     with (rasterio.Env()):
    #         with rasterio.open(input_path) as src:
    #             # read the image and downscale it
    #             stride = 10
    #             image = src.read(1)
    #             image = image[::stride, ::stride]
    #
    #             # remap value -128 ('no data') to 0 and convert to unit8
    #             indices = (image == -128)
    #             image[indices] = 0
    #             image = image.astype(np.uint8)
    #
    #             # determine source transform
    #             height = image.shape[0]
    #             width = image.shape[1]
    #             src_transform, src_width, src_height = calculate_default_transform(
    #                 src.crs, src.crs, width, height, *src.bounds
    #             )
    #
    #             # determine destination transform
    #             dst_crs = CRS().from_epsg(4326)
    #             dst_transform, dst_width, dst_height = calculate_default_transform(
    #                 src.crs, dst_crs, width, height, *src.bounds
    #             )
    #
    #             # update parameters
    #             kwargs = src.meta.copy()
    #             kwargs.update({
    #                 'crs': dst_crs,
    #                 'transform': dst_transform,
    #                 'width': width,
    #                 'height': height,
    #                 'nodata': 0,
    #                 'dtype': 'uint8'
    #             })
    #
    #             # reproject and write to file
    #             with rasterio.open(processed_content_path, 'w', **kwargs) as dst:
    #                 reproject(
    #                     source=image,
    #                     destination=rasterio.band(dst, 1),
    #                     src_transform=src_transform,
    #                     src_crs=src.crs,
    #                     dst_transform=dst_transform,
    #                     dst_crs=dst_crs,
    #                     resampling=Resampling.nearest
    #                 )

    @classmethod
    def prepare_files(cls, mappings: Dict[str, dict]) -> Dict[str, dict]:
        # prepare the city admin zones dataset
        processed_content_path = mappings['city-admin-zones']['path'] + ".processed"
        caz_index, caz_features = cls.prepare_city_admin_zones(mappings['city-admin-zones']['path'])
        if not os.path.isfile(processed_content_path):
            with open(processed_content_path, 'w') as f_out:
                json.dump({
                    'type': 'FeatureCollection',
                    'crs': {'type': 'name', 'properties': {'name': 'urn:ogc:def:crs:OGC:1.3:CRS84'}},
                    'features': list(caz_features.values())
                }, f_out, indent=2)
        mappings['city-admin-zones']['path'] = processed_content_path

        # prepare the vegetation dataset
        processed_content_path = mappings['vegetation']['path'] + ".processed"
        if not os.path.isfile(processed_content_path):
            with open(processed_content_path, 'w') as f_out:
                json.dump({
                    'type': 'FeatureCollection',
                    'crs': {'type': 'name', 'properties': {'name': 'urn:ogc:def:crs:OGC:1.3:CRS84'}},
                    'features': cls.prepare_vegetation(mappings['vegetation']['path'])
                }, f_out, indent=2)
        mappings['vegetation']['path'] = processed_content_path

        # prepare the land-use dataset
        landuse_index, landuse_features, landcover_features = cls.prepare_land_use_zoning(mappings['land-use']['path'])
        processed_content_path = mappings['land-use']['path']+".processed"
        if not os.path.isfile(processed_content_path):
            with open(processed_content_path, 'w') as f_out:
                json.dump({
                    'type': 'FeatureCollection',
                    'crs': {'type': 'name', 'properties': {'name': 'urn:ogc:def:crs:OGC:1.3:CRS84'}},
                    'features': list(landuse_features.values())
                }, f_out, indent=2)
        mappings['land-use']['path'] = processed_content_path

        # write the derived land cover dataset
        processed_content_path = processed_content_path.replace('land-use', 'land-cover')
        if not os.path.isfile(processed_content_path):
            with open(processed_content_path, 'w') as f_out:
                json.dump({
                    'type': 'FeatureCollection',
                    'crs': {'type': 'name', 'properties': {'name': 'urn:ogc:def:crs:OGC:1.3:CRS84'}},
                    'features': landcover_features
                }, f_out, indent=2)
        mappings['land-cover'] = {
            'path': processed_content_path,
            'type': 'DUCT.GeoVectorData',
            'format': 'geojson'
        }

        # prepare the building footprint dataset
        processed_content_path = mappings['building-footprints']['path'] + ".processed"
        if not os.path.isfile(processed_content_path):
            with open(processed_content_path, 'w') as f_out:
                json.dump({
                    'type': 'FeatureCollection',
                    'crs': {'type': 'name', 'properties': {'name': 'urn:ogc:def:crs:OGC:1.3:CRS84'}},
                    'features': cls.prepare_building_footprints(
                        mappings['building-footprints']['path'], landuse_index, landuse_features
                    )
                }, f_out, indent=2)
        mappings['building-footprints']['path'] = processed_content_path

        return mappings

    @classmethod
    def create(cls, destination_folder: str, bdp: BaseDataPackage, context: SDKContext) -> (str, str):
        # initialise the db (delete files first if they already exist)
        db_file0 = os.path.join(destination_folder, f"{bdp.id}.db")
        db_file1 = os.path.join(destination_folder, f"{bdp.id}.json")
        for f in [db_file0, db_file1]:
            if os.path.isfile(f):
                logger.warning(f"BDP db/json file for {bdp.city_name}:{bdp.name} exists at {f} -> remove")
                os.remove(f)

        # download all the base data objects
        objects = bdp.download(context, destination_folder)

        # create the BDP database
        db = DUCTBaseDataPackageDB(bdp.name, db_file0)

        # load city-admin-zones
        t0 = get_timestamp_now()
        with open(objects['city-admin-zones'], 'r') as f:
            content = json.load(f)
            features = content['features']

            # add the features and import them as zones
            group_id = db.add_temporary_geometries(features)
            db.import_geometries_as_zones(group_id)
        t1 = get_timestamp_now()
        print(f"Loading city-admin-zones: {int((t1 - t0) / 1000)} seconds")

        # load building-footprint
        with open(objects['building-footprints'], 'r') as f:
            content = json.load(f)
            features = content['features']
            bld_group_id = db.add_temporary_geometries(features)
        t2 = get_timestamp_now()
        print(f"Loading building-footprints: {int((t2 - t1) / 1000)} seconds")

        # load vegetation
        with open(objects['vegetation'], 'r') as f:
            content = json.load(f)
            features = content['features']
            veg_group_id = db.add_temporary_geometries(features)
        t3 = get_timestamp_now()
        print(f"Loading vegetation: {int((t3 - t2) / 1000)} seconds")

        # load land-cover
        with open(objects['land-cover'], 'r') as f:
            content = json.load(f)
            features = content['features']
            lc_group_id = db.add_temporary_geometries(features)
        t4 = get_timestamp_now()
        print(f"Loading land-cover: {int((t4 - t3) / 1000)} seconds")

        # load land-use
        with open(objects['land-use'], 'r') as f:
            content = json.load(f)
            features = content['features']
            lu_group_id = db.add_temporary_geometries(features)
        t5 = get_timestamp_now()
        print(f"Loading land-use: {int((t5 - t4) / 1000)} seconds")

        db.import_geometries_as_zone_configuration({
            GeometryType.building: bld_group_id,
            GeometryType.vegetation: veg_group_id,
            GeometryType.landcover: lc_group_id,
            GeometryType.landuse: lu_group_id
        }, 'Default', include_empty_zones=True)

        t6 = get_timestamp_now()
        print(f"Loading import geometries as Default zone configuration: {int((t6 - t5) / 1000)} seconds")

        # verify that every zone has a configuration
        missing_configs = []
        for zone_id, zone in db.get_zones().items():
            configs = zone.get_configs()
            if len(configs) != 1:
                missing_configs.append(zone_id)

        if missing_configs:
            raise ExplorerRuntimeError(f"Found zones with missing configurations: {missing_configs}")

        # write the BDP to disk
        bdp_path = os.path.join(destination_folder, f"{bdp.id}.json")
        write_json_to_file(bdp.dict(), bdp_path, indent=4)

        # delete temporary files
        for path in objects.values():
            os.remove(path)

        return db_file0, bdp_path
