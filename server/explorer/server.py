from __future__ import annotations

import inspect
import json
import os
import pkgutil
import shutil
from typing import List, Dict, Optional, Tuple

from fastapi import Depends, UploadFile, File, Form
from fastapi.responses import StreamingResponse, Response

from pydantic import BaseModel
from saas.core.helpers import get_timestamp_now
from saas.core.logging import Logging
from saas.rest.schemas import EndpointDefinition
from saas.sdk.app.auth import User
from saas.sdk.app.base import Application, get_current_active_user
from saas.sdk.base import LogMessage
from shapely.geometry import Polygon
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy_json import NestedMutableJson
from starlette.responses import FileResponse
import sentry_sdk

import explorer
from explorer.analysis.base import Analysis
from explorer.bdp import BaseDataPackageDB, GeometryType
from explorer.cache import CachedJSONObject
from explorer.checks import CheckProjectExists, CheckUserHasAccess, CheckIfUser, CheckUserIsOwner
from explorer.dots.dot import ImportableDataObjectType, UploadPostprocessResult, UploadDatasetResponseItem, \
    DataObjectType
from explorer.meta import __title__, __version__, __description__, __endpoint_prefix__

from explorer.module.base import BuildModule
from explorer.project import Project, make_analysis_id, make_analysis_group_id, load_area_of_interest
from explorer.renderer.base import NetworkRenderer, make_geojson_result
from explorer.renderer.buildings_renderer import BuildingsRenderer
from explorer.renderer.landcover_renderer import LandcoverRenderer
from explorer.renderer.landuse_renderer import LanduseRenderer
from explorer.renderer.vegetation_renderer import VegetationRenderer
from explorer.renderer.zone_renderer import ZoneRenderer
from explorer.schemas import BaseDataPackage, ExplorerInformation, ProjectMeta, ExplorerRuntimeError, Scene, \
    AnalysesByScene, AnalysisGroup, AnalysesByConfiguration, AnalysisInfo, BDPsByCity, BDPInfo, \
    AnalysisSpecification, AnalysisResult, BuildModuleSpecification, ExplorerDatasetInfo, \
    ZonesConfigurationMapping, ZoneConfiguration, AnalysisCompareResults, ExplorerPublicInformation
from explorer.view.base import View

logger = Logging.get('explorer.server')

Base = declarative_base()

sentry_sdk.init(
    dsn=os.getenv('SENTRY_DNS'),
    environment=os.getenv('ENVIRONMENT')
)


class CreateProjectParameters(BaseModel):
    name: str
    city: str
    bdp_id: str


class SupportedDatasetInfo(BaseModel):
    data_type: str
    data_type_label: str
    formats: List[str]
    description: str
    preview_image_url: str


class FetchDatasetsResponse(BaseModel):
    supported: List[SupportedDatasetInfo]
    pending: List[ExplorerDatasetInfo]
    available: List[ExplorerDatasetInfo]


class UploadDatasetParameters(BaseModel):
    data_type: str


class UploadDatasetResponse(BaseModel):
    mode: str
    verification_messages: List[LogMessage]
    datasets: List[UploadDatasetResponseItem]


class UpdateDatasetParameters(BaseModel):
    args: dict
    geo_type: Optional[str]


class ImportDatasetParameters(BaseModel):
    name: str


class AddZoneConfigParameters(BaseModel):
    config_name: str
    selected_zones: List[int]
    datasets: Dict[str, str]

    def datasets_with_geotype(self) -> Dict[GeometryType, str]:
        return {
            GeometryType(key): value for key, value in self.datasets.items()
        }


class AddZoneConfigResponse(BaseModel):
    obj_id: str
    configs: Dict[int, ZoneConfiguration]


class DeleteProjectResponse(BaseModel):
    deleted: bool


class CreateSceneParameters(BaseModel):
    name: str
    zone_config_mapping: ZonesConfigurationMapping
    module_settings: Dict


class UpdateMapParameters(BaseModel):
    parameters: Dict


class CreateAnalysisGroupParameters(BaseModel):
    analysis_type: str
    group_name: str
    parameters: Dict


class EnquireAnalysisResponse(BaseModel):
    analysis_id: str
    estimated_cost: str
    estimated_time: str
    cached_results_available: bool
    approval_required: bool
    messages: List[LogMessage]


class SubmitAnalysisParameters(BaseModel):
    group_id: str
    scene_id: str
    name: str
    aoi_obj_id: Optional[str]


class EnquireAnalysisParameters(BaseModel):
    analysis_type: str
    parameters: Dict
    scene_id: str
    aoi_obj_id: Optional[str]


class DBAnalysisStats(Base):
    __tablename__ = 'analysis_statistics'
    id = Column("id", Integer, primary_key=True)
    analysis_type = Column("analysis_type", String(64), nullable=False)
    parameters = Column("parameters", NestedMutableJson, nullable=False)
    runtime = Column("runtime", Integer, nullable=False)


