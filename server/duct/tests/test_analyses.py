import json
import logging
import os
import shutil
import time
import unittest

from tests.base_testcase import create_wd, create_rnd_hex_string

from duct.analyses.mesoscale_urban_climate import MesoscaleUrbanClimateAnalysis
from saas.core.exceptions import SaaSRuntimeException
from saas.core.helpers import read_json_from_file, validate_json, get_timestamp_now
from saas.core.keystore import Keystore
from saas.core.logging import Logging
from saas.core.schemas import GithubCredentials, SSHCredentials
from saas.sdk.app.auth import UserDB, UserAuth
from saas.sdk.base import connect

from duct.analyses.microscale_urban_climate import MicroscaleUrbanClimateAnalysis
from explorer.analysis.base import Analysis, AnalysisContext
from explorer.bdp import BaseDataPackageDB
from explorer.dots.area_of_interest import AreaOfInterest
from explorer.dots.dot import ImportableDataObjectType, DataObjectType
from explorer.module.base import BuildModule
from explorer.project import AnalysisContextImpl, make_analysis_id, DBAnalysisRun
from explorer.proxy import ExplorerProxy
from explorer.renderer.base import NetworkRenderer
from explorer.schemas import AnalysisResult, ZonesConfigurationMapping
from explorer.server import ExplorerServer

Logging.initialise(logging.INFO)
logger = Logging.get(__name__, level=logging.DEBUG)

nextcloud_path = os.path.join(os.environ['HOME'], 'Nextcloud', 'DT-Lab', 'Testing')
bdps_path = os.path.join(nextcloud_path, 'base_data_packages')
bdp_id = '4fc2e31f6864f856db6c24463a98b4e93954bc97d89e807d702a0343507b35d4'
# bdp_id = ''
duct_fom_commit_id = '3ff2b1a'


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

        # create a scene
        module_settings = {}
        zone_config_mapping = ZonesConfigurationMapping.empty()
        cls._scene = cls._proxy.create_scene(cls._project.id, 'the scene', zone_config_mapping, module_settings)

    @classmethod
    def tearDownClass(cls):
        if cls._server is not None:
            # # undeploy processor
            # cls._proc.undeploy()

            # shutdown server
            cls._server.shutdown()

            # delete working directory
            shutil.rmtree(cls._wd_path, ignore_errors=True)

    def _helper_create_analysis_context(self, analysis: Analysis, analysis_parameters: dict = None,
                                        aoi_obj_id: str = None) -> AnalysisContext:
        project = self._server.get_project(self._project.id)

        # create an analysis group
        analysis_parameters = analysis_parameters if analysis_parameters else {}
        group = self._proxy.create_analysis_group(self._project.id, analysis.name(), 'group name', analysis_parameters)

        # create analysis id and path
        analysis_id = make_analysis_id(group.id, self._scene.id, '')
        analysis_path = os.path.join(self._wd_path, analysis_id)
        os.makedirs(analysis_path, exist_ok=True)

        # create the analysis run record
        with project._session() as session:
            # create db record
            record = DBAnalysisRun(
                id=analysis_id, project_id=self._project.id, group_id=group.id, scene_id=self._scene.id,
                name=analysis_id, type=analysis.name(), type_label=analysis.label(), username=self._user.login,
                t_created=get_timestamp_now(), status='initialised', progress=0,
                checkpoint=AnalysisContextImpl.Checkpoint(name='initialised', args={}).dict(),
                results={}
            )
            session.add(record)
            session.commit()

        context = AnalysisContextImpl(project, analysis_id, aoi_obj_id, self._context, analysis, project._session)
        os.makedirs(context.analysis_path, exist_ok=True)

        return context

    def test_miuc_prepare_input(self):
        analysis = MicroscaleUrbanClimateAnalysis()
        sdk = self._context

        # upload area of interest to DOR
        aoi_obj_path = os.path.join(nextcloud_path, 'duct_dots', 'aoi.geojson')
        aoi_obj = sdk.upload_content(aoi_obj_path, AreaOfInterest.DATA_TYPE, 'geojson', False)

        # upload some building AH data to DOR
        bld_ah_path = os.path.join(nextcloud_path, 'ucmpalm_prep', 'input', 'bld_ah_profile.csv')
        bld_ah_obj = sdk.upload_content(bld_ah_path, 'duct.building-ah-profile', 'csv', False)

        # create analysis context
        context = self._helper_create_analysis_context(analysis, aoi_obj_id=aoi_obj.meta.obj_id)

        location, bbox = analysis._determine_domain(context)
        assert location == (103.73851217742049, 1.3401828018998154)
        assert bbox.west == 103.72988018670357
        assert bbox.north == 1.3488615392842194
        assert bbox.east == 103.74714410739787
        assert bbox.south == 1.331503975344926

        # copy/create areas to wd path
        shutil.copyfile(aoi_obj_path, os.path.join(self._wd_path, 'aoi.geojson'))
        with open(os.path.join(self._wd_path, 'domain.geojson'), 'w') as f:
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

        lc_obj, bld_obj, veg_obj = analysis._prepare_input_data(context, self._scene, bbox.as_shapely_polygon(),
                                                                ah_profile_obj_id=bld_ah_obj.meta.obj_id)
        assert lc_obj is not None
        assert bld_obj is not None
        assert veg_obj is not None

    def test_micuc_extract_feature(self):
        ## MESO
        content_paths = {
            '#': os.path.join(nextcloud_path, 'ucmwrf_sim', 'output', 'd04-near-surface-climate')
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
        export_path = os.path.join(self._wd_path, 'meso.export')
        json_path = os.path.join(self._wd_path, 'meso.json')
        parameters = {
            'time': 0
        }
        project = None

        analysis = MesoscaleUrbanClimateAnalysis()
        analysis.extract_feature(content_paths, result, parameters, project, self._context, export_path, json_path)


        ## MICRO
        content_paths = {
            '#': os.path.join(nextcloud_path, 'ucmpalm_sim', 'output', 'climatic-variables')
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
        export_path = os.path.join(self._wd_path, 'micro.export')
        json_path = os.path.join(self._wd_path, 'micro.json')
        parameters = {
            'time': 1
        }
        project = None

        analysis = MicroscaleUrbanClimateAnalysis()
        analysis.extract_feature(content_paths, result, parameters, project, self._context, export_path, json_path)


if __name__ == '__main__':
    unittest.main()
