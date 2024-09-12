import logging
import os
import unittest

from saas.core.keystore import Keystore
from saas.core.logging import Logging
from saas.sdk.base import connect
from tests.base_testcase import create_wd

from duct.bdp import DUCTBaseDataPackageDB
from duct.dots.duct_ahprofile import AnthropogenicHeatProfile
from duct.dots.duct_lcz import LocalClimateZoneMap
from explorer.schemas import BoundingBox, Dimensions, BaseDataPackage
from infrares.bdp import InfrariskBaseDataPackageDB, PCNBaseDataPackageDB, YesenBaseDataPackageDB

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

    def test_bdp_create_infrarisk(self):
        # upload BDP
        bdp = BaseDataPackage.upload(
            self._context, 'Shelby County', 'Public Dataset (test)',
            BoundingBox(west=-90.3107227531639296, north=35.4107553234207444,
                        east=-89.6335486721696384, south=34.9930824603582096),

            # width=61.37km, height=46.44km -> assume 100m resolution -> grid=613x464
            Dimensions(width=613, height=464),

            # for timezone, lookup Memphis which is the biggest city in Shelby county here: https://time.is/Memphis
            'America/Chicago',
            {
                'city-admin-zones': {
                    # source for v1: https://github.com/OpenDataDE/State-zip-code-GeoJSON/blob/master/tn_tennessee_zip_codes_geo.min.json
                    'path': os.path.join(nextcloud_path, 'bdp_files', 'bdp-infrarisk', 'city-admin-zones-v1'),
                    'type': 'DUCT.GeoVectorData',
                    'format': 'geojson'
                },
                'population-data': {
                    'path': os.path.join(nextcloud_path, 'bdp_files', 'bdp-infrarisk', 'population-data'),
                    'type': 'infrarisk.PopulationData',
                    'format': 'csv'
                },
                'network-data': {
                    'path': os.path.join(nextcloud_path, 'bdp_files', 'bdp-infrarisk', 'network-data'),
                    'type': 'infrarisk.NetworkData',
                    'format': 'Package[tar.gz]'
                },
                'se-data': {
                    'path': os.path.join(nextcloud_path, 'bdp_files', 'bdp-infrarisk', 'se-data'),
                    'type': 'infrarisk.SocioEconomicData',
                    'format': 'Package[tar.gz]'
                },
                'scenario-data': {
                    'path': os.path.join(nextcloud_path, 'bdp_files', 'bdp-infrarisk', 'scenario-data-from_scene'),
                    'type': 'infrarisk.ScenarioData',
                    'format': 'Package[tar.gz]'
                }
            }
        )

        paths = InfrariskBaseDataPackageDB.create(bdps_path, bdp, self._context)
        assert paths is not None
        assert os.path.isfile(paths[0])
        assert os.path.isfile(paths[1])
        assert '11c2032a97e5ead2d4f2970cf7ae5abc70adabf8adef92d0f4eb3baa44defdcb' in paths[0]
        assert '11c2032a97e5ead2d4f2970cf7ae5abc70adabf8adef92d0f4eb3baa44defdcb' in paths[1]

    def test_bdp_create_pcn(self):
        # upload BDP
        bdp = BaseDataPackage.upload(
            self._context, 'Singapore', 'Public Dataset (PCN)',
            BoundingBox(west=103.55161, north=1.53428, east=104.14966, south=1.19921),
            Dimensions(width=211, height=130),
            'Asia/Singapore',
            {
                'city-admin-zones': {
                    'path': os.path.join(nextcloud_path, 'bdp_files', 'bdp-pcn', 'city-admin-zones'),
                    'type': 'DUCT.GeoVectorData',
                    'format': 'geojson'
                },
                'building-footprints': {
                    'path': os.path.join(nextcloud_path, 'bdp_files', 'bdp-pcn', 'building-footprints'),
                    'type': 'DUCT.GeoVectorData',
                    'format': 'geojson'
                },
                'land-use': {
                    'path': os.path.join(nextcloud_path, 'bdp_files', 'bdp-pcn', 'land-use'),
                    'type': 'DUCT.GeoVectorData',
                    'format': 'geojson'
                },
                'network-data': {
                    'path': os.path.join(nextcloud_path, 'bdp_files', 'bdp-pcn', 'network-data'),
                    'type': 'pcn.NetworkData',
                    'format': 'geojson'
                }
            }
        )

        paths = PCNBaseDataPackageDB.create(bdps_path, bdp, self._context)
        assert paths is not None
        assert os.path.isfile(paths[0])
        assert os.path.isfile(paths[1])
        assert 'd5f4c26d003876539a43a97066a625d3d171a2f8c197a9a991c7768a5b5b0102' in paths[0]
        assert 'd5f4c26d003876539a43a97066a625d3d171a2f8c197a9a991c7768a5b5b0102' in paths[1]

    def test_bdp_create_yesen(self):
        # upload BDP
        bdp = BaseDataPackage.upload(
            self._context, 'Singapore', 'Yesen+ Dataset',
            BoundingBox(west=103.55161, north=1.53428, east=104.14966, south=1.19921),
            Dimensions(width=211, height=130),
            'Asia/Singapore',
            {
                'city-admin-zones': {
                    'path': os.path.join(nextcloud_path, 'bdp_files', 'bdp-yesen', 'city-admin-zones'),
                    'type': 'DUCT.GeoVectorData',
                    'format': 'geojson'
                },
                'building-footprints': {
                    'path': os.path.join(nextcloud_path, 'bdp_files', 'bdp-yesen', 'building-footprints'),
                    'type': 'DUCT.GeoVectorData',
                    'format': 'geojson'
                },
                'land-use': {
                    'path': os.path.join(nextcloud_path, 'bdp_files', 'bdp-yesen', 'land-use'),
                    'type': 'DUCT.GeoVectorData',
                    'format': 'geojson'
                },
                'network-data': {
                    'path': os.path.join(nextcloud_path, 'bdp_files', 'bdp-yesen', 'network-data'),
                    'type': 'yesen.NetworkData',
                    'format': 'Package[tar.gz]'
                }
            }
        )

        paths = YesenBaseDataPackageDB.create(bdps_path, bdp, self._context)
        assert paths is not None
        assert os.path.isfile(paths[0])
        assert os.path.isfile(paths[1])
        assert 'cc364137dc83e282b18f90a5e873fe1ccff858c4a06f782560624b19c64d75e0' in paths[0]
        assert 'cc364137dc83e282b18f90a5e873fe1ccff858c4a06f782560624b19c64d75e0' in paths[1]


if __name__ == '__main__':
    unittest.main()
