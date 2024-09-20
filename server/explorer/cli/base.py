import time
import traceback
from typing import Optional, Dict

from InquirerPy.base import Choice
from pydantic.class_validators import List
from saas.core.logging import Logging
from saas.sdk.app.auth import UserAuth, UserDB
from saas.sdk.app.exceptions import AppRuntimeError
from saas.sdk.base import connect

from saas.sdk.cli.commands import UserInit, UserCreate, UserRemove, UserEnable, UserDisable, UserList, UserUpdate
from saas.sdk.cli.exceptions import CLIRuntimeError
from saas.sdk.cli.helpers import CLIParser, CLICommand, CLICommandGroup, Argument, prompt_if_missing, \
    prompt_for_string, extract_address, prompt_for_confirmation, load_keystore, prompt_for_selection

import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from tabulate import tabulate

from explorer.bdp import BaseDataPackageDB
from explorer.dots.dot import ImportableDataObjectType, DataObjectType
from explorer.project import DBAnalysisRun, DBAnalysisGroup, DBScene
from explorer.renderer.base import NetworkRenderer
from explorer.schemas import ExplorerRuntimeError, BaseDataPackage, Dimensions, BoundingBox, ProjectInfo
from explorer.server import ExplorerServer
from explorer.analysis.base import Analysis
from explorer.module.base import BuildModule
from explorer.view.base import View

logger = Logging.get('explorer.cli')

Base = declarative_base()


class BDPCreate(CLICommand):
    def __init__(self, bdp_spec: dict, bdp_class,
                 name: str = 'create', description: str = 'create base data package and upload it to a DOR') -> None:
        self._bdp_spec = bdp_spec
        self._bdp_class = bdp_class

        super().__init__(name, description, arguments=[
            Argument('--bdp_directory', dest='bdp_directory', action='store', required=False,
                     help=f"the directory that contains the base data packages"),
            Argument('--city', dest='city', action='store', required=False,
                     help=f"the name of the city the base data package is associated with"),
            Argument('--name', dest='name', action='store', required=False,
                     help=f"the name of the base data package"),
            Argument('--bounding_box', dest='bounding_box', action='store', required=False,
                     help=f"the bounding box as a comma-separated string of longitudes and latitudes: west, north, "
                          f"east, south (e.g., '103.55161, 1.53428, 104.14966, 1.19921')"),
            Argument('--dimension', dest='dimension', action='store', required=False,
                     help=f"the dimension (width, height) of the domain"),
            Argument('--timezone', dest='timezone', action='store', required=False,
                     help=f"the timezone"),
            Argument('--address', dest='address', action='store', required=False,
                     help=f"the address (host:port) of the node"),
            Argument('file', metavar='file', type=str, nargs=len(bdp_spec),
                     help="files with contents for the base data package")
        ])

    def execute(self, args: dict) -> None:
        # load the keystore
        keystore = load_keystore(args, ensure_publication=False)

        # prompt for missing information
        prompt_if_missing(args, 'bdp_directory', prompt_for_string, message="Enter the base data package directory:")
        prompt_if_missing(args, 'address', prompt_for_string,
                          message="Enter the target SaaS node's REST address [host:port]:",
                          default='127.0.0.1:5001')
        prompt_if_missing(args, 'city', prompt_for_string, message="Enter the name of the city:")
        prompt_if_missing(args, 'name', prompt_for_string, message="Enter the name of the base data package:")
        prompt_if_missing(args, 'bounding_box', prompt_for_string,
                          message="Enter the bounding box [west, north, east, south]:")
        prompt_if_missing(args, 'dimension', prompt_for_string,
                          message="Enter the dimension [width, height]:")
        prompt_if_missing(args, 'timezone', prompt_for_string, message="Enter the timezone:")

        # determine the bounding box
        bbox = args['bounding_box'].split(',')
        bbox = [float(v) for v in bbox]
        bbox = BoundingBox(west=bbox[0], north=bbox[1], east=bbox[2], south=bbox[3])
        bbox.check_sanity()

        # determine the dimension
        dimension = args['dimension'].split(',')
        dimension = [int(v) for v in dimension]
        dimension = Dimensions(width=dimension[0], height=dimension[1])

        timezone = args['timezone']

        # first check if all files exist and if they are files to begin with
        remaining = {}
        for file in args['file']:
            if not os.path.isfile(file):
                raise CLIRuntimeError(f"Not found or not a file: {file}")
            else:
                remaining[file] = os.path.abspath(file)

        # attempt auto mapping
        mapping = dict(self._bdp_spec)
        for name, spec in mapping.items():
            if name in remaining:
                mapping[name]['path'] = remaining.pop(name)
                print(f"Using auto-mapping for '{name}' -> {mapping[name]['path']}")

        # still any remaining?
        if len(remaining) > 0:
            for name, spec in mapping.items():
                if 'path' in spec:
                    continue

                choices = [Choice(path, os.path.basename(path)) for path in remaining]
                selection = prompt_for_selection(choices, f"Select the {spec['type']}/{spec['format']} file to be used "
                                                          f"as '{name}':", allow_multiple=False)
                remaining.pop(selection)
                mapping[name]['path'] = selection

        # prepare the files before uploading to the DOR
        if hasattr(self._bdp_class, 'prepare_files') and callable(getattr(self._bdp_class, 'prepare_files')):
            mapping = self._bdp_class.prepare_files(mapping)

        # upload the files to the DOR and tag accordingly
        print(f"Uploading files...", end='')
        context = connect(extract_address(args['address']), keystore)
        bdp = BaseDataPackage.upload(context, args['city'], args['name'], bbox, dimension, timezone, mapping)
        print(f"done")

        # create the directory if needed
        bdp_directory = os.path.join(args['bdp_directory'])
        if not os.path.isdir(bdp_directory):
            os.makedirs(bdp_directory, exist_ok=True)

        # create the BDP database
        print(f"Creating database...", end='')
        db_path, bdp_path = self._bdp_class.create(bdp_directory, bdp, context)
        print(f"done")

        print(f"Created building base data package {bdp.id}: db={db_path} json={bdp_path}")


