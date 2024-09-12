import json
import logging
import os
import shutil
import unittest

from saas.core.keystore import Keystore
from saas.sdk.base import connect
from tests.base_testcase import create_wd

from saas.core.logging import Logging

from duct.dots.duct_ahprofile import AnthropogenicHeatProfile
from duct.modules.ah_module import heatmap_traffic, heatmap_power, heatmap_others, AnthropogenicHeatModule, \
    raster_to_geojson, export_traffic, export_power, export_others
from explorer.project import Project
from explorer.schemas import ProjectInfo, BaseDataPackage, BoundingBox, Dimensions, ProjectMeta

Logging.initialise(logging.INFO)
logger = Logging.get(__name__, level=logging.DEBUG)

nextcloud_path = os.path.join(os.environ['HOME'], 'Nextcloud', 'DT-Lab', 'Testing')


class DUCTAHModuleTestCase(unittest.TestCase):
    _node_address = ("127.0.0.1", 5001)

    def setUp(self):
        self._objects = []
        self._wd_path = create_wd()

        # upload data objects (if necessary)
        ah_ev0_path = os.path.join(nextcloud_path, 'ah_vf_mixer', 'traffic_baseline_SH.geojson')
        ah_ev1_path = os.path.join(nextcloud_path, 'ah_vf_mixer', 'traffic_ev100_SH.geojson')
        sh_power_path = os.path.join(nextcloud_path, 'ah_vf_mixer', 'power_baseline_SH_20160201.geojson')
        lh_power_path = os.path.join(nextcloud_path, 'ah_vf_mixer', 'power_baseline_LH_20160201.geojson')
        keystore = Keystore.create(self._wd_path, 'name', 'email', 'password')
        self._context = connect(self._node_address, keystore)
        ah_ev0 = self._context.upload_content(ah_ev0_path, AnthropogenicHeatProfile.DATA_TYPE, 'geojson', False)
        ah_ev1 = self._context.upload_content(ah_ev1_path, AnthropogenicHeatProfile.DATA_TYPE, 'geojson', False)
        sh_power = self._context.upload_content(sh_power_path, AnthropogenicHeatProfile.DATA_TYPE, 'geojson', False)
        lh_power = self._context.upload_content(lh_power_path, AnthropogenicHeatProfile.DATA_TYPE, 'geojson', False)
        self._objects.extend([ah_ev0, ah_ev1, sh_power, lh_power])

        # create a fake project
        owner = 'owner'
        bounding_box = BoundingBox(west=103.55161, north=1.53428, east=104.14966, south=1.19921)
        meta = ProjectMeta(
            id='prj_id',
            name='name of project',
            state='initialised',
            bounding_box=bounding_box
        )
        bdp = BaseDataPackage(
            name='bdp',
            city_name='city',
            bounding_box=bounding_box,
            grid_dimension=Dimensions(width=210, height=129),
            timezone='Asia/Singapore',
            references={
                'sh-traffic-baseline': ah_ev0.meta.obj_id,
                'sh-traffic-ev100': ah_ev1.meta.obj_id,
                'sh-power-baseline': sh_power.meta.obj_id,
                'lh-power-baseline': lh_power.meta.obj_id
            }
        )
        info = ProjectInfo(
            meta=meta,
            users=[owner],
            owner=owner,
            folder=self._wd_path,
            bdp=bdp,
            bld_footprints_by_hash={},
            datasets={}
        )
        self._project = Project(None, info)

    def tearDown(self):
        # try to delete objects we created to reduce the spam in the DOR
        for obj in self._objects:
            try:
                obj.delete()
            except Exception:
                pass

        shutil.rmtree(self._wd_path, ignore_errors=True)

    def test_heatmap_traffic(self):
        t = 7
        for p_ev in [0.0, 0.5, 1.0]:
            raster = heatmap_traffic(p_ev, t, self._project, self._context)
            result = raster_to_geojson(raster, self._project, "Traffic AH Emissions")

            path = os.path.join(self._wd_path, f'test_traffic_{p_ev*100}_{t}h.geojson')
            with open(path, 'w') as f:
                json.dump(result['geojson'], f)

            path = os.path.join(self._wd_path, f'test_traffic_{p_ev*100}_export.geojson')
            export_traffic(p_ev, path ,self._project, self._context)

    def test_heatmap_power(self):
        t = 7
        base_demand = 48623  # [GWh]
        ev100_demand = 2300  # [GWh]
        p_demand = 0.5
        renewables = 0
        imports = 0
        for p_ev in [0.0, 0.5, 1.0]:
            raster = heatmap_power(base_demand, ev100_demand, p_ev, p_demand, renewables, imports, t, self._project, self._context)
            result = raster_to_geojson(raster, self._project, "Power Plant AH Emissions")

            path = os.path.join(self._wd_path, f'test_power_{p_ev*100}_{t}h.geojson')
            with open(path, 'w') as f:
                json.dump(result['geojson'], f)

            sh_path = os.path.join(self._wd_path, f'test_power_{p_ev*100}_export_sh.geojson')
            lh_path = os.path.join(self._wd_path, f'test_power_{p_ev*100}_export_lh.geojson')
            export_power(base_demand, ev100_demand, p_ev, p_demand, renewables, imports, sh_path, lh_path, self._project, self._context)

    def test_heatmap_others(self):
        ohe_path = os.path.join(nextcloud_path, 'ah_vf_mixer', 'industry_baseline_SH.geojson')
        ohe = self._context.upload_content(ohe_path, AnthropogenicHeatProfile.DATA_TYPE, 'geojson', False)
        self._objects.append(ohe)

        t = 7
        raster = heatmap_others(ohe.meta.obj_id, t, self._project, self._context)
        result = raster_to_geojson(raster, self._project, "Other AH Emissions")

        path = os.path.join(self._wd_path, f'test_ohe_{t}h.geojson')
        with open(path, 'w') as f:
            json.dump(result['geojson'], f)

        sh_path = os.path.join(self._wd_path, f'test_ohe_export_sh.geojson')
        lh_path = os.path.join(self._wd_path, f'test_ohe_export_lh.geojson')
        export_others(ohe.meta.obj_id, sh_path, lh_path, self._project, self._context)

    def test_raster(self):
        module = AnthropogenicHeatModule()

        parameters = {
            'module_settings': {
                module.name(): {
                    "demand_chart": {},
                    "base_demand": 48623,
                    "ev100_demand": 2300,
                    "p_ev": 0,
                    "p_demand": 0,
                    "renewables": 0,
                    "imports": 0,
                    'others': '',
                    "time": 0
                }
            }
        }

        result = module.raster_image(self._project, parameters, self._context)
        assert len(result) == 2
        assert result is not None

        parameters['module_settings'][module.name()]["time"] = 5

        result = module.raster_image(self._project, parameters, self._context)
        assert len(result) == 2
        assert result is not None


if __name__ == '__main__':
    unittest.main()
