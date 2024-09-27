import logging
import os
import unittest

from saas.core.keystore import Keystore
from saas.core.logging import Logging
from saas.sdk.base import connect
from tests.base_testcase import create_wd

from explorer.bdp.bdp import DUCTBaseDataPackageDB
from explorer.dots.duct_ahprofile import AnthropogenicHeatProfile
from explorer.dots.duct_lcz import LocalClimateZoneMap
from explorer.schemas import BoundingBox, Dimensions, BaseDataPackage

Logging.initialise(logging.INFO)
logger = Logging.get(__name__, level=logging.DEBUG)

nextcloud_path = os.path.join(os.environ['HOME'], 'Nextcloud', 'DT-Lab', 'Testing')
bdps_path = os.path.join(nextcloud_path, 'base_data_packages')

bdp_source_path = os.path.join(os.environ['HOME'], 'Desktop')


class BDPTestCase(unittest.TestCase):
    _wd_path = None
    _keystore = None
    _node_address = ('127.0.0.1', 5001)
    _context = None

    @classmethod
    def setUpClass(cls):
        cls._wd_path = create_wd()
        cls._keystore = Keystore.create(cls._wd_path, 'name', 'email', 'password')
        cls._context = connect(cls._node_address, cls._keystore)

    @classmethod
    def tearDownClass(cls):
        pass

    def test_bdp_create_duct(self):
        caz_processed_path = os.path.join(bdp_source_path, 'bdp-duct2', 'city-admin-zones.processed')
        luz_processed_path = os.path.join(bdp_source_path, 'bdp-duct2', 'land-use.processed')
        lc_processed_path = os.path.join(bdp_source_path, 'bdp-duct2', 'land-cover.processed')
        bld_processed_path = os.path.join(bdp_source_path, 'bdp-duct2', 'building-footprints.processed')
        veg_processed_path = os.path.join(bdp_source_path, 'bdp-duct2', 'vegetation.processed')
        need_to_prepare = not (os.path.isfile(caz_processed_path) and os.path.isfile(luz_processed_path) and
                               os.path.isfile(bld_processed_path) and os.path.isfile(veg_processed_path) and
                               os.path.isfile(lc_processed_path))

        # prepare files
        if need_to_prepare:
            mapping = DUCTBaseDataPackageDB.prepare_files({
                'city-admin-zones': {
                    'path': os.path.join(bdp_source_path, 'bdp-duct2', 'city-admin-zones'),
                    'type': 'DUCT.GeoVectorData',
                    'format': 'geojson'
                },
                'land-use': {
                    'path': os.path.join(bdp_source_path, 'bdp-duct2', 'land-use'),
                    'type': 'DUCT.GeoVectorData',
                    'format': 'geojson'
                },
                'building-footprints': {
                    'path': os.path.join(bdp_source_path, 'bdp-duct2', 'building-footprints'),
                    'type': 'DUCT.GeoVectorData',
                    'format': 'geojson'
                },
                'vegetation': {
                    'path': os.path.join(bdp_source_path, 'bdp-duct2', 'vegetation'),
                    'type': 'DUCT.GeoVectorData',
                    'format': 'geojson'
                },
                # land-cover will be derived from land-use (as a workaround for lack of actual data)
                'lcz-baseline': {
                    'path': os.path.join(bdp_source_path, 'bdp-duct2', 'lcz-baseline'),
                    'type': LocalClimateZoneMap.DATA_TYPE,
                    'format': 'tiff'
                },
                'sh-traffic-baseline': {
                    'path': os.path.join(bdp_source_path, 'bdp-duct2', 'sh-traffic-baseline'),
                    'type': AnthropogenicHeatProfile.DATA_TYPE,
                    'format': 'geojson'
                },
                'sh-traffic-ev100': {
                    'path': os.path.join(bdp_source_path, 'bdp-duct2', 'sh-traffic-ev100'),
                    'type': AnthropogenicHeatProfile.DATA_TYPE,
                    'format': 'geojson'
                },
                'sh-power-baseline': {
                    'path': os.path.join(bdp_source_path, 'bdp-duct2', 'sh-power-baseline'),
                    'type': AnthropogenicHeatProfile.DATA_TYPE,
                    'format': 'geojson'
                },
                'lh-power-baseline': {
                    'path': os.path.join(bdp_source_path, 'bdp-duct2', 'lh-power-baseline'),
                    'type': AnthropogenicHeatProfile.DATA_TYPE,
                    'format': 'geojson'
                },
                'description': {
                    'path': os.path.join(bdp_source_path, 'bdp-duct2', 'description'),
                    'type': 'BDPDescription',
                    'format': 'markdown'
                }
            })
        else:
            mapping = {
                'city-admin-zones': {
                    'path': caz_processed_path,
                    'type': 'DUCT.GeoVectorData',
                    'format': 'geojson'
                },
                'land-use': {
                    'path': luz_processed_path,
                    'type': 'DUCT.GeoVectorData',
                    'format': 'geojson'
                },
                'building-footprints': {
                    'path': bld_processed_path,
                    'type': 'DUCT.GeoVectorData',
                    'format': 'geojson'
                },
                'vegetation': {
                    'path': veg_processed_path,
                    'type': 'DUCT.GeoVectorData',
                    'format': 'geojson'
                },
                'land-cover': {
                    'path': lc_processed_path,
                    'type': 'DUCT.GeoVectorData',
                    'format': 'geojson'
                },
                'lcz-baseline': {
                    'path': os.path.join(bdp_source_path, 'bdp-duct2', 'lcz-baseline'),
                    'type': LocalClimateZoneMap.DATA_TYPE,
                    'format': 'tiff'
                },
                'sh-traffic-baseline': {
                    'path': os.path.join(bdp_source_path, 'bdp-duct2', 'sh-traffic-baseline'),
                    'type': AnthropogenicHeatProfile.DATA_TYPE,
                    'format': 'geojson'
                },
                'sh-traffic-ev100': {
                    'path': os.path.join(bdp_source_path, 'bdp-duct2', 'sh-traffic-ev100'),
                    'type': AnthropogenicHeatProfile.DATA_TYPE,
                    'format': 'geojson'
                },
                'sh-power-baseline': {
                    'path': os.path.join(bdp_source_path, 'bdp-duct2', 'sh-power-baseline'),
                    'type': AnthropogenicHeatProfile.DATA_TYPE,
                    'format': 'geojson'
                },
                'lh-power-baseline': {
                    'path': os.path.join(bdp_source_path, 'bdp-duct2', 'lh-power-baseline'),
                    'type': AnthropogenicHeatProfile.DATA_TYPE,
                    'format': 'geojson'
                },
                'description': {
                    'path': os.path.join(bdp_source_path, 'bdp-duct2', 'description'),
                    'type': 'BDPDescription',
                    'format': 'markdown'
                }
            }

        # upload BDP
        bdp = BaseDataPackage.upload(
            self._context, 'Singapore', 'Public Dataset (test)',
            BoundingBox(west=103.55161, north=1.53428, east=104.14966, south=1.19921),
            Dimensions(width=211, height=130), 'Asia/Singapore', mapping
        )

        # create the BDP
        paths = DUCTBaseDataPackageDB.create(bdps_path, bdp, self._context)
        assert paths is not None
        assert os.path.isfile(paths[0])
        assert os.path.isfile(paths[1])
        assert '4fc2e31f6864f856db6c24463a98b4e93954bc97d89e807d702a0343507b35d4' in paths[0]
        assert '4fc2e31f6864f856db6c24463a98b4e93954bc97d89e807d702a0343507b35d4' in paths[1]


if __name__ == '__main__':
    unittest.main()
