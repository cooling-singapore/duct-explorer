import os
import tempfile
import time

import pytest
from dotenv import load_dotenv
from saas.core.keystore import Keystore
from saas.core.schemas import GithubCredentials
from saas.node import Node
from saas.sdk.base import connect
from saas.tests.base_testcase import PortMaster, create_rnd_hex_string
from saas.sdk.app.auth import UserDB, UserAuth

from explorer.analysis.base import Analysis
from explorer.bdp.bdp import DUCTBaseDataPackageDB
from explorer.dots.dot import ImportableDataObjectType, DataObjectType
from explorer.dots.duct_ahprofile import AnthropogenicHeatProfile
from explorer.dots.duct_lcz import LocalClimateZoneMap
from explorer.module.base import BuildModule
from explorer.proxy import ExplorerProxy
from explorer.renderer.base import NetworkRenderer
from explorer.schemas import BaseDataPackage, BoundingBox, Dimensions, ZonesConfigurationMapping
from explorer.server import ExplorerServer

load_dotenv()

TEST_DATA_PATH = os.environ['TEST_DATA_PATH']
EXPLORER_DATA_PATH = os.path.join(TEST_DATA_PATH, 'duct_explorer')

DUCT_FOM_COMMIT_ID = 'b7be6a1'
DUCT_FOM_REPOSITORY = 'https://github.com/cooling-singapore/duct-fom'


@pytest.fixture(scope="session")
def bdp_source_path():
    return os.path.join(TEST_DATA_PATH, 'bdp_files', 'bdp-duct.v27')


@pytest.fixture(scope="session")
def wd_path():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture(scope="session")
def node_path():
    return os.path.join(TEST_DATA_PATH, '_node')


@pytest.fixture(scope="session")
def node_keystore(node_path):
    keystore_id_path = os.path.join(node_path, 'keystore_id')
    if os.path.exists(keystore_id_path):
        with open(keystore_id_path, 'r') as f:
            keystore_id = f.readline().strip()

        keystore_path = os.path.join(node_path, f"{keystore_id}.json")
        keystore = Keystore.load(keystore_path, 'password')

    else:
        keystore = Keystore.create(node_path, 'node', 'node@somwhere.com', 'password')

        with open(keystore_id_path, 'w') as f:
            f.write(f"{keystore.identity.id}\n")

    keystore.github_credentials.update(
        DUCT_FOM_REPOSITORY, GithubCredentials(
            login=os.environ['GITHUB_USERNAME'], personal_access_token=os.environ['GITHUB_TOKEN']
        )
    )

    return keystore


@pytest.fixture(scope="session")
def node_rest_address():
    return PortMaster.generate_rest_address()


@pytest.fixture(scope="session")
def node_p2p_address():
    return PortMaster.generate_p2p_address()


@pytest.fixture(scope="session")
def node_instance(node_path, node_keystore, node_rest_address, node_p2p_address, bdp_source_path):
    instance = Node.create(
        node_keystore, node_path, node_p2p_address, rest_address=node_rest_address,
        enable_dor=True, enable_rti=True, retain_job_history=True, strict_deployment=False
    )

    time.sleep(1)

    yield instance

    instance.shutdown()

    time.sleep(1)


@pytest.fixture(scope="session")
def node_context(node_rest_address, node_instance, node_keystore):
    context = connect(node_rest_address, node_keystore)
    yield context


