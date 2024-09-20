import json
import logging
import os
import shutil
import time
import unittest
from typing import List, Dict

import geojson
from saas.core.exceptions import SaaSRuntimeException
from saas.core.helpers import read_json_from_file, get_timestamp_now, validate_json
from saas.core.keystore import Keystore
from saas.core.logging import Logging
from saas.core.schemas import GithubCredentials, SSHCredentials
from saas.rest.exceptions import UnsuccessfulRequestError
from saas.sdk.app.auth import UserDB, UserAuth
from saas.sdk.base import connect
from tests.base_testcase import create_wd, create_rnd_hex_string

from duct.dots.duct_lcz import LocalClimateZoneMap
from duct.dots.duct_urban_geometries import UrbanGeometries
from duct.modules.vegetation_fraction_module import VegetationFractionModule, _make_marks
from explorer.bdp import BaseDataPackageDB
from explorer.dots.area_of_interest import AreaOfInterest
from explorer.dots.dot import ImportableDataObjectType, DataObjectType
from explorer.geodb import GeometryType
from explorer.project import AnalysisContextImpl
from explorer.proxy import ExplorerProxy
from explorer.renderer.base import NetworkRenderer
from explorer.schemas import Scene, AnalysisGroup, ZonesConfigurationMapping, ZoneConfiguration, ExplorerDatasetInfo
from explorer.server import ExplorerServer, FetchDatasetsResponse, UploadDatasetResponse
from explorer.analysis.base import Analysis
from explorer.module.base import BuildModule

Logging.initialise(logging.INFO)
logger = Logging.get(__name__, level=logging.DEBUG)

nextcloud_path = os.path.join(os.environ['HOME'], 'Nextcloud', 'DT-Lab', 'Testing')
bdps_path = os.path.join(nextcloud_path, 'base_data_packages')
bdp_id = '4fc2e31f6864f856db6c24463a98b4e93954bc97d89e807d702a0343507b35d4'
duct_fom_commit_id = 'dccdeb9'


def update_keystore_from_credentials(keystore: Keystore, credentials_path: str = None) -> None:
    """
    Updates a keystore with credentials loaded from credentials file. This is a convenience function useful for
    testing purposes. A valid example content may look something like this:
    {
        "name": "John Doe",
        "email": "john.doe@internet.com",
        "ssh-credentials": [
            {
            "name": "my-remote-machine-A",
            "login": "johnd",
            "host": "10.8.0.1",
            "password": "super-secure-password-123"
            },
            {
            "name": "my-remote-machine-B",
            "login": "johnd",
            "host": "10.8.0.2",
            "key_path": "/home/johndoe/machine-b-key"
            }
        ],
        "github-credentials": [
            {
                "repository": "https://github.com/my-repo",
                "login": "JohnDoe",
                "personal_access_token": "ghp_xyz..."
            }
        ]
    }

    For SSH credentials note that you can either indicate a password or a path to a key file.

    :param keystore: the keystore that is to be updated
    :param credentials_path: the optional path to the credentials file (default is $HOME/.saas-credentials.json)
    :return:
    """

    credentials_schema = {
        'type': 'object',
        'properties': {
            'name': {'type': 'string'},
            'email': {'type': 'string'},
            'ssh-credentials': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'name': {'type': 'string'},
                        'login': {'type': 'string'},
                        'host': {'type': 'string'},
                        'password': {'type': 'string'},
                        'key_path': {'type': 'string'}
                    },
                    'required': ['name', 'login', 'host']
                }
            },
            'github-credentials': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'repository': {'type': 'string'},
                        'login': {'type': 'string'},
                        'personal_access_token': {'type': 'string'}
                    },
                    'required': ['repository', 'login', 'personal_access_token']
                }
            }
        }
    }

    # load the credentials and validate
    path = credentials_path if credentials_path else os.path.join(os.environ['HOME'], '.saas-credentials.json')
    if os.path.isfile(path):
        credentials = read_json_from_file(path)
        if not validate_json(content=credentials, schema=credentials_schema):
            raise SaaSRuntimeException("JSON validation failed", details={
                'instance': credentials,
                'schema': credentials_schema
            })

        # update profile (if applicable)
        keystore.update_profile(name=credentials['name'] if 'name' in credentials else None,
                                email=credentials['email'] if 'email' in credentials else None)

        # do we have SSH credentials?
        if 'ssh-credentials' in credentials:
            for item in credentials['ssh-credentials']:
                # password or key path?
                if 'password' in item:
                    keystore.ssh_credentials.update(item['name'],
                                                    SSHCredentials(host=item['host'], login=item['login'],
                                                                   key=item['password'], key_is_password=True))

                elif 'key_path' in item:
                    # read the ssh key from file
                    with open(item['key_path'], 'r') as f:
                        ssh_key = f.read()

                    keystore.ssh_credentials.update(item['name'],
                                                    SSHCredentials(host=item['host'], login=item['login'],
                                                                   key=ssh_key, key_is_password=False))

                else:
                    raise RuntimeError(f"Unexpected SSH credentials format: {item}")

            keystore.sync()

        # do we have Github credentials?
        if 'github-credentials' in credentials:
            for item in credentials['github-credentials']:
                keystore.github_credentials.update(item['repository'], GithubCredentials.parse_obj(item))
            keystore.sync()