class BDPRemove(CLICommand):
    def __init__(self) -> None:
        super().__init__('remove', 'deletes a base data package', arguments=[
            Argument('--bdp_directory', dest='bdp_directory', action='store', required=False,
                     help=f"the directory that contains the base data packages"),
            Argument('--bdp_id', dest='bdp_id', action='store', required=False,
                     help=f"the id of the base data package"),
            Argument('--address', dest='address', action='store', required=False,
                     help=f"the address (host:port) of the node")
        ])

    def execute(self, args: dict) -> None:
        # get the BDP directory
        prompt_if_missing(args, 'bdp_directory', prompt_for_string, message="Enter the base data package directory:")
        bdp_directory = os.path.join(args['bdp_directory'])
        if not os.path.isdir(bdp_directory):
            raise ExplorerRuntimeError(f"Not a directory: {bdp_directory}")

        # get the list of base data packages
        candidates: Dict[str, BaseDataPackage] = {}
        for bdp_id in BaseDataPackageDB.list(bdp_directory):
            bdp_path = os.path.join(bdp_directory, f"{bdp_id}.json")
            try:
                candidates[bdp_id] = BaseDataPackage.parse_file(bdp_path)
            except Exception:
                logger.warning(f"could not load base data package at {bdp_path} -> corrupted?")

        # check if we have an id
        if not args['bdp_id']:
            choices = [
                Choice(bdp_id, name=f"{bdp_id}: {bdp.name} | {bdp.city_name}") for bdp_id, bdp in candidates.items()
            ]
            args['bdp_id'] = prompt_for_selection(choices, f"Select the base data package:", allow_multiple=False)

        elif args['bdp_id'] not in candidates:
            raise ExplorerRuntimeError(f"No base data package '{args['bdp_id']}' found.")

        # load the BDP
        bdp_path = os.path.join(bdp_directory, f"{args['bdp_id']}.json")
        bdp = BaseDataPackage.parse_file(bdp_path)

        prompt_if_missing(args, 'address', prompt_for_string,
                          message="Enter the target SaaS node's REST address [host:port]:",
                          default='127.0.0.1:5001')

        # load the keystore
        keystore = load_keystore(args, ensure_publication=False)

        # find the data objects for this BDP
        context = connect(extract_address(args['address']), keystore)
        objects = {}
        not_found = []
        not_owned = []
        for name, obj_id in bdp.references.items():
            # can we find the data object?
            obj = context.find_data_object(obj_id)
            if not obj:
                not_found.append(f"{name}/{obj_id[:4]}...{-4:}")

            # do we own the data object?
            if obj.meta.owner_iid != keystore.identity.id:
                not_owned.append(f"{name}/{obj_id[:4]}...{obj_id[-4:]}")

            objects[name] = obj

        if not_found or not_owned:
            print("The following issue(s) have been encountered:")
            print(f"- Data objects not found: {' '.join(not_found) if not_found else 'none'}")
            print(f"- Data objects not owned: {' '.join(not_owned) if not_owned else 'none'}")
            raise ExplorerRuntimeError(f"Cannot proceed to delete the base data package")

        # delete all the data objects
        for name, obj in objects.items():
            obj.delete()
            print(f"Data object {name}/{obj.meta.obj_id} deleted.")

        # delete the files
        BaseDataPackageDB.remove(bdp_directory, args['bdp_id'])
        print(f"Removed base data package {args['bdp_id']} at {bdp_directory}")


