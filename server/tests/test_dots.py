import json
import os
import shutil
from typing import List, Tuple, Dict

from explorer.analysis.building_energy_efficiency import BuildingEnergyEfficiency
from explorer.dots.area_of_interest import AreaOfInterest
from explorer.dots.dot import UploadPostprocessResult
from explorer.dots.duct_ahprofile import AnthropogenicHeatProfile
from explorer.dots.duct_bemcea import aggregate_ah_data, BuildingAnnualEnergy, BuildingAnnualGeneration, \
    create_system_summary_charts, create_network_map, create_connected_building_map, create_pie_charts, \
    create_network_flow_chart
from explorer.dots.duct_bld_eff_std import BuildingEfficiencyStandard
from explorer.dots.duct_lcz import LocalClimateZoneMap
from explorer.dots.duct_nsc_variables import NearSurfaceClimateVariableRaster, extract_nsc_data, \
    NearSurfaceClimateVariableLinechart
from explorer.dots.duct_urban_geometries import UrbanGeometries
from explorer.geodb import GeometryType
from explorer.renderer.base import hex_color_to_components
from explorer.schemas import ZoneConfiguration
from tests.conftest import EXPLORER_DATA_PATH


def test_geojson_verify():
    input_path = os.path.join(EXPLORER_DATA_PATH, 'aoi.geojson')
    dot = AreaOfInterest()

    result = dot.verify_content(input_path)
    assert result.is_verified


def test_shp_verify():
    input_path = os.path.join(EXPLORER_DATA_PATH, 'aoi.zip')
    dot = AreaOfInterest()

    result = dot.verify_content(input_path)
    assert result.is_verified


def test_upload_postprocess(wd_path, explorer_server, explorer_project):
    input_path0 = os.path.join(EXPLORER_DATA_PATH, 'aoi.zip')
    input_path1 = os.path.join(wd_path, 'uploaded')
    shutil.copy(input_path0, input_path1)
    dot = AreaOfInterest()

    project = explorer_server.get_project(explorer_project.id)
    result: List[Tuple[str, str, UploadPostprocessResult]] = dot.upload_postprocess(project, input_path1)
    print(result)
    assert len(result) == 1


def test_NearSurfaceClimateVariables(wd_path):
    input_path = os.path.join(EXPLORER_DATA_PATH, 'd04-near-surface-climate')
    dot = NearSurfaceClimateVariableRaster()
    datetime_0h = '20160417160000'

    export_path = os.path.join(wd_path, 'feature.tiff')
    export_format = 'tiff'
    parameters = {
        'key': '2m_air_temperature',
        'datetime_0h': datetime_0h,
        'time': 0,
        'no_data': 0,
        'legend_title': 'title',
        'color_schema': [
            {'value': 0, 'color': hex_color_to_components('#ffffff', 0), 'label': '-'},
            {'value': 1, 'color': hex_color_to_components('#dd1111', 192), 'label': 'Urban'},
        ]
    }

    dot.export_feature(input_path, parameters, export_path, export_format)
    assert os.path.isfile(export_path)

    json = dot.extract_feature(input_path, parameters)
    assert json is not None

    export_path = os.path.join(wd_path, 'feature_delta.tiff')
    parameters_delta = {
        'A': {
            'key': '2m_air_temperature',
            'datetime_0h': datetime_0h,
            'time': 0,
        },
        'B': {
            'key': '2m_air_temperature',
            'datetime_0h': datetime_0h,
            'time': 0,
        },
        'common': {
            'no_data': 0,
            'legend_title': 'title',
            'color_schema': None
        }
    }
    dot.export_delta_feature(input_path, input_path, parameters_delta, export_path, export_format)
    assert os.path.isfile(export_path)

    json = dot.extract_delta_feature(input_path, input_path, parameters_delta)
    assert json is not None