class ExplorerServer(Application):
    @classmethod
    def search_for_classes(cls, packages: list[str], base_class) -> List:
        # determine base path
        base_path = explorer.__path__
        base_path = base_path[0]
        base_path = os.path.abspath(os.path.dirname(base_path))

        # collect classes
        classes = []
        for package_name in packages:
            pnc = package_name.split('.')
            package_path = [os.path.join(base_path, *pnc)]

            for module_info in pkgutil.iter_modules(package_path):
                module = __import__(f"{package_name}.{module_info.name}", fromlist=[module_info.name])
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, base_class) and obj != base_class:
                        classes.append(obj)
                if hasattr(module, '__path__'):
                    classes.extend(cls.search_for_classes([module.__name__], base_class))
        return classes

    def __init__(self, server_address: (str, int), node_address: (str, int), wd_path: str) -> None:
        super().__init__(server_address, node_address, __endpoint_prefix__, wd_path,
                         __title__, __version__, __description__)

        self._projects_path = os.path.join(wd_path, 'projects')
        os.makedirs(os.path.join(self._projects_path), exist_ok=True)

        self._bdps_path = os.path.join(wd_path, 'bdps')
        os.makedirs(os.path.join(self._bdps_path), exist_ok=True)

        self._temp_path = os.path.join(wd_path, 'temp')
        os.makedirs(os.path.join(self._temp_path), exist_ok=True)

        self._db_path = os.path.join(wd_path, 'server.db')
        self._engine = create_engine(f"sqlite:///{self._db_path}")
        Base.metadata.create_all(self._engine)
        self._session = sessionmaker(bind=self._engine)

        self._views: Dict[str, View] = {}
        self._analyses: Dict[str, Analysis] = {}
        self._build_modules: Dict[str, BuildModule] = {}
        self._network_renderers: Dict[str, NetworkRenderer] = {}
        self._bdps: Dict[str, Dict[str, Tuple[BaseDataPackage, str]]] = {}
        self._dots: Dict[str, DataObjectType] = {}
        self._projects: Dict[str, Optional[Project]] = {}

    def _project_path(self, project_id: str) -> str:
        return os.path.join(self._projects_path, project_id)

    def _bdp_db_path(self, bdp_id: str) -> str:
        return os.path.join(self._bdps_path, f"{bdp_id}.db")

    def _bdp_descriptor_path(self, bdp_id: str) -> str:
        return os.path.join(self._bdps_path, f"{bdp_id}.json")

    def get_dot(self, data_type: str) -> Optional[DataObjectType]:
        with self._mutex:
            return self._dots.get(data_type, None)

    def add_view(self, view: View) -> None:
        with self._mutex:
            logger.info(f"adding view {view.name()}")
            self._views[view.name()] = view

    def add_analysis_instance(self, analysis: Analysis) -> None:
        with self._mutex:
            logger.info(f"adding analysis {analysis.name()}")
            self._analyses[analysis.name()] = analysis

    def add_build_module(self, build_module: BuildModule) -> None:
        with self._mutex:
            logger.info(f"adding build module {build_module.name()}")
            self._build_modules[build_module.name()] = build_module

    def add_data_object_type(self, dot: DataObjectType) -> None:
        with self._mutex:
            logger.info(f"adding data object type {dot.name()}")
            self._dots[dot.name()] = dot

    def add_network_renderers(self, renderer: NetworkRenderer) -> None:
        with self._mutex:
            logger.info(f"adding network renderer {renderer.type()}")
            self._network_renderers[renderer.type()] = renderer

    def get_analysis_instance(self, analysis_type: str) -> Optional[Analysis]:
        return self._analyses.get(analysis_type, None)

    def get_build_module(self, module_name: str) -> Optional[BuildModule]:
        with self._mutex:
            return self._build_modules.get(module_name, None)

    def add_analysis_runtime_sample(self, analysis_type: str, parameters: dict, runtime: int) -> None:
        with self._session() as session:
            session.add(DBAnalysisStats(analysis_type=analysis_type,
                                        parameters=parameters,
                                        runtime=runtime))
            session.commit()

    def get_analysis_runtime_estimate(self, analysis_type: str) -> Optional[Tuple[int, int]]:
        with self._session() as session:
            records = session.query(DBAnalysisStats).filter_by(analysis_type=analysis_type).all()
            runtimes = [record.runtime for record in records]
            if len(runtimes) > 0:
                min_runtime = min(runtimes)
                max_runtime = max(runtimes)
                return min_runtime, max_runtime

            else:
                return None

    def import_bdp(self, directory: str, bdp_id: str) -> None:
        # check if files exist
        bdp_path0 = os.path.join(directory, f"{bdp_id}.json")
        db_path0 = os.path.join(directory, f"{bdp_id}.db")
        if not os.path.isfile(bdp_path0) or not os.path.isfile(db_path0):
            raise ExplorerRuntimeError(f"Files not found for BDP {bdp_id} at {directory}")

        bdp_path1 = self._bdp_descriptor_path(bdp_id)
        db_path1 = self._bdp_db_path(bdp_id)
        shutil.copyfile(bdp_path0, bdp_path1)
        shutil.copyfile(db_path0, db_path1)

    def initialise(self, service_user: User) -> None:
        # search for base data packages
        logger.info(f"search for base data packages...")
        sdk = self._get_context(service_user)
        bdp_ids = []
        for name in os.listdir(self._bdps_path):
            temp = name.split('.')
            bdp_id = temp[0]
            if bdp_id not in bdp_ids and BaseDataPackageDB.exists(self._bdps_path, bdp_id):
                # only load the BDP
                bdp = BaseDataPackage.parse_file(self._bdp_descriptor_path(bdp_id))
                logger.info(f"found BDP {bdp.city_name}:{bdp.name} at {bdp_id}.[json/db] -> "
                            f"checking for broken references")

                # check if all referenced data objects are available
                broken = {}
                desc_obj = None
                for obj_name, obj_id in bdp.references.items():
                    obj = sdk.find_data_object(obj_id)
                    if obj is None:
                        broken[obj_name] = obj_id
                    elif obj_name == 'description':
                        desc_obj = obj

                # do we have any broken references?
                if len(broken) > 0:
                    logger.warning(f"BDP {bdp.city_name}:{bdp.name} has broken object references -> "
                                   f"skipping. broken references: {broken}")

                else:
                    logger.info(f"BDP {bdp.city_name}:{bdp.name} object references verified -> adding")

                    # load the description (if any)
                    description = "No description available."
                    if desc_obj:
                        description_path = desc_obj.download(self._temp_path)
                        with open(description_path, 'r') as f:
                            description = f.read()
                        os.remove(description_path)

                    # get the BDPs by city
                    if bdp.city_name not in self._bdps:
                        self._bdps[bdp.city_name] = {}
                    cities = self._bdps[bdp.city_name]

                    # keep the BDP and the BDP db path
                    if bdp.id not in cities:
                        cities[bdp.id] = (bdp, description)

                    bdp_ids.append(bdp_id)

        # search for new projects
        self._search_for_new_projects()

        logger.info(f"server done initialising.")

    def endpoints(self) -> List[EndpointDefinition]:
        check_if_user = Depends(CheckIfUser(self))
        check_project_exists = Depends(CheckProjectExists(self))
        check_user_has_access = Depends(CheckUserHasAccess(self))
        check_user_is_owner = Depends(CheckUserIsOwner(self))

        return [
            EndpointDefinition('GET', self.endpoint_prefix, 'public_info', self.get_public_info, ExplorerPublicInformation,
                               []),

            EndpointDefinition('GET', self.endpoint_prefix, 'info', self.get_info, ExplorerInformation,
                               [check_if_user]),

            EndpointDefinition('GET', self.endpoint_prefix, 'info/scene/{project_id}',
                               self.get_info_scene, List[Dict],
                               [check_project_exists, check_if_user]),

            EndpointDefinition('GET', self.endpoint_prefix, 'project', self.get_projects, List[ProjectMeta],
                               [check_if_user]),

            EndpointDefinition('POST', self.endpoint_prefix, 'project', self.create_project, ProjectMeta,
                               [check_if_user]),

            EndpointDefinition('DELETE', self.endpoint_prefix, 'project/{project_id}', self.delete_project,
                               DeleteProjectResponse, [check_project_exists, check_user_is_owner]),

            EndpointDefinition('GET', self.endpoint_prefix, 'dataset/{project_id}',
                               self.fetch_datasets, FetchDatasetsResponse,
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('POST', self.endpoint_prefix, 'dataset/{project_id}',
                               self.upload_dataset, UploadDatasetResponse,
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('PUT', self.endpoint_prefix, 'dataset/{project_id}/{object_id}',
                               self.update_dataset, UploadPostprocessResult,
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('POST', self.endpoint_prefix, 'dataset/{project_id}/{object_id}',
                               self.import_dataset, ExplorerDatasetInfo,
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('DELETE', self.endpoint_prefix, 'dataset/{project_id}/{object_id}',
                               self.delete_dataset, ExplorerDatasetInfo,
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('GET', self.endpoint_prefix, 'dataset/{project_id}/{object_id}',
                               self.get_dataset, List[Dict],
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('POST', self.endpoint_prefix, 'zone_config/{project_id}',
                               self.add_zone_config, AddZoneConfigResponse,
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('GET', self.endpoint_prefix, 'zone_config/{project_id}/{zone_id}',
                               self.get_zone_configs, List[ZoneConfiguration],
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('DELETE', self.endpoint_prefix, 'zone_config/{project_id}/{config_id}',
                               self.delete_zone_config, ZoneConfiguration,
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('GET', self.endpoint_prefix, 'geometries/{project_id}/{geo_type}',
                               self.download_geometries, None, [check_project_exists, check_user_has_access]),

            EndpointDefinition('GET', self.endpoint_prefix, 'networks/{project_id}/{network_id}',
                               self.download_networks, None, [check_project_exists, check_user_has_access]),

            EndpointDefinition('GET', self.endpoint_prefix, 'view/{project_id}/{view_id}',
                               self.get_view, None, [check_project_exists, check_user_has_access]),

            EndpointDefinition('PUT', self.endpoint_prefix, 'module/{project_id}/{module_id}/update',
                               self.update_module_data, Dict,
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('PUT', self.endpoint_prefix, 'module/{project_id}/{module_id}/upload',
                               self.upload_module_data, Dict,
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('GET', self.endpoint_prefix, 'module/{project_id}/{module_id}/raster',
                               self.get_module_raster, List[dict],
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('GET', self.endpoint_prefix, 'module/{project_id}/{module_id}/chart',
                               self.get_module_chart, Dict,
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('PUT', self.endpoint_prefix, 'module/{project_id}',
                               self.refresh_project, None,
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('POST', self.endpoint_prefix, 'scene/{project_id}',
                               self.create_scene, Scene,
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('GET', self.endpoint_prefix, 'scene/{project_id}',
                               self.get_scenes, List[Scene],
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('DELETE', self.endpoint_prefix, 'scene/{project_id}/{scene_id}',
                               self.delete_scene, Scene,
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('GET', self.endpoint_prefix, 'analysis/{project_id}/info',
                               self.get_info_analyses, List[Dict],
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('GET', self.endpoint_prefix, 'analysis/{project_id}/scene',
                               self.get_analyses_by_scene, List[AnalysesByScene],
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('GET', self.endpoint_prefix, 'analysis/{project_id}/configuration',
                               self.get_analyses_by_configuration, List[AnalysesByConfiguration],
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('POST', self.endpoint_prefix, 'analysis/{project_id}',
                               self.create_analysis_group, AnalysisGroup,
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('GET', self.endpoint_prefix, 'analysis/{project_id}/enquire',
                               self.enquire_analysis, EnquireAnalysisResponse,
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('POST', self.endpoint_prefix, 'analysis/{project_id}/submit',
                               self.submit_analysis, AnalysisInfo,
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('GET', self.endpoint_prefix, 'analysis/{project_id}/{analysis_id}',
                               self.get_analysis, Optional[AnalysisInfo],
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('PUT', self.endpoint_prefix, 'analysis/{project_id}/{analysis_id}/resume',
                               self.resume_analysis, AnalysisInfo,
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('PUT', self.endpoint_prefix, 'analysis/{project_id}/{analysis_id}/cancel',
                               self.cancel_analysis, AnalysisInfo,
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('DELETE', self.endpoint_prefix, 'analysis/{project_id}/{analysis_id}',
                               self.delete_analysis, Optional[AnalysisInfo],
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('GET', self.endpoint_prefix, 'analysis/{project_id}/{group_id}/config',
                               self.get_group_config, AnalysisGroup,
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('GET', self.endpoint_prefix, 'result/{project_id}/{analysis_id}/{result_id}',
                               self.get_result, List[Dict],
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('GET', self.endpoint_prefix,
                               'result/{project_id}/compare/{result_id}/{analysis_id0}/{analysis_id1}',
                               self.get_compare_result, AnalysisCompareResults,
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('GET', self.endpoint_prefix,
                               'result/{project_id}/delta/{result_id}/{analysis_id0}/{analysis_id1}',
                               self.get_result_delta, List[Dict],
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('GET', self.endpoint_prefix, 'export/{project_id}/{analysis_id}/{result_id}',
                               self.export_result, None,
                               [check_project_exists, check_user_has_access]),

            EndpointDefinition('GET', self.endpoint_prefix,
                               'export/{project_id}/{result_id}/{analysis_id0}/{analysis_id1}',
                               self.export_result_delta, None,
                               [check_project_exists, check_user_has_access])
        ]

    def get_public_info(self) -> ExplorerPublicInformation:
        return ExplorerPublicInformation(
            server_version=__version__
        )

    def get_info(self) -> ExplorerInformation:
        """
        Retrieves useful information about the server, This includes lists of supported modules, data object
        types and base data packages.
        """
        bdps = [
            BDPsByCity(city=city, packages=[
                BDPInfo(id=bdp_id, name=item[0].name, city=item[0].city_name, bounding_box=item[0].bounding_box,
                        timezone=item[0].timezone, description=item[1]) for bdp_id, item in packages.items()
            ]) for city, packages in self._bdps.items()
        ]

        return ExplorerInformation(
            build_modules=list(self._build_modules.keys()),
            analyses_types=list(self._analyses.keys()),
            dots=list(self._dots.keys()),
            bdps=bdps,
            core_version=__version__
        )

    def get_info_analyses(self, project_id: str, scale: str = None, aoi_obj_id: Optional[str] = None, scene_id: str = None,
                          user: User = Depends(get_current_active_user)) -> List[AnalysisSpecification]:
        """
        Retrieves a list of supported analyses types and their specification.
        """
        sdk = self._get_context(user)
        project = self._projects.get(project_id)

        # filter analyses depending on whether all required processors are available
        result = []
        for analysis in self._analyses.values():
            spec = analysis.specification(project, sdk, aoi_obj_id=aoi_obj_id, scene_id=scene_id)

            # check if we can find all the required processors
            all_found = True
            for proc_name in spec.required_processors:
                if sdk.find_processor_by_name(proc_name) is None:
                    logger.debug(f"processor {proc_name} not found -> exclude {analysis.name()}")
                    all_found = False
                    break

            for bdp_name in spec.required_bdp:
                project = self._projects[project_id]
                if bdp_name not in project.info.bdp.references:
                    logger.debug(f"BDP object {bdp_name} not found -> exclude {analysis.name()}")
                    all_found = False
                    break

            if all_found:
                result.append(spec)

        return result

    def get_info_scene(self, project_id: str) -> List[BuildModuleSpecification]:
        """
        Retrieves a list of build modules and their specification.
        """
        project = self._projects.get(project_id)

        result: List[BuildModuleSpecification] = []
        for build_module in self._build_modules.values():
            spec = build_module.specification(project)
            result.append(spec)

        return result

    def _search_for_new_projects(self) -> None:
        # search for projects and put placeholder
        with self._mutex:
            new_projects = [prj_id for prj_id in os.listdir(self._projects_path) if prj_id not in self._projects]
            for prj_id in new_projects:
                self._projects[prj_id] = None

        # load all new projects
        for prj_id in new_projects:
            try:
                with self._mutex:
                    self._projects[prj_id] = Project.load(self, os.path.join(self._projects_path, prj_id))
                logger.info(f"[{prj_id}] added project -> loading...")

            except Exception as e:
                logger.error(f"[{prj_id}] error while creating project: {e}")

    def get_projects(self, user: User = Depends(get_current_active_user)) -> List[ProjectMeta]:
        """
        Retrieves meta information (id and name) of all projects.
        """

        # search for new projects (if any)
        self._search_for_new_projects()

        return [project.meta for project in self._projects.values() if project is not None and project.has_access(user)]

    def get_project(self, project_id: str) -> Optional[Project]:
        return self._projects.get(project_id, None)

    def create_project(self, p: CreateProjectParameters, user: User = Depends(get_current_active_user)) -> ProjectMeta:
        """
        Creates a new project and returns the meta information (id, name and state) about the project.
        """
        # get the BDP
        if p.city not in self._bdps or p.bdp_id not in self._bdps[p.city]:
            raise ExplorerRuntimeError(f"No base dataset found for '{p.city}:{p.bdp_id}'")

        # create and initialise the project
        bdp, _ = self._bdps[p.city][p.bdp_id]
        sdk = self._get_context(user)
        project = Project.create(self, p.name, [user.login], user.login, self._projects_path, bdp,
                                 self._bdp_db_path(p.bdp_id), sdk)

        # keep the project
        with self._mutex:
            self._projects[project.meta.id] = project

        return project.meta

    def delete_project(self, project_id: str, user: User = Depends(get_current_active_user)) -> DeleteProjectResponse:
        """
        Deletes a project. This can only be done if the user is also the owner of the project.
        """
        with self._mutex:
            if self._projects[project_id].meta.state in ['initialised', 'broken']:
                project = self._projects.pop(project_id)

        # do we have a project at this point? if so, delete it.
        if project:
            shutil.rmtree(project.info.folder, ignore_errors=True)
            logger.info(f"deleting project {project_id} -> done.")
            return DeleteProjectResponse(deleted=True)

        else:
            logger.warning(f"deleting project {project_id} -> failed, project not initialised/broken yet.")
            return DeleteProjectResponse(deleted=False)

    def fetch_datasets(self, project_id: str) -> FetchDatasetsResponse:
        """
        Retrieve information about all supported and available datasets for a given project.
        :param project_id: the project id
        :return:
        """
        # collect a list of all supported datasets
        supported = []
        for instance in self._dots.values():
            if isinstance(instance, ImportableDataObjectType):
                supported.append(SupportedDatasetInfo(
                    data_type=instance.name(),
                    data_type_label=instance.label(),
                    formats=instance.supported_formats(),
                    description=instance.description(),
                    preview_image_url=instance.preview_image_url()
                ))

        # collect a list of all available datasets
        project = self._projects[project_id]
        pending = project.pending_datasets
        available = list(project.info.datasets.values()) if project.info.datasets else []

        return FetchDatasetsResponse(supported=supported, pending=pending, available=available)

    def upload_dataset(self, project_id: str, body: str = Form(...),
                       attachment: UploadFile = File(...)) -> UploadDatasetResponse:
        """
        Upload a dataset.
        """

        # create parameters object
        p = UploadDatasetParameters.parse_obj(json.loads(body))

        # do we have a data object type for this?
        if p.data_type not in self._dots:
            raise ExplorerRuntimeError(f"Unsupported data object type '{p.data_type}'")
        dot: DataObjectType = self._dots[p.data_type]

        # is the DOT importable
        if not isinstance(dot, ImportableDataObjectType):
            raise ExplorerRuntimeError(f"Data of data object type '{p.data_type}' cannot be imported")
        dot: ImportableDataObjectType = dot

        # get the project
        project = self._projects[project_id]

        # write the content to the temporary file
        temp_obj_path = os.path.join(project.info.temp_path, f"{dot.name()}_{p.data_type}_{get_timestamp_now()}.temp")
        with open(temp_obj_path, "wb") as f:
            shutil.copyfileobj(attachment.file, f)

        # upload the file (this may split the original file into multiple files/datasets)
        is_verified, verification_messages, datasets = project.upload_dataset(temp_obj_path, dot)

        # delete the temporary file
        os.remove(temp_obj_path)

        if is_verified:
            return UploadDatasetResponse(
                verification_messages=verification_messages,
                # TODO: it uses the 'mode' of the first dataset. are there cases where different datasets can
                #  ask for different modes? if so, what does that mean for the whole workflow?
                mode=datasets[0][2].mode,
                datasets=[
                    UploadDatasetResponseItem(obj_id=obj_id, info=result, target=dot.target().value)
                    for obj_id, _, result in datasets
                ]
            )
        else:
            return UploadDatasetResponse(
                verification_messages=verification_messages,
                mode='',
                datasets=[]
            )

    def update_dataset(self, project_id: str, object_id: str, parameters: UpdateDatasetParameters,
                       user: User = Depends(get_current_active_user)) -> UploadPostprocessResult:
        # get the project
        project = self._projects[project_id]

        geo_type = GeometryType(parameters.geo_type) if parameters.geo_type else None

        # import the dataset
        response = project.update_dataset(object_id, parameters.args, geo_type=geo_type)
        return response

    def import_dataset(self, project_id: str, object_id: str, parameters: ImportDatasetParameters,
                       user: User = Depends(get_current_active_user)) -> ExplorerDatasetInfo:
        # get the project
        project = self._projects[project_id]

        # import the dataset
        sdk = self._get_context(user)
        dataset = project.import_dataset(object_id, sdk, parameters.name)

        return dataset

    def delete_dataset(self, project_id: str, object_id: str,
                       user: User = Depends(get_current_active_user)) -> ExplorerDatasetInfo:
        # get the project
        project = self._projects[project_id]

        sdk = self._get_context(user)

        # is the dataset a zone configuration?
        dataset = project.info.datasets.get(object_id)
        if dataset and dataset.type == 'zone-configuration':
            # retrieve the data object with the zone configuration details
            obj = sdk.find_data_object(dataset.obj_id)
            content_path = os.path.join(project.info.temp_path, f"zone_config_{dataset.obj_id}.json")
            if obj is None:
                logger.warning(f"zone configuration dataset object {dataset.obj_id} not found.")
            else:
                # download and load the content of the zone configuration
                obj.download(content_path)
                with open(content_path, 'r') as f:
                    content: Dict[int, dict] = json.load(f)
                os.remove(content_path)

                # delete the zone configuration
                for zone_id, config in content.items():
                    config_id = config['config_id']
                    project.delete_zone_config(config_id)
                    logger.info(f"deleted config {config_id} ({config['name']}) from zone {zone_id}")

        # delete the dataset
        dataset = project.delete_dataset(object_id, sdk)

        return dataset

    def get_dataset(self, project_id: str, object_id: str, user: User = Depends(get_current_active_user)) -> List[dict]:
        project = self._projects[project_id]

        sdk = self._get_context(user)
        return project.get_dataset(object_id, sdk)

    def add_zone_config(self, project_id: str, parameters: AddZoneConfigParameters,
                        user: User = Depends(get_current_active_user)) -> AddZoneConfigResponse:
        """
        Creates zone configurations for selected zones based on uploaded dataset objects.
        :param project_id:
        :param parameters:
        :return:
        """
        with self._mutex:
            project = self._projects[project_id]

        sdk = self._get_context(user)

        # add the zone configuration
        configs: Dict[int, ZoneConfiguration] = project.add_zone_configs(
            parameters.config_name, parameters.selected_zones,  parameters.datasets_with_geotype()
        )

        # create a dataset content
        content_path = os.path.join(project.info.temp_path, f"zone_config_info.json")
        with open(content_path, 'w') as f:
            content: Dict[int, dict] = {
                zone_id: config.dict() for zone_id, config in configs.items()
            }
            json.dump(content, f)

        # add the dataset to the library
        dataset = ExplorerDatasetInfo(name=parameters.config_name, type="zone-configuration",
                                      type_label="Zone Configuration", format="json", obj_id=None, extra={})
        project.info.add_dataset(dataset, content_path, sdk)

        # cleanup
        os.remove(content_path)

        return AddZoneConfigResponse(obj_id=dataset.obj_id, configs=configs)

    def get_zone_configs(self, project_id: str, zone_id: int) -> List[ZoneConfiguration]:
        """
        Returns a zone configuration.
        """
        project = self._projects[project_id]
        return project.get_zone_configs(zone_id)

    def delete_zone_config(self, project_id: str, config_id: int) -> ZoneConfiguration:
        """
        Deletes a zone configuration. Landuse/Building/Vegetation geometries associated with the specified
        configuration will also be deleted
        """
        project = self._projects[project_id]
        return project.delete_zone_config(config_id)

    def download_geometries(self, project_id: str, geo_type: str, set_id: str = None, area: str = None,
                            use_cache: str = None, user: User = Depends(get_current_active_user)) -> Response:
        """
        Retrieves a GeoJSON feature collection with features of a certain geometry type ('temp', 'zone', 'landuse',
        'landcover', 'building'). The 'temp' geometry type is assigned to geometries that have been uploaded but not
        imported yet. The optional set id can be used to refer to a specific group of geometries. This is either the
        scene id or the group id obtained when uploading geometries. If the optional area is specified, geometries are
        filtered accordingly and only features inside the area are included. Area has to be in the 'free:N:lon1,lat1,
        lon2,lat2, ...,lonN,latN' or the 'bbox:west, north,east,south' format. By default, the cache is used to
        retrieve geometries faster. This can be prevented by setting use_cache to False.
        """

        # if we have an area, decompose it
        if area is not None:
            area = area.split(':')
            if area[0] == 'bbox':
                west = float(area[1])
                north = float(area[2])
                east = float(area[3])
                south = float(area[4])
                area = Polygon([[west, north], [east, north], [east, south], [west, south]])

            elif area[0] == 'free':
                free_area = []
                for i in range(int(area[1])):
                    lon = float(area[i * 2 + 2])
                    lat = float(area[i * 2 + 3])
                    free_area.append((lon, lat))
                area = Polygon(free_area)

            elif area[0] == 'aoi_obj_id':
                aoi_obj_id = area[1]
                area = load_area_of_interest(self._get_context(user), self._temp_path, aoi_obj_id)

            else:
                raise ExplorerRuntimeError(f"Unexpected area type '{area[0]}'.")
        else:
            area = None

        # use the cache?
        if use_cache is None or use_cache.lower() == 'true':
            use_cache = True
        else:
            use_cache = False

        # get the project
        project = self._projects[project_id]

        if geo_type == GeometryType.zone.value:
            renderer = ZoneRenderer()
            if set_id is None:
                geojson: CachedJSONObject = project.geometries(geo_type=GeometryType.zone, area=area,
                                                               use_cache=use_cache)
                result = make_geojson_result('Zones', geojson.content(), renderer.get())

            else:
                geojson: CachedJSONObject = project.geometries(geo_type=GeometryType.zone, area=area, set_id=set_id,
                                                               use_cache=use_cache)
                result = make_geojson_result('Zones with Alternative Configurations', geojson.content(),
                                             renderer.get())

        elif geo_type == GeometryType.landuse.value:
            geojson: CachedJSONObject = project.geometries(geo_type=GeometryType.landuse, set_id=set_id, area=area,
                                                           use_cache=use_cache)
            renderer = LanduseRenderer()
            result = make_geojson_result('Land-use', geojson.content(), renderer.get())

        elif geo_type == GeometryType.landcover.value:
            geojson: CachedJSONObject = project.geometries(geo_type=GeometryType.landcover, set_id=set_id, area=area,
                                                           use_cache=use_cache)
            renderer = LandcoverRenderer()
            result = make_geojson_result('Land-cover', geojson.content(), renderer.get())

        elif geo_type == GeometryType.building.value:
            geojson: CachedJSONObject = project.geometries(geo_type=GeometryType.building, set_id=set_id, area=area,
                                                           use_cache=use_cache)
            renderer = BuildingsRenderer()
            result = make_geojson_result('Buildings', geojson.content(), renderer.get())

        elif geo_type == GeometryType.vegetation.value:
            renderer = VegetationRenderer()
            geojson: CachedJSONObject = project.geometries(geo_type=GeometryType.vegetation, set_id=set_id, area=area,
                                                           use_cache=use_cache)
            result = make_geojson_result('Vegetation', geojson.content(), renderer.get())

        else:
            raise ExplorerRuntimeError(f"Unsupported geometry type: {geo_type}")

        async def gpp_streamer():
            yield json.dumps(result).encode('utf-8')

        return StreamingResponse(
            headers={'Cache-Control': 'public, max-age=31557600'} if use_cache else None,
            content=gpp_streamer(),
            media_type='application/octet-stream'
        )

    def download_networks(self, project_id: str, network_id: str, use_cache: str = None) -> Response:
        """
        Retrieves a GeoJSON feature collection with features of a network with a given id. By default, the cache is
        used to retrieve geometries faster. This can be prevented by setting use_cache to False.
        """

        # use the cache?
        if use_cache is None or use_cache.lower() == 'true':
            use_cache = True
        else:
            use_cache = False

        # get the project
        project = self._projects[project_id]

        # get the features
        geojson = project.network_as_geojson(network_id, use_cache)
        geojson = geojson.content()

        if network_id in self._network_renderers:
            renderer = self._network_renderers[network_id]
        else:
            raise ExplorerRuntimeError(f"Invalid network renderer id: '{network_id}'")

        # combine features and combine with renderer information
        combined = {
            'type': 'network',
            'title': renderer.title(),
            'pointData': {
                'type': 'geojson',
                'title': renderer.point_title(),
                'geojson': {'type': 'Feature', 'geometry': {}} if network_id == 'transport' else geojson['nodes'],
                'renderer': renderer.point_renderer()
            },
            'lineData': {
                'type': 'geojson',
                'title': renderer.line_title(),
                'geojson': geojson['links'],
                'renderer': renderer.line_renderer()
            }
        }

        async def content_streamer():
            yield json.dumps(combined).encode('utf-8')

        return StreamingResponse(
            headers={'Cache-Control': 'public, max-age=31557600'} if use_cache else None,
            content=content_streamer(),
            media_type='application/octet-stream'
        )

    def get_view(self, project_id: str, view_id: str, set_id: str = None, area: str = None,
                 use_cache: str = None, user: User = Depends(get_current_active_user)) -> Response:
        """
        Retrieves a list of GeoJSON feature collections to be displayed by the frontend in multiple layers. By
        default, the cache is used to retrieve geometries faster. This can be prevented by setting use_cache to False.
        """

        # if we have an area, decompose it
        if area is not None:
            area = area.split(':')
            if area[0] == 'bbox':
                west = float(area[1])
                north = float(area[2])
                east = float(area[3])
                south = float(area[4])
                area = Polygon([[west, north], [east, north], [east, south], [west, south]])

            elif area[0] == 'free':
                free_area = []
                for i in range(int(area[1])):
                    lon = float(area[i * 2 + 2])
                    lat = float(area[i * 2 + 3])
                    free_area.append((lon, lat))
                area = Polygon(free_area)

            elif area[0] == 'aoi_obj_id':
                aoi_obj_id = area[1]
                area = load_area_of_interest(self._get_context(user), self._temp_path, aoi_obj_id)

            else:
                raise ExplorerRuntimeError(f"Unexpected area type '{area[0]}'.")
        else:
            area = None

        # use the cache?
        if use_cache is None or use_cache.lower() == 'true':
            use_cache = True
        else:
            use_cache = False

        # get the view and the project
        view = self._views[view_id] if view_id in self._views else self._views['default']
        project = self._projects[project_id]

        # generate the layers for this view
        layers = view.generate(project, set_id=set_id, area=area, use_cache=use_cache)

        async def content_streamer():
            yield json.dumps(layers).encode('utf-8')

        return StreamingResponse(
            headers={'Cache-Control': 'public, max-age=31557600'} if use_cache else None,
            content=content_streamer(),
            media_type='application/octet-stream'
        )

    def create_scene(self, project_id: str, p: CreateSceneParameters) -> Scene:
        """
        Creates a new scene.
        """
        project = self._projects[project_id]
        return project.create_scene(p.name, p.zone_config_mapping, p.module_settings)

    def get_scenes(self, project_id: str) -> List[Scene]:
        """
        Retrieves a list of available scenes.
        """
        project = self._projects[project_id]
        return project.get_scenes()

    def delete_scene(self, project_id: str, scene_id: str) -> Scene:
        """
        Deletes a specific scene.
        """
        project = self._projects[project_id]
        return project.delete_scene(scene_id)

    def update_module_data(self, project_id: str, module_id: str, p: UpdateMapParameters,
                           user: User = Depends(get_current_active_user)) -> Dict:
        """
        Update data used by a specific module.
        """

        project = self._projects[project_id]
        active_module = self._build_modules[module_id]

        # deserialize content
        content = p.parameters if p.parameters else {}

        # handle the upload
        result = active_module.update(project, content, self._get_context(user))
        return result

    def upload_module_data(self, project_id: str, module_id: str, attachment: UploadFile = File(...),
                           user: User = Depends(get_current_active_user)) -> Dict:
        """
        Upload data used by a specific module.
        """

        project = self._projects[project_id]
        active_module = self._build_modules[module_id]

        content = attachment.file.read()
        content = json.loads(content)

        # handle the upload
        result = active_module.upload(project, content, self._get_context(user))
        return result

    def get_module_raster(self, project_id: str, module_id: str, parameters: str,
                          user: User = Depends(get_current_active_user)) -> List[dict]:
        """
        Returns a raster image (as JSON object) for a specific module and a set of parameters.
        """
        project = self._projects[project_id]
        active_module = self._build_modules[module_id]

        # deserialise parameters and get the results
        parameters = json.loads(parameters) if parameters else {}

        return active_module.raster_image(project, parameters, self._get_context(user))

    def get_module_chart(self, project_id: str, module_id: str, parameters: str,
                         user: User = Depends(get_current_active_user)) -> Dict:
        """
        Returns a chart (as JSON object) for a specific module and a set of parameters.
        """
        project = self._projects[project_id]
        active_module = self._build_modules[module_id]

        # deserialise parameters and get the results
        parameters = json.loads(parameters) if parameters else {}

        return active_module.chart(project, parameters, self._get_context(user))

    def refresh_project(self, project_id: str, user: User = Depends(get_current_active_user)) -> None:
        project = self._projects[project_id]

        project.vf_mixer.refresh(self._get_context(user))

    def get_analyses_by_scene(self, project_id: str) -> List[AnalysesByScene]:
        """
        Retrieves a list of all analysis runs, sorted by scenes.
        """
        project = self._projects[project_id]
        return project.get_analyses_by_scene()

    def get_analyses_by_configuration(self, project_id: str) -> List[AnalysesByConfiguration]:
        """
        Retrieves a list of all analysis runs, sorted by analysis groups/configuration.
        """
        project = self._projects[project_id]
        return project.get_analyses_by_configuration()

    def create_analysis_group(self, project_id: str, p: CreateAnalysisGroupParameters) -> AnalysisGroup:
        """
        Creates a new analysis group/configuration based on a set of parameters for the specified analysis type.
        """
        project = self._projects[project_id]

        # check if the analysis type is supported
        if p.analysis_type not in self._analyses:
            raise ExplorerRuntimeError(f"Analysis type is not supported: {p.analysis_type}")

        # get the analysis instance
        analysis = self._analyses[p.analysis_type]

        # generate a group id
        group_id = make_analysis_group_id(project_id, analysis.name(), p.parameters)

        group = project.create_analysis_group(group_id, p.group_name, analysis, p.parameters)
        return group

    def enquire_analysis(self, project_id: str, p: str,
                         user: User = Depends(get_current_active_user)) -> EnquireAnalysisResponse:
        """
        Enquires if a particular analysis run as already been carried out (i.e., if the results are already available
        in the cache) and retrieves some useful information about the estimated runtime.
        """
        project = self._projects[project_id]

        # deserialise parameters
        p = EnquireAnalysisParameters.parse_obj(json.loads(p))

        # check if the analysis type is supported
        if p.analysis_type not in self._analyses:
            raise ExplorerRuntimeError(f"Analysis type is not supported: {p.analysis_type}")

        # get the scene
        scene = project.get_scene(p.scene_id)
        if not scene:
            raise ExplorerRuntimeError(f"Scene {p.scene_id} not found")

        # load the aoi (if any)
        aoi = None
        if p.aoi_obj_id is not None:
            aoi = load_area_of_interest(self._get_context(user), self._temp_path, p.aoi_obj_id)

        # check parameters
        analysis = self._analyses[p.analysis_type]
        verification_messages = analysis.verify_parameters(project, scene, p.parameters, aoi)

        def format_time(runtime):
            if runtime >= 3600:
                return f"{runtime / 3600:.1f} hours"
            elif runtime >= 60:
                return f"{int(runtime / 60)} minutes"
            else:
                return f"{runtime} seconds"

        # get a runtime estimate
        estimate = self.get_analysis_runtime_estimate(p.analysis_type)
        estimated_time = 'unknown' if estimate is None else f"{format_time(estimate[0])} to {format_time(estimate[1])}"

        # determine analysis id
        group_id = make_analysis_group_id(project_id, p.analysis_type, p.parameters)
        analysis_id = make_analysis_id(group_id, p.scene_id, p.aoi_obj_id)

        # get analysis run info (if any)
        analysis_run = project.get_analysis_info(analysis_id)

        return EnquireAnalysisResponse(
            analysis_id=analysis_id,
            estimated_cost='unknown',
            estimated_time=estimated_time,
            cached_results_available=analysis_run is not None and analysis_run.results is not None,
            approval_required=False,
            messages=verification_messages
        )

    def submit_analysis(self, project_id: str, p: SubmitAnalysisParameters,
                        user: User = Depends(get_current_active_user)) -> AnalysisInfo:
        """
        Submits an analysis for execution.
        """
        project = self._projects[project_id]

        # get the analysis group
        group = project.get_analysis_group(p.group_id)
        if not group:
            raise ExplorerRuntimeError(f"Analysis group not found: {p.group_id}")

        # get the analysis instance
        if group.type not in self._analyses:
            raise ExplorerRuntimeError(f"Analysis type '{group.type}' not supported")
        analysis = self._analyses[group.type]

        # get the scene
        scene = project.get_scene(p.scene_id)
        if not scene:
            raise ExplorerRuntimeError(f"Scene {p.scene_id} not found")

        return project.submit_analysis(analysis, group, scene, p.aoi_obj_id, p.name, user,
                                       self._get_context(user))

    def get_analysis(self, project_id: str, analysis_id: str) -> Optional[AnalysisInfo]:
        """
        Retrieves information about a specific analysis run.
        """
        project = self._projects[project_id]

        return project.get_analysis_info(analysis_id)

    def resume_analysis(self, project_id: str, analysis_id: str,
                        user: User = Depends(get_current_active_user)) -> AnalysisInfo:
        """
        Attempts to resume an analysis run that is in state 'cancelled' or 'failed'. Whether the attempt will be be
        successful depends on the circumstances of the analysis.
        """
        project = self._projects[project_id]

        return project.resume_analysis(analysis_id, self._get_context(user))

    def cancel_analysis(self, project_id: str, analysis_id: str) -> AnalysisInfo:
        """
        Cancels an analysis run that is in state 'initialised' or 'running'.
        """
        project = self._projects[project_id]

        return project.cancel_analysis(analysis_id)

    def delete_analysis(self, project_id: str, analysis_id: str,
                        user: User = Depends(get_current_active_user)) -> AnalysisInfo:
        """
        Deletes an analysis run that is in state 'cancelled', 'failed', or 'finished'. If an analysis is 'initialised'
        or 'running' it needs to be cancelled first. When an analysis is deleted, all its associated data objects (if
        any) are deleted as well.
        """

        project = self._projects[project_id]

        return project.delete_analysis(analysis_id, self._get_context(user))

    def _get_result(self, project_id: str, analysis_id: str, result_id: str, parameters: str = None,
                    user: User = Depends(get_current_active_user)) -> (str, str):

        project = self._projects[project_id]

        # do we have analysis info?
        info = project.get_analysis_info(analysis_id)
        if not info:
            raise ExplorerRuntimeError(f"Analysis '{analysis_id}' not found")

        # get the analysis instance
        if info.analysis_type not in self._analyses:
            raise ExplorerRuntimeError(f"Analysis '{info.analysis_type}' not found")
        analysis = self._analyses[info.analysis_type]

        # do we have that result?
        results = {result.name: result for result in info.results}
        if result_id not in results:
            raise ExplorerRuntimeError(f"Analysis '{info.analysis_type}' result '{result_id}' not found")

        # deserialise parameters and get the results
        parameters = json.loads(parameters) if parameters else {}
        return project.get_result(analysis, analysis_id, results[result_id], parameters, self._get_context(user))

    def get_result(self, project_id: str, analysis_id: str, result_id: str, parameters: str = None,
                   user: User = Depends(get_current_active_user)) -> List[dict]:
        """
        Retrieves a specific result from a completed analysis run. Depending on the type, results can be parameterised.
        The parameter specification is provided in the analysis information of the result.
        """

        _, json_path = self._get_result(project_id, analysis_id, result_id, parameters, user)
        with open(json_path, 'r') as f:
            content = f.read()
            content = json.loads(content)
            return content

    def get_compare_result(self, project_id: str, result_id: str, analysis_id0: str, analysis_id1: str,
                           parameters0: str = None, parameters1: str = None,
                           user: User = Depends(get_current_active_user)) -> AnalysisCompareResults:
        """
        Retrieves results from selected two completed analysis runs to compare the results. Depending on the type,
        results can be parameterised. The parameter specification is provided in the analysis information of the result.
        """

        project = self._projects[project_id]

        # check and get the analysis and result for both runs
        analysis0, result0 = self._check_and_get(project, result_id, analysis_id0)
        analysis1, result1 = self._check_and_get(project, result_id, analysis_id1)
        if analysis0 != analysis1:
            raise ExplorerRuntimeError(f"Mismatching analysis instances for {analysis_id0}:{analysis0.name()} and "
                                       f"{analysis_id1}:{analysis1.name()}")

        # deserialize parameters and get the result
        parameters0 = json.loads(parameters0) if parameters0 else {}
        parameters1 = json.loads(parameters1) if parameters1 else {}

        _, json_path0 = project.get_result(analysis0, analysis_id0, result0, parameters0, self._get_context(user))
        _, json_path1 = project.get_result(analysis1, analysis_id1, result1, parameters1, self._get_context(user))

        with open(json_path0, 'r') as f:
            content0 = f.read()
            content0 = json.loads(content0)

        with open(json_path1, 'r') as f:
            content1 = f.read()
            content1 = json.loads(content1)

        return analysis0.get_compare_results(content0, content1)

    def export_result(self, project_id: str, analysis_id: str, result_id: str, parameters: str = None,
                      user: User = Depends(get_current_active_user)) -> Response:
        """
        Retrieves a specific result from a completed analysis run and sends the data content suitable for export as
        file. Depending on the type, results can be parameterised. The parameter specification is provided in the
        analysis information of the result.
        """

        export_path, _ = self._get_result(project_id, analysis_id, result_id, parameters, user)
        return FileResponse(export_path, media_type='application/octet-stream')

    def _check_and_get(self, project: Project, result_id: str, analysis_id: str) -> (Analysis, AnalysisResult):
        # do we have analysis info?
        info = project.get_analysis_info(analysis_id)
        if not info:
            raise ExplorerRuntimeError(f"Analysis '{analysis_id}' not found")

        # get the analysis instance
        if info.analysis_type not in self._analyses:
            raise ExplorerRuntimeError(f"Analysis '{info.analysis_type}' not found")

        analysis = self._analyses[info.analysis_type]

        # do we have that result?
        results = {result.name: result for result in info.results}
        if result_id not in results:
            raise ExplorerRuntimeError(f"Analysis '{info.analysis_type}' result '{result_id}' not found")

        return analysis, results[result_id]

    def _get_result_delta(self, project_id: str, result_id: str, analysis_id0: str, analysis_id1: str,
                          parameters0: str = None, parameters1: str = None,
                          user: User = Depends(get_current_active_user)) -> (str, str):

        project = self._projects[project_id]

        # check and get the analysis and result for both runs
        analysis0, result0 = self._check_and_get(project, result_id, analysis_id0)
        analysis1, result1 = self._check_and_get(project, result_id, analysis_id1)
        if analysis0 != analysis1:
            raise ExplorerRuntimeError(f"Mismatching analysis instances for {analysis_id0}:{analysis0.name()} and "
                                       f"{analysis_id1}:{analysis1.name()}")

        # deserialise parameters and get the result
        parameters0 = json.loads(parameters0) if parameters0 else {}
        parameters1 = json.loads(parameters1) if parameters1 else {}

        return project.get_result_delta(analysis0, analysis_id0, analysis_id1, result0, result1,
                                        parameters0, parameters1, self._get_context(user))

    def get_result_delta(self, project_id: str, result_id: str, analysis_id0: str, analysis_id1: str,
                         parameters0: str = None, parameters1: str = None,
                         user: User = Depends(get_current_active_user)) -> Dict:
        """
        Retrieves the 'delta' (i.e., the difference) of the specific results from two completed analysis runs.
        Depending on the type, results can be parameterised. The parameter specifications are provided in the analysis
        information of the results.
        """

        _, json_path = self._get_result_delta(project_id, result_id, analysis_id0, analysis_id1,
                                              parameters0, parameters1, user)
        with open(json_path, 'r') as f:
            content = f.read()
            content = json.loads(content)
            return content

    def export_result_delta(self, project_id: str, result_id: str, analysis_id0: str, analysis_id1: str,
                            parameters0: str = None, parameters1: str = None,
                            user: User = Depends(get_current_active_user)) -> Response:
        """
        Retrieves the 'delta' (i.e., the difference) of the specific results from two completed analysis runs and
        sends the data content suitable for export as file. Depending on the type, results can be parameterised. The
        parameter specifications are provided in the analysis information of the results.
        """

        export_path, _ = self._get_result_delta(project_id, result_id, analysis_id0, analysis_id1,
                                                parameters0, parameters1, user)
        return FileResponse(export_path, media_type='application/octet-stream')

    def get_group_config(self, project_id: str, group_id: str) -> AnalysisGroup:

        """
        Retrieves analysis group configuration information
        """
        project = self._projects[project_id]

        # get the analysis group
        group = project.get_analysis_group(group_id)
        if not group:
            raise ExplorerRuntimeError(f"Analysis group not found: {group_id}")

        return group
