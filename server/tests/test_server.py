import json
import os
import time
from typing import List, Dict

import geojson

from saas.rest.exceptions import UnsuccessfulRequestError
from saas.core.helpers import get_timestamp_now

from explorer.dots.area_of_interest import AreaOfInterest
from explorer.dots.duct_urban_geometries import UrbanGeometries
from explorer.geodb import GeometryType
from explorer.project import AnalysisContextImpl
from explorer.schemas import ExplorerDatasetInfo, ZoneConfiguration, ZonesConfigurationMapping, Scene, AnalysisGroup
from explorer.server import FetchDatasetsResponse, UploadDatasetResponse
from tests.conftest import EXPLORER_DATA_PATH


def extract_geojson(input_path: str, output_path: str = None) -> dict:
    assert (os.path.isfile(input_path))
    with open(input_path, 'r') as f1:
        content = json.load(f1)
        content = content['geojson']
    output_path = output_path if output_path else input_path
    with open(output_path, 'w') as f2:
        f2.write(json.dumps(content))
    return content['features']


def test_get_info(explorer_proxy, explorer_project):
    results = explorer_proxy.public_info()
    assert (results is not None)
    results = results.dict()
    print(results)

    results = explorer_proxy.info()
    assert (results is not None)
    results = results.dict()
    print(results)

    results = explorer_proxy.get_info_analyses(explorer_project.id, scale='meso', aoi_obj_id='0x123', scene_id='0x456')
    assert (results is not None)
    print(results)

    results = explorer_proxy.get_info_scene(explorer_project.id)
    assert (results is not None)
    results = [result.dict() for result in results]
    print(results)


def test_get_geometries(wd_path, explorer_proxy, explorer_project, explorer_scene):
    bbox_area = {
        'west': 103.8168,
        'north': 1.3236,
        'east': 103.8303,
        'south': 1.3167
    }

    free_area = [
        (103.8168, 1.3236),
        (103.8303, 1.3236),
        (103.8303, 1.3167),
        (103.8168, 1.3167)
    ]

    # retrieve the administrative zones (all)
    download_path = os.path.join(wd_path, 'zones0.geojson')
    explorer_proxy.download_geometries(explorer_project.id, download_path, geo_type=GeometryType.zone)
    features = extract_geojson(download_path)
    assert len(features) == 332

    # retrieve the administrative zones (within area)
    download_path = os.path.join(wd_path, 'zones_subset1.geojson')
    explorer_proxy.download_geometries(explorer_project.id, download_path, geo_type=GeometryType.zone,
                                       bbox_area=bbox_area)
    features = extract_geojson(download_path)
    assert len(features) == 4

    # retrieve the administrative zones (within area)
    download_path = os.path.join(wd_path, 'zones_subset2.geojson')
    explorer_proxy.download_geometries(explorer_project.id, download_path, geo_type=GeometryType.zone,
                                       free_area=free_area)
    features = extract_geojson(download_path)
    assert len(features) == 4

    # retrieve the landuse zones (within area)
    download_path = os.path.join(wd_path, 'landuse_zones_subset.geojson')
    explorer_proxy.download_geometries(explorer_project.id, download_path, geo_type=GeometryType.landuse,
                                       free_area=free_area, set_id='scene:'+explorer_scene.id)
    features = extract_geojson(download_path)
    assert len(features) == 589

    # retrieve the landcover zones (within area)
    download_path = os.path.join(wd_path, 'landcover_zones_subset.geojson')
    explorer_proxy.download_geometries(explorer_project.id, download_path, geo_type=GeometryType.landcover,
                                       free_area=free_area, set_id='scene:'+explorer_scene.id)
    features = extract_geojson(download_path)
    assert len(features) == 589

    # retrieve the buildings (area)
    download_path = os.path.join(wd_path, 'buildings_area.geojson')
    explorer_proxy.download_geometries(explorer_project.id, download_path, geo_type=GeometryType.building,
                                       free_area=free_area, set_id='scene:'+explorer_scene.id)
    features = extract_geojson(download_path)
    assert len(features) == 427

    # retrieve all landuse zones
    download_path = os.path.join(wd_path, 'landuse_all.geojson')
    explorer_proxy.download_geometries(explorer_project.id, download_path, geo_type=GeometryType.landuse,
                                       set_id='scene:'+explorer_scene.id)
    features = extract_geojson(download_path)
    assert len(features) == 120739

    # retrieve the buildings (scene = 'default')
    download_path = os.path.join(wd_path, 'buildings_all.geojson')
    explorer_proxy.download_geometries(explorer_project.id, download_path, geo_type=GeometryType.building,
                                       set_id='scene:'+explorer_scene.id)
    features = extract_geojson(download_path)
    assert len(features) == 110052

    # retrieve the buildings (scene = 'invalid')
    download_path = os.path.join(wd_path, 'buildings_none.geojson')
    try:
        explorer_proxy.download_geometries(explorer_project.id, download_path, geo_type=GeometryType.building,
                                           set_id='scene:invalid')
        assert False
    except UnsuccessfulRequestError as e:
        assert 'Scene \'invalid\' not found' in e.reason