def test_DUCTUrbanGeometries_verify():
    dot = UrbanGeometries()

    result = dot.verify_content(os.path.join(EXPLORER_DATA_PATH, 'urban_geometries_shp.zip'))
    print(result.dict())
    assert '49' in result.messages[0].message
    assert 'tree:3' in result.messages[1].message
    assert '1' in result.messages[2].message

    result = dot.verify_content(os.path.join(EXPLORER_DATA_PATH, 'urban_geometries_geojson.zip'))
    print(result.dict())
    assert '49' in result.messages[0].message
    assert 'tree:3' in result.messages[1].message
    assert '1' in result.messages[2].message

    result = dot.verify_content(os.path.join(EXPLORER_DATA_PATH, 'Sengkang_1003.dxf'))
    print(result.dict())
    assert len(result.messages) == 1
    assert '165' in result.messages[0].message
    for expected in ['02:tree', '01:building', '03:landuse']:
        assert expected in result.messages[0].message

    result = dot.verify_content(os.path.join(EXPLORER_DATA_PATH, 'relocatedpark.dxf'))
    print(result.dict())
    assert len(result.messages) == 4
    assert '1' in result.messages[0].message
    assert '3' in result.messages[1].message
    assert '3' in result.messages[2].message
    assert '104' in result.messages[3].message
    for expected in ['building:5', 'relocatedpark:3414']:
        assert expected in result.messages[3].message


def test_DUCTUrbanGeometries_upload_postprocess(wd_path, explorer_server, explorer_project):
    project = explorer_server.get_project(explorer_project.id)
    dot = UrbanGeometries()

    input_path0 = os.path.join(EXPLORER_DATA_PATH, 'urban_geometries_shp.zip')
    input_path1 = os.path.join(wd_path, 'uploaded.zip')
    shutil.copy(input_path0, input_path1)

    result: List[Tuple[str, str, UploadPostprocessResult]] = dot.upload_postprocess(project, input_path1)
    print(result)
    assert len(result) == 3
    assert result[0][2].geo_type == GeometryType.building.value
    assert result[1][2].geo_type == GeometryType.vegetation.value
    assert result[2][2].geo_type == GeometryType.landcover.value

    input_path0 = os.path.join(EXPLORER_DATA_PATH, 'urban_geometries_geojson.zip')
    input_path1 = os.path.join(wd_path, 'uploaded.zip')
    shutil.copy(input_path0, input_path1)

    result: List[Tuple[str, str, UploadPostprocessResult]] = dot.upload_postprocess(project, input_path1)
    print(result)
    assert len(result) == 3
    assert result[0][2].geo_type == GeometryType.building.value
    assert result[1][2].geo_type == GeometryType.vegetation.value
    assert result[2][2].geo_type == GeometryType.landcover.value

    input_path0 = os.path.join(EXPLORER_DATA_PATH, 'relocatedpark.dxf')
    input_path1 = os.path.join(wd_path, 'uploaded.dxf')
    shutil.copy(input_path0, input_path1)

    result: List[Tuple[str, str, UploadPostprocessResult]] = dot.upload_postprocess(project, input_path1)
    print(result)
    assert len(result) == 2
    assert result[0][2].geo_type == GeometryType.vegetation.value
    assert result[1][2].geo_type == GeometryType.landcover.value


def test_DUCTUrbanGeometries_update_preimport(wd_path, explorer_server, explorer_project):
    project = explorer_server.get_project(explorer_project.id)
    dot = UrbanGeometries()

    input_path0 = os.path.join(EXPLORER_DATA_PATH, 'building.geojson')
    input_path1 = os.path.join(wd_path, 'uploaded')
    shutil.copy(input_path0, input_path1)

    # postprocess 'uploaded' data
    result: List[Tuple[str, str, UploadPostprocessResult]] = dot.upload_postprocess(project, input_path1)
    assert result[0][2].geo_type == GeometryType.building.value

    # the client would be using the geometries endpoint to get the GeoJSON features. we simply read the
    # building features directly from the file.
    obj_path = result[0][1]
    with open(obj_path, 'r') as f:
        content = json.load(f)
        buildings = content['features']
    assert(len(buildings) == 1)

    # we need to do some fixing -> set building height and type
    # do some fixing
    editor_config = result[0][2].editor_config
    building_height = 99
    building_type = editor_config['fields'][1]['domain']['codedValues'][0]['code']
    for building in buildings:
        # buildings should need fixing
        properties = building['properties']
        properties['height'] = building_height
        properties['building_type'] = building_type

    # fix the attributes
    result: UploadPostprocessResult = dot.update_preimport(project, result[0][1], {
        'features': buildings
    }, GeometryType.building)
    assert result.geo_type == GeometryType.building.value

    # check if the building has been updated
    with open(obj_path, 'r') as f:
        content = json.load(f)
        buildings = content['features']
        assert(len(buildings) == 1)

        building = buildings[0]
        assert(building['properties']['height'] == building_height)
        assert(building['properties']['building_type'] == building_type)


