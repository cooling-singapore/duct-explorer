import json
import logging
import os
import shutil
import time
import unittest
from typing import Optional

from saas.core.exceptions import SaaSRuntimeException
from saas.core.helpers import read_json_from_file, validate_json
from saas.core.keystore import Keystore
from saas.core.logging import Logging
from saas.core.schemas import GithubCredentials, SSHCredentials
from saas.dor.schemas import DataObject
from saas.sdk.app.auth import UserDB, UserAuth
from saas.sdk.base import SDKProcessor, connect, SDKCDataObject
from tests.base_testcase import create_rnd_hex_string, create_wd

from duct.analyses.mesoscale_urban_climate import normalise
from explorer.analysis.base import Analysis, AnalysisStatus
from explorer.bdp import BaseDataPackageDB
from explorer.dots.dot import ImportableDataObjectType, DataObjectType
from explorer.module.base import BuildModule
from explorer.proxy import ExplorerProxy
from explorer.renderer.base import NetworkRenderer
from explorer.schemas import AnalysisInfo, Scene, ZonesConfigurationMapping
from explorer.server import ExplorerServer, EnquireAnalysisResponse

Logging.initialise(logging.INFO)
logger = Logging.get(__name__, level=logging.DEBUG)

nextcloud_path = os.path.join(os.environ['HOME'], 'Nextcloud', 'DT-Lab', 'Testing')
bdps_path = os.path.join(nextcloud_path, 'base_data_packages')
bdp_id = '4fc2e31f6864f856db6c24463a98b4e93954bc97d89e807d702a0343507b35d4'
# bdp_id = ''
duct_fom_commit_id = 'b7be6a1'


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