class BDPList(CLICommand):
    def __init__(self) -> None:
        super().__init__('list', 'lists all available base data package', arguments=[
            Argument('--bdp_directory', dest='bdp_directory', action='store', required=False,
                     help=f"the directory that contains the base data packages")
        ])

    def execute(self, args: dict) -> None:
        # get the BDP directory
        prompt_if_missing(args, 'bdp_directory', prompt_for_string, message="Enter the base data package directory:")
        bdp_directory = os.path.join(args['bdp_directory'])
        if not os.path.isdir(bdp_directory):
            raise ExplorerRuntimeError(f"Not a directory: {bdp_directory}")

        # get the list of base data packages
        result = BaseDataPackageDB.list(bdp_directory)
        if len(result) == 0:
            print(f"No base data packages found at {bdp_directory}")

        else:
            print(f"Found {len(result)} base data packages at {bdp_directory}:")

            # headers
            lines = [
                ['BDP ID', 'NAME', 'CITY', 'BOUNDING BOX', 'DIMENSION', 'TIMEZONE'],
                ['------', '----', '----', '------------', '---------', '--------']
            ]

            for bdp_id in result:
                # load the BDP
                try:
                    bdp_path = os.path.join(bdp_directory, f"{bdp_id}.json")
                    bdp: BaseDataPackage = BaseDataPackage.parse_file(bdp_path)
                    lines.append(
                        [bdp_id, bdp.name, bdp.city_name, bdp.bounding_box.as_str(), bdp.grid_dimension.as_str(),
                         bdp.timezone]
                    )
                except Exception:
                    lines.append([bdp_id, 'corrupted', '', '', '', ''])

            print(tabulate(lines, tablefmt="plain"))
            print()


class DBWrapper:
    def __init__(self, project_path: str):
        # initialise project db
        db_path = os.path.join(project_path, 'project.db')
        print(f"Loading project DB at {db_path}...", end='')
        self._engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(self._engine)
        self._session = sessionmaker(bind=self._engine)
        print(f"done.")

    def get_all_analyses(self) -> List[DBAnalysisRun]:
        with self._session() as session:
            records = session.query(DBAnalysisRun).all()
            return records

    def get_analysis_group(self, group_id: str) -> Optional[DBAnalysisGroup]:
        with self._session() as session:
            record = session.query(DBAnalysisGroup).get(group_id)
            return record

    def get_scene(self, scene_id: str) -> Optional[DBScene]:
        with self._session() as session:
            record = session.query(DBScene).get(scene_id)
            return record