def test_get_geometries_queenstown(wd_path, explorer_proxy, explorer_project, explorer_scene):
    # retrieve the administrative zones (all)
    download_path = os.path.join(wd_path, 'zones.geojson')
    explorer_proxy.download_geometries(explorer_project.id, download_path, geo_type=GeometryType.zone)
    features = extract_geojson(download_path)
    assert(len(features) == 332)

    # identify all zones that are part of Queenstown
    all_buildings = []
    for feature in features:
        if feature['properties']['planning_area_name'] == 'Queenstown':
            coordinates = list(geojson.utils.coords(feature))
            download_path = os.path.join(wd_path, f"{feature['properties']['subzone_code']}.geojson")
            explorer_proxy.download_geometries(explorer_project.id, download_path, geo_type=GeometryType.building,
                                               free_area=coordinates, set_id='scene:'+explorer_scene.id)
            features = extract_geojson(download_path)
            all_buildings.extend(features)
    assert(len(all_buildings) == 2712)
    download_path = os.path.join(wd_path, 'queenstown.geojson')
    with open(download_path, 'w') as f:
        json.dump({
            'type': 'FeatureCollection',
            'features': all_buildings
        }, f)


def test_get_geometries_cached(wd_path, explorer_proxy, explorer_project, explorer_scene):
    bbox_area = {
        'west': 103.8169,
        'north': 1.3235,
        'east': 103.8302,
        'south': 1.3168
    }

    # retrieve the buildings (area) NOT CACHED
    t0 = get_timestamp_now()
    download_path = os.path.join(wd_path, 'landuse_area1.geojson')
    explorer_proxy.download_geometries(explorer_project.id, download_path, geo_type=GeometryType.landuse,
                                       bbox_area=bbox_area, set_id='scene:'+explorer_scene.id)
    features = extract_geojson(download_path)
    assert(len(features) > 0)

    # retrieve the buildings (area) NOT CACHED
    t1 = get_timestamp_now()
    download_path = os.path.join(wd_path, 'landuse_area2.geojson')
    explorer_proxy.download_geometries(explorer_project.id, download_path, geo_type=GeometryType.landuse,
                                       bbox_area=bbox_area, set_id='scene:'+explorer_scene.id)
    features = extract_geojson(download_path)
    assert(len(features) > 0)

    t2 = get_timestamp_now()
    dt0 = t1 - t0
    dt1 = t2 - t1
    print(f"dt0={dt0}")
    print(f"dt1={dt1}")
    assert(dt0 > dt1)


def test_area_of_interest(explorer_server, explorer_proxy, explorer_project, node_context):
    # fetch dataset information
    result: FetchDatasetsResponse = explorer_proxy.fetch_datasets(explorer_project.id)
    print(result)
    n_pending = len(result.pending)
    n_available = len(result.available)

    # upload building data
    content_path = os.path.join(EXPLORER_DATA_PATH, 'aoi.geojson')
    result: UploadDatasetResponse = explorer_proxy.upload_dataset(explorer_project.id, content_path,
                                                                  AreaOfInterest().name())
    aoi_obj_id = result.datasets[0].obj_id

    # import the AOI
    result: ExplorerDatasetInfo = explorer_proxy.import_dataset(explorer_project.id, aoi_obj_id, 'JE')
    print(result)

    # fetch dataset information
    result: FetchDatasetsResponse = explorer_proxy.fetch_datasets(explorer_project.id)
    print(result)
    assert len(result.pending) == n_pending
    assert len(result.available) == n_available + 1

    # determine AOI obj id
    aoi_obj_id = None
    for dataset in result.available:
        if dataset.name == 'JE':
            aoi_obj_id = dataset.obj_id
            break
    assert aoi_obj_id is not None

    # test if getting AOI works in analysis context
    project = explorer_server.get_project(explorer_project.id)
    context = AnalysisContextImpl(project, 'analysis_id', aoi_obj_id, node_context, None, None)

    # get the AOI
    os.makedirs(context.analysis_path, exist_ok=True)
    aoi = context.area_of_interest()
    assert aoi is not None


