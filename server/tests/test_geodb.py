import json
import os
import time
from typing import List

from saas.core.helpers import get_timestamp_now

from explorer.geodb import GeometriesDB, GeoZone, GeometryType
from explorer.schemas import ExplorerRuntimeError


def test_add_delete_temp_geometries(wd_path, bdp_source_path):
    # read the features from the input file
    input_path = os.path.join(bdp_source_path, 'city-admin-zones.processed')
    with open(input_path, 'r') as f:
        content = json.load(f)

    geodb_path = os.path.join(wd_path, f'geo_{get_timestamp_now()}.db')
    geodb = GeometriesDB('geodb', geodb_path)
    group_id = geodb.add_temporary_geometries(content['features'])
    assert group_id is not None

    # try to delete a group that doesn't exist
    n = geodb.delete_temporary_geometries('fake_group_id')
    assert n == 0

    # try to delete the group that was just added
    n = geodb.delete_temporary_geometries(group_id)
    assert n == len(content['features'])


def test_import_as_zones(wd_path, bdp_source_path):
    # read the features from the input file
    input_path = os.path.join(bdp_source_path, 'city-admin-zones.processed')
    with open(input_path, 'r') as f:
        content = json.load(f)

    geodb_path = os.path.join(wd_path, f'geo_{get_timestamp_now()}.db')
    geodb = GeometriesDB('geodb', geodb_path)
    group_id = geodb.add_temporary_geometries(content['features'])
    assert group_id is not None

    # try to import with a fake group id
    try:
        geodb.import_geometries_as_zones('fake_group_id')
        assert False
    except ExplorerRuntimeError as e:
        assert e.reason == "Temporary geometry group 'fake_group_id' not found."

    # import with the correct group id
    imported: List[GeoZone] = geodb.import_geometries_as_zones(group_id)
    assert len(imported) == len(content['features'])


def test_import_as_zones_with_pruning(wd_path, bdp_source_path):
    # read the features from the input file
    input_path = os.path.join(bdp_source_path, 'city-admin-zones.processed')
    with open(input_path, 'r') as f:
        content = json.load(f)

    geodb_path = os.path.join(wd_path, f'geo_{get_timestamp_now()}.db')
    geodb = GeometriesDB('geodb', geodb_path, interval=5, expiry=1)  # set aggressive pruning parameters
    group_id = geodb.add_temporary_geometries(content['features'])
    assert group_id is not None

    # try to import with a fake group id
    try:
        geodb.import_geometries_as_zones('fake_group_id')
        assert False
    except ExplorerRuntimeError as e:
        assert e.reason == "Temporary geometry group 'fake_group_id' not found."

    # import with the correct group id
    imported: List[GeoZone] = geodb.import_geometries_as_zones(group_id)
    assert len(imported) == len(content['features'])

    # sleep for some time so pruning is triggered
    time.sleep(10)

    # get all the zones
    zones = geodb.get_zones()
    assert len(imported) == len(zones)


def test_import_as_configurations(wd_path, bdp_source_path):
    geodb_path = os.path.join(wd_path, f'geo_{get_timestamp_now()}.db')
    geodb = GeometriesDB('geodb', geodb_path)

    # read the zone from the input file
    with open(os.path.join(bdp_source_path, 'city-admin-zones.processed'), 'r') as f:
        content = json.load(f)
        group_id = geodb.add_temporary_geometries(content['features'])
        geodb.import_geometries_as_zones(group_id)

    # read the features from the input file
    with open(os.path.join(bdp_source_path, 'land-use.processed'), 'r') as f:
        content = json.load(f)
        group_id0 = geodb.add_temporary_geometries(content['features'])

    # read the features from the input file
    with open(os.path.join(bdp_source_path, 'building-footprints.processed'), 'r') as f:
        content = json.load(f)
        group_id1 = geodb.add_temporary_geometries(content['features'])

    # import with the correct group id
    imported, remaining = geodb.import_geometries_as_zone_configuration({
        GeometryType.landuse: group_id0,
        GeometryType.building: group_id1
    }, 'Default', include_empty_zones=True, produce_results=True)

    assert (len(imported[GeometryType.landuse]) == 120739)
    assert (len(imported[GeometryType.building]) == 110052)
    assert (len(imported[GeometryType.vegetation]) == 0)
    assert (len(imported[GeometryType.landcover]) == 0)

    print('done')