class ExplorerAnalysisTestCase(unittest.TestCase):
    _server_address = ('127.0.0.1', 5021)
    _node_address = ('127.0.0.1', 5001)
    _wd_path = None
    _server = None
    _proxy = None
    _project = None
    _scene = None

    _keystore_path = None
    _datastore_path = None
    _owner = None
    _user = None
    _context = None

    @classmethod
    def setUpClass(cls):
        # create folders
        cls._wd_path = create_wd()
        cls._keystore_path = os.path.join(cls._wd_path, 'keystore')
        os.makedirs(cls._keystore_path, exist_ok=True)

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
        cls._server = ExplorerServer(cls._server_address, cls._node_address, cls._wd_path)

        for c in ExplorerServer.search_for_classes(['duct.analyses'], Analysis):
            cls._server.add_analysis_instance(c())

        for c in ExplorerServer.search_for_classes(['duct.modules'], BuildModule):
            cls._server.add_build_module(c())

        for c in ExplorerServer.search_for_classes(['duct.dots'], DataObjectType):
            if c != ImportableDataObjectType:
                cls._server.add_data_object_type(c())

        for c in ExplorerServer.search_for_classes(['duct.renderer'], NetworkRenderer):
            cls._server.add_network_renderers(c())

        cls._server.startup()
        cls._proxy = ExplorerProxy(cls._server_address, cls._user, password)

        # get SaaS context
        cls._context = connect(cls._node_address, cls._user.keystore)

        # make identities known
        cls._context.publish_identity(cls._owner.identity)
        cls._context.publish_identity(cls._user.identity)

        if not BaseDataPackageDB.exists(bdps_path, bdp_id):
            raise RuntimeError(f"BDP doesn't exist")

        else:
            cls._server.import_bdp(bdps_path, bdp_id)

        # initialise the server
        cls._server.initialise(cls._owner)

        # create test project
        info = cls._proxy.info()
        bdp = info.bdps[0].packages[0]
        cls._project = cls._proxy.create_project(bdp.city, bdp.id, 'test project')
        print(cls._project)

        # wait for the project to be initialised
        project_id = cls._project.id
        while cls._project.state != 'initialised':
            time.sleep(5)
            projects = cls._proxy.get_projects()
            projects = {project.id: project for project in projects}
            cls._project = projects[project_id]

        print(f"project {project_id} initialised")

    @classmethod
    def tearDownClass(cls):
        if cls._server is not None:
            # # undeploy processor
            # cls._proc.undeploy()

            # shutdown server
            cls._server.shutdown()

            # delete working directory
            shutil.rmtree(cls._wd_path, ignore_errors=True)

    def _helper_upload_and_deploy(self, url: str, commit_id: str, proc_path: str, proc_config: str,
                                  ssh_profile: str = None) -> SDKProcessor:

        gpp = self._context.upload_gpp(url, commit_id, proc_path, proc_config)
        exec_node = self._context.rti()
        proc = gpp.deploy(exec_node, ssh_profile=ssh_profile)
        return proc

    def _helper_upload_data(self, content_path: str, data_type: str, data_format: str) -> SDKCDataObject:
        obj = self._context.upload_content(
            content_path=content_path,
            data_type=data_type,
            data_format=data_format,
            access_restricted=False
        )
        obj.update_tags([
            DataObject.Tag(key='project_id', value=self._project.id)
        ])

        return obj

    def _helper_run_analysis(self, analysis_type: str, parameters: dict, scene: Scene,
                             resume_if_timeout: bool = True) -> (str, str, str):

        # enquire on analysis first before submitting it
        result: EnquireAnalysisResponse = \
            self._proxy.enquire_analysis(self._project.id, analysis_type, scene.id, parameters)
        print(result)
        assert(not result.cached_results_available)

        # create an analysis group
        group = self._proxy.create_analysis_group(self._project.id, analysis_type, 'group name', parameters)
        print(group)

        # submit the analysis
        info: AnalysisInfo = self._proxy.submit_analysis(self._project.id, group.id, scene.id, 'test')
        print(info)

        while True:
            time.sleep(1)

            info: AnalysisInfo = self._proxy.get_analysis(self._project.id, info.analysis_id)
            print(f"{info.analysis_id} [{info.status}] -> {info.progress}%")

            if info.status in [AnalysisStatus.CANCELLED.value, AnalysisStatus.FAILED.value,
                               AnalysisStatus.COMPLETED.value]:
                break

        return scene.id, group.id, info.analysis_id

    def test_analyse_urban_wind_corridors_via_endpoints(self):
        analysis_type = 'wind-corridor-potential'

        # create a scene
        module_settings = {}
        zone_config_mapping = ZonesConfigurationMapping.empty()
        scene = self._proxy.create_scene(self._project.id, 'the scene', zone_config_mapping, module_settings)

        # deploy the UWC processor
        proc = self._context.find_processor_by_id('9536fa1b0fc6b6d7612d648a8435b6085c08872a329d26fb90d8927a1d9876ff')
        if proc is None:
            proc = self._helper_upload_and_deploy("https://github.com/cooling-singapore/duct-fom", duct_fom_commit_id,
                                                  "ucm-mva/proc_uwc", "gce-ubuntu-22.04")
            logger.info(f"proc_id (UWC): {proc.descriptor.proc_id}")

        # deploy the UVP processor
        proc = self._context.find_processor_by_id('53229e943b22f2afa34515e68e959116d2512398726ea44aee8e1ccee3d3417b')
        if proc is None:
            proc = self._helper_upload_and_deploy("https://github.com/cooling-singapore/duct-fom", duct_fom_commit_id,
                                                  "ucm-mva/proc_uvp", "gce-ubuntu-22.04")

            logger.info(f"proc_id (UVP): {proc.descriptor.proc_id}")

        # create project and run analysis
        parameters = {'spatial_resolution': 600}
        scene_id, group_id, analysis_id = self._helper_run_analysis(analysis_type, parameters, scene)

        # get result
        result: dict = self._proxy.get_result(self._project.id, analysis_id, 'wind-corridors-ns', {})
        assert(result is not None)
        print(json.dumps(result))

        # get delta
        result: dict = self._proxy.get_result_delta(self._project.id, 'wind-corridors-ns',
                                                    analysis_id, analysis_id, {}, {})
        assert(result is not None)
        print(json.dumps(result))

        # download result
        download_path = os.path.join(self._wd_path, 'wind-corridors-ns.zip')
        self._proxy.export_result(self._project.id, analysis_id, 'wind-corridors-ns', {}, download_path)
        assert (os.path.isfile(download_path))

        # download delta
        download_path = os.path.join(self._wd_path, 'wind-corridors-ns-delta.zip')
        self._proxy.export_result_delta(self._project.id, 'wind-corridors-ns', analysis_id, analysis_id, {}, {},
                                        download_path)
        assert (os.path.isfile(download_path))

        # enquire on analysis: cached results should be available now
        result: EnquireAnalysisResponse = \
            self._proxy.enquire_analysis(self._project.id, analysis_type, scene_id, parameters)
        print(json.dumps(result.dict(), indent=2))
        assert result.cached_results_available

        # delete the analysis
        info: Optional[AnalysisInfo] = self._proxy.delete_analysis(self._project.id, analysis_id)
        print(result)
        assert(info is not None)

    def test_analyse_mesoscale_urban_climate_normalise(self):
        input_path = os.path.join(nextcloud_path, 'ucmwrf-sim', 'output', 'd04-near-surface-climate')
        output_path = os.path.join(nextcloud_path, 'ucmwrf-sim', 'output', 'd04-near-surface-climate_normalised')

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

    def test_analyse_mesoscale_urban_climate_via_endpoints(self):
        analysis_type = 'mesoscale-urban-climate'

        # proc_prep = self._helper_upload_and_deploy("https://github.com/cooling-singapore/duct-fom",
        #                                            duct_fom_commit_id, "ucm-wrf/proc_prep", "gce-ubuntu-20.04",
        #                                            ssh_profile='gce-ucmwrf')
        #
        # proc_sim = self._helper_upload_and_deploy("https://github.com/cooling-singapore/duct-fom",
        #                                           duct_fom_commit_id, "ucm-wrf/proc_sim_gcp", "default",
        #                                           ssh_profile='gce-ucmwrf')

        # get mixer and refresh it
        # project = self._server.get_project(self._project.id)
        # project.ah_mixer.refresh(self._context)
        # project.vf_mixer.refresh(self._context)

        # create project and run analysis
        parameters = {
            'dt_sim_warmup': '24_12',
            'use_debug_config': False,
            'date': '2016-04-01'
        }
        scene_id, group_id, analysis_id = self._helper_run_analysis(analysis_type, parameters)

        # get result
        result: dict = self._proxy.get_result(self._project.id, analysis_id, 'nsc-stats', {
            'variable': 'at',
            'time': '0150000'
        })
        assert(result is not None)
        print(json.dumps(result))

        # get delta
        result: dict = self._proxy.get_result_delta(self._project.id, 'nsc-stats', analysis_id, analysis_id,
                                                    {'variable': 'at', 'component': 'mean', 'time': '0150000'},
                                                    {'variable': 'at', 'component': 'mean', 'time': '0150000'})
        assert(result is not None)
        print(json.dumps(result))

        # enquire on analysis: cached results should be available now
        result: EnquireAnalysisResponse = \
            self._proxy.enquire_analysis(self._project.id, analysis_type, scene_id, parameters)
        print(json.dumps(result.dict(), indent=2))
        assert result.cached_results_available

        # delete the analysis
        info: Optional[AnalysisInfo] = self._proxy.delete_analysis(self._project.id, analysis_id)
        print(result)
        assert(info is not None)

        # delete the data objects
        for obj in ah_objects:
            obj.delete()

    def test_analyse_microscale_urban_winds_via_endpoints(self):
        analysis_type = 'microscale-urban-winds'

        proc_prep = self._helper_upload_and_deploy("https://github.com/cooling-singapore/duct-fom",
                                                   duct_fom_commit_id, "ucm-iem/proc_prep", "default")

        proc_sim = self._helper_upload_and_deploy("https://github.com/cooling-singapore/duct-fom",
                                                  duct_fom_commit_id, "ucm-iem/proc_sim", "aspire1",
                                                  ssh_profile='nscc')

        # create project and run analysis
        west = 103.81071
        south = 1.28859
        east = 103.81533
        north = 1.2923
        parameters = {
            'bounding_box': f"free:5:{west}:{north}:{east}:{north}:{east}:{south}:{west}:{south}:{west}:{north}",
            'wind_direction': 0.0,
            'wind_speed': 1.0
        }
        scene_id, group_id, analysis_id = self._helper_run_analysis(analysis_type, parameters)

        # get result
        result: dict = self._proxy.get_result(self._project.id, analysis_id, 'wind-speed', {})
        assert(result is not None)
        print(json.dumps(result))

        # get delta
        result: dict = self._proxy.get_result_delta(self._project.id, 'wind-speed', analysis_id, analysis_id, {}, {})
        assert(result is not None)
        print(json.dumps(result))

        # enquire on analysis: cached results should be available now
        result: EnquireAnalysisResponse = \
            self._proxy.enquire_analysis(self._project.id, analysis_type, scene_id, parameters)
        print(json.dumps(result.dict(), indent=2))
        assert result.cached_results_available

        # delete the analysis
        info: Optional[AnalysisInfo] = self._proxy.delete_analysis(self._project.id, analysis_id)
        print(result)
        assert(info is not None)

    def test_analyse_building_energy_and_photovoltaics_via_endpoints(self):
        analysis_type = 'building-energy-and-photovoltaics'

        self._helper_upload_and_deploy("https://github.com/cooling-singapore/duct-fom",
                                       duct_fom_commit_id, "bem-cea/processor_gen", "default")

        self._helper_upload_and_deploy("https://github.com/cooling-singapore/duct-fom",
                                       duct_fom_commit_id, "bem-cea/processor_sim", "default")

        self._helper_upload_and_deploy("https://github.com/cooling-singapore/duct-fom",
                                       duct_fom_commit_id, "bem-cea/processor_eei", "default")

        from duct.analyses.building_energy_efficiency import DEFAULT_WEATHER, DEFAULT_BUILDING_TYPE_MAP
        parameters = {
            "parameters": {
                "building_type_mapping": DEFAULT_BUILDING_TYPE_MAP,
                "default_building_type": "MULTI_RES",
                "building_standard_mapping": {
                    "office": "standard",
                    "residential": "standard",
                    "hotel": "standard",
                    "retail": "standard"
                },
                "default_building_standard": "STANDARD1",
                "commit_id": "sg-sle-database",
                "database_name": "SG_SLE",
                "terrain_height": 0,
                "weather": DEFAULT_WEATHER
            },
            "building_footprints": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "id": 7,
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [
                                        103.8359585,
                                        1.2716031
                                    ],
                                    [
                                        103.8359391,
                                        1.2720658
                                    ],
                                    [
                                        103.8373561,
                                        1.2721251
                                    ],
                                    [
                                        103.8373755,
                                        1.2716624
                                    ],
                                    [
                                        103.8359585,
                                        1.2716031
                                    ]
                                ]
                            ]
                        },
                        "properties": {
                            "id": 393437829,
                            "name": "Unknown:6",
                            "height": 15,
                            "area": 8141.044775976488,
                            "building_type": "Port / Airport"
                        }
                    },
                    {
                        "type": "Feature",
                        "id": 10,
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [
                                        103.8376111,
                                        1.2716728
                                    ],
                                    [
                                        103.8375917,
                                        1.2721355
                                    ],
                                    [
                                        103.8390087,
                                        1.2721948
                                    ],
                                    [
                                        103.839028,
                                        1.2717321
                                    ],
                                    [
                                        103.8376111,
                                        1.2716728
                                    ]
                                ]
                            ]
                        },
                        "properties": {
                            "id": 393437832,
                            "name": "Unknown:9",
                            "height": 15,
                            "area": 8140.721484274703,
                            "building_type": "Port / Airport"
                        }
                    }
                ]
            },
        }
        scene_id, group_id, analysis_id = self._helper_run_analysis(analysis_type, parameters)

        # get result
        result: dict = self._proxy.get_result(self._project.id, analysis_id, 'annual_energy',
                                              {"variable": "energy_consumption"})
        assert(result is not None)
        print(json.dumps(result))

        # get delta
        result: dict = self._proxy.get_result_delta(self._project.id, 'annual_energy', analysis_id, analysis_id,
                                                    {"variable": "energy_consumption"},
                                                    {"variable": "energy_consumption"})
        assert(result is not None)
        print(json.dumps(result))

        # enquire on analysis: cached results should be available now
        result: EnquireAnalysisResponse = \
            self._proxy.enquire_analysis(self._project.id, analysis_type, scene_id, parameters)
        print(json.dumps(result.dict(), indent=2))
        assert result.cached_results_available

        # delete the analysis
        info: Optional[AnalysisInfo] = self._proxy.delete_analysis(self._project.id, analysis_id)
        print(result)
        assert(info is not None)


if __name__ == '__main__':
    unittest.main()