def test_DUCTUrbanGeometries_upload_update_import(wd_path, explorer_server, explorer_project):
    project = explorer_server.get_project(explorer_project.id)
    dot = UrbanGeometries()

    input_path0 = os.path.join(EXPLORER_DATA_PATH, 'urban_geometries_shp.zip')
    input_path1 = os.path.join(wd_path, 'uploaded.zip')
    shutil.copy(input_path0, input_path1)

    # how many configs do we have?
    zone_id = 317
    configs = project.get_zone_configs(zone_id)
    n0 = len(configs)

    # upload
    is_verified, verification_messages, datasets = project.upload_dataset(input_path1, dot)
    assert is_verified
    assert len(datasets) == 3
    bld_obj_id = datasets[0][0]
    veg_obj_id = datasets[1][0]
    lc_obj_id = datasets[2][0]
    editor_config = datasets[0][2].editor_config

    geometries = project.geometries(GeometryType.building, f"temp:{bld_obj_id}")
    geometries = geometries.content()
    assert geometries is not None
    buildings = geometries['features']
    assert (len(buildings) == 1)

    # we need to do some fixing -> set building height and type
    # do some fixing
    building_height = 99
    building_type = editor_config['fields'][1]['domain']['codedValues'][0]['code']
    for building in buildings:
        # buildings should need fixing
        properties = building['properties']
        properties['height'] = building_height
        properties['building_type'] = building_type

    # update
    result: UploadPostprocessResult = project.update_dataset(bld_obj_id, {
        'features': buildings
    }, GeometryType.building)
    assert result is not None

    # import as zone configuration
    selected_zones = [zone_id]
    result: Dict[int, ZoneConfiguration] = \
        project.add_zone_configs('alt config', selected_zones=selected_zones, datasets={
            GeometryType.building: bld_obj_id,
            GeometryType.vegetation: veg_obj_id,
            GeometryType.landcover: lc_obj_id
        })
    assert len(result) == 1
    assert zone_id in result

    # the number of geometries is not just what was uploaded. they have been merged with the base data for this
    # entire zone.
    assert len(result[zone_id].landcover_ids) == 80 + 40
    assert len(result[zone_id].vegetation_ids) == 49 + 1416
    assert len(result[zone_id].building_ids) == 1 + 57

    # we should have one more configuration now
    configs = project.get_zone_configs(zone_id)
    n1 = len(configs)
    assert n1 == n0 + 1
    config_id = configs[-1].config_id

    # fetch the geometries
    lc_geometries = project.geometries(GeometryType.landcover, set_id=f"zone_config:{zone_id}={config_id}").content()
    veg_geometries = project.geometries(GeometryType.vegetation, set_id=f"zone_config:{zone_id}={config_id}").content()
    bld_geometries = project.geometries(GeometryType.building, set_id=f"zone_config:{zone_id}={config_id}").content()
    assert len(lc_geometries['features']) == 80 + 40
    assert len(veg_geometries['features']) == 49 + 1416
    assert len(bld_geometries['features']) == 1 + 57


def test_problematic_geometries():
    with open(os.path.join(EXPLORER_DATA_PATH, 'problematic_feature.json'), 'r') as f:
        content = f.read()
        feature0 = json.loads(content)

    feature1 = UrbanGeometries.check_feature_geometry(feature0)
    print(feature0['geometry'])
    print(feature1['geometry'])
    assert(feature0['properties'] == feature1['properties'])
    assert(feature0['geometry'] != feature1['geometry'])

    feature2 = UrbanGeometries.check_feature_geometry(feature1)
    print(feature1['geometry'])
    print(feature2['geometry'])
    assert(feature1['properties'] == feature2['properties'])
    assert(feature1['geometry'] == feature2['geometry'])


def test_DUCTLCZMap_verify():
    dot = LocalClimateZoneMap()

    input_path0 = os.path.join(EXPLORER_DATA_PATH, 'lcz-map0.tiff')
    result = dot.verify_content(input_path0)
    assert result.is_verified
    assert len(result.messages) == 0

    input_path1 = os.path.join(EXPLORER_DATA_PATH, 'lcz-map.tiff')
    result = dot.verify_content(input_path1)
    assert result.is_verified
    assert len(result.messages) == 0


