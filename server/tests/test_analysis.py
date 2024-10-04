import json
import os
import shutil
import time
from typing import Optional

from saas.sdk.base import SDKProcessor, SDKGPPDataObject
from saas.core.helpers import get_timestamp_now

from explorer.analysis.base import AnalysisStatus, Analysis, AnalysisContext
from explorer.analysis.mesoscale_urban_climate import normalise, MesoscaleUrbanClimateAnalysis
from explorer.analysis.microscale_urban_climate import MicroscaleUrbanClimateAnalysis
from explorer.dots.area_of_interest import AreaOfInterest
from explorer.project import DBAnalysisRun, AnalysisContextImpl, make_analysis_id
from explorer.schemas import Scene, AnalysisInfo, AnalysisResult
from explorer.server import EnquireAnalysisResponse
from tests.conftest import DUCT_FOM_REPOSITORY, DUCT_FOM_COMMIT_ID, EXPLORER_DATA_PATH


def helper_upload_and_deploy(node_context, url: str, commit_id: str, proc_path: str, proc_config: str,
                             ssh_profile: str = None) -> SDKProcessor:
    gpp: SDKGPPDataObject = node_context.upload_gpp(url, commit_id, proc_path, proc_config)
    exec_node = node_context.rti()
    proc = gpp.deploy(exec_node, ssh_profile=ssh_profile)
    return proc


def helper_create_analysis_context(wd_path, explorer_server, explorer_project, explorer_proxy, explorer_scene,
                                   explorer_user, node_context, analysis: Analysis, analysis_parameters: dict = None,
                                   aoi_obj_id: str = None) -> AnalysisContext:
    project = explorer_server.get_project(explorer_project.id)

    # create an analysis group
    analysis_parameters = analysis_parameters if analysis_parameters else {}
    group = explorer_proxy.create_analysis_group(explorer_project.id, analysis.name(), 'group name', analysis_parameters)

    # create analysis id and path
    analysis_id = make_analysis_id(group.id, explorer_scene.id, '')
    analysis_path = os.path.join(wd_path, analysis_id)
    os.makedirs(analysis_path, exist_ok=True)

    # create the analysis run record
    with project._session() as session:
        # create db record
        record = DBAnalysisRun(
            id=analysis_id, project_id=explorer_project.id, group_id=group.id, scene_id=explorer_scene.id,
            name=analysis_id, type=analysis.name(), type_label=analysis.label(), username=explorer_user.login,
            t_created=get_timestamp_now(), status='initialised', progress=0,
            checkpoint=AnalysisContextImpl.Checkpoint(name='initialised', args={}).dict(),
            results={}
        )
        session.add(record)
        session.commit()

    context = AnalysisContextImpl(project, analysis_id, aoi_obj_id, node_context, analysis, project._session)
    os.makedirs(context.analysis_path, exist_ok=True)

    return context


def helper_run_analysis(explorer_project, explorer_proxy, analysis_type: str, parameters: dict,
                        scene: Scene) -> (str, str, str):

    # enquire on analysis first before submitting it
    result: EnquireAnalysisResponse = \
        explorer_proxy.enquire_analysis(explorer_project.id, analysis_type, scene.id, parameters)
    print(result)
    assert not result.cached_results_available

    # create an analysis group
    group = explorer_proxy.create_analysis_group(explorer_project.id, analysis_type, 'group name', parameters)
    print(group)

    # submit the analysis
    info: AnalysisInfo = explorer_proxy.submit_analysis(explorer_project.id, group.id, scene.id, 'test')
    print(info)

    while True:
        time.sleep(1)

        info: AnalysisInfo = explorer_proxy.get_analysis(explorer_project.id, info.analysis_id)
        print(f"{info.analysis_id} [{info.status}] -> {info.progress}%")

        if info.status in [AnalysisStatus.CANCELLED.value, AnalysisStatus.FAILED.value,
                           AnalysisStatus.COMPLETED.value]:
            break

    return scene.id, group.id, info.analysis_id


