from __future__ import annotations

import json
import os
from typing import List, Any, Dict, Union, Optional

import numpy as np
import rasterio
from rasterio.features import rasterize
from saas.core.helpers import hash_string_object, hash_json_object
from saas.core.logging import Logging
from shapely.geometry import shape, Polygon

from explorer.cache import CachedJSONObject, Cache
from explorer.geodb import GeoFeature, GeometriesDB, GeometryType, GeoZoneConfiguration, DBZoneConfiguration, \
    DBBuildingGeometries, DBNetworkNode, DBNetworkLink, DBLanduseGeometries, DBZoneGeometries, DBVegetationGeometries, \
    DBLandcoverGeometries, BulkRecordLoader
from explorer.schemas import ExplorerRuntimeError, ProjectInfo, BoundingBox, Dimensions, Network, NetworkNode, \
    NetworkLink, ZonesConfigurationMapping

logger = Logging.get('explorer.bdp')


def _make_feature_collection(records: List[Union[GeoFeature, DBBuildingGeometries,
                                                 DBLanduseGeometries, DBLandcoverGeometries]]) -> dict:
    features = []
    for record in records:
        # scan the geometries for Polygons and convert into MultiPolygons for consistency required by ArcGIS. also,
        # check for geometries without any coordinates and filter them out.
        geometry = dict(record.geometry)
        if geometry['type'] == 'Polygon':
            # convert to multipolygon
            geometry['type'] = 'MultiPolygon'
            geometry['coordinates'] = [geometry['coordinates']]

        if geometry['type'] == 'MultiPolygon':
            # do we have missing coordinates?
            if not geometry['coordinates'] or any(i == [] for i in geometry['coordinates']):
                logger.warning(f"MultiPolygon without coordinates: {record.id} properties={record.properties} "
                               f"geometry={geometry}")
                continue

        # add to features
        features.append({
            'type': 'Feature',
            'id': record.id,
            'geometry': geometry,
            'properties': dict(record.properties)
        })

    return {
        'type': 'FeatureCollection',
        'features': features
    }


class BaseDataPackageDB(GeometriesDB):
    def __init__(self, name: str, db_path: str) -> None:
        super().__init__(name, db_path)

    @classmethod
    def exists(cls, directory: str, db_id: str) -> bool:
        # check if files exist
        bdp_path = os.path.join(directory, f"{db_id}.json")
        db_path = os.path.join(directory, f"{db_id}.db")
        return os.path.isfile(bdp_path) and os.path.isfile(db_path)

    @classmethod
    def remove(cls, directory: str, db_id: str) -> None:
        bdp_path = os.path.join(directory, f"{db_id}.json")
        if bdp_path:
            os.remove(bdp_path)

        db_path = os.path.join(directory, f"{db_id}.db")
        if db_path:
            os.remove(db_path)

    @classmethod
    def list(cls, directory: str) -> List[str]:
        # find all potential BDP id candidates
        result = []
        for filename in os.listdir(directory):
            # determine BDP id
            temp = filename.split('.')
            bdp_id = temp[0]

            # do we have both a JSON and a DB file?
            bdp_path = os.path.join(directory, f"{bdp_id}.json")
            db_path = os.path.join(directory, f"{bdp_id}.db")
            if os.path.isfile(bdp_path) and os.path.isfile(db_path) and bdp_id not in result:
                result.append(bdp_id)

        return result