class AnalysisList(CLICommand):
    def __init__(self) -> None:
        super().__init__('list', 'shows a list of all analyses belonging to a project', arguments=[
            Argument('--project_id', dest='project_id', action='store', help=f"id of the project"),
            Argument('--analysis_id', dest='analysis_id', action='store', help=f"id of the analysis")
        ])

    def execute(self, args: dict) -> None:
        # search for all projects
        projects_path = os.path.join(args['datastore'], 'projects')
        choices = []
        for project_id in os.listdir(projects_path):
            # is this a project path?
            project_path = os.path.join(projects_path, project_id)
            if not os.path.isdir(project_path):
                continue

            # do we have a info file?
            info_path = os.path.join(project_path, 'info.json')
            if not os.path.isfile(info_path):
                continue

            # read the project information
            try:
                info = ProjectInfo.parse_file(info_path)
            except Exception:
                print(f"Cannot read info.json file for project {project_id} -> skipping")
                continue

            # add project information to list
            choices.append(
                Choice(name=f"{info.meta.id} ({info.meta.name}) by {info.owner}", value=project_id)
            )

        if len(choices) == 0:
            raise CLIRuntimeError(f"No projects found.")

        prompt_if_missing(args, 'project_id', prompt_for_selection,
                          choices=choices,
                          message="Select the project:")

        # check if the project path exists
        project_path = os.path.join(projects_path, args['project_id'])
        if not os.path.isdir(project_path):
            raise CLIRuntimeError(f"No directory found for project {args['project_id']}.")

        # get all the analyses
        db = DBWrapper(project_path)
        analyses: dict[str, DBAnalysisRun] = {item.id: item for item in db.get_all_analyses()}
        choices = []
        for analysis_id, item in analyses.items():
            choices.append(
                Choice(name=f"{analysis_id} ({item.name} {item.type}) -> {item.status} ({item.progress}%)",
                       value=analysis_id)
            )

        if len(analyses) == 0:
            print(f"No analyses found for project {args['project_id']}")

        else:
            prompt_if_missing(args, 'analysis_id', prompt_for_selection,
                              choices=choices,
                              message="Select the analysis:")

            # check if the analysis exists
            if not args['analysis_id'] in analyses:
                raise CLIRuntimeError(f"Analysis {args['analysis_id']} not found.")
            analysis = analyses[args['analysis_id']]

            print(f"Analysis {analysis.id} Details:")
            print(f"- Name: {analysis.name}")
            print(f"- Type: {analysis.type}")
            print(f"- Status: {analysis.status}")
            print(f"- Progress: {analysis.progress}%")
            print(f"- Created: {analysis.t_created} by {analysis.username}")
            print(f"- Message: {analysis.message if analysis.message else '(none)'}")
            print(f"- Results: {analysis.results if analysis.results else '(none)'}")

            # get the analysis group
            group = db.get_analysis_group(analysis.group_id)
            if group is None:
                print(f"- Analysis Group: {analysis.group_id} -> not found. DB corrupted?")
            else:
                print(f"- Analysis Group: {group.id}")
                print(f"  - Name: {group.name}")
                print(f"  - Type: {group.type}")
                print(f"  - Parameters: {group.parameters}")

            # get the scene
            scene = db.get_scene(analysis.scene_id)
            if scene is None:
                print(f"- Scene: {analysis.scene_id} -> not found. DB corrupted?")
            else:
                print(f"- Scene: {scene.id}")
                print(f"  - Name: {scene.name}")
                print(f"  - caz_alt_mapping: {scene.caz_alt_mapping}")
                print(f"  - bld_footprint_hash: {scene.bld_footprint_hash}")
                print(f"  - module_settings: {scene.module_settings}")

            print()


