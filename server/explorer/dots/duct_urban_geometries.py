import json
import os
import tempfile
import zipfile
import geopandas as gpd
from typing import Dict, List, Optional, Tuple, Union

import pyproj
import ezdxf
from ezdxf.addons.geo import GeoProxy
from ezdxf.entities import DXFGraphic
from geojson import Feature, Point as GeoJSONPoint

from saas.core.helpers import get_timestamp_now, generate_random_string
from saas.core.logging import Logging
from shapely.geometry import shape

from explorer.exceptions import DUCTRuntimeError
from explorer.dots.dot import ImportableDataObjectType, UploadPostprocessResult, ImportTarget, DOTVerificationMessage, \
    DOTVerificationResult
from explorer.geodb import GeometryType
from explorer.schemas import ExplorerRuntimeError

logger = Logging.get('explorer.dots.urban_geometries')


class UrbanGeometries(ImportableDataObjectType):
    DATA_TYPE = 'duct.urban_geometries'

    DEFAULT_BUILDING_HEIGHT = 10
    DEFAULT_VEGETATION_HEIGHT = 4
    DEFAULT_VEGETATION_GIRTH = 1

    @classmethod
    def lc_type_label(cls, lc_type: str) -> str:
        temp = lc_type.split(':')
        return cls.LC_CATEGORIES[temp[0]][temp[1]]

    # define landcover categories, types and labels
    LC_CATEGORIES: Dict[str, Dict[str, str]] = {
        'soil': {
            '1': 'coarse',
            '2': 'medium',
            '3': 'medium-fine',
            '4': 'fine',
            '5': 'very fine',
            '6': 'organic'
        },
        'vegetation': {
            '1': 'bare soil',
            '2': 'crops, mixed farming',
            '3': 'short grass',
            '4': 'evergreen needleleaf trees',
            '5': 'deciduous needleleaf trees',
            '6': 'evergreen broadleaf trees',
            '7': 'deciduous broadleaf trees',
            '8': 'tall grass',
            '9': 'desert',
            '10': 'tundra',
            '11': 'irrigated crops',
            '12': 'semi desert',
            '13': 'ice caps and glaciers',
            '14': 'bogs and marshes',
            '15': 'evergreen shrubs',
            '16': 'deciduous shrubs',
            '17': 'mixed forest/woodland',
            '18': 'interrupted forest'
        },
        'pavement': {
            '1': 'asphalt/concrete mix',
            '2': 'asphalt (asphalt concrete)',
            '3': 'concrete (Portland concrete)',
            '4': 'sett',
            '5': 'paving stones',
            '6': 'cobblestone',
            '7': 'metal',
            '8': 'wood',
            '9': 'gravel',
            '10': 'fine gravel',
            '11': 'pebblestone',
            '12': 'woodchips',
            '13': 'tartan (sports)',
            '14': 'artifical turf (sports)',
            '15': 'clay (sports)'
        },
        'water': {
            '1': 'lake',
            '2': 'river',
            '3': 'ocean',
            '4': 'pond',
            '5': 'fountain'
        }
    }
    LC_TYPES = []
    LC_LABELS = []
    for category, subcategories in LC_CATEGORIES.items():
        for type_id, description in subcategories.items():
            LC_TYPES.append(f"{category}:{type_id}")
            LC_LABELS.append(f"{category.capitalize()}: {description.capitalize()}")

    @classmethod
    def veg_type_label(cls, veg_type: str) -> str:
        temp = veg_type.split(':')
        return cls.VEG_CATEGORIES[temp[0]][temp[1]]

    # define vegetation categories, types and labels
    VEG_CATEGORIES: Dict[str, Dict[str, str]] = {
        'tree': {
            '1': 'default',
            '2': 'acer',
            '7': 'betula',
            '36': 'gleditsia',
            '73': 'sasa'
        }
    }
    VEG_TYPES = []
    VEG_LABELS = []
    for category, subcategories in VEG_CATEGORIES.items():
        for type_id, description in subcategories.items():
            VEG_TYPES.append(f"{category}:{type_id}")
            VEG_LABELS.append(f"{category.capitalize()}: {description.capitalize()}")

    @classmethod
    def bld_type_label(cls, bld_type: str) -> str:
        temp = bld_type.split(':')
        return cls.BLD_CATEGORIES[temp[0]][temp[1]]

    # define building categories
    BLD_CATEGORIES: Dict[str, Dict[str, str]] = {
        'residential': {
            '1': 'multi-storey residential',
            '2': 'single-storey residential'
        },
        'commercial': {
            '1': 'office',
            '2': 'hotel',
            '3': 'retail',
            '4': 'supermarket',
            '5': 'restaurant',
            '6': 'university',
            '7': 'school',
            '8': 'library',
            '9': 'hospital',
            '10': 'sport facilities (indoor)',
            '11': 'sport facilities (outdoor)',
            '12': 'parking'
        },
        'industrial': {
            '1': 'industry',
            '2': 'data centre',
            '3': 'cooling facilities',
        }
    }
    BLD_TYPES = []
    BLD_LABELS = []
    for category, subcategories in BLD_CATEGORIES.items():
        for type_id, description in subcategories.items():
            BLD_TYPES.append(f"{category}:{type_id}")
            BLD_LABELS.append(f"{category.capitalize()}: {description.capitalize()}")

    @classmethod
    def check_feature_geometry(cls, feature: dict) -> Optional[dict]:
        geometry = feature['geometry']
        geometry = shape(geometry)
        if geometry.is_valid:
            return feature
        else:
            simplified = geometry.simplify(tolerance=0.01)
            if simplified.is_valid:
                result = feature.copy()
                result['geometry'] = simplified.__geo_interface__

                if result['geometry']['type'] == 'Polygon':
                    result['geometry']['type'] = 'MultiPolygon'
                    result['geometry']['coordinates'] = [result['geometry']['coordinates']]

                return result
            else:
                return None

    @classmethod
    def determine_building_name(cls) -> str:
        suffix = generate_random_string(4)
        timestamp = get_timestamp_now()
        return f"Unknown:{timestamp}-{suffix}"

    @classmethod
    def read_as_shapefile(cls, path: str, counts: Dict[str, Union[int, set]]) -> \
            Optional[Tuple[list[dict], list[dict], list[dict]]]:
        try:
            # results
            bld_features = []
            veg_features = []
            lc_features = []

            # read the shape file and extract all polygons
            gdf = gpd.read_file(path)

            # define the source and target CRS (??? to EPSG:4326)
            source_crs = gdf.crs
            target_crs = pyproj.CRS.from_epsg(4326)
            transformer = pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)

            for _, entity in gdf.iterrows():
                # determine type
                if 'building_type' in entity or 'bld_type' in entity:
                    # valid cat/sub cat?
                    building_type = entity['building_type'] \
                        if 'building_type' in entity else entity['bld_type']
                    if building_type not in cls.BLD_TYPES:
                        counts['invalid_bld_cats'].add(building_type)
                        continue

                    # do we have a geometry
                    if entity.geometry is None:
                        continue

                    # get geometry
                    geometry = entity.geometry.__geo_interface__

                    # convert coordinate system
                    coordinates = []
                    if geometry['type'] == 'Polygon':
                        for polygon in geometry['coordinates']:
                            polygon = [transformer.transform(x, y) for x, y in polygon]
                            coordinates.append(polygon)

                    elif geometry['type'] == 'MultiPolygon':
                        for polygons in geometry['coordinates']:
                            polygons1 = []
                            for polygon in polygons:
                                polygon = [transformer.transform(x, y) for x, y in polygon]
                                polygons1.append(polygon)
                            coordinates.append(polygons1)

                    else:
                        counts['non_polygon_bld_entities'] = counts['non_polygon_bld_entities'] + 1
                        continue
                    geometry['coordinates'] = coordinates

                    # do we have height information?
                    if 'height' in entity and isinstance(entity['height'], (int, float)) and entity['height'] > 0:
                        height = entity.height
                    else:
                        counts['missing_bld_height_entities'] = counts['missing_bld_height_entities'] + 1
                        height = cls.DEFAULT_BUILDING_HEIGHT

                    # buildings need to have a name property
                    if 'name' in entity and isinstance(entity['name'], str) and entity['name'] is not None \
                            and len(entity['name']) > 0:
                        name = entity['name']
                    else:
                        name = cls.determine_building_name()

                    # create properties
                    properties = {
                        'building_type': building_type,
                        'height': height,
                        'name': name
                    }

                    # check the feature geometry
                    feature = cls.check_feature_geometry({
                        'type': 'Feature',
                        'geometry': geometry,
                        'properties': properties
                    })

                    if feature is None:
                        counts['invalid_polygons_skipped'] = counts['invalid_polygons_skipped'] + 1
                    else:
                        bld_features.append(feature)

                elif 'vegetation_type' in entity or 'veg_type' in entity:
                    # valid cat/sub cat?
                    vegetation_type = entity['vegetation_type'] \
                        if 'vegetation_type' in entity else entity['veg_type']
                    if vegetation_type not in cls.VEG_TYPES:
                        counts['invalid_veg_cats'].add(vegetation_type)
                        continue

                    # do we have height information?
                    if 'height' in entity and isinstance(entity['height'], (int, float)) and entity['height'] > 0:
                        height = entity.height
                    else:
                        counts['missing_veg_height_entities'] = counts['missing_veg_height_entities'] + 1
                        height = cls.DEFAULT_VEGETATION_HEIGHT

                    # do we have girth information?
                    if 'girth' in entity and isinstance(entity['girth'], (int, float)) and entity['girth'] > 0:
                        girth = entity.girth
                    else:
                        counts['missing_veg_girth_entities'] = counts['missing_veg_girth_entities'] + 1
                        girth = cls.DEFAULT_VEGETATION_GIRTH

                    # do we have a geometry
                    if entity.geometry is None:
                        continue

                    # get geometry
                    geometry = entity.geometry.__geo_interface__

                    # is it a point
                    if geometry['type'] != 'Point':
                        counts['non_point_veg_entities'] = counts['non_point_veg_entities'] + 1
                        continue

                    # convert coordinate system
                    geometry['coordinates'] = \
                        transformer.transform(geometry['coordinates'][0], geometry['coordinates'][1])

                    veg_features.append({
                        "type": "Feature",
                        "properties": {
                            "vegetation_type": vegetation_type,
                            "height": height,
                            "girth": girth
                        },
                        "geometry": geometry
                    })

                elif 'landcover_type' in entity or 'lc_type' in entity:
                    # valid cat/sub cat?
                    landcover_type = entity['landcover_type'] \
                        if 'landcover_type' in entity else entity['lc_type']
                    if landcover_type not in cls.LC_TYPES:
                        counts['invalid_lc_cats'].add(landcover_type)
                        continue

                    # do we have a geometry
                    if entity.geometry is None:
                        continue

                    # get geometry
                    geometry = entity.geometry.__geo_interface__

                    # is it a polygon, convert coordinate system
                    coordinates = []
                    if geometry['type'] == 'Polygon':
                        for polygon in geometry['coordinates']:
                            polygon = [transformer.transform(x, y) for x, y in polygon]
                            coordinates.append(polygon)

                    elif geometry['type'] == 'MultiPolygon':
                        for polygons in geometry['coordinates']:
                            polygons1 = []
                            for polygon in polygons:
                                polygon = [transformer.transform(x, y) for x, y in polygon]
                                polygons1.append(polygon)
                            coordinates.append(polygons1)

                    else:
                        counts['non_polygon_lc_entities'] = counts['non_polygon_lc_entities'] + 1
                        continue
                    geometry['coordinates'] = coordinates

                    # create properties
                    properties = {
                        'landcover_type': landcover_type,
                    }

                    # check the feature geometry
                    feature = cls.check_feature_geometry({
                        'type': 'Feature',
                        'geometry': geometry,
                        'properties': properties
                    })

                    if feature is None:
                        counts['invalid_polygons_skipped'] = counts['invalid_polygons_skipped'] + 1
                    else:
                        lc_features.append(feature)
                else:
                    counts['unrecognised_entities'] = counts['unrecognised_entities'] + 1

            return bld_features, veg_features, lc_features

        except Exception as e:
            return None  # we just assume it wasn't a shapefile at this point

    @classmethod
    def read_as_geojson(cls, path: str, counts: Dict[str, Union[int, set]]) -> \
            Optional[Tuple[list[dict], list[dict], list[dict]]]:

        try:
            # results
            bld_features = []
            veg_features = []
            lc_features = []

            # try read features from the GeoJSON (if it is one...
            with open(path, 'r') as f:
                content = json.load(f)
                features = content['features']

            # read the coordinate system
            if 'crs' not in content:
                counts['no_coordinate_system'] = counts['no_coordinate_system'] + 1
                return None

            # define the source and target CRS (??? to EPSG:4326)
            crs_name = content['crs']['properties']['name']
            source_crs = pyproj.CRS.from_string(crs_name)
            target_crs = pyproj.CRS.from_epsg(4326)
            transformer = pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)

            # iterate over all features
            for feature in features:
                properties = feature['properties']

                # determine type
                if 'building_type' in properties or 'bld_type' in properties:
                    # valid cat/sub cat?
                    building_type = properties['building_type'] \
                        if 'building_type' in properties else properties['bld_type']
                    if building_type not in cls.BLD_TYPES:
                        counts['invalid_bld_cats'].add(building_type)
                        continue

                    # is it a polygon, convert coordinate system
                    geometry = feature['geometry']
                    coordinates = []
                    if geometry['type'] == 'Polygon':
                        for polygon in geometry['coordinates']:
                            polygon = [transformer.transform(x, y) for x, y in polygon]
                            coordinates.append(polygon)

                    elif geometry['type'] == 'MultiPolygon':
                        for polygons in geometry['coordinates']:
                            polygons1 = []
                            for polygon in polygons:
                                polygon = [transformer.transform(x, y) for x, y in polygon]
                                polygons1.append(polygon)
                            coordinates.append(polygons1)

                    else:
                        counts['non_polygon_bld_entities'] = counts['non_polygon_bld_entities'] + 1
                        continue
                    geometry['coordinates'] = coordinates

                    # do we have height information?
                    if ('height' in properties and isinstance(properties['height'], (int, float))
                            and properties['height'] > 0):
                        height = properties['height']
                    else:
                        counts['missing_bld_height_entities'] = counts['missing_bld_height_entities'] + 1
                        height = cls.DEFAULT_BUILDING_HEIGHT

                    # buildings need to have a name property
                    if 'name' in properties and isinstance(properties['name'], str) and \
                            properties['name'] is not None and len(properties['name']) > 0:
                        name = properties['name']
                    else:
                        name = cls.determine_building_name()

                    # create properties
                    properties = {
                        'building_type': building_type,
                        'height': height,
                        'name': name
                    }

                    # check the feature geometry
                    feature = cls.check_feature_geometry({
                        'type': 'Feature',
                        'geometry': geometry,
                        'properties': properties
                    })

                    if feature is None:
                        counts['invalid_polygons_skipped'] = counts['invalid_polygons_skipped'] + 1
                    else:
                        bld_features.append(feature)

                elif 'vegetation_type' in properties or 'veg_type' in properties:
                    # valid cat/sub cat?
                    vegetation_type = properties['vegetation_type'] \
                        if 'vegetation_type' in properties else properties['veg_type']
                    if vegetation_type not in cls.VEG_TYPES:
                        counts['invalid_veg_cats'].add(vegetation_type)
                        continue

                    # is it a point
                    geometry = feature['geometry']
                    if geometry['type'] != 'Point':
                        counts['non_point_veg_entities'] = counts['non_point_veg_entities'] + 1
                        continue

                    # do we have height information?
                    if ('height' in properties and isinstance(properties['height'], (int, float))
                            and properties['height'] > 0):
                        height = properties['height']
                    else:
                        counts['missing_veg_height_entities'] = counts['missing_veg_height_entities'] + 1
                        height = cls.DEFAULT_VEGETATION_HEIGHT

                    # do we have height information?
                    if ('girth' in properties and isinstance(properties['girth'], (int, float))
                            and properties['girth'] > 0):
                        girth = properties['girth']
                    else:
                        counts['missing_veg_girth_entities'] = counts['missing_veg_girth_entities'] + 1
                        girth = cls.DEFAULT_VEGETATION_GIRTH

                    # convert coordinate system
                    geometry['coordinates'] = \
                        transformer.transform(geometry['coordinates'][0], geometry['coordinates'][1])

                    veg_features.append({
                        "type": "Feature",
                        "properties": {
                            "vegetation_type": vegetation_type,
                            "height": height,
                            "girth": girth
                        },
                        "geometry": geometry
                    })

                elif 'landcover_type' in properties or 'lc_type' in properties:
                    # valid cat/sub cat?
                    landcover_type = properties['landcover_type'] \
                        if 'landcover_type' in properties else properties['lc_type']
                    if landcover_type not in cls.LC_TYPES:
                        counts['invalid_lc_cats'].add(landcover_type)
                        continue

                    # is it a polygon, convert coordinate system
                    geometry = feature['geometry']
                    coordinates = []
                    if geometry['type'] == 'Polygon':
                        for polygon in geometry['coordinates']:
                            polygon = [transformer.transform(x, y) for x, y in polygon]
                            coordinates.append(polygon)

                    elif geometry['type'] == 'MultiPolygon':
                        for polygons in geometry['coordinates']:
                            polygons1 = []
                            for polygon in polygons:
                                polygon = [transformer.transform(x, y) for x, y in polygon]
                                polygons1.append(polygon)
                            coordinates.append(polygons1)

                    else:
                        counts['non_polygon_bld_entities'] = counts['non_polygon_bld_entities'] + 1
                        continue
                    geometry['coordinates'] = coordinates

                    # create properties
                    properties = {
                        'landcover_type': landcover_type,
                    }

                    # check the feature geometry
                    feature = cls.check_feature_geometry({
                        'type': 'Feature',
                        'geometry': geometry,
                        'properties': properties
                    })

                    if feature is None:
                        counts['invalid_polygons_skipped'] = counts['invalid_polygons_skipped'] + 1
                    else:
                        lc_features.append(feature)

                else:
                    counts['unrecognised_entities'] = counts['unrecognised_entities'] + 1

            return bld_features, veg_features, lc_features

        except Exception as e:
            return None  # we just assume it wasn't a GeoJSON at this point

    @classmethod
    def read_as_dxf(cls, path: str, counts: Dict[str, Union[int, set]]) -> \
            Optional[Tuple[list[dict], list[dict], list[dict]]]:

        # define the source and target CRS (EPSG:3414 to EPSG:4326)
        # FIXME: this shouldn't be hardcoded! the source CRS should be indicated somehow in the file OR a default
        #  should be defined in the project somehow.
        source_crs = pyproj.CRS.from_epsg(3414)
        target_crs = pyproj.CRS.from_epsg(4326)
        transformer = pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)

        # results
        bld_features = []
        veg_features = []
        lc_features = []

        try:
            # open the file as DXF and get the model space
            doc = ezdxf.readfile(path)
            msp = doc.modelspace()

            # iterate over all entities
            for entity in msp.query('*'):
                # get the entity type. note: the isinstance isn't really necessary but for the sake of PyCharm not
                # complaining about using GeoProxy. we only look into Points and Hatches - which inherit from DXFGraphic.
                entity_type = entity.dxf.dxftype
                if not isinstance(entity, DXFGraphic):
                    continue

                # determine the type of entity by its layer attribute
                layer = entity.get_dxf_attrib('layer')
                layer = layer.replace('_', ':')
                if ':' in layer:
                    layer = layer.split(':')
                    category = layer[0]
                    sub_cat = layer[1]
                    geometry_type = f"{category}:{sub_cat}"

                    if category in cls.BLD_CATEGORIES:
                        # valid sub cat?
                        if sub_cat not in cls.BLD_CATEGORIES[category]:
                            counts['invalid_bld_cats'].add(layer)
                            continue

                        # valid entity type?
                        if entity_type != 'HATCH':
                            counts['non_polygon_bld_entities'] = counts['non_polygon_bld_entities'] + 1
                            continue

                        # convert into GeoJSON geometry
                        proxy = GeoProxy.from_dxf_entities(entity)
                        geometry = proxy.__geo_interface__

                        # is it a polygon? if not, we skip it
                        if geometry['type'] != 'Polygon':
                            counts['non_polygon_bld_entities'] = counts['non_polygon_bld_entities'] + 1
                            continue

                        # convert coordinate system
                        coordinates = []
                        for polygon in geometry['coordinates']:
                            polygon = [transformer.transform(x, y) for x, y in polygon]
                            coordinates.append(polygon)
                        geometry['coordinates'] = coordinates

                        # create properties
                        properties = {
                            'building_type': geometry_type,
                            'height': cls.DEFAULT_BUILDING_HEIGHT,  # we don't have building height info in the DXF
                            'name': cls.determine_building_name()  # we don't have building name info in the DXF
                        }
                        counts['missing_bld_height_entities'] = counts['missing_bld_height_entities'] + 1

                        # check the feature geometry
                        feature = cls.check_feature_geometry({
                            'type': 'Feature',
                            'geometry': geometry,
                            'properties': properties
                        })

                        if feature is None:
                            counts['invalid_polygons_skipped'] = counts['invalid_polygons_skipped'] + 1
                        else:
                            bld_features.append(feature)

                    elif category in cls.VEG_CATEGORIES:
                        # valid sub cat?
                        if sub_cat not in cls.VEG_CATEGORIES[category]:
                            counts['invalid_veg_cats'].add(layer)
                            continue

                        # valid entity type?
                        if entity_type != 'POINT':
                            counts['non_point_veg_entities'] = counts['non_point_veg_entities'] + 1
                            continue

                        # convert coordinates
                        x, y, z = transformer.transform(
                            entity.dxf.location.x,
                            entity.dxf.location.y,
                            entity.dxf.location.z
                        )

                        geometry = GeoJSONPoint((x, y, z))
                        veg_features.append(Feature(geometry=geometry, properties={
                            'vegetation_type': geometry_type,
                            'height': cls.DEFAULT_VEGETATION_HEIGHT,  # we don't have vegetation height in the DXF
                            'girth': cls.DEFAULT_VEGETATION_GIRTH  # we don't have vegetation girth in the DXF
                        }))
                        counts['missing_veg_height_entities'] = counts['missing_veg_height_entities'] + 1
                        counts['missing_veg_girth_entities'] = counts['missing_veg_girth_entities'] + 1

                    elif category in cls.LC_CATEGORIES:
                        # valid sub cat?
                        if sub_cat not in cls.LC_CATEGORIES[category]:
                            counts['invalid_lc_cats'] = counts['invalid_lc_cats'] + 1
                            continue

                        # valid entity type?
                        if entity_type != 'HATCH':
                            counts['non_polygon_bld_entities'] = counts['non_polygon_bld_entities'] + 1
                            continue

                        # convert into GeoJSON geometry
                        proxy = GeoProxy.from_dxf_entities(entity)
                        geometry = proxy.__geo_interface__

                        # is it a polygon? if not, we skip it
                        if geometry['type'] != 'Polygon':
                            counts['non_polygon_lc_entities'] = counts['non_polygon_lc_entities'] + 1
                            continue

                        # convert coordinate system
                        coordinates = []
                        for polygon in geometry['coordinates']:
                            polygon = [transformer.transform(x, y) for x, y in polygon]
                            coordinates.append(polygon)
                        geometry['coordinates'] = coordinates

                        # create properties
                        properties = {
                            'landcover_type': geometry_type
                        }

                        # check the feature geometry
                        feature = cls.check_feature_geometry({
                            'type': 'Feature',
                            'geometry': geometry,
                            'properties': properties
                        })

                        if feature is None:
                            counts['invalid_polygons_skipped'] = counts['invalid_polygons_skipped'] + 1
                        else:
                            lc_features.append(feature)

                    else:
                        counts['unrecognised_entities'] = counts['unrecognised_entities'] + 1
                        counts['unrecognised_cats'].add(geometry_type)
                else:
                    counts['unrecognised_entities'] = counts['unrecognised_entities'] + 1
                    counts['unrecognised_cats'].add(layer)

            return bld_features, veg_features, lc_features

        except Exception:
            return None  # we just assume it wasn't a DXF at this point

    @classmethod
    def read_as_zip(cls, path: str, counts: Dict[str, int]) -> Optional[Tuple[list[dict], list[dict], list[dict]]]:
        try:
            with open(path, 'rb') as f:
                # peek into the file to determine if it's a zip file
                peek = f.read(4)
                if peek != b'\x50\x4B\x03\x04':
                    return None  # it's not, abort...

            with tempfile.TemporaryDirectory() as tmp_dir:
                bld_features = []
                veg_features = []
                lc_features = []

                # unzip the contents
                with zipfile.ZipFile(path, 'r') as zip:
                    zip.extractall(tmp_dir)
                    files = zip.namelist()

                    all_geojson = [f for f in files if f.endswith('.geojson') and not f.startswith('__MACOSX')]
                    all_shp = [f for f in files if f.endswith('.shp') and not f.startswith('__MACOSX')]
                    all_dxf = [f for f in files if f.endswith('.dxf') and not f.startswith('__MACOSX')]

                    # are there GeoJSON files?
                    for path in all_geojson:
                        features = cls.read_as_geojson(os.path.join(tmp_dir, path), counts)
                        if features is not None:
                            bld_features.extend(features[0])
                            veg_features.extend(features[1])
                            lc_features.extend(features[2])

                    # are there shape file?
                    for path in all_shp:
                        features = cls.read_as_shapefile(os.path.join(tmp_dir, path), counts)
                        if features is not None:
                            bld_features.extend(features[0])
                            veg_features.extend(features[1])
                            lc_features.extend(features[2])

                    # are there DXF file?
                    for path in all_dxf:
                        features = cls.read_as_dxf(os.path.join(tmp_dir, path), counts)
                        if features is not None:
                            bld_features.extend(features[0])
                            veg_features.extend(features[1])
                            lc_features.extend(features[2])

                return bld_features, veg_features, lc_features

        except Exception as e:
            return None

    @classmethod
    def create_verification_messages(cls, counts: Dict[str, Union[int, set]]) -> List[DOTVerificationMessage]:
        messages = []

        if counts['no_coordinate_system'] > 0:
            messages.append(DOTVerificationMessage(
                severity='warning', message=f"Ignoring {counts['no_coordinate_system']} input files with no "
                                            f"coordinate system."))

        if counts['non_point_veg_entities'] > 0:
            messages.append(DOTVerificationMessage(
                severity='warning', message=f"Ignoring {counts['non_point_veg_entities']} vegetation entities that are "
                                            f"not point geometries."))

        if counts['non_polygon_bld_entities'] > 0:
            messages.append(DOTVerificationMessage(
                severity='warning', message=f"Ignoring {counts['non_polygon_bld_entities']} building entities that are "
                                            f"not polygon geometries."))

        if counts['non_polygon_lc_entities'] > 0:
            messages.append(DOTVerificationMessage(
                severity='warning', message=f"Ignoring {counts['non_polygon_lc_entities']} land-cover entities that "
                                            f"are not polygon geometries."))

        if counts['missing_bld_height_entities'] > 0:
            messages.append(DOTVerificationMessage(
                severity='warning', message=f"Found {counts['missing_bld_height_entities']} building entities without "
                                            f"height information. Unless fixed, {cls.DEFAULT_BUILDING_HEIGHT}m "
                                            f"default height is used."))

        if counts['missing_veg_height_entities'] > 0:
            messages.append(DOTVerificationMessage(
                severity='warning', message=f"Found {counts['missing_veg_height_entities']} vegetation entities without "
                                            f"height information. Unless fixed, {cls.DEFAULT_VEGETATION_HEIGHT}m "
                                            f"default height is used."))

        if counts['missing_veg_girth_entities'] > 0:
            messages.append(DOTVerificationMessage(
                severity='warning', message=f"Found {counts['missing_veg_girth_entities']} vegetation entities without "
                                            f"girth information. Unless fixed, {cls.DEFAULT_VEGETATION_GIRTH}m "
                                            f"default girth is used."))

        if counts['missing_coordinate_entities'] > 0:
            messages.append(DOTVerificationMessage(
                severity='warning', message=f"Found {counts['missing_coordinate_entities']} entities without "
                                            f"coordinates. They will be ignored."))

        if len(counts['invalid_bld_cats']) > 0:
            messages.append(DOTVerificationMessage(
                severity='warning', message=f"Ignoring building entities with invalid sub-categories: "
                                            f"{' '.join(counts['invalid_bld_cats'])}."))

        if len(counts['invalid_veg_cats']) > 0:
            messages.append(DOTVerificationMessage(
                severity='warning', message=f"Ignoring vegetation entities with invalid sub-categories: "
                                            f"{' '.join(counts['invalid_veg_cats'])}."))

        if len(counts['invalid_lc_cats']) > 0:
            messages.append(DOTVerificationMessage(
                severity='warning', message=f"Ignoring land-cover entities with invalid sub-categories: "
                                            f"{' '.join(counts['invalid_lc_cats'])}."))

        if counts['invalid_polygons_skipped'] > 0:
            messages.append(DOTVerificationMessage(
                severity='warning', message=f"Ignoring {counts['invalid_polygons_skipped']} entities with invalid "
                                            f"polygons."))

        if counts['unrecognised_entities'] > 0:
            if len(counts['unrecognised_cats']) > 0:
                messages.append(DOTVerificationMessage(
                    severity='warning', message=f"Ignoring {counts['unrecognised_entities']} entities with "
                                                f"unrecognised categories: {' '.join(counts['unrecognised_cats'])}."))
            else:
                messages.append(DOTVerificationMessage(
                    severity='warning', message=f"Ignoring {counts['unrecognised_entities']} entities of "
                                                f"unknown type."))

        return messages

    @classmethod
    def read_content(cls, content_path: str) -> \
            Tuple[Optional[Tuple[list[dict], list[dict], list[dict]]], str, Dict[str, Union[str, set]]]:

        # try to read the content
        counts = {
            'no_coordinate_system': 0,
            'non_point_veg_entities': 0,
            'non_polygon_bld_entities': 0,
            'non_polygon_lc_entities': 0,
            'unrecognised_entities': 0,
            'missing_bld_height_entities': 0,
            'missing_veg_height_entities': 0,
            'missing_veg_girth_entities': 0,
            'missing_coordinate_entities': 0,
            'invalid_bld_cats': set(),
            'invalid_veg_cats': set(),
            'invalid_lc_cats': set(),
            'unrecognised_cats': set(),
            'invalid_polygons_skipped': 0
        }
        content, data_format = cls.read_as_zip(content_path, counts), 'zip'
        if content is None:
            content, data_format = cls.read_as_dxf(content_path, counts), 'dxf'
        if content is None:
            content, data_format = cls.read_as_shapefile(content_path, counts), 'shp'
        if content is None:
            content, data_format = cls.read_as_geojson(content_path, counts), 'geojson'

        # check if we have features with non-coordinates
        missing_coordinate_entities = 0
        checked_content = ([], [], [])
        for i in range(len(content)):
            for feature in content[i]:
                # do we have missing coordinates?
                if feature['geometry']['coordinates'] is [] or feature['geometry']['coordinates'] is [[]]:
                    missing_coordinate_entities += 1
                else:
                    checked_content[i].append(feature)
        counts['missing_coordinate_entities'] = missing_coordinate_entities

        return checked_content, data_format, counts

    def name(self) -> str:
        return self.DATA_TYPE

    def label(self) -> str:
        return 'Urban Geometries'

    def supported_formats(self) -> List[str]:
        return ['geojson', 'shp', 'dxf']

    def target(self) -> ImportTarget:
        return ImportTarget.geodb

    def description(self) -> str:
        return ("Urban geometries data contains basic elements that define an urban environment. This comprises of"
                " land cover data which defines the type of land surfaces, including both natural (e.g. vegetation, "
                "water bodies) and man-made surfaces (e.g. concrete, asphalt). Individual tree species can also be "
                "defined in the data. The acceptable formats and required attributes are listed below. <br><br> "
                "For detailed guide on preparing the input file, please click "
                "<a href='' target='_blank'>here</a>. <br><br> "
                "<b>Required data attributes:</b>"
                "<ul><li>Geometric shapes containing land cover information</li>"
                "<li>Points containing tree species information</li>"
                "<li>Building footprints containing height information (where applicable)</li></ul> "
                "<b>Accepted file formats:</b>"
                "<ul><li>geojson</li></ul>"
                "<ul><li>shp</li></ul>"
                "<ul><li>dxf</li></ul>"
                )

    def preview_image_url(self) -> str:
        return 'dot_urban_geometries.png'

    def upload_postprocess(self, project, temp_obj_path: str) -> List[Tuple[str, str, UploadPostprocessResult]]:
        # read the content. we really should have content at this point because verification was successful
        content, data_format, counts = self.read_content(temp_obj_path)
        if content is None:
            raise ExplorerRuntimeError("Unexpected error while reading content after DOT verification")

        # assign feature ids
        next_feature_id = 0
        for features in content:
            for feature in features:
                feature['id'] = str(next_feature_id)
                feature['properties']['id'] = str(next_feature_id)
                next_feature_id += 1

        # unpack contensts and prepare results
        bld_features, veg_features, lc_features = content
        result: List[Tuple[str, str, UploadPostprocessResult]] = []
        tnow = get_timestamp_now()

        # handle building features
        if len(bld_features) > 0:
            bld_obj_id = f"{self.name()}_{tnow}_bld"
            bld_obj_path = os.path.join(project.info.temp_path, bld_obj_id)

            # write the object file as GeoJSON
            with open(bld_obj_path, 'w') as f:
                f.write(json.dumps({
                    'type': 'FeatureCollection',
                    'features': bld_features
                }))

            editor_config = {
                'objectIdField': 'id',
                'geometryType': 'polygon',
                'fields': [
                    {
                        'name': 'name',
                        'alias': 'Building Name',
                        'type': 'string',
                        'nullable': False,
                        'editable': False
                    },
                    {
                        'name': 'building_type',
                        'alias': 'Building Type',
                        'type': 'string',
                        'nullable': True,
                        'valueType': 'type-or-category',
                        'domain': {
                            'type': 'coded-value',
                            'codedValues': [{'code': UrbanGeometries.BLD_TYPES[i], 'name': UrbanGeometries.BLD_LABELS[i]}
                                            for i in range(len(UrbanGeometries.BLD_TYPES))]
                        }
                    },
                    {
                        'name': 'height',
                        'alias': 'Building Height',
                        'type': 'double',
                        'nullable': False,
                        'valueType': 'measurement',
                        'defaultValue': UrbanGeometries.DEFAULT_BUILDING_HEIGHT,
                        'domain': {
                            'type': 'range',
                            'minValue': 1,
                            'maxValue': 300
                        }
                    }],
                'allowedWorkflows': ['update']
            }

            result.append((bld_obj_id, bld_obj_path,
                           UploadPostprocessResult(title='Update Building Attributes',
                                                   description='This step ensures that the data layers '
                                                               'contain the necessary attributes and can be '
                                                               'used appropriately. Use the edit feature on '
                                                               'the map to assign attributes to a layer or '
                                                               'update an existing one. You may also delete '
                                                               'layers that are not required.',
                                                   geo_type=GeometryType.building.value,
                                                   mode='fix-attr-and-pick', editor_config=editor_config,
                                                   extra={})))

            # load the geometries into the geo db
            project.geo_db.add_temporary_geometries(bld_features, bld_obj_id)

        # handle vegetation features
        if len(veg_features) > 0:
            veg_obj_id = f"{self.name()}_{tnow}_veg"
            veg_obj_path = os.path.join(project.info.temp_path, veg_obj_id)

            # write the object file as GeoJSON
            with open(veg_obj_path, 'w') as f:
                f.write(json.dumps({
                    'type': 'FeatureCollection',
                    'features': veg_features
                }))

            editor_config = {
                'objectIdField': 'id',
                'geometryType': 'point',
                'fields': [{
                    'name': 'vegetation_type',
                    'alias': 'Vegetation Type',
                    'type': 'string',
                    'nullable': True,
                    'valueType': 'type-or-category',
                    'domain': {
                        'type': 'coded-value',
                        'codedValues': [{'code': UrbanGeometries.VEG_TYPES[i], 'name': UrbanGeometries.VEG_LABELS[i]}
                                        for i in range(len(UrbanGeometries.VEG_TYPES))]
                    }
                }, {
                    'name': 'height',
                    'alias': 'Vegetation Height',
                    'type': 'double',
                    'nullable': False,
                    'valueType': 'measurement',
                    'defaultValue': UrbanGeometries.DEFAULT_VEGETATION_HEIGHT,
                    'domain': {
                        'type': 'range',
                        'minValue': 1,
                        'maxValue': 20
                    }
                }, {
                    'name': 'girth',
                    'alias': 'Vegetation Girth',
                    'type': 'double',
                    'nullable': False,
                    'valueType': 'measurement',
                    'defaultValue': UrbanGeometries.DEFAULT_VEGETATION_GIRTH,
                    'domain': {
                        'type': 'range',
                        'minValue': 0.5,
                        'maxValue': 5
                    }
                }],
                'allowedWorkflows': ['update']
            }

            result.append((veg_obj_id, veg_obj_path,
                           UploadPostprocessResult(title='Update Vegetation Attributes',
                                                   description='This step ensures that the data layers '
                                                               'contain the necessary attributes and can be '
                                                               'used appropriately. Use the edit feature on '
                                                               'the map to assign attributes to a layer or '
                                                               'update an existing one. You may also delete '
                                                               'layers that are not required.',
                                                   geo_type=GeometryType.vegetation.value,
                                                   mode='fix-attr-and-pick', editor_config=editor_config,
                                                   extra={})))

            # load the geometries into the geo db
            project.geo_db.add_temporary_geometries(veg_features, veg_obj_id)

        # handle land-cover features
        if len(lc_features) > 0:
            lc_obj_id = f"{self.name()}_{tnow}_lc"
            lc_obj_path = os.path.join(project.info.temp_path, lc_obj_id)

            # write the object file as GeoJSON
            with open(lc_obj_path, 'w') as f:
                f.write(json.dumps({
                    'type': 'FeatureCollection',
                    'features': lc_features
                }))

            editor_config = {
                'objectIdField': 'id',
                'geometryType': 'polygon',
                'fields': [{
                    'name': 'landcover_type',
                    'alias': 'Landcover Type',
                    'type': 'string',
                    'nullable': True,
                    'valueType': 'type-or-category',
                    'domain': {
                        'type': 'coded-value',
                        'codedValues': [{'code': UrbanGeometries.LC_TYPES[i], 'name': UrbanGeometries.LC_LABELS[i]}
                                        for i in range(len(UrbanGeometries.LC_TYPES))]
                    }
                }],
                'allowedWorkflows': ['update']
            }

            result.append((lc_obj_id, lc_obj_path,
                           UploadPostprocessResult(title='Update Land-cover Attributes',
                                                   description='This step ensures that the data layers '
                                                               'contain the necessary attributes and can be '
                                                               'used appropriately. Use the edit feature on '
                                                               'the map to assign attributes to a layer or '
                                                               'update an existing one. You may also delete '
                                                               'layers that are not required.',
                                                   geo_type=GeometryType.landcover.value,
                                                   mode='fix-attr-and-pick', editor_config=editor_config,
                                                   extra={})))

            # load the geometries into the geo db
            project.geo_db.add_temporary_geometries(lc_features, lc_obj_id)

        return result

    def update_preimport(self, project, obj_path: str, args: dict,
                         geo_type: Optional[GeometryType]) -> UploadPostprocessResult:
        # does the geo_type make sense?
        if geo_type is None or geo_type not in [GeometryType.landcover, GeometryType.vegetation, GeometryType.building]:
            raise ExplorerRuntimeError(f'[{self.name()}] Unexpected geo_type during pre-import update: {geo_type}')

        # write the updated features
        features = args['features']
        with open(obj_path, 'w') as f:
            f.write(json.dumps({
                'type': 'FeatureCollection',
                'features': features
            }))

        if geo_type == GeometryType.building:
            return UploadPostprocessResult(title='Update Building Attributes', description='',
                                           geo_type=geo_type.value, mode='fix-attr-and-pick',
                                           extra={})

        elif geo_type == GeometryType.vegetation:
            return UploadPostprocessResult(title='Update Vegetation Attributes', description='',
                                           geo_type=geo_type.value, mode='fix-attr-and-pick',
                                           extra={})
        elif geo_type == GeometryType.landcover:
            return UploadPostprocessResult(title='Update Land-cover Attributes', description='',
                                           geo_type=geo_type.value, mode='fix-attr-and-pick',
                                           extra={})

    def verify_content(self, content_path: str) -> DOTVerificationResult:
        # try to read contents
        content, data_format, counts = self.read_content(content_path)

        # generate messages
        messages = self.create_verification_messages(counts)

        # do we have content?
        if content is None:
            data_format = 'unknown'
            messages.append(DOTVerificationMessage(
                severity='error', message=f"File is either invalid or format is not supported."))

        # do we have any error messages?
        is_verified = True
        for message in messages:
            if message.severity == 'error':
                is_verified = False
                break

        return DOTVerificationResult(messages=messages, is_verified=is_verified, data_format=data_format)

    def extract_feature(self, content_path: str, parameters: dict) -> Dict:
        raise DUCTRuntimeError(f"Not implemented")

    def extract_delta_feature(self, content_path0: str, content_path1: str, parameters: dict) -> Dict:
        raise DUCTRuntimeError(f"Not implemented")

    def export_feature(self, content_path: str, parameters: dict, export_path: str, export_format: str) -> None:
        raise DUCTRuntimeError(f"Not implemented")

    def export_delta_feature(self, content_path0: str, content_path1: str, parameters: dict,
                             export_path: str, export_format: str) -> None:
        raise DUCTRuntimeError(f"Not implemented")