def test_upload_import_delete_geometries(wd_path, explorer_project, explorer_proxy, explorer_scene):
    # get all the zones
    zone_path = os.path.join(wd_path, 'zones.geojson')
    explorer_proxy.download_geometries(explorer_project.id, zone_path, geo_type=GeometryType.zone,
                                       set_id='scene:'+explorer_scene.id)
    with open(zone_path, 'r') as f:
        zones = json.load(f)

    # find the CAZ with the required subzone code of Paya Lebar Airbase
    subzone_code = 'SESZ06'
    plab_feature = None
    for feature in zones['geojson']['features']:
        if feature['properties']['name'] == subzone_code:
            plab_feature = feature
            break
    plab_feature['properties']['id'] = plab_feature['id']

    plab_configs = explorer_proxy.get_zone_configs(explorer_project.id, plab_feature['id'])
    n0 = len(plab_configs)

    # fetch dataset information
    result: FetchDatasetsResponse = explorer_proxy.fetch_datasets(explorer_project.id)
    print(result)
    n_pending = len(result.pending)
    n_available = len(result.available)

    # upload building data
    content_path = os.path.join(EXPLORER_DATA_PATH, 'building.geojson')
    result: UploadDatasetResponse = explorer_proxy.upload_dataset(explorer_project.id, content_path,
                                                                  UrbanGeometries().name())
    bld_dataset_id = result.datasets[0].obj_id
    with open(content_path, 'r') as f:
        buildings_geojson = json.load(f)

    # update the buildings
    explorer_proxy.update_dataset(explorer_project.id, bld_dataset_id, {
        'features': buildings_geojson['features']
    }, geo_type=GeometryType.building)

    result: Dict[int, ZoneConfiguration] = \
        explorer_proxy.add_zone_configs(explorer_project.id, 'my config', [plab_feature['id']], {
            GeometryType.building: bld_dataset_id
        })
    print(result)

    # there should be now one more configuration
    plab_configs = explorer_proxy.get_zone_configs(explorer_project.id, plab_feature['id'])
    n1 = len(plab_configs)
    assert n1 == n0 + 1

    # number of datasets should be one more now
    result: FetchDatasetsResponse = explorer_proxy.fetch_datasets(explorer_project.id)
    print(result)
    assert len(result.pending) == n_pending
    assert len(result.available) == n_available + 1
    dataset: ExplorerDatasetInfo = result.available[-1]

    # retrieve the administrative zones with zone config present -> in this case: one zone has an alt config,
    # that zone should be returned
    download_path = os.path.join(wd_path, 'zones2.geojson')
    explorer_proxy.download_geometries(explorer_project.id, download_path, geo_type=GeometryType.zone,
                                       set_id='zone_config:')
    features = extract_geojson(download_path)
    assert (features[0]['id'] == plab_feature['id'])

    # retrieve the dataset
    result: List[dict] = explorer_proxy.get_datasets(explorer_project.id, dataset.obj_id)
    print(result)
    assert (len(result) == 3)  # 3 because default geometries are retained even though we only imported buildings

    # retrieve the administrative zones with zone config present -> in this case: one zone has an alt config,
    # that zone should be returned
    download_path = os.path.join(wd_path, 'zones3.json')
    try:
        explorer_proxy.download_geometries(explorer_project.id, download_path, geo_type=GeometryType.zone,
                                           set_id=f"zone_config:{plab_feature['id']}=-1")
        assert False
    except UnsuccessfulRequestError as e:
        assert f"Configuration -1 referenced but not found for zone {plab_feature['id']}" in e.reason

    # delete the zone configuration
    explorer_proxy.delete_dataset(explorer_project.id, dataset.obj_id)

    # number of datasets should be the same as before
    result: FetchDatasetsResponse = explorer_proxy.fetch_datasets(explorer_project.id)
    print(result)
    assert len(result.pending) == n_pending
    assert len(result.available) == n_available

    # there should be now 1 configuration less
    plab_configs = explorer_proxy.get_zone_configs(explorer_project.id, plab_feature['id'])
    n2 = len(plab_configs)
    assert n2 == n0