def test_DUCTLCZMap_upload_postprocess(wd_path, explorer_server, explorer_project):
    project = explorer_server.get_project(explorer_project.id)

    input_path0 = os.path.join(EXPLORER_DATA_PATH, 'lcz-map0.tiff')
    input_path1 = os.path.join(wd_path, 'uploaded.tiff')
    shutil.copy(input_path0, input_path1)
    dot = LocalClimateZoneMap()

    result: List[Tuple[str, str, UploadPostprocessResult]] = dot.upload_postprocess(project, input_path1)
    print(result)
    assert len(result) == 1
    assert result[0][2].mode == 'skip'


def test_DUCTLCZMap_update_preimport(wd_path, explorer_server, explorer_project):
    project = explorer_server.get_project(explorer_project.id)

    input_path0 = os.path.join(EXPLORER_DATA_PATH, 'lcz-map0.tiff')
    input_path1 = os.path.join(wd_path, 'uploaded.tiff')
    shutil.copy(input_path0, input_path1)
    dot = LocalClimateZoneMap()

    # postprocess 'uploaded' data
    result: List[Tuple[str, str, UploadPostprocessResult]] = dot.upload_postprocess(project, input_path1)

    result: UploadPostprocessResult = dot.update_preimport(project, result[0][1], {}, None)
    assert result.mode == 'skip'


def test_DUCTLCZMap_upload_update_import(wd_path, explorer_server, explorer_project, node_context):
    project = explorer_server.get_project(explorer_project.id)

    input_path0 = os.path.join(EXPLORER_DATA_PATH, 'lcz-map0.tiff')
    input_path1 = os.path.join(wd_path, 'uploaded.tiff')
    shutil.copy(input_path0, input_path1)
    dot = LocalClimateZoneMap()

    # upload
    is_verified, verification_messages, datasets = project.upload_dataset(input_path1, dot)
    assert is_verified
    assert len(datasets) == 1

    obj_id = datasets[0][0]

    result: List[dict] = project.get_dataset(obj_id, node_context)
    assert result is not None
    assert len(result) == 1

    dataset = project.import_dataset(obj_id, node_context, 'My LCZ dataset')
    assert dataset is not None


def test_DUCTNSCVar_extract_data():
    input_path0 = os.path.join(EXPLORER_DATA_PATH, 'd04-near-surface-climate')

    parameters = {
        'key': '2m_air_temperature',
        'datetime_0h': '20160417000000',
        'time': 3,
        'no_data': 999
    }
    bbox, dims, raster = extract_nsc_data(input_path0, parameters)
    assert bbox.dict() == {
        'west': 103.54771423339844, 'north': 1.5313873291015625, 'east': 104.11181640625, 'south': 1.1859970092773438
    }
    assert dims.width == 210
    assert dims.height == 129


def test_DUCTNSCVar_extract_feature_linechart():
    input_path0 = os.path.join(EXPLORER_DATA_PATH, 'd04-near-surface-climate')

    parameters = {
        'legend_title': 'Air Temperature',
        'key': '2m_air_temperature',
        'datetime_0h': '20160417000000',
        'time': 3,
        'no_data': 999
    }

    dot = NearSurfaceClimateVariableLinechart()
    result = dot.extract_feature(input_path0, parameters)
    print(result)


def test_DUCTAHProfile_csv_verify():
    dot = AnthropogenicHeatProfile()

    input_path0 = os.path.join(EXPLORER_DATA_PATH, 'power_baseline_SH_20160201.csv')
    result = dot.verify_content(input_path0)
    assert result.is_verified
    assert len(result.messages) == 0


def test_DUCTAHProfile_geojson_verify():
    dot = AnthropogenicHeatProfile()

    input_path0 = os.path.join(EXPLORER_DATA_PATH, 'power_baseline_SH_20160201.geojson')
    result = dot.verify_content(input_path0)
    assert result.is_verified
    assert len(result.messages) == 0


def test_DUCTAHProfile_geojson_upload_postprocess(wd_path, explorer_server, explorer_project):
    project = explorer_server.get_project(explorer_project.id)

    input_path0 = os.path.join(EXPLORER_DATA_PATH, 'power_baseline_SH_20160201.geojson')
    input_path1 = os.path.join(wd_path, 'uploaded.geojson')
    shutil.copy(input_path0, input_path1)

    dot = AnthropogenicHeatProfile()

    result: List[Tuple[str, str, UploadPostprocessResult]] = dot.upload_postprocess(project, input_path1)
    print(result)
    assert len(result) == 1
    assert result[0][2].mode == 'fix-attr-and-skip'


