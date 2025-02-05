import json
import sqlite3
import threading
import time

from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import List, Dict, Optional, Tuple, Any, Union

import shapely.geometry
from rtree import index
from saas.core.helpers import get_timestamp_now, generate_random_string
from saas.core.logging import Logging
from shapely import Polygon, Point, MultiPolygon, GeometryCollection
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy_json import NestedMutableJson

from explorer.schemas import ExplorerRuntimeError, Network

logger = Logging.get('explorer.geodb')

Base = declarative_base()


class GeometryType(Enum):
    temp = 'temp'
    zone = 'zone'
    landuse = 'landuse'
    landcover = 'landcover'
    building = 'building'
    vegetation = 'vegetation'


@dataclass
class GeoFeature:
    id: Optional[int]
    type: GeometryType
    geometry: Dict
    properties: Dict
    shape: shape
    bounds: Tuple[float]

    def make_geojson_feature(self) -> dict:
        return {
            "type": "Feature",
            "properties": self.properties,
            "geometry": self.geometry
        }


def _make_geo_features(records, geo_type: GeometryType) -> List[GeoFeature]:
    features = []
    for record in records:
        geo_shape = shape(record.geometry)
        features.append(GeoFeature(id=record.id, type=geo_type, geometry=dict(record.geometry),
                                   properties=dict(record.properties), shape=geo_shape,
                                   bounds=geo_shape.bounds))
    return features


@dataclass
class GeoZoneConfiguration:
    id: int
    zone_id: int
    name: str
    landuse_ids: List[int]
    landcover_ids: List[int]
    building_ids: List[int]
    vegetation_ids: List[int]

    _session_maker: sessionmaker = None

    def set_session_maker(self, session_maker: sessionmaker) -> None:
        self._session_maker = session_maker

    def get_landuse_geometries(self) -> List[GeoFeature]:
        with self._session_maker() as s:
            records = BulkRecordLoader.load(DBLanduseGeometries, s, self.landuse_ids)
            return _make_geo_features(records, GeometryType.landuse)

    def get_landcover_geometries(self) -> List[GeoFeature]:
        with self._session_maker() as s:
            records = BulkRecordLoader.load(DBLandcoverGeometries, s, self.landcover_ids)
            return _make_geo_features(records, GeometryType.landcover)

    def get_building_geometries(self) -> List[GeoFeature]:
        with self._session_maker() as s:
            records = BulkRecordLoader.load(DBBuildingGeometries, s, self.building_ids)
            return _make_geo_features(records, GeometryType.building)

    def get_vegetation_geometries(self) -> List[GeoFeature]:
        with self._session_maker() as s:
            records = BulkRecordLoader.load(DBVegetationGeometries, s, self.vegetation_ids)
            return _make_geo_features(records, GeometryType.vegetation)


@dataclass
class GeoZone(GeoFeature):
    name: str

    _session_maker: sessionmaker = None

    def set_session_maker(self, session_maker: sessionmaker) -> None:
        self._session_maker = session_maker

    def has_alternative_configs(self) -> bool:
        return self.properties[f'config_count'] > 1

    def get_configs(self) -> List[GeoZoneConfiguration]:
        # get the config ids for this zone
        properties = self.properties
        config_ids = [config['id'] for config in properties['config_details']]

        # load the configurations
        with self._session_maker() as session:
            records = BulkRecordLoader.load(DBZoneConfiguration, session, config_ids)
            return [GeoZoneConfiguration(id=record.id, zone_id=self.id, name=record.name,
                                         landuse_ids=list(record.landuse_ids),
                                         landcover_ids=list(record.landcover_ids),
                                         building_ids=list(record.building_ids),
                                         vegetation_ids=list(record.vegetation_ids)) for record in records]


class DBZoneGeometries(Base):
    __tablename__ = 'geo_zone'
    id = Column("id", Integer, primary_key=True)
    geometry = Column("geometry", NestedMutableJson, nullable=False)
    properties = Column("properties", NestedMutableJson, nullable=False)
    bounds = Column("bounds", String, nullable=False)
    name = Column("name", String, nullable=False)


class DBZoneConfiguration(Base):
    __tablename__ = 'geo_zone_configuration'
    id = Column("id", Integer, primary_key=True)
    zone_id = Column("zone_id", Integer, nullable=False)
    name = Column("name", String, nullable=False)
    landuse_ids = Column("landuse_ids", NestedMutableJson, nullable=False)
    landcover_ids = Column("landcover_ids", NestedMutableJson, nullable=False)
    building_ids = Column("building_ids", NestedMutableJson, nullable=False)
    vegetation_ids = Column("vegetation_ids", NestedMutableJson, nullable=False)


class DBLanduseGeometries(Base):
    __tablename__ = 'geo_landuse'
    id = Column("id", Integer, primary_key=True)
    geometry = Column("geometry", NestedMutableJson, nullable=False)
    properties = Column("properties", NestedMutableJson, nullable=False)