def test_create_get_delete_scene(explorer_project, explorer_proxy):
    module_settings = {
        "electric-vehicles": {
            "integerRangeSteps": 30
        },
        "transport-share": {
            "current_share": "77",
            "new_share": "88"
        },
        "vegetation-fraction": {
            "veg_fraction_mode": "custom_fraction",
            "custom_lcz_vegetation": [
                {
                    "name": "lcz4",
                    "value": 50
                },
                {
                    "name": "lcz7",
                    "value": 30
                }
            ]
        }
    }

    # try to generate a scene with a non-existing alt config
    try:
        config = ZonesConfigurationMapping(selection={12: -1})
        explorer_proxy.create_scene(explorer_project.id, 'test scene', config, module_settings)
        assert False

    except UnsuccessfulRequestError as e:
        assert 'Encountered non-existing configuration -1 for zone 12' in e.reason

    result: List[Scene] = explorer_proxy.get_scenes(explorer_project.id)
    assert len(result) == 1

    # create a new zone configuration for Sengkang
    plab_zone_id = 317
    content_path = os.path.join(EXPLORER_DATA_PATH, 'building.geojson')
    result: UploadDatasetResponse = \
        explorer_proxy.upload_dataset(explorer_project.id, content_path, UrbanGeometries().name())
    assert len(result.datasets) == 1

    result: Dict[int, ZoneConfiguration] = \
        explorer_proxy.add_zone_configs(explorer_project.id, 'plab', selected_zones=[plab_zone_id],
                                        datasets={GeometryType.building: result.datasets[0].obj_id})
    assert plab_zone_id in result

    alt_config_id = result[plab_zone_id].config_id

    # try to generate a scene using the alt config for PLAB zone
    try:
        config_mapping = ZonesConfigurationMapping(selection={plab_zone_id: alt_config_id})
        result: Scene = explorer_proxy.create_scene(explorer_project.id, 'test scene', config_mapping, module_settings)
        valid_scene_id = result.id
        print(result)

    except Exception:
        assert False

    result: List[Scene] = explorer_proxy.get_scenes(explorer_project.id)
    assert len(result) == 2

    # try to remove a scene with an invalid id
    try:
        explorer_proxy.delete_scene(explorer_project.id, 'invalid scene id')
        assert False

    except UnsuccessfulRequestError as e:
        assert 'No scene found with id' in e.reason

    # try to remove a scene with a valid id
    try:
        explorer_proxy.delete_scene(explorer_project.id, valid_scene_id)

    except Exception:
        assert False

    result: List[Scene] = explorer_proxy.get_scenes(explorer_project.id)
    assert len(result) == 1

    plab_configs = explorer_proxy.get_zone_configs(explorer_project.id, plab_zone_id)
    n0 = len(plab_configs)

    # delete the latest configuration
    result: ZoneConfiguration = explorer_proxy.delete_zone_config(explorer_project.id, alt_config_id)
    assert result.name == 'plab'
    assert result.config_id == alt_config_id

    plab_configs = explorer_proxy.get_zone_configs(explorer_project.id, plab_zone_id)
    n1 = len(plab_configs)
    assert n1 == n0 - 1


def test_get_analysis_group_config(explorer_project, explorer_proxy):
    parameters = {}
    result: AnalysisGroup = explorer_proxy.create_analysis_group(explorer_project.id, 'wind-corridor-potential',
                                                                 "test group", parameters)

    group_config = explorer_proxy.get_group_config(explorer_project.id, result.id)
    print(group_config)
    assert group_config


def test_create_delete_project(explorer_project, explorer_proxy):
    results = explorer_proxy.get_projects()
    n = len(results)

    # create project
    info = explorer_proxy.info()
    bdp = info.bdps[0].packages[0]
    project = explorer_proxy.create_project(bdp.city, bdp.id, 'test project shehani')
    print(project)
    assert project is not None

    # wait for the project to be initialised
    project_id = project.id
    while project.state != 'initialised':
        time.sleep(5)
        projects = explorer_proxy.get_projects()
        projects = {project.id: project for project in projects}
        project = projects[project_id]
    print(f"project {project_id} initialised")

    results = explorer_proxy.get_projects()
    assert len(results) == n + 1

    result = explorer_proxy.delete_project(project_id)
    assert result.deleted

    results = explorer_proxy.get_projects()
    assert len(results) == n