class Service(CLICommand):
    default_userstore = os.path.join(os.environ['HOME'], '.userstore')
    default_server_address = '127.0.0.1:5021'
    default_node_address = '127.0.0.1:5001'

    def __init__(self):
        super().__init__('service', 'start an Explorer server instance', arguments=[
            Argument('--userstore', dest='userstore', action='store', default=self.default_userstore,
                     help=f"path to the userstore (default: '{self.default_userstore}')"),
            Argument('--bdp_directory', dest='bdp_directory', action='store', required=False,
                     help=f"the directory that contains the base data packages"),
            Argument('--secret_key', dest='secret_key', action='store', required=False,
                     help=f"the secret key used to secure passwords"),
            Argument('--server_address', dest='server_address', action='store',
                     help=f"address used by the server REST service interface (default: '{self.default_server_address}')."),
            Argument('--node_address', dest='node_address', action='store',
                     help=f"address used by the node REST  service interface (default: '{self.default_node_address}')."),
            Argument('--app_domains', dest='app_domains', action='store',
                     help=f"the comma-separated application domains to be used (e.g., duct,infrarisk)")
        ])

    def execute(self, args: dict) -> None:
        # check the userstore directory
        if not os.path.isdir(args['userstore']):
            raise ExplorerRuntimeError(f"Directory does not exist: {args['userstore']}")

        # check the datastore directory
        if not os.path.isdir(args['datastore']):
            raise ExplorerRuntimeError(f"Directory does not exist: {args['datastore']}")

        # get the BDP directory
        prompt_if_missing(args, 'bdp_directory', prompt_for_string, message="Enter the BDP directory:")
        if not os.path.isdir(args['bdp_directory']):
            raise ExplorerRuntimeError(f"BDP Directory does not exist: {args['bdp_directory']}")

        # get the secret key and check it
        prompt_if_missing(args, 'secret_key', prompt_for_string, message="Enter the secret key:", hide=True)
        if len(args['secret_key']) != 32:
            raise ExplorerRuntimeError(f"Secret key must have a size of 32 characters")

        # get the server address
        prompt_if_missing(args, 'server_address', prompt_for_string,
                          message="Enter address for the server REST service:",
                          default=self.default_server_address)

        # get the node address
        prompt_if_missing(args, 'node_address', prompt_for_string,
                          message="Enter address of the SaaS node REST service:",
                          default=self.default_node_address)

        # get the app domains
        prompt_if_missing(args, 'app_domains', prompt_for_string,
                          message="Enter app domains (comma-separated):",
                          default=self.default_node_address)

        # initialise user database and publish all identities
        UserDB.initialise(args['userstore'])
        UserDB.publish_all_user_identities(extract_address(args['node_address']))

        # initialise user authentication
        UserAuth.initialise(args['secret_key'])
        UserAuth._access_token_expires_minutes = 120  # FIXME: this should be removed eventually

        # create server instance
        server = ExplorerServer(extract_address(args['server_address']),
                                extract_address(args['node_address']),
                                args['datastore'])

        # get packages
        domains = args['app_domains'].split(',')
        domains = [d.strip() for d in domains]
        domains.append('explorer')  # add the generic domain
        print(f"using the following app domains: {domains}")

        # add all known views (for the primary domain ONLY! that's because there would be otherwise confusion
        # which 'xyz' view to use if there are multiples.)
        for c in ExplorerServer.search_for_classes([f"{domains[0]}.views"], View):
            server.add_view(c())

        # add all known analyses
        for c in ExplorerServer.search_for_classes([f"{d}.analyses" for d in domains], Analysis):
            server.add_analysis_instance(c())

        # add all build modules
        for c in ExplorerServer.search_for_classes([f"{d}.modules" for d in domains], BuildModule):
            server.add_build_module(c())

        # add all building object types
        for c in ExplorerServer.search_for_classes([f"{d}.dots" for d in domains], DataObjectType):
            if c != ImportableDataObjectType:
                server.add_data_object_type(c())

        # add all network renderers
        for c in ExplorerServer.search_for_classes([f"{d}.renderer" for d in domains], NetworkRenderer):
            server.add_network_renderers(c())

        # startup the server
        server.startup()

        # load all the existing BDPs
        bdp_ids: List[str] = BaseDataPackageDB.list(args['bdp_directory'])
        for bdp_id in bdp_ids:
            print(f"importing base data package {bdp_id}")
            server.import_bdp(args['bdp_directory'], bdp_id)

        # get service user (create if necessary)
        service_users = UserDB.get_user('service_explorer')
        if service_users is None:
            service_users = UserDB.add_user('service_explorer', 'service_explorer', args['secret_key'])
            print(f"using new service user: {service_users.login}")

        else:
            print(f"using existing service user: {service_users.login}")

        # initialise the server
        server.initialise(service_users)

        try:
            # wait for confirmation to terminate the server
            print("Waiting to be terminated...")
            terminate = False
            while not terminate:
                # only show prompt if shell is interactive
                if sys.stdin.isatty():
                    terminate = prompt_for_confirmation("Terminate the server?", default=False)

                else:
                    # wait for a bit...
                    time.sleep(0.5)

        except KeyboardInterrupt:
            print("Received stop signal")
        finally:
            print("Shutting down the node...")
            server.shutdown()