class DBLandcoverGeometries(Base):
    __tablename__ = 'geo_landcover'
    id = Column("id", Integer, primary_key=True)
    geometry = Column("geometry", NestedMutableJson, nullable=False)
    properties = Column("properties", NestedMutableJson, nullable=False)


class DBBuildingGeometries(Base):
    __tablename__ = 'geo_building'
    id = Column("id", Integer, primary_key=True)
    geometry = Column("geometry", NestedMutableJson, nullable=False)
    properties = Column("properties", NestedMutableJson, nullable=False)


class DBVegetationGeometries(Base):
    __tablename__ = 'geo_vegetation'
    id = Column("id", Integer, primary_key=True)
    geometry = Column("geometry", NestedMutableJson, nullable=False)
    properties = Column("properties", NestedMutableJson, nullable=False)


class DBNetworkNode(Base):
    __tablename__ = 'network_node'
    id = Column("id", Integer, primary_key=True, autoincrement=True)
    network_id = Column("network_id", String, nullable=False)
    name = Column("name", String, nullable=False)
    lon = Column("lon", Float, nullable=False)
    lat = Column("lat", Float, nullable=False)
    properties = Column("properties", NestedMutableJson, nullable=False)


class DBNetworkLink(Base):
    __tablename__ = 'network_link'
    id = Column("id", Integer, primary_key=True, autoincrement=True)
    network_id = Column("network_id", String, nullable=False)
    name = Column("name", String, nullable=False)
    from_node = Column("from_node", String, nullable=False)
    to_node = Column("to_node", String, nullable=False)
    properties = Column("properties", NestedMutableJson, nullable=False)


class BulkRecordLoader:
    mutex = threading.Lock()
    max_variable_number = None

    @classmethod
    def load(cls, db_class, session, all_ids: List[int]) -> List[Any]:
        with cls.mutex:
            # lazy initialise the max variable number
            if cls.max_variable_number is None:
                conn = sqlite3.connect(":memory:")
                cursor = conn.cursor()
                cls.max_variable_number = 0

                try:
                    for i in range(100, 100000, 100):
                        # construct a query with i variables
                        placeholders = ",".join(["?" for _ in range(i)])
                        query = f"SELECT {placeholders};"

                        # execute the query with i parameters
                        params = tuple(range(1, i + 1))
                        cursor.execute(query, params)

                        cls.max_variable_number = i

                except sqlite3.OperationalError:
                    pass

                finally:
                    cursor.close()
                    conn.close()

        # do we have a number > 0?
        if cls.max_variable_number == 0:
            raise ExplorerRuntimeError('Max db variable number is zero')

        # perform chunked loading of records
        records = []
        for i in range(0, len(all_ids), cls.max_variable_number):
            chunk_ids = all_ids[i:i + cls.max_variable_number]
            chunk = session.query(db_class).filter(db_class.id.in_(chunk_ids)).all()
            records.extend(chunk)
        return records