def test_upload_import_failing(explorer_project, explorer_proxy):
    content_path_wrong = os.path.join(EXPLORER_DATA_PATH, 'lcz-map.tiff')
    content_path = os.path.join(EXPLORER_DATA_PATH, 'urban_geometries_shp.zip')

    # try to fetch all known datasets
    try:
        result = explorer_proxy.fetch_datasets(explorer_project.id)
        print(result)
        assert result is not None

    except Exception as e:
        print(e)
        assert False

    # try to upload with an unknown type and format
    try:
        explorer_proxy.upload_dataset(explorer_project.id, content_path, 'unknown_type')
        assert False

    except Exception as e:
        assert 'Unsupported data object type' in e.args[0]

    # try to upload with a wrong content
    try:
        result = explorer_proxy.upload_dataset(explorer_project.id, content_path_wrong, UrbanGeometries.DATA_TYPE)
        assert len(result.datasets) == 0

    except Exception as e:
        print(e)
        assert False

    # try to upload with the correct content
    try:
        result = explorer_proxy.upload_dataset(explorer_project.id, content_path, UrbanGeometries.DATA_TYPE)
        print(result)
        assert result.datasets[0].obj_id is not None

        object_id = result.datasets[0].obj_id

    except Exception as e:
        print(e)
        assert False

    # try to delete the pending dataset
    try:
        explorer_proxy.delete_dataset(explorer_project.id, object_id)

    except Exception as e:
        print(e)
        assert False

    # try to import with wrong object id
    try:
        explorer_proxy.import_dataset(explorer_project.id, 'wrong_object_id', 'name of dataset')
        assert False

    except Exception as e:
        print(e)
        assert 'No pending dataset' in e.args[0]


def test_upload_import_as_dataset(explorer_project, explorer_proxy):
    content_path = os.path.join(EXPLORER_DATA_PATH, 'building.geojson')

    # try to import with correct object id
    try:
        result = explorer_proxy.upload_dataset(explorer_project.id, content_path, UrbanGeometries.DATA_TYPE)
        object_id = result.datasets[0].obj_id

        result = explorer_proxy.fetch_datasets(explorer_project.id)
        n_available = len(result.available)

        result = explorer_proxy.import_dataset(explorer_project.id, object_id, 'my dataset')
        print(result)
        assert result.name == 'my dataset'
        object_id = result.obj_id

        result = explorer_proxy.fetch_datasets(explorer_project.id)
        print(result)
        assert len(result.available) == n_available + 1

        # delete the dataset
        result = explorer_proxy.delete_dataset(explorer_project.id, object_id)
        print(result)
        assert result.name == 'my dataset'

        result = explorer_proxy.fetch_datasets(explorer_project.id)
        print(result)
        assert len(result.available) == n_available

    except Exception as e:
        print(e)
        assert False


def test_upload_import_as_zone_config(explorer_server, explorer_project, explorer_proxy):
    content_path = os.path.join(EXPLORER_DATA_PATH, 'urban_geometries_shp.zip')

    # try to import with correct object id
    try:
        # determine the zone id used for selected import
        zones = explorer_server.get_project(explorer_project.id).geometries(GeometryType.zone).content()
        selected_zone_id = None
        for feature in zones['features']:
            name = feature['properties']['name']
            if name == 'SESZ06':  # that's the name of the zone where the buildings are inside
                selected_zone_id = feature['id']
                break

        result: UploadDatasetResponse = \
            explorer_proxy.upload_dataset(explorer_project.id, content_path, UrbanGeometries.DATA_TYPE)
        bld_object_id = result.datasets[0].obj_id
        veg_object_id = result.datasets[1].obj_id
        lc_object_id = result.datasets[2].obj_id

        configs: List[ZoneConfiguration] = explorer_proxy.get_zone_configs(explorer_project.id, selected_zone_id)
        n0 = len(configs)

        # create a new configuration
        result: Dict[int, ZoneConfiguration] = \
            explorer_proxy.add_zone_configs(
                explorer_project.id, 'my config', selected_zones=[selected_zone_id], datasets={
                    GeometryType.building: bld_object_id,
                    GeometryType.vegetation: veg_object_id,
                    GeometryType.landcover: lc_object_id
                }
            )
        assert selected_zone_id in result
        assert result[selected_zone_id].name == 'my config'
        assert len(result[selected_zone_id].building_ids) == 653
        assert len(result[selected_zone_id].vegetation_ids) == 3716
        assert len(result[selected_zone_id].landcover_ids) == 662

        configs: List[ZoneConfiguration] = explorer_proxy.get_zone_configs(explorer_project.id, selected_zone_id)
        n1 = len(configs)
        assert n1 == n0 + 1

        # delete the latest configuration
        config_id = configs[-1].config_id
        zone_config = explorer_proxy.delete_zone_config(explorer_project.id, config_id)
        assert zone_config is not None
        assert zone_config.config_id == config_id

        configs: List[ZoneConfiguration] = explorer_proxy.get_zone_configs(explorer_project.id, selected_zone_id)
        n2 = len(configs)
        assert n0 == n2

    except Exception as e:
        print(e)
        assert False