class ProjectGeometriesDB(GeometriesDB):
    def __init__(self, info: ProjectInfo, cache: Cache = None) -> None:
        super().__init__(f"prj:{info.meta.id}", info.geo_db_path)

        # determine the default zone config mapping (we do so by fixing an empty config mapping -> the fixing will
        # add missing selections with the default configs)
        self._default_zone_alt_mapping = self.fix_zones_config_mapping(ZonesConfigurationMapping.empty())

        self._obj_cache = cache
        self._zones_masks = {}

    def fix_zones_config_mapping(self, zone_config_mapping: ZonesConfigurationMapping) -> ZonesConfigurationMapping:
        # iterate over all zones and fix missing or wrong config selections
        all_zones = self.get_zones()
        for zone_id, zone in all_zones.items():
            # get the existing configurations for this zone
            configs = zone.get_configs()

            # is there a selection specified in the first place? if not, then select the first
            # config, i.e., the default config
            if zone_id not in zone_config_mapping.selection:
                zone_config_mapping.selection[zone_id] = configs[0].id

            # does the configuration exist? it should. if it doesn't then something bigger may not be working.
            existing_config_ids = [config.id for config in configs]
            if zone_config_mapping.selection[zone_id] not in existing_config_ids:
                raise ExplorerRuntimeError(f"Encountered non-existing configuration "
                                           f"{zone_config_mapping.selection[zone_id]} for zone {zone_id}")

        return zone_config_mapping

    def default_zones_config_mapping(self) -> ZonesConfigurationMapping:
        return self._default_zone_alt_mapping

    def get_zone_configuration(self, config_id: int) -> GeoZoneConfiguration:
        with self._mutex:
            with self._sessionmaker() as session:
                # get the record for this config id
                config_record = session.query(DBZoneConfiguration).get(config_id)
                if config_record is None:
                    raise ExplorerRuntimeError(f"Zone configuration {config_id} not found in database.")

                # create a geo zone configuration object for the to-be-deleted config
                config = GeoZoneConfiguration(id=config_id, zone_id=config_record.zone_id, name=config_record.name,
                                              landuse_ids=list(config_record.landuse_ids),
                                              landcover_ids=list(config_record.landcover_ids),
                                              building_ids=list(config_record.building_ids),
                                              vegetation_ids=list(config_record.vegetation_ids))
                return config

    def delete_zone_configuration(self, config_id: int) -> GeoZoneConfiguration:
        def index_of_config(zone: GeoFeature, config_id: int) -> Optional[int]:
            for index, obj in enumerate(zone.properties['config_details']):
                if obj['id'] == config_id:
                    return index
            return None

        with self._mutex:
            with self._sessionmaker() as session:
                # get the record for this config id
                config_record = session.query(DBZoneConfiguration).get(config_id)
                if config_record is None:
                    raise ExplorerRuntimeError(f"Zone configuration {config_id} not found in database.")

                # get the zone and determine the index of the configuration
                zone = self._get_zone(config_record.zone_id)
                idx = index_of_config(zone, config_id)
                if idx is None:
                    raise ExplorerRuntimeError(f"Zone {zone.id} has no configuration {config_id}.")

                # update the properties
                properties = zone.properties
                properties['config_count'] -= 1
                removed_config = properties['config_details'].pop(idx)

                # check if the config ids match
                if removed_config['id'] != config_id:
                    raise ExplorerRuntimeError(f"Mismatching ids when removing config in zone {zone.id}: "
                                               f"config_id={config_id} check={removed_config['id']}")

                # get the database record and set the new properties
                zone = session.query(DBZoneGeometries).get(zone.id)
                zone.properties = properties

                # create a geo zone configuration object for the to-be-deleted config
                config = GeoZoneConfiguration(id=config_id, zone_id=zone.id, name=config_record.name,
                                              landuse_ids=list(config_record.landuse_ids),
                                              landcover_ids=list(config_record.landcover_ids),
                                              building_ids=list(config_record.building_ids),
                                              vegetation_ids=list(config_record.vegetation_ids))
                config.set_session_maker(self._sessionmaker)

                # delete the configuration and all associated landuse, building, and vegetation features
                session.delete(config_record)
                session.query(DBLanduseGeometries).filter(DBLanduseGeometries.id.in_(config.landuse_ids)).delete()
                session.query(DBLandcoverGeometries).filter(DBLandcoverGeometries.id.in_(config.landcover_ids)).delete()
                session.query(DBBuildingGeometries).filter(DBBuildingGeometries.id.in_(config.building_ids)).delete()
                session.query(DBVegetationGeometries).filter(
                    DBVegetationGeometries.id.in_(config.vegetation_ids)).delete()

                # commit all the modifications to the database
                session.commit()

                return config

    def geometries(self, geo_type: GeometryType, group_id: str = None, area: Polygon = None,
                   zone_config_mapping: ZonesConfigurationMapping = None, use_cache: bool = True) -> CachedJSONObject:
        # generate a cache object id
        token = f"{geo_type}:{group_id if group_id else ''}:{str(area) if area else ''}:" \
                f"{zone_config_mapping.selection if zone_config_mapping else ''}"
        cache_obj_id = hash_string_object(token).hex()

        # see if we already have this object cached
        cached_obj: CachedJSONObject = self._obj_cache.json(cache_obj_id)
        if use_cache and cached_obj is not None:
            return cached_obj

        if geo_type == GeometryType.zone:
            # if an area has been provided, we limit the result to at most these zones
            zones = self.get_zones_by_area(area) if area else self.get_zones()

            # do we have zone config mapping? if so, then select only those zones that are included in the selection
            if zone_config_mapping:
                zones = [zone for zone in zones.values() if zone.id in zone_config_mapping.selection]
            else:
                zones = list(zones.values())

            content = _make_feature_collection(zones)

        elif geo_type in [GeometryType.landuse, GeometryType.landcover, GeometryType.building, GeometryType.vegetation]:
            # is it a temporary geometry object?
            if group_id is not None and group_id.startswith('temp:'):
                set_id = group_id[5:]
                if set_id not in self._tmp_cache:
                    raise ExplorerRuntimeError(f"Geometry dataset {group_id} not found")

                if area is None:
                    geometries = self._tmp_cache[set_id]
                else:
                    geometries = []
                    for geometry in self._tmp_cache[set_id]:
                        if area.intersection(geometry.shape).area > 0:
                            geometries.append(geometry)

                content = _make_feature_collection(geometries)

            else:
                # if an area has been provided, we limit the result to at most these zones
                zones = self.get_zones_by_area(area) if area else self.get_zones()

                # if we don't have a zone alt config mapping, use the default one
                zone_config_mapping = zone_config_mapping if zone_config_mapping else self.default_zones_config_mapping()

                # get all the relevant configuration ids
                relevant_config_ids = []
                for zone_id, config_id in zone_config_mapping.selection.items():
                    if zone_id in zones:
                        relevant_config_ids.append(config_id)

                with self._sessionmaker() as session:
                    # load all the relevant configurations from the database...
                    configurations = BulkRecordLoader.load(DBZoneConfiguration, session, relevant_config_ids)

                    # determine the ids of all the records we need and load the building/landuse geometries
                    if geo_type == GeometryType.landuse:
                        all_ids = [id for config in configurations for id in config.landuse_ids]
                        records = BulkRecordLoader.load(DBLanduseGeometries, session, all_ids)
                    elif geo_type == GeometryType.landcover:
                        all_ids = [id for config in configurations for id in config.landcover_ids]
                        records = BulkRecordLoader.load(DBLandcoverGeometries, session, all_ids)
                    elif geo_type == GeometryType.building:
                        all_ids = [id for config in configurations for id in config.building_ids]
                        records = BulkRecordLoader.load(DBBuildingGeometries, session, all_ids)
                    else:
                        all_ids = [id for config in configurations for id in config.vegetation_ids]
                        records = BulkRecordLoader.load(DBVegetationGeometries, session, all_ids)

                    # create a list of included features
                    included = []
                    for record in records:
                        geometry = record.geometry
                        geo_shape = shape(geometry)

                        # if we have an area of interest specified, filter and crop features according to the area
                        if area is not None:
                            # if the feature is a building or vegetation, then don't crop but skip it if it's
                            # not FULLY inside the area of interest.
                            if geo_type in [GeometryType.building, GeometryType.vegetation]:
                                if not geo_shape.within(area):
                                    continue

                            # if it's not a building/vegetation, crop it to the bounds of the area of interest
                            else:
                                # is there any overlap? i.e. is there anything left after cropping? if no, skip it
                                geo_intersection = geo_shape.intersection(area)
                                if geo_intersection.area == 0:
                                    continue

                                # update geometry and geo_shape
                                geometry = geo_intersection.__geo_interface__
                                geo_shape = shape(geometry)

                        included.append(GeoFeature(id=record.id, type=geo_type, geometry=geometry,
                                                   properties=record.properties, shape=geo_shape,
                                                   bounds=geo_shape.bounds))

                    content = _make_feature_collection(included)

        else:
            raise ExplorerRuntimeError(f"Invalid geometry type: {geo_type}")

        # create the cache object
        cached_obj: CachedJSONObject = self._obj_cache.json(cache_obj_id, content)
        return cached_obj

    def network_as_geojson(self, network_id: str, use_cache: bool = True) -> CachedJSONObject:
        # generate a cache object id
        token = f"network:{network_id}"
        cache_obj_id = hash_string_object(token).hex()

        # see if we already have this object cached
        cached_obj: CachedJSONObject = self._obj_cache.json(cache_obj_id)
        if use_cache and cached_obj is not None:
            return cached_obj

        # helper function to replace NaN values with None
        def replace_nan_with_none(properties: dict[str, Any]) -> dict[str, Any]:
            result = properties.copy()
            for key, value in result.items():
                if isinstance(value, float) and value != value:
                    result[key] = None
            return result

        # convert network into geojson
        network = self.network(network_id)
        node_features = []
        link_features = []
        for node in network.nodes.values():
            feature = {
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [node.lon, node.lat],
                },
                'properties': replace_nan_with_none(node.properties)
            }
            feature['properties']['id'] = node.id
            node_features.append(feature)

        for link in network.links.values():
            from_node = network.nodes[link.from_node]
            to_node = network.nodes[link.to_node]
            feature = {
                'type': 'Feature',
                'geometry': {
                    'type': 'LineString',
                    'coordinates': [
                        [from_node.lon, from_node.lat],
                        [to_node.lon, to_node.lat]
                    ]
                },
                'properties': replace_nan_with_none(link.properties)
            }
            feature['properties']['id'] = link.id
            link_features.append(feature)

        content = {
            'nodes': {
                'type': 'FeatureCollection',
                'features': node_features
            },
            'links':  {
                'type': 'FeatureCollection',
                'features': link_features
            }
        }

        # create the cache object
        cached_obj: CachedJSONObject = self._obj_cache.json(cache_obj_id, content)
        return cached_obj

    def network(self, network_id: str) -> Network:
        with self._sessionmaker() as session:
            # get all nodes and links for the network
            node_records = session.query(DBNetworkNode).filter(DBNetworkNode.network_id == network_id).all()
            link_records = session.query(DBNetworkLink).filter(DBNetworkLink.network_id == network_id).all()

            # recreate the network data structure
            nodes: Dict[str, NetworkNode] = {
                record.name: NetworkNode(id=record.name, lat=record.lat, lon=record.lon,
                                         properties=record.properties) for record in node_records
            }

            links: Dict[str, NetworkLink] = {
                record.name: NetworkLink(id=record.name, from_node=record.from_node, to_node=record.to_node,
                                         properties=record.properties) for record in link_records
            }
            network = Network(nodes=nodes, links=links)
            return network

    def store_buildings_by_configuration(self, zone_config_mapping: ZonesConfigurationMapping,
                                         content_path: str) -> None:
        # read all the configurations from the database and collect all the buildings as GeoJSON features
        config_ids = list(zone_config_mapping.selection.values())
        with self._sessionmaker() as session:
            # get feature ids for all selected configurations
            features_ids = []
            for record in BulkRecordLoader.load(DBZoneConfiguration, session, config_ids):
                features_ids.extend(list(record.building_ids))

            # load all the building features
            features = []
            for record in BulkRecordLoader.load(DBBuildingGeometries, session, features_ids):
                features.append({
                    'type': 'Feature',
                    'id': record.id,
                    'geometry': dict(record.geometry),
                    'properties': dict(record.properties)
                })

            # write the feature collection to file
            with open(content_path, 'w') as f:
                s = json.dumps({
                    'type': 'FeatureCollection',
                    'features': features
                })

                f.write(s)

    def zones_mask(self, bounding_box: BoundingBox, dimensions: Dimensions) -> np.ndarray:
        # determine the hash
        h = hash_json_object({'bounding_box': bounding_box.dict(), 'dimensions': dimensions.dict()}).hex()

        # do we have a mask for this configuration?
        with self._mutex:
            if h in self._zones_masks:
                return self._zones_masks[h]

        # if not, create one
        with rasterio.Env():
            zones = self.geometries(GeometryType.zone).content()
            geometries = [(feature['geometry'], 1) for feature in zones['features']]
            raster = rasterize(geometries,
                               transform=rasterio.transform.from_bounds(bounding_box.west, bounding_box.south,
                                                                        bounding_box.east, bounding_box.north,
                                                                        dimensions.width, dimensions.height),
                               out_shape=(dimensions.height, dimensions.width),
                               fill=0
                               )

            with self._mutex:
                self._zones_masks[h] = raster

            return raster