def extract_geojson(input_path: str, output_path: str = None) -> dict:
    assert (os.path.isfile(input_path))
    with open(input_path, 'r') as f1:
        content = json.load(f1)
        content = content['geojson']
    output_path = output_path if output_path else input_path
    with open(output_path, 'w') as f2:
        f2.write(json.dumps(content))
    return content['features']


class ExplorerServerTestCase(unittest.TestCase):
    _wd_path = None
    _keystore_path = None
    _datastore_path = None

    _server_address = ('127.0.0.1', 5021)
    _node_rest_address = ('127.0.0.1', 5001)
    _node_p2p_address = ('127.0.0.1', 4001)
    _node_keystore = None
    _node = None
    _context = None

    _owner = None
    _user = None

    _server = None
    _proxy = None
    _project = None
    _scene = None

    @classmethod
    def setUpClass(cls):
        # create folders
        cls._wd_path = create_wd()
        cls._keystore_path = os.path.join(cls._wd_path, 'keystore')
        os.makedirs(cls._keystore_path, exist_ok=True)

        # # create node
        # cls._node_keystore = Keystore.create(cls._keystore_path, 'name', 'email', 'password')
        # cls._node = Node.create(cls._node_keystore, cls._wd_path, p2p_address=cls._node_p2p_address,
        #                         boot_node_address=cls._node_p2p_address, rest_address=cls._node_rest_address,
        #                         enable_dor=True, enable_rti=True, strict_deployment=False)

        # initialise user Auth and DB
        UserAuth.initialise(create_rnd_hex_string(32))
        UserDB.initialise(cls._wd_path)

        # create users: owner and user
        password = 'password'
        cls._owner = UserDB.add_user('foo.bar@email.com', 'Foo Bar', password)
        cls._user = UserDB.add_user('john.doe@email.com', 'John Doe', password)

        # update credentials
        update_keystore_from_credentials(cls._user.keystore)

        # create Dashboard server and proxy
        cls._server = ExplorerServer(cls._server_address, cls._node_rest_address, cls._wd_path)

        for c in ExplorerServer.search_for_classes(['duct.analyses'], Analysis):
            cls._server.add_analysis_instance(c())

        for c in ExplorerServer.search_for_classes(['duct.modules'], BuildModule):
            cls._server.add_build_module(c())

        for c in ExplorerServer.search_for_classes(['duct.dots', 'explorer.dots'], DataObjectType):
            if c != ImportableDataObjectType:
                cls._server.add_data_object_type(c())

        for c in ExplorerServer.search_for_classes(['duct.renderer'], NetworkRenderer):
            cls._server.add_network_renderers(c())

        cls._server.startup()
        cls._proxy = ExplorerProxy(cls._server_address, cls._user, password)

        # get SaaS context
        cls._context = connect(cls._node_rest_address, cls._user.keystore)

        # make identities known
        cls._context.publish_identity(cls._owner.identity)
        cls._context.publish_identity(cls._user.identity)

        assert BaseDataPackageDB.exists(bdps_path, bdp_id)
        cls._server.import_bdp(bdps_path, bdp_id)

        # initialise the server
        cls._server.initialise(cls._user)

        # create test project
        info = cls._proxy.info()
        bdp = info.bdps[0].packages[0]
        cls._project = cls._proxy.create_project(bdp.city, bdp.id, 'test project')
        print(cls._project)

        # wait for the project to be initialised
        project_id = cls._project.id
        while cls._project.state != 'initialised':
            time.sleep(1)
            projects = cls._proxy.get_projects()
            projects = {project.id: project for project in projects}
            cls._project = projects[project_id]

        print(f"project {project_id} initialised")

        # create scene
        module_settings = {}
        zone_config_mapping = ZonesConfigurationMapping.empty()
        cls._scene = cls._proxy.create_scene(cls._project.id, 'Default', zone_config_mapping, module_settings)
        print(cls._scene)

    @classmethod
    def tearDownClass(cls):
        if cls._server is not None:
            # shutdown server
            cls._server.shutdown()

            # delete working directory
            shutil.rmtree(cls._wd_path, ignore_errors=True)

    def test_get_info(self):
        results = self._proxy.public_info()
        assert (results is not None)
        results = results.dict()
        print(results)

        results = self._proxy.info()
        assert (results is not None)
        results = results.dict()
        print(results)

        results = self._proxy.get_info_analyses(self._project.id, scale='meso', aoi_obj_id='0x123', scene_id='0x456')
        assert (results is not None)
        print(results)

        results = self._proxy.get_info_scene(self._project.id)
        assert (results is not None)
        results = [result.dict() for result in results]
        print(results)

    def test_get_create_projects(self):
        results = self._proxy.get_projects()
        print(results)
        assert(results is not None)
        assert(len(results) == 1)

        info = self._proxy.info()
        bdp = info.bdps[0].packages[0]

        project = self._proxy.create_project(bdp.city, bdp.id, 'test project 2')
        print(project)
        assert(project is not None)

        # wait for the project to be initialised
        project_id = project.id
        while project.state != 'initialised':
            time.sleep(1)
            projects = self._proxy.get_projects()
            projects = {project.id: project for project in projects}
            project = projects[project_id]
        print(f"project {project_id} initialised")

        results = self._proxy.get_projects()
        print(results)
        assert(results is not None)
        assert(len(results) == 2)

    def test_get_geometries(self):
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
        download_path = os.path.join(self._wd_path, 'zones0.geojson')
        self._proxy.download_geometries(self._project.id, download_path, geo_type=GeometryType.zone)
        features = extract_geojson(download_path)
        assert(len(features) == 332)

        # retrieve the administrative zones with zone config present -> in this case: no zones with alt configs,
        # so no zones will be returned
        download_path = os.path.join(self._wd_path, 'zones1.geojson')
        self._proxy.download_geometries(self._project.id, download_path, geo_type=GeometryType.zone,
                                        set_id='zone_config:')
        features = extract_geojson(download_path)
        assert(len(features) == 0)

        # retrieve the administrative zones (within area)
        download_path = os.path.join(self._wd_path, 'zones_subset1.geojson')
        self._proxy.download_geometries(self._project.id, download_path, geo_type=GeometryType.zone,
                                        bbox_area=bbox_area)
        features = extract_geojson(download_path)
        assert(len(features) == 4)

        # retrieve the administrative zones (within area)
        download_path = os.path.join(self._wd_path, 'zones_subset2.geojson')
        self._proxy.download_geometries(self._project.id, download_path, geo_type=GeometryType.zone,
                                        free_area=free_area)
        features = extract_geojson(download_path)
        assert(len(features) == 4)

        # retrieve the landuse zones (within area)
        download_path = os.path.join(self._wd_path, 'landuse_zones_subset.geojson')
        self._proxy.download_geometries(self._project.id, download_path, geo_type=GeometryType.landuse,
                                        free_area=free_area, set_id='scene:'+self._scene.id)
        features = extract_geojson(download_path)
        assert(len(features) == 589)

        # retrieve the landcover zones (within area)
        download_path = os.path.join(self._wd_path, 'landcover_zones_subset.geojson')
        self._proxy.download_geometries(self._project.id, download_path, geo_type=GeometryType.landcover,
                                        free_area=free_area, set_id='scene:'+self._scene.id)
        features = extract_geojson(download_path)
        assert(len(features) == 589)

        # retrieve the buildings (area)
        download_path = os.path.join(self._wd_path, 'buildings_area.geojson')
        self._proxy.download_geometries(self._project.id, download_path, geo_type=GeometryType.building,
                                        free_area=free_area, set_id='scene:'+self._scene.id)
        features = extract_geojson(download_path)
        assert(len(features) == 427)

        # retrieve all landuse zones
        download_path = os.path.join(self._wd_path, 'landuse_all.geojson')
        self._proxy.download_geometries(self._project.id, download_path, geo_type=GeometryType.landuse,
                                        set_id='scene:'+self._scene.id)
        features = extract_geojson(download_path)
        assert(len(features) == 120739)

        # retrieve the buildings (scene = 'default')
        download_path = os.path.join(self._wd_path, 'buildings_all.geojson')
        self._proxy.download_geometries(self._project.id, download_path, geo_type=GeometryType.building,
                                        set_id='scene:'+self._scene.id)
        features = extract_geojson(download_path)
        assert(len(features) == 110052)

        # retrieve the buildings (scene = 'invalid')
        download_path = os.path.join(self._wd_path, 'buildings_none.geojson')
        try:
            self._proxy.download_geometries(self._project.id, download_path, geo_type=GeometryType.building,
                                            set_id='scene:invalid')
            assert False
        except UnsuccessfulRequestError as e:
            assert 'Scene \'invalid\' not found' in e.reason

    def test_get_geometries_queenstown(self):
        # retrieve the administrative zones (all)
        download_path = os.path.join(self._wd_path, 'zones.geojson')
        self._proxy.download_geometries(self._project.id, download_path, geo_type=GeometryType.zone)
        features = extract_geojson(download_path)
        assert(len(features) == 332)

        # identify all zones that are part of Queenstown
        all_buildings = []
        for feature in features:
            if feature['properties']['planning_area_name'] == 'Queenstown':
                coordinates = list(geojson.utils.coords(feature))
                download_path = os.path.join(self._wd_path, f"{feature['properties']['subzone_code']}.geojson")
                self._proxy.download_geometries(self._project.id, download_path, geo_type=GeometryType.building,
                                                free_area=coordinates, set_id='scene:'+self._scene.id)
                features = extract_geojson(download_path)
                all_buildings.extend(features)
        assert(len(all_buildings) == 2712)
        download_path = os.path.join(self._wd_path, 'queenstown.geojson')
        with open(download_path, 'w') as f:
            json.dump({
                'type': 'FeatureCollection',
                'features': all_buildings
            }, f)

    def test_get_geometries_cached(self):
        bbox_area = {
            'west': 103.8169,
            'north': 1.3235,
            'east': 103.8302,
            'south': 1.3168
        }

        # retrieve the buildings (area) NOT CACHED
        t0 = get_timestamp_now()
        download_path = os.path.join(self._wd_path, 'landuse_area1.geojson')
        self._proxy.download_geometries(self._project.id, download_path, geo_type=GeometryType.landuse,
                                        bbox_area=bbox_area, set_id='scene:'+self._scene.id)
        features = extract_geojson(download_path)
        assert(len(features) > 0)

        # retrieve the buildings (area) NOT CACHED
        t1 = get_timestamp_now()
        download_path = os.path.join(self._wd_path, 'landuse_area2.geojson')
        self._proxy.download_geometries(self._project.id, download_path, geo_type=GeometryType.landuse,
                                        bbox_area=bbox_area, set_id='scene:'+self._scene.id)
        features = extract_geojson(download_path)
        assert(len(features) > 0)

        t2 = get_timestamp_now()
        dt0 = t1 - t0
        dt1 = t2 - t1
        print(f"dt0={dt0}")
        print(f"dt1={dt1}")
        assert(dt0 > dt1)

    def test_area_of_interest(self):
        # fetch dataset information
        result: FetchDatasetsResponse = self._proxy.fetch_datasets(self._project.id)
        print(result)
        n_pending = len(result.pending)
        n_available = len(result.available)

        # upload building data
        content_path = os.path.join(nextcloud_path, 'duct_dots', 'aoi.geojson')
        result: UploadDatasetResponse = self._proxy.upload_dataset(self._project.id, content_path,
                                                                   AreaOfInterest().name())
        aoi_obj_id = result.datasets[0].obj_id

        # import the AOI
        result: ExplorerDatasetInfo = self._proxy.import_dataset(self._project.id, aoi_obj_id, 'JE')
        print(result)

        # fetch dataset information
        result: FetchDatasetsResponse = self._proxy.fetch_datasets(self._project.id)
        print(result)
        assert len(result.pending) == n_pending
        assert len(result.available) == n_available + 1

        # determine AOI obj id
        aoi_obj_id = None
        for dataset in result.available:
            if dataset.name == 'JE':
                aoi_obj_id = result.available[0].obj_id
        assert aoi_obj_id is not None

        # test if getting AOI works in analysis context
        project = self._server.get_project(self._project.id)
        context = AnalysisContextImpl(project, 'analysis_id', aoi_obj_id, self._context, None, None)

        # get the AOI
        os.makedirs(context.analysis_path, exist_ok=True)
        aoi = context.area_of_interest()
        assert aoi is not None

    def test_upload_import_delete_geometries(self):
        # get all the zones
        zone_path = os.path.join(self._wd_path, 'zones.geojson')
        self._proxy.download_geometries(self._project.id, zone_path, geo_type=GeometryType.zone,
                                        set_id='scene:'+self._scene.id)
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

        # fetch dataset information
        result: FetchDatasetsResponse = self._proxy.fetch_datasets(self._project.id)
        print(result)
        n_pending = len(result.pending)
        n_available = len(result.available)

        # upload building data
        content_path = os.path.join(nextcloud_path, 'duct_dots', 'urban_geometries_geojson', 'building.geojson')
        result: UploadDatasetResponse = self._proxy.upload_dataset(self._project.id, content_path,
                                                                   UrbanGeometries().name())
        bld_dataset_id = result.datasets[0].obj_id
        with open(content_path, 'r') as f:
            buildings_geojson = json.load(f)

        # update the buildings
        self._proxy.update_dataset(self._project.id, bld_dataset_id, {
            'features': buildings_geojson['features']
        }, geo_type=GeometryType.building)

        result: Dict[int, ZoneConfiguration] = \
            self._proxy.add_zone_configs(self._project.id, 'my config', [plab_feature['id']], {
                GeometryType.building: bld_dataset_id
            })
        print(result)

        # there should be now 2 configurations
        plab_configs = self._proxy.get_zone_configs(self._project.id, plab_feature['id'])
        n_configs = len(plab_configs)
        assert(n_configs > 1)

        # number of datasets should be one more now
        result: FetchDatasetsResponse = self._proxy.fetch_datasets(self._project.id)
        print(result)
        assert(len(result.pending) == n_pending)
        assert(len(result.available) == n_available + 1)
        dataset: ExplorerDatasetInfo = result.available[-1]

        # retrieve the administrative zones with zone config present -> in this case: one zone has an alt config,
        # that zone should be returned
        download_path = os.path.join(self._wd_path, 'zones2.geojson')
        self._proxy.download_geometries(self._project.id, download_path, geo_type=GeometryType.zone,
                                        set_id='zone_config:')
        features = extract_geojson(download_path)
        assert (len(features) == 1)
        assert (features[0]['id'] == plab_feature['id'])

        # retrieve the dataset
        result: List[dict] = self._proxy.get_datasets(self._project.id, dataset.obj_id)
        print(result)
        assert (len(result) == 3)  # 3 because default geometries are retained even though we only imported buildings

        # retrieve the administrative zones with zone config present -> in this case: one zone has an alt config,
        # that zone should be returned
        download_path = os.path.join(self._wd_path, 'zones3.json')
        try:
            self._proxy.download_geometries(self._project.id, download_path, geo_type=GeometryType.zone,
                                            set_id=f"zone_config:{plab_feature['id']}=-1")
            assert False
        except UnsuccessfulRequestError as e:
            assert f"Configuration -1 referenced but not found for zone {plab_feature['id']}" in e.reason

        # retrieve the administrative zones with zone config present -> in this case: one zone has an alt config,
        # that zone should be returned
        download_path0 = os.path.join(self._wd_path, 'zones30.geojson')
        download_path1 = os.path.join(self._wd_path, 'zones31.geojson')
        download_path2 = os.path.join(self._wd_path, 'zones32.geojson')
        download_path3 = os.path.join(self._wd_path, 'zones33.geojson')
        self._proxy.download_geometries(self._project.id, download_path0, geo_type=GeometryType.zone,
                                        set_id=f"zone_config:{plab_feature['id']}={plab_configs[1].config_id}")
        self._proxy.download_geometries(self._project.id, download_path1, geo_type=GeometryType.landuse,
                                        set_id=f"zone_config:{plab_feature['id']}={plab_configs[1].config_id}")
        self._proxy.download_geometries(self._project.id, download_path2, geo_type=GeometryType.building,
                                        set_id=f"zone_config:{plab_feature['id']}={plab_configs[1].config_id}")
        self._proxy.download_geometries(self._project.id, download_path3, geo_type=GeometryType.vegetation,
                                        set_id=f"zone_config:{plab_feature['id']}={plab_configs[1].config_id}")
        features0 = extract_geojson(download_path0)
        assert (len(features0) == 1)
        assert (features0[0]['id'] == plab_feature['id'])
        features1 = extract_geojson(download_path1)
        features2 = extract_geojson(download_path2)
        features3 = extract_geojson(download_path3)
        assert (len(features1) == len(plab_configs[1].landuse_ids))
        assert (len(features2) == len(plab_configs[1].building_ids))
        assert (len(features3) == len(plab_configs[1].vegetation_ids))

        # delete the zone configuration
        self._proxy.delete_dataset(self._project.id, dataset.obj_id)

        # number of datasets should be the same as before
        result: FetchDatasetsResponse = self._proxy.fetch_datasets(self._project.id)
        print(result)
        assert(len(result.pending) == n_pending)
        assert(len(result.available) == n_available)

        # there should be now 1 configuration less
        plab_configs = self._proxy.get_zone_configs(self._project.id, plab_feature['id'])
        assert(len(plab_configs) == n_configs - 1)

    def test_create_get_delete_scene(self):
        # result: List[Scene] = self._proxy.get_scenes(self._project.id)
        # print(result)
        # assert(len(result) == 1)
        # default_scene_id = result[0].id

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
            self._proxy.create_scene(self._project.id, 'test scene', config, module_settings)
            assert False

        except UnsuccessfulRequestError as e:
            assert 'Encountered non-existing configuration -1 for zone 12' in e.reason

        result: List[Scene] = self._proxy.get_scenes(self._project.id)
        assert (len(result) == 1)

        # create a new zone configuration for Sengkang
        plab_zone_id = 317
        content_path = os.path.join(nextcloud_path, 'duct_dots', 'urban_geometries_geojson', 'building.geojson')
        result: UploadDatasetResponse = \
            self._proxy.upload_dataset(self._project.id, content_path, UrbanGeometries().name())
        assert(len(result.datasets) == 1)

        result: Dict[int, ZoneConfiguration] = \
            self._proxy.add_zone_configs(self._project.id, 'plab', selected_zones=[plab_zone_id],
                                         datasets={GeometryType.building: result.datasets[0].obj_id})
        assert(plab_zone_id in result)

        alt_config_id = result[plab_zone_id].config_id

        # try to generate a scene using the alt config for PLAB zone
        try:
            config_mapping = ZonesConfigurationMapping(selection={plab_zone_id: alt_config_id})
            result: Scene = self._proxy.create_scene(self._project.id, 'test scene', config_mapping, module_settings)
            valid_scene_id = result.id
            print(result)

        except Exception:
            assert False

        result: List[Scene] = self._proxy.get_scenes(self._project.id)
        assert(len(result) == 2)

        # try to remove a scene with an invalid id
        try:
            self._proxy.delete_scene(self._project.id, 'invalid scene id')
            assert False

        except UnsuccessfulRequestError as e:
            assert 'No scene found with id' in e.reason

        # try to remove a scene with a valid id
        try:
            self._proxy.delete_scene(self._project.id, valid_scene_id)

        except Exception:
            assert False

        result: List[Scene] = self._proxy.get_scenes(self._project.id)
        assert(len(result) == 1)

        # delete the latest configuration
        result: ZoneConfiguration = self._proxy.delete_zone_config(self._project.id, alt_config_id)
        assert result.name == 'plab'
        assert result.config_id == alt_config_id

        plab_configs = self._proxy.get_zone_configs(self._project.id, plab_zone_id)
        assert(len(plab_configs) == 1)

    # def test_add_analysis_group(self):
    #     # get some analysis type
    #     # TODO: this only includes analyses that have all the required processors deployed - which is not
    #     #  currently the case. This means the test case is currently broken.
    #     analyses = self._proxy.get_info_analyses(self._project.id)
    #     analysis_type = analyses[0].name
    #
    #     # create an analysis group
    #     parameters = {}
    #     result: AnalysisGroup = self._proxy.create_analysis_group(self._project.id, analysis_type, "test group",
    #                                                               parameters)
    #     print(result)
    #
    #     result: List[AnalysesByScene] = self._proxy.get_analyses_by_scene(self._project.id)
    #     print(result)
    #     assert(len(result) == 1)
    #     assert(result[0].scene_name == 'Default')
    #     assert(len(result[0].analyses) == 0)
    #
    #     result: List[AnalysesByConfiguration] = self._proxy.get_analyses_by_configuration(self._project.id)
    #     print(result)
    #     assert(len(result) == 1)
    #     assert(len(result[0].analyses) == 0)

    def test_get_analysis_group_config(self):
        # create an analysis group
        parameters = {}
        result: AnalysisGroup = self._proxy.create_analysis_group(self._project.id, 'wind-corridor-potential',
                                                                  "test group", parameters)

        group_config = self._proxy.get_group_config(self._project.id, result.id)
        print(group_config)

    def test_delete_project(self):
        results = self._proxy.get_projects()
        print(results)
        assert (results is not None)
        assert (len(results) == 1)

        info = self._proxy.info()
        bdp = info.bdps[0].packages[0]

        project = self._proxy.create_project(bdp.city, bdp.id, 'test project shehani')
        print(project)
        assert (project is not None)

        # wait for the project to be initialised
        project_id = project.id
        while project.state != 'initialised':
            time.sleep(5)
            projects = self._proxy.get_projects()
            projects = {project.id: project for project in projects}
            project = projects[project_id]
        print(f"project {project_id} initialised")

        results = self._proxy.get_projects()
        print(results)

        is_deleted = self._proxy.delete_project(project_id)
        print(is_deleted)

    def test_upload_import_failing(self):
        results = self._proxy.get_projects()
        print(results)
        assert (results is not None)

        content_path_wrong = os.path.join(nextcloud_path, 'duct_dots', 'lcz-map_vivek.tiff')
        content_path = os.path.join(nextcloud_path, 'duct_dots', 'urban_geometries_shp.zip')

        project = results[0]

        # try to fetch all known datasets
        try:
            result = self._proxy.fetch_datasets(project.id)
            print(result)
            assert(result is not None)

        except Exception as e:
            print(e)
            assert False

        # try to upload with an unknown type and format
        try:
            self._proxy.upload_dataset(project.id, content_path, 'unknown_type')
            assert False

        except Exception as e:
            assert 'Unsupported data object type' in e.args[0]

        # # try to upload with an unknown format
        # try:
        #     self._proxy.upload_dataset(project.id, content_path, 'duct.urban_geometry')
        #     assert False
        #
        # except Exception as e:
        #     assert 'Unsupported data format' in e.args[0]

        # try to upload with a wrong content
        try:
            result = self._proxy.upload_dataset(project.id, content_path_wrong, UrbanGeometries.DATA_TYPE)
            assert len(result.datasets) == 0

        except Exception as e:
            print(e)
            assert False

        # try to upload with the correct content
        try:
            result = self._proxy.upload_dataset(project.id, content_path, UrbanGeometries.DATA_TYPE)
            print(result)
            assert(result.datasets[0].obj_id is not None)

            object_id = result.datasets[0].obj_id

        except Exception as e:
            print(e)
            assert False

        # try to delete the pending dataset
        try:
            self._proxy.delete_dataset(project.id, object_id)

        except Exception as e:
            print(e)
            assert False

        # try to import with wrong object id
        try:
            self._proxy.import_dataset(project.id, 'wrong_object_id', 'name of dataset')
            assert False

        except Exception as e:
            print(e)
            assert 'No pending dataset' in e.args[0]

    def test_upload_import_as_dataset(self):
        results = self._proxy.get_projects()
        print(results)
        assert (results is not None)

        content_path = os.path.join(nextcloud_path, 'duct_dots', 'urban_geometries_geojson', 'building.geojson')
        project = results[0]

        # try to import with correct object id
        try:
            result = self._proxy.upload_dataset(project.id, content_path, UrbanGeometries.DATA_TYPE)
            object_id = result.datasets[0].obj_id

            result = self._proxy.fetch_datasets(project.id)
            n_available = len(result.available)

            result = self._proxy.import_dataset(project.id, object_id, 'my dataset')
            print(result)
            assert result.name == 'my dataset'
            object_id = result.obj_id

            result = self._proxy.fetch_datasets(project.id)
            print(result)
            assert len(result.available) == n_available + 1

            # delete the dataset
            result = self._proxy.delete_dataset(project.id, object_id)
            print(result)
            assert result.name == 'my dataset'

            result = self._proxy.fetch_datasets(project.id)
            print(result)
            assert len(result.available) == n_available

        except Exception as e:
            print(e)
            assert False

    def test_upload_import_as_zone_config(self):
        results = self._proxy.get_projects()
        print(results)
        assert (results is not None)

        content_path = os.path.join(nextcloud_path, 'duct_dots', 'urban_geometries_shp.zip')
        project = results[0]

        # try to import with correct object id
        try:
            # determine the zone id used for selected import
            zones = self._server.get_project(project.id).geometries(GeometryType.zone).content()
            selected_zone_id = None
            for feature in zones['features']:
                name = feature['properties']['name']
                if name == 'SESZ06':  # that's the name of the zone where the buildings are inside
                    selected_zone_id = feature['id']
                    break

            result: UploadDatasetResponse = \
                self._proxy.upload_dataset(project.id, content_path, UrbanGeometries.DATA_TYPE)
            bld_object_id = result.datasets[0].obj_id
            veg_object_id = result.datasets[1].obj_id
            lc_object_id = result.datasets[2].obj_id

            configs: List[ZoneConfiguration] = self._proxy.get_zone_configs(self._project.id, selected_zone_id)
            assert len(configs) == 1

            # create a new configuration
            result: Dict[int, ZoneConfiguration] = \
                self._proxy.add_zone_configs(project.id, 'my config', selected_zones=[selected_zone_id], datasets={
                    GeometryType.building: bld_object_id,
                    GeometryType.vegetation: veg_object_id,
                    GeometryType.landcover: lc_object_id
                })
            assert selected_zone_id in result
            assert result[selected_zone_id].name == 'my config'
            assert len(result[selected_zone_id].building_ids) == 653
            assert len(result[selected_zone_id].vegetation_ids) == 3716
            assert len(result[selected_zone_id].landcover_ids) == 662

            configs: List[ZoneConfiguration] = self._proxy.get_zone_configs(self._project.id, selected_zone_id)
            assert len(configs) == 2

            # delete the latest configuration
            config_id = configs[-1].config_id
            zone_config = self._proxy.delete_zone_config(self._project.id, config_id)
            assert (zone_config is not None)
            assert (zone_config.config_id == config_id)

            configs: List[ZoneConfiguration] = self._proxy.get_zone_configs(self._project.id, 12)
            assert len(configs) == 1

        except Exception as e:
            print(e)
            assert False

    def test_vf_mixer(self):
        # get mixer
        project = self._server.get_project(self._project.id)
        mixer = project.vf_mixer

        # update the mixer with a specific LCZ map
        lcz_path = os.path.join(nextcloud_path, 'duct_dots', 'lcz-map_vivek.tiff')
        lcz_obj = self._context.upload_content(lcz_path, LocalClimateZoneMap.DATA_TYPE, 'tiff', False, False)
        mixer.update_lcz(lcz_obj.meta.obj_id, self._context)

        module_settings = {
            'landuse-landcover': {
                'lcz_obj_id': lcz_obj.meta.obj_id
            },
            'vegetation-fraction': {
                f'p_lcz{i + 1}': VegetationFractionModule.vf_defaults[i] for i in range(10)
            }
        }

        # export the LCZ and VF maps
        lcz_export_path = os.path.join(self._wd_path, 'lcz.export.tiff')
        vf_export_path = os.path.join(self._wd_path, 'vf.export.tiff')
        mixer.export_lcz_and_vf(module_settings, lcz_export_path, vf_export_path, self._context)
        assert os.path.isfile(lcz_export_path)
        assert os.path.isfile(vf_export_path)

        result = mixer.raster_lcz()
        assert result is not None
        assert result['type'] == 'heatmap'

        result = mixer.raster_vf(module_settings['vegetation-fraction'])
        assert result is not None
        assert result['type'] == 'heatmap'

        result = self._server.get_module_raster(self._project.id, 'vegetation-fraction',
                                                parameters=json.dumps({'module_settings': module_settings}),
                                                user=self._user)
        assert result is not None
        assert len(result) == 1
        assert result[0]['type'] == 'heatmap'

    def test_veg_frac_mod_make_marks(self):
        for i in range(10):
            v_default = VegetationFractionModule.vf_defaults[i]
            v_max = VegetationFractionModule.vf_defaults[i] + 10 if i < (7 - 1) else VegetationFractionModule.vf_defaults[i]  # default is max for LCZ7-10
            marks = _make_marks(v_default, v_max)
            print(marks)


if __name__ == '__main__':
    unittest.main()