def test_DUCTAHProfile_geojson_update_preimport(wd_path, explorer_server, explorer_project):
    project = explorer_server.get_project(explorer_project.id)

    input_path0 = os.path.join(EXPLORER_DATA_PATH, 'power_baseline_SH_20160201.geojson')
    input_path1 = os.path.join(wd_path, 'uploaded.geojson')
    shutil.copy(input_path0, input_path1)

    dot = AnthropogenicHeatProfile()

    # postprocess 'uploaded' data
    result: List[Tuple[str, str, UploadPostprocessResult]] = dot.upload_postprocess(project, input_path1)

    result: UploadPostprocessResult = dot.update_preimport(project, result[0][1], {}, None)
    assert result.mode == 'skip'


def test_DUCTAHProfile_geojson_upload_update_import(wd_path, explorer_server, explorer_project, node_context):
    project = explorer_server.get_project(explorer_project.id)

    input_path0 = os.path.join(EXPLORER_DATA_PATH, 'power_baseline_SH_20160201.geojson')
    input_path1 = os.path.join(wd_path, 'uploaded.geojson')
    shutil.copy(input_path0, input_path1)

    dot = AnthropogenicHeatProfile()

    # upload
    is_verified, verification_messages, datasets = project.upload_dataset(input_path1, dot)
    assert is_verified
    assert len(datasets) == 1

    obj_id = datasets[0][0]

    result: List[dict] = project.get_dataset(obj_id, node_context)
    assert result is not None
    assert len(result) == 1

    dataset = project.import_dataset(obj_id, node_context, 'My AH dataset')
    assert dataset is not None


def test_DUCTBldEffStd_verify():
    dot = BuildingEfficiencyStandard()

    input_path0 = os.path.join(EXPLORER_DATA_PATH, 'RES_CONDO_GREEN.csv')
    result = dot.verify_content(input_path0)
    assert result.is_verified
    assert len(result.messages) == 0


def test_DUCTBldEffStd_upload_import(wd_path, explorer_server, explorer_project, node_context):
    project = explorer_server.get_project(explorer_project.id)

    input_path0 = os.path.join(EXPLORER_DATA_PATH, 'RES_CONDO_GREEN.csv')
    input_path1 = os.path.join(wd_path, 'RES_CONDO_GREEN.csv')
    shutil.copy(input_path0, input_path1)
    dot = BuildingEfficiencyStandard()

    # upload
    is_verified, verification_messages, datasets = project.upload_dataset(input_path1, dot)
    assert is_verified
    assert len(datasets) == 1

    obj_id = datasets[0][0]

    result: List[dict] = project.get_dataset(obj_id, node_context)
    assert result is not None
    assert len(result) == 1

    dataset = project.import_dataset(obj_id, node_context, 'My BldEffStd dataset')
    assert dataset is not None

    # test the specification of the analysis
    analysis = BuildingEnergyEfficiency()
    spec = analysis.specification(project, node_context)
    eff_standards = spec.parameters_schema['properties']['efficiency_standards']['properties']
    residential_stds = eff_standards['residential']
    assert len(residential_stds['enum']) == 3
    assert len(residential_stds['enumNames']) == 3


def test_DUCTBuildingAHEmissions_bee_aggregate_ah_data():
    input_path0 = os.path.join(EXPLORER_DATA_PATH, 'bemcea_ah_emissions')
    result = aggregate_ah_data(input_path0)
    assert result is not None


def test_DUCTBuildingAHEmissions_dc_aggregate_ah_data():
    input_path0 = os.path.join(EXPLORER_DATA_PATH, 'dcncea_ah_emissions')
    result = aggregate_ah_data(input_path0)
    assert result is not None


def test_DUCTBuildingAnnualEnergy_extract_feature_energy_consumption():
    bf_path = os.path.join(EXPLORER_DATA_PATH, 'ZHoa2IMv_building.geojson')
    content_path = os.path.join(EXPLORER_DATA_PATH, 'ZHoa2IMv_annual_energy_demand')

    with open(bf_path, 'r') as f:
        building_footprints = json.load(f)

    parameters = {
        'variable': 'energy_consumption',
        'building_footprints': building_footprints
    }

    dot = BuildingAnnualEnergy()
    result = dot.extract_feature(content_path, parameters)
    assert len(result) == 2