def main():
    try:
        default_datastore = os.path.join(os.environ['HOME'], '.datastore-explorer')
        default_keystore = os.path.join(os.environ['HOME'], '.keystore')
        default_temp_dir = os.path.join(os.environ['HOME'], '.temp')
        default_log_level = 'INFO'

        # common commands
        commands = [
            CLICommandGroup('user', 'manage users', commands=[
                UserInit(),
                UserList(),
                UserCreate(),
                UserRemove(),
                UserEnable(),
                UserDisable(),
                UserUpdate()
            ]),
            CLICommandGroup('analysis', 'manage analysis runs', commands=[
                AnalysisList()
            ]),
            Service()
        ]

        # search for and add domain specific CLI command groups
        for c in ExplorerServer.search_for_classes(['duct', 'infrares'], CLICommandGroup):
            commands.append(c())

        cli = CLIParser('Explorer command line interface (CLI)', arguments=[
            Argument('--datastore', dest='datastore', action='store', default=default_datastore,
                     help=f"path to the datastore (default: '{default_datastore}')"),
            Argument('--keystore', dest='keystore', action='store', default=default_keystore,
                     help=f"path to the keystore (default: '{default_keystore}')"),
            Argument('--temp-dir', dest='temp-dir', action='store', default=default_temp_dir,
                     help=f"path to directory used for intermediate files (default: '{default_temp_dir}')"),
            Argument('--keystore-id', dest='keystore-id', action='store',
                     help=f"id of the keystore to be used if there are more than one available "
                          f"(default: id of the only keystore if only one is available )"),
            Argument('--password', dest='password', action='store',
                     help=f"password for the keystore"),
            Argument('--log-level', dest='log-level', action='store',
                     choices=['INFO', 'DEBUG'], default=default_log_level,
                     help=f"set the log level (default: '{default_log_level}')"),
            Argument('--log-to-aws', dest='log-to-aws', action='store_const', const=False,
                     help="enables logging to AWS CloudWatch"),
            Argument('--log-path', dest='log-path', action='store',
                     help=f"enables logging to file using the given path"),
            Argument('--log-console', dest="log-console", action='store_const', const=False,
                     help=f"enables logging to the console"),

        ], commands=commands)

        cli.execute(sys.argv[1:])
        sys.exit(0)

    except ExplorerRuntimeError as e:
        print(e.reason)
        sys.exit(-1)

    except CLIRuntimeError as e:
        print(e.reason)
        sys.exit(-1)

    except AppRuntimeError as e:
        print(e.reason)
        sys.exit(-1)

    except KeyboardInterrupt:
        print("Interrupted by user.")
        sys.exit(-2)

    except Exception as e:
        trace = ''.join(traceback.format_exception(None, e, e.__traceback__))
        print(f"Unrefined exception:\n{trace}")
        sys.exit(-3)


if __name__ == "__main__":
    main()