@pytest.fixture(scope="session")
def bdp_id(node_path, node_context, bdp_source_path):
    bdp_id_path = os.path.join(node_path, 'bdp_id')
    if os.path.isfile(bdp_id_path):
        with open(bdp_id_path, 'r') as f:
            bdp_id = f.readline().strip()
            return bdp_id

    else:
        caz_processed_path = os.path.join(bdp_source_path, 'city-admin-zones.processed')
        luz_processed_path = os.path.join(bdp_source_path, 'land-use.processed')
        lc_processed_path = os.path.join(bdp_source_path, 'land-cover.processed')
        bld_processed_path = os.path.join(bdp_source_path, 'building-footprints.processed')
        veg_processed_path = os.path.join(bdp_source_path, 'vegetation.processed')
        assert os.path.isfile(caz_processed_path) and \
               os.path.isfile(luz_processed_path) and \
               os.path.isfile(bld_processed_path) and \
               os.path.isfile(veg_processed_path) and \
               os.path.isfile(lc_processed_path)

        # do we have already the BDP stored in this node?
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
                'path': os.path.join(bdp_source_path, 'lcz-baseline'),
                'type': LocalClimateZoneMap.DATA_TYPE,
                'format': 'tiff'
            },
            'sh-traffic-baseline': {
                'path': os.path.join(bdp_source_path, 'sh-traffic-baseline'),
                'type': AnthropogenicHeatProfile.DATA_TYPE,
                'format': 'geojson'
            },
            'sh-traffic-ev100': {
                'path': os.path.join(bdp_source_path, 'sh-traffic-ev100'),
                'type': AnthropogenicHeatProfile.DATA_TYPE,
                'format': 'geojson'
            },
            'sh-power-baseline': {
                'path': os.path.join(bdp_source_path, 'sh-power-baseline'),
                'type': AnthropogenicHeatProfile.DATA_TYPE,
                'format': 'geojson'
            },
            'lh-power-baseline': {
                'path': os.path.join(bdp_source_path, 'lh-power-baseline'),
                'type': AnthropogenicHeatProfile.DATA_TYPE,
                'format': 'geojson'
            },
            'description': {
                'path': os.path.join(bdp_source_path, 'description'),
                'type': 'BDPDescription',
                'format': 'markdown'
            }
        }

        # upload BDP
        bdp = BaseDataPackage.upload(
            node_context, 'Singapore', 'Public Dataset (test)',
            BoundingBox(west=103.55161, north=1.53428, east=104.14966, south=1.19921),
            Dimensions(width=211, height=130), 'Asia/Singapore', mapping
        )

        # create the BDP
        paths = DUCTBaseDataPackageDB.create(node_path, bdp, node_context)
        assert paths is not None
        assert os.path.isfile(paths[0])
        assert os.path.isfile(paths[1])
        assert '4fc2e31f6864f856db6c24463a98b4e93954bc97d89e807d702a0343507b35d4' in paths[0]
        assert '4fc2e31f6864f856db6c24463a98b4e93954bc97d89e807d702a0343507b35d4' in paths[1]

        with(bdp_id_path, 'w') as f:
            f.write(bdp.id)

        return bdp.id


@pytest.fixture(scope="session")
def explorer_rest_address():
    return PortMaster.generate_rest_address()


@pytest.fixture(scope="session")
def explorer_user(wd_path, node_context):
    # initialise user Auth and DB
    UserAuth.initialise(create_rnd_hex_string(32))
    UserDB.initialise(wd_path)

    password = 'password'
    user = UserDB.add_user('john.doe@email.com', 'John Doe', password)

    node_context.publish_identity(user.identity)
    return user


@pytest.fixture(scope="session")
def explorer_server(wd_path, node_keystore, node_rest_address, explorer_rest_address, explorer_user, node_path, bdp_id):
    # create Dashboard server and proxy
    server = ExplorerServer(explorer_rest_address, node_rest_address, wd_path)

    for c in ExplorerServer.search_for_classes(['explorer.analysis'], Analysis):
        server.add_analysis_instance(c())

    for c in ExplorerServer.search_for_classes(['explorer.module'], BuildModule):
        server.add_build_module(c())

    for c in ExplorerServer.search_for_classes(['explorer.dots'], DataObjectType):
        if c != ImportableDataObjectType:
            server.add_data_object_type(c())

    for c in ExplorerServer.search_for_classes(['explorer.renderer'], NetworkRenderer):
        server.add_network_renderers(c())

    server.import_bdp(node_path, bdp_id)

    server.startup()

    # initialise the server
    server.initialise(explorer_user)

    yield server

    server.shutdown()


@pytest.fixture(scope="session")
def explorer_proxy(explorer_rest_address, explorer_user, explorer_server):
    proxy = ExplorerProxy(explorer_rest_address, explorer_user, 'password')
    return proxy


@pytest.fixture(scope="session")
def explorer_project(explorer_proxy):
    # create test project
    info = explorer_proxy.info()
    bdp = info.bdps[0].packages[0]
    project = explorer_proxy.create_project(bdp.city, bdp.id, 'test project')

    # wait for the project to be initialised
    project_id = project.id
    while project.state != 'initialised':
        time.sleep(1)
        projects = explorer_proxy.get_projects()
        projects = {project.id: project for project in projects}
        project = projects[project_id]

    print(f"project {project_id} initialised")

    yield project

    explorer_proxy.delete_project(project_id)


@pytest.fixture(scope="session")
def explorer_scene(explorer_proxy, explorer_project):
    module_settings = {}
    zone_config_mapping = ZonesConfigurationMapping.empty()
    scene = explorer_proxy.create_scene(explorer_project.id, 'Default', zone_config_mapping, module_settings)

    print(f"scene {scene.id} created")

    return scene