class GeometriesDB:
    def __init__(self, name: str, db_path: str, interval: int = 60, expiry: int = 60 * 60) -> None:
        self._name = name
        self._mutex = Lock()

        # initialise db
        self._db_path = db_path
        self._engine = create_engine(f"sqlite:///{self._db_path}")
        Base.metadata.create_all(self._engine)
        self._sessionmaker = sessionmaker(bind=self._engine)

        # initialise the various caches
        self._tmp_cache: Dict[str, List[GeoFeature]] = {}

        # rebuild the zones index
        self._zones_index = index.Index()
        self._zones_cache: Dict[int, Optional[GeoZone]] = {}
        self._zones_accessed: Dict[int, int] = {}
        self._rebuild_zone_index()

        # start the pruning worker
        self._prune_worker = threading.Thread(name=f"{name}:prune-worker", target=self._prune, kwargs={
            'interval': interval,
            'expiry': expiry
        }, daemon=True)
        self._prune_worker.start()

    @property
    def name(self) -> str:
        return self._name

    def _rebuild_zone_index(self) -> None:
        zones_index = index.Index()
        zones_cache: Dict[int, Optional[GeoZone]] = {}
        zones_accessed: Dict[int, int] = {}

        # create the index and cache for all zones (index only, not the zones themselves)
        t0 = get_timestamp_now()
        with self._sessionmaker() as session:
            records = session.query(DBZoneGeometries).with_entities(DBZoneGeometries.id, DBZoneGeometries.bounds).all()
            for record in records:
                # deserialise bounds
                bounds = record.bounds
                bounds = bounds.split(',')
                bounds = [float(v) for v in bounds]

                zones_index.insert(record.id, bounds)
                zones_cache[record.id] = None
                zones_accessed[record.id] = get_timestamp_now()

        t1 = get_timestamp_now()
        logger.info(f"[geodb:{self._name}:init] rebuilding index over {len(records)} zone "
                    f"done in {int((t1 - t0) / 1000)} seconds")

        # replace the existing index and cache with the new ones
        with self._mutex:
            self._zones_index = zones_index
            self._zones_cache = zones_cache
            self._zones_accessed = zones_accessed

    def _get_zone(self, zone_id: int) -> Optional[GeoZone]:
        if self._zones_cache[zone_id] is None:
            with self._sessionmaker() as session:
                record = session.query(DBZoneGeometries).get(zone_id)
                if record is not None:
                    geo_shape = shape(record.geometry)
                    zone = GeoZone(id=record.id, type=GeometryType.zone, geometry=dict(record.geometry),
                                   properties=dict(record.properties), shape=geo_shape, bounds=record.bounds,
                                   name=record.name)
                    zone.set_session_maker(self._sessionmaker)
                    self._zones_cache[zone_id] = zone
                else:
                    raise ExplorerRuntimeError(f"Attempting to get non-existing zone {zone_id}")

        self._zones_accessed[zone_id] = get_timestamp_now()
        return self._zones_cache[zone_id]

    def _get_zones(self, zone_ids: List[int]) -> Dict[int, GeoZone]:
        result = {}

        # first try to find zones in the cache
        missing = []
        for zone_id in zone_ids:
            zone = self._zones_cache.get(zone_id, None)
            if zone:
                result[zone_id] = zone
            else:
                missing.append(zone_id)

        # if anything is missing, read it from the database
        if len(missing) > 0:
            with self._sessionmaker() as session:
                records = BulkRecordLoader.load(DBZoneGeometries, session, missing)
                for record in records:
                    # create geo zone object
                    geo_shape = shape(record.geometry)
                    zone = GeoZone(id=record.id, type=GeometryType.zone, geometry=dict(record.geometry),
                                   properties=dict(record.properties), shape=geo_shape, bounds=geo_shape.bounds,
                                   name=record.name)
                    zone.set_session_maker(self._sessionmaker)
                    result[zone.id] = zone

                    # put the zone into the cache
                    self._zones_cache[zone.id] = zone

        # update all last accessed timestamps
        last_accessed = get_timestamp_now()
        for zone_id in result.keys():
            self._zones_accessed[zone_id] = last_accessed

        return result

    def _prune(self, interval: int, expiry: int) -> None:
        while True:
            # determine the cutoff time and prune the cache
            cutoff = get_timestamp_now() - 1000 * expiry
            with self._mutex:
                pruned = 0
                for feature_id, last_accessed in self._zones_accessed.items():
                    # has the feature not been accessed since the cutoff time?
                    if last_accessed < cutoff and self._zones_cache[feature_id] is not None:
                        self._zones_cache[feature_id] = None
                        pruned += 1

            if pruned > 0:
                logger.info(f"{self._prune_worker.name} -> {pruned} geometries pruned")

            # sleep for a while
            time.sleep(interval)

    def get_zone(self, zone_id: int) -> Optional[GeoZone]:
        with self._mutex:
            return self._get_zone(zone_id)

    def get_zones(self, zone_ids: List[int] = None) -> Dict[int, GeoZone]:
        with self._mutex:
            # use given zone_ids or use all zone_ids if none are given
            zone_ids = zone_ids if zone_ids else self._zones_cache.keys()
            return self._get_zones(zone_ids)

    def get_zones_by_area(self, area: Polygon) -> Dict[int, GeoZone]:
        with self._mutex:
            # find candidates that overlap with the area of interest
            candidates = self._zones_index.intersection(area.bounds)
            candidates = self._get_zones(list(candidates))

            # determine which candidate is included
            included = {}
            for candidate in candidates.values():
                if area.intersection(candidate.shape).area > 0:
                    included[candidate.id] = candidate

            return included

    def add_temporary_geometries(self, features: List[dict], object_id: str = None) -> str:
        # determine group id and create a group object in the cache
        group_id = object_id if object_id else generate_random_string(length=16)
        group: List[GeoFeature] = []
        with self._mutex:
            self._tmp_cache[group_id] = group

        # import all features
        for feature in features:
            geometry = feature['geometry']
            properties = feature['properties']

            geo_shape = shape(geometry)
            geo_bounds = geo_shape.bounds

            group.append(GeoFeature(id=None, type=GeometryType.temp, geometry=geometry, properties=properties,
                                    shape=geo_shape, bounds=geo_bounds))

        return group_id

    def delete_temporary_geometries(self, group_id: str) -> int:
        with self._mutex:
            geometries = self._tmp_cache.pop(group_id, None)
            return 0 if geometries is None else len(geometries)

    def import_geometries_as_zones(self, group_id: str) -> List[GeoZone]:
        with self._mutex:
            # do we have a group in tmp?
            group: List[GeoFeature] = self._tmp_cache.pop(group_id, None)
            if group is None:
                raise ExplorerRuntimeError(f"Temporary geometry group '{group_id}' not found.")

            # important each geometry as zone
            t0 = get_timestamp_now()
            imported = []
            with self._sessionmaker() as session:
                # create zone records
                records = []
                for entity in group:
                    if 'name' not in entity.properties or entity.properties['name'] is None:
                        entity.properties['name'] = 'undefined'

                    # initialise properties for building/landuse configurations
                    entity.properties['config_count'] = 0
                    entity.properties['config_details'] = []

                    # create record
                    bounds = ','.join([str(v) for v in entity.bounds])
                    records.append(DBZoneGeometries(geometry=entity.geometry, properties=entity.properties,
                                                    bounds=bounds, name=entity.properties['name']))

                # bulk import zones to db
                session.bulk_save_objects(records, return_defaults=True)
                session.commit()

                # records should now have ids, read and return geo zones
                for record in records:
                    # create geo zone
                    geo_shape = shape(record.geometry)
                    zone = GeoZone(id=record.id, type=GeometryType.zone, geometry=dict(record.geometry),
                                   properties=dict(record.properties), shape=geo_shape, bounds=geo_shape.bounds,
                                   name=record.name)
                    zone.set_session_maker(self._sessionmaker)

                    # add to imported
                    imported.append(zone)

                    # update cache
                    self._zones_cache[zone.id] = zone
                    self._zones_accessed[zone.id] = t0

            t1 = get_timestamp_now()
            logger.info(f"[geodb:{self._name}:import:zones] import of {len(imported)} zones "
                        f"done in {int((t1 - t0) / 1000)} seconds")

            return imported

    def import_geometries_as_network(self, network_id: str, network: Network) -> None:
        with self._mutex:
            with self._sessionmaker() as s:
                t0 = get_timestamp_now()

                # create node records
                nodes: Dict[str, DBNetworkNode] = {
                    node.id: DBNetworkNode(name=node.id, network_id=network_id, lon=node.lon, lat=node.lat,
                                           properties=node.properties) for node in network.nodes.values()
                }

                # bulk save the nodes in the DB
                s.bulk_save_objects(nodes.values(), return_defaults=True)
                s.commit()

                # create link records
                links: List[DBNetworkLink] = []
                for link in network.links.values():
                    n0 = nodes[link.from_node]
                    n1 = nodes[link.to_node]
                    links.append(DBNetworkLink(name=link.id, network_id=network_id,
                                               from_node=n0.name, to_node=n1.name, properties=link.properties))

                # bulk save the links in the DB
                s.bulk_save_objects(links, return_defaults=True)
                s.commit()

                t1 = get_timestamp_now()
                logger.info(f"[geodb:{self._name}:import:network] bulk import of network with {len(nodes)} nodes and "
                            f"{len(links)} links done in {int((t1 - t0) / 1000)} seconds")

    def _merge_with_default(self, session, relevant_zones: Dict[int, GeoZone],
                            bld_geometries: Dict[int, List[GeoFeature]], veg_geometries: Dict[int, List[GeoFeature]],
                            lc_geometries: Dict[int, List[GeoFeature]], lu_geometries: Dict[int, List[GeoFeature]]) \
            -> Tuple[Dict[int, List[GeoFeature]], Dict[int, List[GeoFeature]], Dict[int, List[GeoFeature]], Dict[int, List[GeoFeature]]]:

        def record_to_feature(record, geo_type: GeometryType) -> GeoFeature:
            geo_shape = shape(record.geometry)
            return GeoFeature(id=record.id, type=geo_type, geometry=dict(record.geometry),
                              properties=dict(record.properties), shape=geo_shape, bounds=geo_shape.bounds)

        def dump(geometries: List[Union[GeoFeature, BaseGeometry]], output_path: str) -> None:
            features = []
            for item in geometries:
                if item is None:
                    continue
                if isinstance(item, GeoFeature):
                    features.append(item.make_geojson_feature())
                else:
                    features.append({
                        "type": "Feature",
                        "properties": {},
                        "geometry": item.__geo_interface__
                    })
            with open(output_path, 'w') as f:
                json.dump({
                    "type": "FeatureCollection",
                    "features": features
                }, f, indent=2)

        def merge(features: Optional[List[Union[GeoFeature, BaseGeometry]]]) -> Optional[BaseGeometry]:
            if features is None:
                return None

            geometries: List[BaseGeometry] = [(f.shape if isinstance(f, GeoFeature) else f) for f in features if f is not None]
            if len(geometries) == 0:
                return None
            else:
                union = geometries[0]

                if len(features) > 1:
                    for f in geometries[1:]:
                        union = union.union(f)

                return union

        def filter_and_fill(base: List[GeoFeature], exclusion_area: Optional[BaseGeometry],
                            filler: Optional[List[GeoFeature]]) -> List[GeoFeature]:

            # if there is no base, just return the filler
            if len(base) == 0:
                return filler if filler is not None else []

            # if there is an exclusion area, apply it
            if exclusion_area is not None:
                result = [f for f in base
                          if isinstance(f.shape, shapely.geometry.Point) and not exclusion_area.contains(f.shape)
                          or not isinstance(f.shape, shapely.geometry.Point) and not exclusion_area.intersects(f.shape)]
            else:
                result = list(base)

            # if there are filler geometries, add them
            if filler is not None:
                result.extend(filler)

            return result

        def cut_and_fill(base: List[GeoFeature], filler: Optional[List[GeoFeature]]) -> List[GeoFeature]:
            # if there is no base, just return the filler
            if len(base) == 0:
                return filler if filler is not None else []

            # if there is no filler, just return the base
            if filler is None or len(filler) == 0:
                return base

            # merge the filler into a 'cut-out' template
            cut_out = merge(filler)

            # cut the hole...
            result: List[GeoFeature] = []
            for f in base:
                overlap = f.shape.intersection(cut_out)
                if overlap.area > 0:
                    c = f.shape.difference(cut_out)

                    f.geometry = c.__geo_interface__
                    f.shape = c
                    f.bounds = c.bounds

                result.append(f)

            # ...and fill it with the replacement
            result.extend(filler)

            return result

        # handle each zone one by one
        bld_result: Dict[int, List[GeoFeature]] = {}
        veg_result: Dict[int, List[GeoFeature]] = {}
        lc_result: Dict[int, List[GeoFeature]] = {}
        lu_result: Dict[int, List[GeoFeature]] = {}
        for zone_id, zone in relevant_zones.items():
            # get the configs and check if there are any to begin with
            configs = zone.get_configs()
            if len(configs) == 0:
                bld_result[zone_id] = bld_geometries.get(zone_id, [])
                veg_result[zone_id] = veg_geometries.get(zone_id, [])
                lc_result[zone_id] = lc_geometries.get(zone_id, [])
                lu_result[zone_id] = lu_geometries.get(zone_id, [])
                continue

            # perform sanity check: name of first config should be 'Default' (by convention, not strictly enforced)
            default_config = configs[0]
            if default_config.name != 'Default':
                logger.warning(f"[_merge_with_default] zone {zone_id} configuration at index is not 'Default'?")

            # load the default geometry records
            bld_default_records = BulkRecordLoader.load(DBBuildingGeometries, session, default_config.building_ids)
            veg_default_records = BulkRecordLoader.load(DBVegetationGeometries, session, default_config.vegetation_ids)
            lc_default_records = BulkRecordLoader.load(DBLandcoverGeometries, session, default_config.landcover_ids)
            lu_default_records = BulkRecordLoader.load(DBLanduseGeometries, session, default_config.landuse_ids)

            # convert the records into geo features
            bld_features = [record_to_feature(record, GeometryType.building) for record in bld_default_records]
            veg_features = [record_to_feature(record, GeometryType.vegetation) for record in veg_default_records]
            lc_features = [record_to_feature(record, GeometryType.landcover) for record in lc_default_records]
            lu_features = [record_to_feature(record, GeometryType.landuse) for record in lu_default_records]

            # for debugging only
            # output_prefix = os.path.join(os.environ['HOME'], 'Desktop', 'temp', f"{zone_id}_")
            # dump(bld_features, output_prefix+'bld_defaults.geojson')
            # dump(veg_features, output_prefix+'veg_defaults.geojson')
            # dump(lc_features, output_prefix+'lc_defaults.geojson')
            # dump(lu_features, output_prefix+'lu_defaults.geojson')

            # create union shape of BLD, LC and LU
            bld_union = merge(bld_geometries.get(zone_id))
            lc_union = merge(lc_geometries.get(zone_id))
            lu_union = merge(lu_geometries.get(zone_id))
            exclusion_area = merge([bld_union, lc_union, lu_union])
            exclusion_area = exclusion_area.convex_hull if exclusion_area else None
            # dump([bld_union, lc_union, lu_union, exclusion_area], output_prefix+'exclusion_area.geojson')

            # use the union shape to filter default buildings
            bld_features = filter_and_fill(bld_features, exclusion_area, bld_geometries.get(zone_id))
            veg_features = filter_and_fill(veg_features, exclusion_area, veg_geometries.get(zone_id))

            # use the LC/LU unions to 'cut a hole' and replace with filler land-cover/land-use...
            lc_features = cut_and_fill(lc_features, lc_geometries.get(zone_id))
            lu_features = cut_and_fill(lu_features, lu_geometries.get(zone_id))

            # for debugging only
            # dump(bld_features, output_prefix+'bld_after.geojson')
            # dump(veg_features, output_prefix+'veg_after.geojson')
            # dump(lc_features, output_prefix+'lc_after.geojson')
            # dump(lu_features, output_prefix+'lu_after.geojson')

            bld_result[zone_id] = bld_features
            veg_result[zone_id] = veg_features
            lc_result[zone_id] = lc_features
            lu_result[zone_id] = lu_features

        return bld_result, veg_result, lc_result, lu_result

    def _prepare_geometries(self, geo_type: GeometryType, group_ids: Dict[GeometryType, str],
                            relevant_zones: Dict[int, GeoZone], relevant_zones_idx: index.Index,
                            include_empty_zones: bool) -> (Dict[int, List[GeoFeature]], List[GeoFeature], List[dict]):
        t0 = get_timestamp_now()

        # do we have a group id?
        if geo_type not in group_ids:
            return {}, [], []

        # do we have a group in tmp?
        group_id = group_ids[geo_type]
        group: List[GeoFeature] = self._tmp_cache.pop(group_id, None)
        if group is None:
            raise ExplorerRuntimeError(f"Temporary geometry group {group_id} not found.")

        # sort the geometries according to the zone they belong to (initialise with empty lists in case we
        # are supposed to include empty zones) and identify remaining geometries that couldn't be matched.
        geometries_by_zone = {zone_id: [] for zone_id in relevant_zones.keys()}
        all_geometries: List[GeoFeature] = []
        remaining_geometries: List[GeoFeature] = []
        problematic_geometries: List[dict] = []
        prepared_geometries = 0
        for geo_feature in group:
            # we need to distinguish between the type of geometry: buildings and vegetation should
            # overlap with multiple zones only in rare cases (vegetation as points actually shouldn't
            # at all). -> they will be added only once to the zone with the highest overlap.
            if geo_type in [GeometryType.building, GeometryType.vegetation]:
                # find the zones with non-zero overlap with that geometry
                max_overlap = 0
                max_overlap_zones = []
                for candidate_zone_id in relevant_zones_idx.intersection(geo_feature.bounds):
                    # calculate the overlapping area (in case of point, area is simply 1)
                    zone_shape = relevant_zones[candidate_zone_id].shape
                    if isinstance(geo_feature.shape, Point):
                        overlap = 1 if zone_shape.contains(geo_feature.shape) else 0
                    else:
                        overlap = geo_feature.shape.intersection(zone_shape).area

                    # is the overlap more than the current max?
                    if overlap > max_overlap:
                        max_overlap = overlap
                        max_overlap_zones = [candidate_zone_id]

                    # is the overlap equal to the current max?
                    elif overlap == max_overlap and max_overlap > 0:
                        max_overlap_zones.append(candidate_zone_id)

                # geometries overlapping exactly with multiple zones should be extremely rare. for most
                # cases we should have only one zone that is having the most overlapping area with the
                # geometry.
                if len(max_overlap_zones) > 1:
                    logger.info(
                        f"rare case of building overlapping with multiple zones with equally: "
                        f"zones={max_overlap_zones} overlap={max_overlap} geo_feature={geo_feature}")

                # append the geometry to the zone with the largest overlap (which is the sole zone id in
                # the list) or the one with the highest zone id.
                if len(max_overlap_zones) > 0:
                    prepared_geometries += 1
                    zone_id = max(max_overlap_zones)

                    # update properties with id information
                    properties = dict(geo_feature.properties)
                    properties['zone_id'] = zone_id

                    geo_feature = GeoFeature(id=None, type=geo_feature.type,
                                             geometry=geo_feature.geometry, properties=properties,
                                             shape=geo_feature.shape, bounds=geo_feature.bounds)
                    geometries_by_zone[zone_id].append(geo_feature)
                else:
                    remaining_geometries.append(geo_feature)

            # for other geometry types, such as land-cover and land-use, they may very well overlap with
            # multiple zones -> they will be to each zone.
            elif geo_type in [GeometryType.landuse, GeometryType.landcover]:
                # if the zone overlaps with the geometry, add the cropped geometry to the zone
                found = False
                for candidate_zone_id in relevant_zones_idx.intersection(geo_feature.bounds):
                    zone_shape = relevant_zones[candidate_zone_id].shape
                    overlap = geo_feature.shape.intersection(zone_shape)
                    if overlap.area > 0:
                        # if the overlap is a GeometryCollection, break it down into its parts
                        parts = []
                        if isinstance(overlap, GeometryCollection):
                            parts.extend(overlap.geoms)
                        else:
                            parts.append(overlap)

                        # handle each part
                        for part in parts:
                            # is the overlap part not a Polygon?
                            if not isinstance(part, (Polygon, MultiPolygon)):
                                problematic_geometries.append(part.__geo_interface__)
                                continue

                            # update properties with id information
                            properties = dict(geo_feature.properties)
                            properties['zone_id'] = candidate_zone_id

                            # create geo feature using the overlap area only (i.e., the geometry cropped by
                            # the zone shape)
                            geo_part = GeoFeature(
                                id=None, type=geo_feature.type, geometry=part.__geo_interface__,
                                properties=properties, shape=part, bounds=part.bounds
                            )

                            all_geometries.append(geo_part)
                            geometries_by_zone[candidate_zone_id].append(geo_part)
                            found = True
                            prepared_geometries += 1

                # no overlap with any zone?
                if not found:
                    remaining_geometries.append(geo_feature)

            else:
                raise ExplorerRuntimeError(f"trying to add unsupported geometry ({geo_type}) to zone")

        # if we are not supposed to include empty zones, strip them
        if not include_empty_zones:
            relevant_zone_ids = [k for k, v in geometries_by_zone.items() if len(v) > 0]
            geometries_by_zone = {k: v for k, v in geometries_by_zone.items() if k in relevant_zone_ids}

        t1 = get_timestamp_now()
        logger.info(f"[geodb:{self._name}:prepare:{geo_type.value}] prepared {prepared_geometries} and "
                    f"ignored {len(remaining_geometries)} features in {int((t1 - t0) / 1000)} seconds")

        return geometries_by_zone, remaining_geometries, problematic_geometries

    def _import_geometries(self, session, db_class, geometries_by_zone: Dict[int, List[GeoFeature]]) -> Dict[int, List]:
        t0 = get_timestamp_now()

        # do we have any geometries?
        if len(geometries_by_zone) == 0:
            return {}

        # for each zone: import features to DB
        all_records: List[db_class] = []
        records_by_zones: Dict[int, List[db_class]] = {}
        for zone_id, features in geometries_by_zone.items():
            records_by_zones[zone_id] = []
            for feature in features:
                record = db_class(geometry=feature.geometry, properties=feature.properties)
                all_records.append(record)
                records_by_zones[zone_id].append(record)

        # store the records to the db
        session.bulk_save_objects(all_records, return_defaults=True)
        session.commit()

        t1 = get_timestamp_now()
        logger.info(f"[geodb:{self._name}:import:{db_class.__name__}] importing {len(all_records)} "
                    f"features done in {int((t1 - t0) / 1000)} seconds")

        return records_by_zones

    def _create_zone_configurations(self, config_name: str, relevant_zones: Dict[int, GeoZone], session,
                                    bld_records: Dict[int, List[DBBuildingGeometries]],
                                    veg_records: Dict[int, List[DBVegetationGeometries]],
                                    lc_records: Dict[int, List[DBLandcoverGeometries]],
                                    lu_records: Dict[int, List[DBLanduseGeometries]]) -> Dict[int, DBZoneConfiguration]:
        t0 = get_timestamp_now()

        # create a zone configuration
        configs_by_zone: Dict[int, DBZoneConfiguration] = {}
        for zone_id in relevant_zones:
            # get all the geometry ids
            bld_ids = [record.id for record in bld_records.get(zone_id, [])]
            veg_ids = [record.id for record in veg_records.get(zone_id, [])]
            lc_ids = [record.id for record in lc_records.get(zone_id, [])]
            lu_ids = [record.id for record in lu_records.get(zone_id, [])]

            # create the zone configuration record
            configs_by_zone[zone_id] = DBZoneConfiguration(zone_id=zone_id, name=config_name,
                                                           landuse_ids=lu_ids, landcover_ids=lc_ids,
                                                           building_ids=bld_ids, vegetation_ids=veg_ids)

        # store the zone configurations to the db
        session.bulk_save_objects(configs_by_zone.values(), return_defaults=True)
        session.commit()

        t1 = get_timestamp_now()
        logger.info(f"[geodb:{self._name}:import:zones] importing {len(configs_by_zone)} configurations "
                    f"done in {int((t1 - t0) / 1000)} seconds")

        return configs_by_zone

    def _update_zone_properties(self, config_name: str, configs_by_zone: Dict[int, DBZoneConfiguration],
                                relevant_zones: Dict[int, GeoZone], session) -> None:
        t0 = get_timestamp_now()

        # update the relevant zone properties
        for zone_id, zone in relevant_zones.items():
            config = configs_by_zone[zone_id]
            zone.properties['config_count'] += 1
            zone.properties['config_details'].append({
                'id': config.id,
                'name': config_name
            })

        # check if we already know about this feature
        for feature_id in relevant_zones.keys():
            if feature_id not in self._zones_cache:
                raise ExplorerRuntimeError(f"Attempt to update properties of zone that is not known to the cache.")

        # load the relevant db records

        # ...ad load the building/landuse geometries in chunks
        all_ids = list(relevant_zones.keys())
        records = BulkRecordLoader.load(DBZoneGeometries, session, all_ids)

        # update the records and the cache
        last_accessed = get_timestamp_now()
        for record in records:
            record.properties = relevant_zones[record.id].properties
            self._zones_accessed[record.id] = last_accessed

        # bulk save
        session.bulk_save_objects(records)
        session.commit()

        t1 = get_timestamp_now()
        logger.info(f"[geodb:{self._name}:import:zones] updating {len(relevant_zones)} zone properties "
                    f"done in {int((t1 - t0) / 1000)} seconds")

    def import_geometries_as_zone_configuration(self, group_ids: Dict[GeometryType, str], config_name: str,
                                                eligible_zone_ids: List[int] = None, include_empty_zones: bool = False,
                                                produce_results: bool = False) -> \
            Optional[Tuple[Dict[GeometryType, List[GeoFeature]], Dict[GeometryType, List[GeoFeature]]]]:

        with self._mutex:
            with self._sessionmaker() as session:
                # determine the relevant zones (either all or only the eligible ones) and make sure
                # they are loaded in the cache
                eligible_zone_ids = eligible_zone_ids if eligible_zone_ids is not None \
                    else list(self._zones_cache.keys())
                rel_zones = self._get_zones(eligible_zone_ids)

                # build the index over the relevant zones
                rel_zones_idx = index.Index()
                for zone_id, zone in rel_zones.items():
                    rel_zones_idx.insert(zone_id, zone.bounds)

                # prepare geometries
                bld_geometries, ignored_bld, problematic_bld = self._prepare_geometries(
                    GeometryType.building, group_ids, rel_zones, rel_zones_idx, include_empty_zones)
                veg_geometries, ignored_veg, problematic_veg = self._prepare_geometries(
                    GeometryType.vegetation, group_ids, rel_zones, rel_zones_idx, include_empty_zones)
                lc_geometries, ignored_lc, problematic_lc = self._prepare_geometries(
                    GeometryType.landcover, group_ids, rel_zones, rel_zones_idx, include_empty_zones)
                lu_geometries, ignored_lu, problematic_lu = self._prepare_geometries(
                    GeometryType.landuse, group_ids, rel_zones, rel_zones_idx, include_empty_zones)

                # merge new with default geometries (if any)
                bld_geometries, veg_geometries, lc_geometries, lu_geometries = self._merge_with_default(
                        session, rel_zones, bld_geometries, veg_geometries, lc_geometries, lu_geometries)

                # import geometries
                bld_records: Dict[int, List[DBBuildingGeometries]] = self._import_geometries(
                    session, DBBuildingGeometries, bld_geometries)
                veg_records: Dict[int, List[DBVegetationGeometries]] = self._import_geometries(
                    session, DBVegetationGeometries, veg_geometries)
                lc_records: Dict[int, List[DBLandcoverGeometries]] = self._import_geometries(
                    session, DBLandcoverGeometries, lc_geometries)
                lu_records: Dict[int, List[DBLanduseGeometries]] = self._import_geometries(
                    session, DBLanduseGeometries, lu_geometries)

                # create configurations for each zone
                configs: Dict[int, DBZoneConfiguration] = self._create_zone_configurations(
                    config_name, rel_zones, session, bld_records, veg_records, lc_records, lu_records)

                # update the zone properties with the new configurations
                self._update_zone_properties(config_name, configs, rel_zones, session)

                # produce results (if requested)
                if produce_results:
                    t0 = get_timestamp_now()

                    imported_bld_geometries = [item for sublist in bld_records.values() for item in sublist]
                    imported_veg_geometries = [item for sublist in veg_records.values() for item in sublist]
                    imported_lu_geometries = [item for sublist in lu_records.values() for item in sublist]
                    imported_lc_geometries = [item for sublist in lc_records.values() for item in sublist]

                    imported = {
                        GeometryType.building: _make_geo_features(imported_bld_geometries, GeometryType.building),
                        GeometryType.vegetation: _make_geo_features(imported_veg_geometries, GeometryType.vegetation),
                        GeometryType.landuse: _make_geo_features(imported_lu_geometries, GeometryType.landuse),
                        GeometryType.landcover: _make_geo_features(imported_lc_geometries, GeometryType.landcover)
                    }

                    ignored = {
                        GeometryType.building: ignored_bld,
                        GeometryType.vegetation: ignored_veg,
                        GeometryType.landuse: ignored_lu,
                        GeometryType.landcover: ignored_lc
                    }

                    t1 = get_timestamp_now()
                    logger.info(f"[geodb:{self._name}:import:zones] done producing results "
                                f"in {int((t1 - t0) / 1000)} seconds")

                    return imported, ignored

                else:
                    logger.info(f"[geodb:{self._name}:import:zones] done importing geometries from groups {group_ids}.")
                    return None
