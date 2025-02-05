import json
import os

from explorer.dots.duct_ahprofile import AnthropogenicHeatProfile
from explorer.dots.duct_lcz import LocalClimateZoneMap
from explorer.module.ah_module import heatmap_traffic, raster_to_geojson, export_traffic, heatmap_power, export_power, \
    heatmap_others, export_others, AnthropogenicHeatModule
from explorer.module.vegetation_fraction_module import VegetationFractionModule, _make_marks
from tests.conftest import EXPLORER_DATA_PATH


def test_vf_mixer(wd_path, explorer_server, explorer_project, explorer_user, node_context):
    # get mixer
    project = explorer_server.get_project(explorer_project.id)
    mixer = project.vf_mixer

    # update the mixer with a specific LCZ map
    lcz_path = os.path.join(EXPLORER_DATA_PATH, 'lcz-map.tiff')
    lcz_obj = node_context.upload_content(lcz_path, LocalClimateZoneMap.DATA_TYPE, 'tiff', False, False)
    mixer.update_lcz(lcz_obj.meta.obj_id, node_context)

    module_settings = {
        'landuse-landcover': {
            'lcz_obj_id': lcz_obj.meta.obj_id
        },
        'vegetation-fraction': {
            f'p_lcz{i + 1}': VegetationFractionModule.vf_defaults[i] for i in range(10)
        }
    }

    # export the LCZ and VF maps
    lcz_export_path = os.path.join(wd_path, 'lcz.export.tiff')
    vf_export_path = os.path.join(wd_path, 'vf.export.tiff')
    mixer.export_lcz_and_vf(module_settings, lcz_export_path, vf_export_path, node_context)
    assert os.path.isfile(lcz_export_path)
    assert os.path.isfile(vf_export_path)

    result = mixer.raster_lcz()
    assert result is not None
    assert result['type'] == 'heatmap'

    result = mixer.raster_vf(module_settings['vegetation-fraction'])
    assert result is not None
    assert result['type'] == 'heatmap'

    result = explorer_server.get_module_raster(explorer_project.id, 'vegetation-fraction',
                                               parameters=json.dumps({'module_settings': module_settings}),
                                               user=explorer_user)
    assert result is not None
    assert len(result) == 1
    assert result[0]['type'] == 'heatmap'


def test_veg_frac_mod_make_marks():
    for i in range(10):
        v_default = VegetationFractionModule.vf_defaults[i]
        v_max = VegetationFractionModule.vf_defaults[i] + 10 if i < (7 - 1) else VegetationFractionModule.vf_defaults[i]  # default is max for LCZ7-10
        marks = _make_marks(v_default, v_max)
        print(marks)


def test_heatmap_traffic(wd_path, explorer_server, explorer_project, node_context):
    project = explorer_server.get_project(explorer_project.id)

    t = 7
    for p_ev in [0.0, 0.5, 1.0]:
        raster = heatmap_traffic(p_ev, t, project, node_context)
        result = raster_to_geojson(raster, project, "Traffic AH Emissions")

        path = os.path.join(wd_path, f'test_traffic_{p_ev*100}_{t}h.geojson')
        with open(path, 'w') as f:
            json.dump(result['geojson'], f)

        path = os.path.join(wd_path, f'test_traffic_{p_ev*100}_export.geojson')
        export_traffic(p_ev, path, project, node_context)
        assert os.path.isfile(path)


def test_heatmap_power(wd_path, explorer_server, explorer_project, node_context):
    project = explorer_server.get_project(explorer_project.id)

    t = 7
    base_demand = 48623  # [GWh]
    ev100_demand = 2300  # [GWh]
    p_demand = 0.5
    renewables = 0
    imports = 0
    for p_ev in [0.0, 0.5, 1.0]:
        raster = heatmap_power(base_demand, ev100_demand, p_ev, p_demand, renewables, imports, t, project, node_context)
        result = raster_to_geojson(raster, project, "Power Plant AH Emissions")

        path = os.path.join(wd_path, f'test_power_{p_ev*100}_{t}h.geojson')
        with open(path, 'w') as f:
            json.dump(result['geojson'], f)

        sh_path = os.path.join(wd_path, f'test_power_{p_ev*100}_export_sh.geojson')
        lh_path = os.path.join(wd_path, f'test_power_{p_ev*100}_export_lh.geojson')
        export_power(
            base_demand, ev100_demand, p_ev, p_demand, renewables, imports, sh_path, lh_path, project, node_context
        )
        assert os.path.isfile(sh_path)
        assert os.path.isfile(lh_path)


def test_heatmap_others(wd_path, explorer_server, explorer_project, node_context):
    project = explorer_server.get_project(explorer_project.id)

    ohe_path = os.path.join(EXPLORER_DATA_PATH, 'industry_baseline_SH.geojson')
    ohe = node_context.upload_content(ohe_path, AnthropogenicHeatProfile.DATA_TYPE, 'geojson', False)

    t = 7
    raster = heatmap_others(ohe.meta.obj_id, t, project, node_context)
    result = raster_to_geojson(raster, project, "Other AH Emissions")

    path = os.path.join(wd_path, f'test_ohe_{t}h.geojson')
    with open(path, 'w') as f:
        json.dump(result['geojson'], f)

    sh_path = os.path.join(wd_path, f'test_ohe_export_sh.geojson')
    lh_path = os.path.join(wd_path, f'test_ohe_export_lh.geojson')
    export_others(ohe.meta.obj_id, sh_path, lh_path, project, node_context)
    assert os.path.isfile(sh_path)
    assert os.path.isfile(lh_path)


def test_raster(explorer_server, explorer_project, node_context):
    project = explorer_server.get_project(explorer_project.id)
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

    result = module.raster_image(project, parameters, node_context)
    assert len(result) == 2
    assert result is not None

    parameters['module_settings'][module.name()]["time"] = 5

    result = module.raster_image(project, parameters, node_context)
    assert len(result) == 2
    assert result is not None