def test_DUCTBuildingAnnualEnergy_extract_feature_energy_use_intensity():
    bf_path = os.path.join(EXPLORER_DATA_PATH, 'ZHoa2IMv_building.geojson')
    content_path = os.path.join(EXPLORER_DATA_PATH, 'ZHoa2IMv_annual_energy_demand')

    with open(bf_path, 'r') as f:
        building_footprints = json.load(f)

    parameters = {
        'variable': 'energy_use_intensity',
        'building_footprints': building_footprints
    }

    dot = BuildingAnnualEnergy()
    result = dot.extract_feature(content_path, parameters)
    assert len(result) == 2


def test_DUCTBuildingAnnualEnergy_extract_feature_energy_efficiency_index():
    bf_path = os.path.join(EXPLORER_DATA_PATH, 'ZHoa2IMv_building.geojson')
    content_path = os.path.join(EXPLORER_DATA_PATH, 'ZHoa2IMv_annual_energy_demand')

    with open(bf_path, 'r') as f:
        building_footprints = json.load(f)

    parameters = {
        'variable': 'energy_efficiency_index',
        'building_footprints': building_footprints
    }

    dot = BuildingAnnualEnergy()
    result = dot.extract_feature(content_path, parameters)
    assert len(result) == 2


def test_DUCTBuildingAnnualGeneration_extract_feature_energy_generation():
    bf_path = os.path.join(EXPLORER_DATA_PATH, '6fvbEVCy_building.geojson')
    content_path = os.path.join(EXPLORER_DATA_PATH, '6fvbEVCy_pv_potential')

    with open(bf_path, 'r') as f:
        building_footprints = json.load(f)

    parameters = {
        'variable': 'energy_generation',
        'building_footprints': building_footprints
    }

    dot = BuildingAnnualGeneration()
    result = dot.extract_feature(content_path, parameters)
    assert len(result) == 2


def test_DUCTSupplySystems_create_system_summary_charts():
    supply_systems_path = os.path.join(EXPLORER_DATA_PATH, 'supply_systems')
    with open(supply_systems_path, 'r') as f:
        content = json.load(f)

    result = create_system_summary_charts(content['DCS'], 'DCS_101')
    print(result)
    assert len(result) == 3


def test_DUCTSupplySystems_create_network_map():
    supply_systems_path = os.path.join(EXPLORER_DATA_PATH, 'supply_systems')
    with open(supply_systems_path, 'r') as f:
        content = json.load(f)

    dcs_name = 'DCS_101'
    cluster_name = 'N1005'
    result = create_network_map(content['DCS'][dcs_name][cluster_name]['network'], dcs_name, cluster_name)
    print(result)


def test_DUCTSupplySystems_create_connected_building_map():
    supply_systems_path = os.path.join(EXPLORER_DATA_PATH, 'supply_systems')
    with open(supply_systems_path, 'r') as f:
        content = json.load(f)

    building_footprints_path = os.path.join(EXPLORER_DATA_PATH, 'building2.geojson')
    with open(building_footprints_path, 'r') as f:
        building_footprints = json.load(f)

    dcs_name = 'DCS_101'
    cluster_name = 'N1005'
    network_map = create_network_map(content['DCS'][dcs_name][cluster_name]['network'], dcs_name, cluster_name)
    result = create_connected_building_map(network_map, building_footprints)
    print(result)


def test_DUCTSupplySystems_create_pie_charts():
    supply_systems_path = os.path.join(EXPLORER_DATA_PATH, 'supply_systems')
    with open(supply_systems_path, 'r') as f:
        content = json.load(f)

    dcs_name = 'DCS_101'
    cluster_name = 'N1005'
    result = create_pie_charts(content['DCS'][dcs_name][cluster_name]['structure'])
    print(result)


def test_DUCTSupplySystems_create_network_flow_chart():
    supply_systems_path = os.path.join(EXPLORER_DATA_PATH, 'supply_systems')
    with open(supply_systems_path, 'r') as f:
        content = json.load(f)

    dcs_name = 'DCS_101'
    cluster_name = 'N1005'
    result = create_network_flow_chart(content['DCS'][dcs_name][cluster_name]['structure'])
    print(result)
