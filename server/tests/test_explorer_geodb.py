import json
import logging
import os
import shutil
import time
import unittest
from typing import List

from saas.core.logging import Logging
from tests.base_testcase import create_wd

from explorer.geodb import GeometriesDB, GeoZone, GeometryType
from explorer.schemas import ExplorerRuntimeError

Logging.initialise(logging.INFO)
logger = Logging.get(__name__, level=logging.DEBUG)

nextcloud_path = os.path.join(os.environ['HOME'], 'Nextcloud', 'DT-Lab', 'Testing')


class GeoDBTestCase(unittest.TestCase):
    def setUp(self):
        self._wd_path = create_wd()

    def tearDown(self):
        shutil.rmtree(self._wd_path, ignore_errors=True)

    def test_add_delete_temp_geometries(self):
        # read the features from the input file
        input_path = os.path.join(nextcloud_path, 'bdp_files', 'bdp-duct', 'city-admin-zones.processed')
        with open(input_path, 'r') as f:
            content = json.load(f)

        geodb_path = os.path.join(self._wd_path, 'geo.db')
        geodb = GeometriesDB('geodb', geodb_path)
        group_id = geodb.add_temporary_geometries(content['features'])
        assert(group_id is not None)

        # try to delete a group that doesn't exist
        n = geodb.delete_temporary_geometries('fake_group_id')
        assert(n == 0)

        # try to delete the group that was just added
        n = geodb.delete_temporary_geometries(group_id)
        assert(n == len(content['features']))

    def test_import_as_zones(self):
        # read the features from the input file
        input_path = os.path.join(nextcloud_path, 'bdp_files', 'bdp-duct', 'city-admin-zones.processed')
        with open(input_path, 'r') as f:
            content = json.load(f)

        geodb_path = os.path.join(self._wd_path, 'geo.db')
        geodb = GeometriesDB('geodb', geodb_path)
        group_id = geodb.add_temporary_geometries(content['features'])
        assert(group_id is not None)

        # try to import with a fake group id
        try:
            geodb.import_geometries_as_zones('fake_group_id')
            assert False
        except ExplorerRuntimeError as e:
            assert e.reason == "Temporary geometry group 'fake_group_id' not found."

        # import with the correct group id
        imported: List[GeoZone] = geodb.import_geometries_as_zones(group_id)
        assert(len(imported) == len(content['features']))

    def test_import_as_zones_with_pruning(self):
        # read the features from the input file
        input_path = os.path.join(nextcloud_path, 'bdp_files', 'bdp-duct', 'city-admin-zones.processed')
        with open(input_path, 'r') as f:
            content = json.load(f)

        geodb_path = os.path.join(self._wd_path, 'geo.db')
        geodb = GeometriesDB('geodb', geodb_path, interval=5, expiry=1)  # set aggressive pruning parameters
        group_id = geodb.add_temporary_geometries(content['features'])
        assert(group_id is not None)

        # try to import with a fake group id
        try:
            geodb.import_geometries_as_zones('fake_group_id')
            assert False
        except ExplorerRuntimeError as e:
            assert e.reason == "Temporary geometry group 'fake_group_id' not found."

        # import with the correct group id
        imported: List[GeoZone] = geodb.import_geometries_as_zones(group_id)
        assert(len(imported) == len(content['features']))

        # sleep for some time so pruning is triggered
        time.sleep(10)

        # get all the zones
        zones = geodb.get_zones()
        assert(len(imported) == len(zones))

    def test_import_as_configurations(self):
        geodb_path = os.path.join(self._wd_path, 'geo.db')
        geodb = GeometriesDB('geodb', geodb_path)

        # read the zone from the input file
        with open(os.path.join(nextcloud_path, 'bdp_files', 'bdp-duct', 'city-admin-zones.processed'), 'r') as f:
            content = json.load(f)
            group_id = geodb.add_temporary_geometries(content['features'])
            geodb.import_geometries_as_zones(group_id)

        # read the features from the input file
        with open(os.path.join(nextcloud_path, 'bdp_files', 'bdp-duct', 'land-use.processed'), 'r') as f:
            content = json.load(f)
            group_id0 = geodb.add_temporary_geometries(content['features'])

        # read the features from the input file
        with open(os.path.join(nextcloud_path, 'bdp_files', 'bdp-duct', 'building-footprints.processed'), 'r') as f:
            content = json.load(f)
            group_id1 = geodb.add_temporary_geometries(content['features'])

        # import with the correct group id
        imported, remaining = geodb.import_geometries_as_zone_configuration({
            GeometryType.landuse: group_id0,
            GeometryType.building: group_id1
        }, 'Default', include_empty_zones=True, produce_results=True)

        assert(len(imported[GeometryType.landuse]) == 120739)
        assert(len(imported[GeometryType.building]) == 110052)
        assert(len(imported[GeometryType.vegetation]) == 0)
        assert(len(imported[GeometryType.landcover]) == 0)

        print('done')


if __name__ == '__main__':
    unittest.main()