def test_analyse_urban_wind_corridors(wd_path, explorer_project, explorer_proxy, explorer_scene, node_context):
    analysis_type = 'wind-corridor-potential'

    # deploy the UWC processor
    proc = node_context.find_processor_by_id('9536fa1b0fc6b6d7612d648a8435b6085c08872a329d26fb90d8927a1d9876ff')
    if proc is None:
        proc = helper_upload_and_deploy(node_context, DUCT_FOM_REPOSITORY, DUCT_FOM_COMMIT_ID,
                                        "ucm-mva/proc_uwc", "gce-ubuntu-22.04")
        print(f"proc_id (UWC): {proc.descriptor.proc_id}")

    # deploy the UVP processor
    proc = node_context.find_processor_by_id('53229e943b22f2afa34515e68e959116d2512398726ea44aee8e1ccee3d3417b')
    if proc is None:
        proc = helper_upload_and_deploy(node_context, DUCT_FOM_REPOSITORY, DUCT_FOM_COMMIT_ID,
                                        "ucm-mva/proc_uvp", "gce-ubuntu-22.04")

        print(f"proc_id (UVP): {proc.descriptor.proc_id}")

    # create project and run analysis
    parameters = {'spatial_resolution': 600}
    scene_id, group_id, analysis_id = helper_run_analysis(explorer_project, explorer_proxy,
                                                          analysis_type, parameters, explorer_scene)

    # get result
    result: dict = explorer_proxy.get_result(explorer_project.id, analysis_id, 'wind-corridors-ns', {})
    assert result is not None
    print(json.dumps(result))

    # get delta
    result: dict = explorer_proxy.get_result_delta(explorer_project.id, 'wind-corridors-ns',
                                                   analysis_id, analysis_id, {}, {})
    assert result is not None
    print(json.dumps(result))

    # download result
    download_path = os.path.join(wd_path, 'wind-corridors-ns.zip')
    explorer_proxy.export_result(explorer_project.id, analysis_id, 'wind-corridors-ns', {}, download_path)
    assert os.path.isfile(download_path)

    # download delta
    download_path = os.path.join(wd_path, 'wind-corridors-ns-delta.zip')
    explorer_proxy.export_result_delta(explorer_project.id, 'wind-corridors-ns', analysis_id, analysis_id, {}, {},
                                       download_path)
    assert os.path.isfile(download_path)

    # enquire on analysis: cached results should be available now
    result: EnquireAnalysisResponse = \
        explorer_proxy.enquire_analysis(explorer_project.id, analysis_type, scene_id, parameters)
    print(json.dumps(result.dict(), indent=2))
    assert result.cached_results_available

    # delete the analysis
    info: Optional[AnalysisInfo] = explorer_proxy.delete_analysis(explorer_project.id, analysis_id)
    print(result)
    assert info is not None


def test_analyse_mesoscale_urban_climate_normalise(wd_path):
    input_path = os.path.join(EXPLORER_DATA_PATH, 'd04-near-surface-climate')
    output_path = os.path.join(wd_path, 'd04-near-surface-climate_normalised')

    t_table = [20160417001000, 20160417012000, 20160417023000, 20160417034000, 20160417045000, 20160417050000,
               20160417060000, 20160417070000, 20160417080000, 20160417090000, 20160417100000, 20160417110000,
               20160417120000, 20160417130000, 20160417140000, 20160417150000, 20160417160000, 20160417170000,
               20160417180000, 20160417190000, 20160417200000, 20160417210000, 20160417220000, 20160417230000,
               20160418000000, 20160418010000, 20160418020000, 20160418030000, 20160418040000, 20160418050000,
               20160418060000, 20160418070000, 20160418080000, 20160418090000, 20160418100000, 20160418110000,
               20160418120000, 20160418130000, 20160418140000, 20160418150000, 20160418160000, 20160418170000,
               20160418180000]

    # begin POI  -> 2016-04-17 16:00:00 UTC -> t[2]=20160417160000
    # end POI    -> 2016-04-18 16:00:00 UTC -> t[3]=20160418160000
    t_poi = (20160417160000, 20160418160000)

    normalise(input_path, output_path, t_table, t_poi, 8)
    assert True


def test_miuc_prepare_input(wd_path, explorer_server, explorer_project, explorer_proxy, explorer_scene,
                            explorer_user, node_context):
    analysis = MicroscaleUrbanClimateAnalysis()

    # upload area of interest to DOR
    aoi_obj_path = os.path.join(EXPLORER_DATA_PATH, 'aoi.geojson')
    aoi_obj = node_context.upload_content(aoi_obj_path, AreaOfInterest.DATA_TYPE, 'geojson', False)

    # upload some building AH data to DOR
    bld_ah_path = os.path.join(EXPLORER_DATA_PATH, 'bld_ah_profile.csv')
    bld_ah_obj = node_context.upload_content(bld_ah_path, 'duct.building-ah-profile', 'csv', False)

    # create analysis context
    context = helper_create_analysis_context(wd_path, explorer_server, explorer_project, explorer_proxy, explorer_scene,
                                             explorer_user, node_context, analysis, aoi_obj_id=aoi_obj.meta.obj_id)

    location, bbox = analysis._determine_domain(context)
    assert location == (103.73851217742049, 1.3401828018998154)
    assert bbox.west == 103.72988018670357
    assert bbox.north == 1.3488615392842194
    assert bbox.east == 103.74714410739787
    assert bbox.south == 1.331503975344926

    # copy/create areas to wd path
    shutil.copyfile(aoi_obj_path, os.path.join(wd_path, 'aoi.geojson'))
    with open(os.path.join(wd_path, 'domain.geojson'), 'w') as f:
        json.dump({
            'type': 'FeatureCollection',
            'features': [{
                'type': 'Feature',
                'properties': {},
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [[
                        (bbox.west, bbox.south), (bbox.west, bbox.north), (bbox.east, bbox.north),
                        (bbox.east, bbox.south), (bbox.west, bbox.south)
                    ]]
                }
            }]
        }, f, indent=2)

    lc_obj, bld_obj, veg_obj = analysis._prepare_input_data(context, explorer_scene, bbox.as_shapely_polygon(),
                                                            ah_profile_obj_id=bld_ah_obj.meta.obj_id)
    assert lc_obj is not None
    assert bld_obj is not None
    assert veg_obj is not None


def test_meuc_extract_feature(wd_path, explorer_server, explorer_project, node_context):
    project = explorer_server.get_project(explorer_project.id)

    content_paths = {
        '#': os.path.join(EXPLORER_DATA_PATH, 'd04-near-surface-climate')
    }

    result = AnalysisResult.parse_obj({
        'name': '2m_air_temperature',
        'obj_id': {'#': 'None'},
        'specification': {
            'description': 'description',
            'parameters': {
                'type': 'object',
                'properties': {
                    'time': {
                        'type': 'integer',
                        'title': 'Hour of Day (0h - 23h)',
                        'minimum': 0,
                        'multipleOf': 1,
                        'maximum': 23,
                        'default': 0
                    }
                },
                'required': ['time']
            }
        },
        'export_format': 'tiff',
        'extras': {
            'datetime_0h': '20160417120000'
        }
    })
    export_path = os.path.join(wd_path, 'meso.export')
    json_path = os.path.join(wd_path, 'meso.json')
    parameters = {
        'time': 0
    }

    analysis = MesoscaleUrbanClimateAnalysis()
    analysis.extract_feature(content_paths, result, parameters, project, node_context, export_path, json_path)
    assert os.path.isfile(export_path)
    assert os.path.isfile(json_path)


def test_miuc_extract_feature(wd_path, explorer_server, explorer_project, node_context):
    project = explorer_server.get_project(explorer_project.id)

    content_paths = {
        '#': os.path.join(EXPLORER_DATA_PATH, 'ucm-palm-sim-climatic-variables')
    }

    result = AnalysisResult.parse_obj({
        'name': 'air_temperature',
        'obj_id': {'#': 'None'},
        'specification': {
            'description': 'description',
            'parameters': {
                'type': 'object',
                'properties': {
                    'time': {
                        'type': 'integer',
                        'title': 'Hour of Day (0h - 23h)',
                        'minimum': 0,
                        'multipleOf': 1,
                        'maximum': 23,
                        'default': 0
                    }
                },
                'required': ['time']
            }
        },
        'export_format': 'tiff',
        'extras': {
            'datetime_0h': '20200701060000',
            'z_idx': 1
        }
    })
    export_path = os.path.join(wd_path, 'micro.export')
    json_path = os.path.join(wd_path, 'micro.json')
    parameters = {
        'time': 1
    }

    analysis = MicroscaleUrbanClimateAnalysis()
    analysis.extract_feature(content_paths, result, parameters, project, node_context, export_path, json_path)
    assert os.path.isfile(export_path)
    assert os.path.isfile(json_path)
