from __future__ import annotations

import inspect
import json
import os
import pkgutil
import shutil
import traceback
from threading import Lock
from typing import List, Dict, Optional, Tuple, Union

import numpy as np
import rasterio
from pydantic import BaseModel

from rasterio import CRS
from rasterio.features import rasterize
from saas.core.exceptions import SaaSRuntimeException
from saas.dor.schemas import DataObject
from saas.sdk.app.auth import User, UserDB

from saas.core.helpers import generate_random_string, hash_json_object, get_timestamp_now
from saas.core.logging import Logging
from saas.sdk.base import SDKContext, SDKCDataObject, LogMessage, connect
from shapely.geometry import Polygon, shape
from sqlalchemy import Column, String, create_engine, Integer
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy_json import NestedMutableJson

from explorer.dots.duct_lcz import LocalClimateZoneMap
from explorer.analysis.base import Analysis, AnalysisContext, AnalysisStatus
from explorer.bdp.base import ProjectGeometriesDB, GeometryType
from explorer.cache import CachedJSONObject, Cache
from explorer.dots.dot import ImportableDataObjectType, UploadPostprocessResult, DOTVerificationResult
from explorer.geodb import GeoZoneConfiguration
from explorer.pool import WorkerPool
from explorer.renderer.base import make_geojson_result, hex_color_to_components
from explorer.renderer.buildings_renderer import BuildingsRenderer
from explorer.renderer.landcover_renderer import LandcoverRenderer
from explorer.renderer.vegetation_renderer import VegetationRenderer
from explorer.schemas import BaseDataPackage, ProjectInfo, ProjectMeta, ExplorerRuntimeError, Scene, \
    AnalysesByScene, AnalysisGroup, AnalysesByConfiguration, AnalysisInfo, AnalysisResult, BoundingBox, Dimensions, \
    Network, ExplorerDatasetInfo, ZonesConfigurationMapping, ZoneConfiguration

logger = Logging.get('explorer.project')

Base = declarative_base()


def make_scene_id(project_id: str, zone_config_mapping: ZonesConfigurationMapping, module_settings: Dict) -> str:
    result = hash_json_object({
        'project_id': project_id,
        'zone_config_mapping': zone_config_mapping.dict(),
        'module_settings': module_settings
    })
    return result.hex()


def make_analysis_group_id(project_id: str, analysis_type: str, parameters: dict) -> str:
    result = hash_json_object({
        'project_id': project_id,
        'analysis_type': analysis_type,
        'parameters': parameters
    })
    return result.hex()


def make_analysis_id(group_id: str, scene_id: str, aoi_obj_id: str) -> str:
    result = hash_json_object({
        'group_id': group_id,
        'scene_id': scene_id,
        'aoi_obj_id': aoi_obj_id if aoi_obj_id is not None else ''
    })
    return result.hex()


def shorten_id(long_id: str) -> str:
    return long_id[:4] + '...' + long_id[-4:]


def make_analysis_info(record: DBAnalysisRun) -> AnalysisInfo:
    return AnalysisInfo(
        analysis_id=record.id, group_id=record.group_id, scene_id=record.scene_id,
        aoi_obj_id=record.aoi_obj_id, name=record.name, analysis_type=record.type,
        analysis_type_label=record.type_label, username=record.username,
        t_created=record.t_created, status=record.status, progress=record.progress,
        results=[AnalysisResult.parse_obj(result) for result in record.results],
        message=record.message
    )


class DBScene(Base):
    __tablename__ = 'scene'
    id = Column("id", String(64), primary_key=True)
    name = Column("name", String, nullable=False)
    zone_config_mapping = Column("zone_config_mapping", NestedMutableJson, nullable=False)
    bld_footprint_hash = Column("bld_footprint_hash", String(64), nullable=True)
    module_settings = Column("module_settings", NestedMutableJson, nullable=False)


class DBAnalysisGroup(Base):
    __tablename__ = 'analysis_group'
    id = Column("id", String(64), primary_key=True)
    name = Column("name", String(64), nullable=False)
    type = Column("type", String(64), nullable=False)
    type_label = Column("type_label", String(64), nullable=False)
    parameters = Column("parameters", NestedMutableJson, nullable=False)


class DBAnalysisRun(Base):
    __tablename__ = 'analysis_run'
    id = Column("id", String(64), primary_key=True)
    project_id = Column("project_id", String(64), nullable=False)
    group_id = Column("group_id", String(64), nullable=False)
    scene_id = Column("scene_id", String(64), nullable=False)
    aoi_obj_id = Column("aoi_obj_id", String(64), nullable=True)
    name = Column("name", String(64), nullable=False)
    type = Column("type", String, nullable=False)
    type_label = Column("type_label", String, nullable=False)
    username = Column("username", String(64), nullable=False)
    t_created = Column("t_created", Integer, nullable=False)
    status = Column("status", String, nullable=False)
    progress = Column("progress", Integer, nullable=False)
    checkpoint = Column("checkpoint", NestedMutableJson, nullable=False)
    results = Column("results", NestedMutableJson, nullable=False)
    message = Column("message", NestedMutableJson, nullable=True)
    runtime = Column("runtime", Integer, nullable=True)


class VFMixer:
    def __init__(self, project: Project):
        self._mutex = Lock()

        self._project = project
        self._lcz_obj_id = None
        self._lcz_content_path = None
        self._lcz_raster = None
        self._lcz_json = None
        self._bbox = None

        self._n_indices = None
        self._0_indices = None
        self._w_indices = None
        self._lcz_indices = None

    def refresh(self, sdk: SDKContext) -> None:
        # do we have a LCZ baseline?
        lcz_obj_id = self._project.info.bdp.references.get('lcz-baseline')
        if not lcz_obj_id:
            return

        with self._mutex:
            # load the default LCZ
            self._load_lcz(lcz_obj_id, sdk)

        # update the LCZ
        self.update_lcz(lcz_obj_id, sdk)

    def _load_lcz(self, lcz_obj_id: str, sdk: SDKContext) -> None:
        self._lcz_obj_id = lcz_obj_id
        self._lcz_content_path = os.path.join(self._project.info.temp_path, f'vf_mixer_{lcz_obj_id}.tiff')
        if not os.path.isfile(self._lcz_content_path):
            # find the data object
            lcz_obj = sdk.find_data_object(lcz_obj_id)
            if lcz_obj is None:
                logger.warning(f'LCZ data object {lcz_obj_id} not found')
                return

            # download the GeoTIFF
            lcz_obj.download(self._lcz_content_path)

        # extract the raster
        dot = LocalClimateZoneMap()
        self._lcz_json = dot.extract_feature(self._lcz_content_path, {})

        # load the bbox and the LCZ raster
        with rasterio.Env():
            with rasterio.open(self._lcz_content_path) as dataset:
                self._bbox = BoundingBox(west=dataset.bounds.left, east=dataset.bounds.right,
                                         south=dataset.bounds.bottom, north=dataset.bounds.top)
                self._lcz_raster = dataset.read(1)

    def update_lcz(self, lcz_obj_id: str, sdk: SDKContext) -> None:
        with self._mutex:
            # load the LCZ (if necessary)
            self._load_lcz(lcz_obj_id, sdk)

            # generate the indices
            self._n_indices = (self._lcz_raster < 30)  # not-urban cells
            self._z_indices = (self._lcz_raster == 0)  # no-value cells
            self._w_indices = (self._lcz_raster == 17) | (self._lcz_raster == 11)  # water cells

            # iterate over all urban LCZs and determine VF
            self._lcz_indices = []
            for i in range(10):
                self._lcz_indices.append((self._lcz_raster == int(31+i)))  # urban LCZ i cells

    def raster_lcz(self) -> dict:
        with self._mutex:
            return self._lcz_json

    def raster_vf(self, module_settings: dict) -> dict:
        with self._mutex:
            # create VF raster
            fractions = [module_settings[f"p_lcz{i+1}"] for i in range(10)]
            vf_raster = np.zeros(shape=self._lcz_raster.shape, dtype=np.float32)
            vf_raster[self._n_indices] = 100  # not-urban cells -> vegetation -> 100
            vf_raster[self._w_indices] = -1  # water -> not vegetation -> -1
            vf_raster[self._0_indices] = -1  # no-value -> not vegetation -> -1
            for i in range(10):
                vf_raster[self._lcz_indices[i]] = fractions[i]

            # turn it into JSON
            height = vf_raster.shape[0]
            width = vf_raster.shape[1]
            json_data = []
            for y in reversed(range(height)):
                for x in range(width):
                    json_data.append(int(vf_raster[y][x]))

            # create the heatmap
            return {
                'type': 'heatmap',
                'area': self._bbox.dict(),
                'grid': {'height': height, 'width': width},
                'legend': 'Urban Vegetation (in %)',
                'colors': [
                    {
                        'value': 0,
                        'color': hex_color_to_components('#993404', 255),
                        'label': '0%'
                    },
                    {
                        'value': 50,
                        'color': hex_color_to_components('#fffee6', 255),
                        'label': '50%'
                    },
                    {
                        'value': 100,
                        'color': hex_color_to_components('#00441b', 255),
                        'label': '100%'
                    }
                ],
                'data': json_data,
                'no_data': -1
            }

    def export_lcz_and_vf(self, module_settings: dict, lcz_export_path: str, vf_export_path: str,
                          sdk: SDKContext) -> None:
        with self._mutex:
            # download the LCZ
            lcz_obj_id = module_settings['landuse-landcover']['lcz_obj_id']
            lcz_obj = sdk.find_data_object(lcz_obj_id)
            if lcz_obj is None:
                raise ExplorerRuntimeError(f'LCZ data object {lcz_obj_id} not found')
            lcz_obj.download(lcz_export_path)

            # read the LCZ
            with rasterio.Env():
                with rasterio.open(lcz_export_path) as dataset:
                    bbox = BoundingBox(west=dataset.bounds.left, east=dataset.bounds.right,
                                       south=dataset.bounds.bottom, north=dataset.bounds.top)
                    lcz_raster = dataset.read(1)

            # create indices
            n_indices = (lcz_raster < 30)  # not-urban cells
            w_indices = (lcz_raster == 17) | (lcz_raster == 11)  # water cells
            z_indices = (lcz_raster == 0)  # 'no-value' cells
            lcz_indices = [(lcz_raster == int(31 + i)) for i in range(10)]  # i-th urban LCZ cells

            # create VF raster
            fractions = [module_settings['vegetation-fraction'][f"p_lcz{i+1}"] for i in range(10)]
            vf_raster = np.zeros(shape=lcz_raster.shape, dtype=np.float32)
            vf_raster[n_indices] = 1.0  # not-urban cells -> vegetation -> 1.0
            vf_raster[w_indices] = -1  # water -> not vegetation -> -1
            vf_raster[z_indices] = -1  # 'no-value' -> not vegetation -> -1
            for i in range(10):
                vf_raster[lcz_indices[i]] = fractions[i]*0.01

            # store as TIFF
            height = vf_raster.shape[0]
            width = vf_raster.shape[1]
            with rasterio.open(vf_export_path, 'w', driver='GTiff', height=height, width=width,
                               count=1, crs=CRS().from_epsg(4326), dtype=np.float32,
                               transform=rasterio.transform.from_bounds(west=bbox.west, south=bbox.south,
                                                                        east=bbox.east, north=bbox.north,
                                                                        width=width, height=height)
                               ) as dst:
                dst.write(vf_raster, 1)


def load_area_of_interest(sdk: SDKContext, download_path: str, aoi_obj_id: str) -> Optional[Polygon]:
    # find the AOI object
    aoi_obj = sdk.find_data_object(aoi_obj_id)
    if aoi_obj is not None:
        # download the aoi
        aoi_path = os.path.join(download_path, f"aoi.geojson")
        aoi_obj.download(aoi_path)

        try:
            # read the aoi
            with open(aoi_path, 'r') as f:
                # get the content and delete the file
                content = json.load(f)
                os.remove(aoi_path)

                # get the first feature and convert it into a shape
                feature = content['features'][0]
                geometry = feature['geometry']
                geometry = shape(geometry)

                # is it a polygon?
                if isinstance(geometry, Polygon):
                    return geometry
                else:
                    logger.warning(f"loaded AOI geometry not a polygon: {geometry}")
                    return None

        except Exception as e:
            logger.warning(f"encountered exception while loading AOI: {e}")


class AnalysisContextImpl(AnalysisContext):
    class Checkpoint(BaseModel):
        name: str
        args: Dict[str, Union[str, int, float, bool, list, dict]]

    def __init__(self, project, analysis_id: str, aoi_obj_id: str, sdk: SDKContext, analysis: Analysis,
                 session_maker: sessionmaker) -> None:
        super().__init__(project, analysis_id, sdk)

        self._mutex = Lock()
        self._aoi_obj_id = aoi_obj_id
        self._analysis = analysis
        self._session_maker = session_maker
        self._progress_weights: Dict[str, int] = {}
        self._progress_workers: Dict[str, float] = {}
        self._area_of_interest = None

        # get the analysis group and the scene
        if self._session_maker is not None:
            with self._session_maker() as session:
                record = session.query(DBAnalysisRun).get(self._analysis_id)
                project: Project = self._project  # for PyCharm only so it knows it's of type 'Project'
                self._group = project.get_analysis_group(record.group_id)
                self._scene = project.get_scene(record.scene_id)

    def aoi_obj_id(self) -> str:
        return self._aoi_obj_id

    def area_of_interest(self) -> Optional[Polygon]:
        # do we need to load the area of interest?
        if self._area_of_interest is None and self._aoi_obj_id is not None:
            self._area_of_interest = load_area_of_interest(self.sdk, self.analysis_path, self._aoi_obj_id)

        return self._area_of_interest

    def bld_footprint_obj_id(self) -> str:
        project: Project = self._project  # for PyCharm only so it knows it's of type 'Project'
        bld_footprint_hash = self._scene.bld_footprint_hash

        # do we already have building footprints with this hash?
        if bld_footprint_hash not in project.info.bld_footprints_by_hash:
            # generate a complete GeoJSON object with that scene's building footprints
            content_path = os.path.join(project.info.temp_path,
                                        f"building-footprints-{bld_footprint_hash}.geojson")
            project.geo_db.store_buildings_by_configuration(self._scene.zone_config_mapping, content_path)

            # upload that GeoJSON file to the DOR
            obj = self._sdk.upload_content(content_path, 'DUCT.GeoVectorData', 'geojson', False)
            obj.update_tags([
                DataObject.Tag(key='contents', value='building-footprints'),
                DataObject.Tag(key='bld_footprint_hash', value=bld_footprint_hash)
            ])

            # update the meta information
            project.info.bld_footprints_by_hash[bld_footprint_hash] = obj.meta.obj_id
            project.info.store()

            # do some clean-up
            os.remove(content_path)

        return project.info.bld_footprints_by_hash[bld_footprint_hash]

    def geometries(self, geo_type: GeometryType, set_id: str = None, area: Polygon = None,
                   use_cache: bool = True) -> Union[dict, list]:
        return self.project.geometries(geo_type, set_id=set_id, area=area, use_cache=use_cache).content()

    def add_update_tracker(self, tracker_id: str, weight: int) -> None:
        with self._mutex:
            self._progress_weights[tracker_id] = weight
            self._progress_workers[tracker_id] = 0

    def update_progress(self, tracker_id: str, progress: int) -> None:
        with self._mutex:
            # 'progress' indicates the progress in percent (0..100%) of a particular worker. within the bigger
            # picture this worker may have a certain weight W. the weighted progress indicates how much this
            # worker has contributed to the overall progress.
            self._progress_workers[tracker_id] = float(progress / 100.0) * self._progress_weights[tracker_id] if \
                tracker_id in self._progress_weights else 0

            # determine the overall progress (0..100) as the ratio of all weighted worker progresses and the sum of
            # all worker weights
            sum_weights = float(sum(list(self._progress_weights.values())))
            sum_progress = float(sum(list(self._progress_workers.values())))
            progress = int(100 * (sum_progress / sum_weights)) if sum_weights > 0 else 0

            with self._session_maker() as session:
                record = session.query(DBAnalysisRun).get(self._analysis_id)
                record.progress = progress
                session.commit()

    def update_message(self, message: LogMessage) -> None:
        with self._mutex:
            with self._session_maker() as session:
                record = session.query(DBAnalysisRun).get(self._analysis_id)
                record.message = message.dict()
                session.commit()

    def checkpoint(self) -> (str, Dict[str, Union[str, int, float, bool, list, dict]], AnalysisStatus):
        with self._session_maker() as session:
            record = session.query(DBAnalysisRun).get(self._analysis_id)
            checkpoint = self.Checkpoint.parse_obj(record.checkpoint)
            mapping = {status.value: status for status in AnalysisStatus}
            return checkpoint.name, checkpoint.args, mapping[record.status]

    def update_checkpoint(self, name: str, args: Dict[str, Union[str, int, float, bool, list, dict]]) -> (
            str, Dict[str, Union[str, int, float, bool, list, dict]], AnalysisStatus):
        with self._mutex:
            with self._session_maker() as session:
                # create checkpoint and dump to analysis folder
                checkpoint = self.Checkpoint(name=name, args=args)
                checkpoint_path = os.path.join(self.analysis_path, f"checkpoint.{checkpoint.name}.json")
                with open(checkpoint_path, 'w') as f:
                    f.write(json.dumps(checkpoint.dict()))

                record = session.query(DBAnalysisRun).get(self._analysis_id)
                record.checkpoint = checkpoint.dict()
                session.commit()

                mapping = {status.value: status for status in AnalysisStatus}
                return checkpoint.name, checkpoint.args, mapping[record.status]

    def run(self):
        try:
            # set the status to 'running'
            with self._session_maker() as session:
                record = session.query(DBAnalysisRun).get(self._analysis_id)
                record.status = AnalysisStatus.RUNNING.value
                session.commit()

            # perform the execution
            logger.info(f"[analysis:{shorten_id(self.analysis_id)}:run] begin execution")
            results = self._analysis.perform_analysis(self._group, self._scene, self)

            # if the analysis has not been cancelled, set the status to 'finished'
            with self._mutex:
                with self._session_maker() as session:
                    record = session.query(DBAnalysisRun).get(self._analysis_id)
                    if record.status == AnalysisStatus.RUNNING.value:
                        logger.info(f"[analysis:{shorten_id(self.analysis_id)}:run] end execution successfully.")
                        record.status = AnalysisStatus.COMPLETED.value
                        record.message = LogMessage(severity='info', message="Done").dict()
                        record.results = [result.dict() for result in results]
                        session.commit()

                    elif record.status == AnalysisStatus.CANCELLED.value:
                        record.message = LogMessage(severity='warning', message="Cancelled").dict()
                        session.commit()
                        logger.info(f"[analysis:{shorten_id(self.analysis_id)}:run] end execution after being cancelled.")

                    else:
                        logger.warning(f"[analysis:{shorten_id(self.analysis_id)}:run] end execution with unexpected "
                                       f"state '{record.status}'")

        except (ExplorerRuntimeError, SaaSRuntimeException) as e:
            logger.error(f"[analysis:{shorten_id(self.analysis_id)}:run] failed with error {e.id}: {e.reason}\n"
                         f"{e.details}")
            with self._mutex:
                with self._session_maker() as session:
                    record = session.query(DBAnalysisRun).get(self._analysis_id)
                    record.status = AnalysisStatus.FAILED.value
                    record.message = LogMessage(severity='error', message=e.reason).dict()
                    session.commit()

        except Exception as e:
            trace = ''.join(traceback.format_exception(None, e, e.__traceback__))
            logger.error(f"[analysis:{shorten_id(self.analysis_id)}:run] failed with unexpected exception: \n{trace}")
            with self._mutex:
                with self._session_maker() as session:
                    record = session.query(DBAnalysisRun).get(self._analysis_id)
                    record.status = AnalysisStatus.FAILED.value
                    record.message = LogMessage(severity='error', message=f"Unexpected exception: {str(e)}").dict()
                    session.commit()


class Project:
    def __init__(self, server, info: ProjectInfo) -> None:
        from explorer.server import ExplorerServer

        self._mutex = Lock()
        self._server: ExplorerServer = server
        self._info = info
        self._obj_cache = Cache(info.cache_path)
        self._geo_db = None
        self._pending_datasets: Dict[str, (ExplorerDatasetInfo, str, ImportableDataObjectType)] = {}
        self._pending_analyses: Dict[str, AnalysisContext] = {}

        # create folders
        os.makedirs(info.temp_path, exist_ok=True)
        os.makedirs(info.cache_path, exist_ok=True)
        os.makedirs(info.analysis_path, exist_ok=True)

        # initialise project db
        self._engine = None
        self._session = None

        # initialise mixers
        self._ah_mixer = None
        self._vf_mixer = None

    @classmethod
    def load(cls, server, project_folder: str) -> Project:
        # create the project
        project = Project(server, ProjectInfo.parse_file(os.path.join(project_folder, 'info.json')))

        # load the keystore of the owner
        owner = UserDB.get_user(project.info.owner)
        from explorer.server import ExplorerServer
        server: ExplorerServer = server
        sdk = connect(server.node_address, owner.keystore)

        # trigger initialisation
        logger.info(f"initialising project [load] {project.meta.id} owned by {project.info.owner}...")
        WorkerPool.instance().submit(project.initialise, sdk)

        return project

    @classmethod
    def create(cls, server, project_name: str, users: List[str], owner: str, projects_path: str, bdp: BaseDataPackage,
               bdp_db_src_path: str, sdk: SDKContext) -> Project:

        # create the project folder
        project_id = generate_random_string(16)
        project_folder = os.path.join(projects_path, project_id)
        os.makedirs(project_folder, exist_ok=True)

        # create project info and sync to disk
        info = ProjectInfo(
            meta=ProjectMeta(id=project_id, name=project_name, bounding_box=bdp.bounding_box, state='uninitialised'),
            users=users,
            owner=owner,
            folder=project_folder,
            bdp=bdp,
            bld_footprints_by_hash={},
            default_scene_id=None,
            datasets={}
        )
        info.store()

        # clone the BDP db
        shutil.copyfile(src=bdp_db_src_path, dst=info.geo_db_path)

        # create project and trigger initialisation
        project = Project(server, info)
        logger.info(f"initialising project [create] {project.meta.id} owned by {project.info.owner}...")
        WorkerPool.instance().submit(project.initialise, sdk)

        return project

    def initialise(self, sdk: SDKContext) -> None:
        try:
            # update state
            self._info.update(state='initialising')

            # create the geodb
            t0 = get_timestamp_now()
            logger.info(f"[{self.meta.id}] initialisation: geometry db...")
            self._geo_db = ProjectGeometriesDB(self._info, self._obj_cache)

            # initialise project db
            t1 = get_timestamp_now()
            logger.info(f"[{self.meta.id}] initialisation: project db...")
            self._engine = create_engine(f"sqlite:///{self._info.prj_db_path}")
            Base.metadata.create_all(self._engine)
            self._session = sessionmaker(bind=self._engine)

            # update mixers
            t2 = get_timestamp_now()
            logger.info(f"[{self.meta.id}] initialisation: refreshing mixers...")
            self._vf_mixer = VFMixer(self)
            self._vf_mixer.refresh(sdk)

            # update state
            t3 = get_timestamp_now()
            self._info.update(state='initialised')

            # load all analysis runs for this project
            t4 = get_timestamp_now()
            with self._session() as session:
                for record in session.query(DBAnalysisRun).filter_by(project_id=self.meta.id).all():
                    if record.status in [AnalysisStatus.INITIALISED.value, AnalysisStatus.RUNNING.value]:
                        self.resume_analysis(record.id, sdk)

            t5 = get_timestamp_now()

            dt1 = t1 - t0
            dt2 = t2 - t1
            dt3 = t3 - t2
            dt4 = t4 - t3
            dt5 = t5 - t4
            print(f"project.initialise: dt1={dt1} dt2={dt2} dt3={dt3} dt4={dt4} dt5={dt5}")

        except Exception as e:
            self._info.update(state='broken')

            trace = ''.join(traceback.format_exception(None, e, e.__traceback__))
            logger.error(trace)

    def search_for_classes(cls, package, base_class) -> List:
        # search for every class in a given base package
        classes = []
        for module_info in pkgutil.iter_modules(package.__path__):
            module = __import__(f"{package.__name__}.{module_info.name}", fromlist=[module_info.name])
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, base_class) and obj != base_class:
                    classes.append(obj)
            if hasattr(module, '__path__'):
                classes.extend(cls.search_for_classes(module, base_class))
        return classes

    @property
    def info(self) -> ProjectInfo:
        return self._info

    @property
    def meta(self) -> ProjectMeta:
        return self._info.meta

    @property
    def geo_db(self) -> ProjectGeometriesDB:
        return self._geo_db

    @property
    def vf_mixer(self) -> VFMixer:
        return self._vf_mixer

    @property
    def pending_datasets(self) -> List[ExplorerDatasetInfo]:
        with self._mutex:
            return [info for info, _, _ in self._pending_datasets.values()]

    @property
    def cache(self) -> Cache:
        return self._obj_cache

    def has_access(self, user: User) -> bool:
        with self._mutex:
            return user.login in self._info.users

    def is_owner(self, user: User) -> bool:
        with self._mutex:
            return user.login == self._info.owner

    def geometries(self, geo_type: GeometryType, set_id: str = None, area: Polygon = None,
                   use_cache: bool = True) -> CachedJSONObject:

        # this function generally just forwards the call to geodb, except for (a) scenes in which case
        # we obtain the zone config mapping and pass it along as well; and (b) zones which may have a
        # zone config mapping encoded in the set id.
        zone_config_mapping = None

        if set_id is not None:
            if set_id.startswith('scene:'):
                temp = set_id.split(':', 1)
                scene = self.get_scene(temp[1])
                if not scene:
                    raise ExplorerRuntimeError(f"Scene '{temp[1]}' not found.")

                zone_config_mapping = scene.zone_config_mapping

            elif set_id.startswith('zone_config:'):
                # first, determine all zones that have alternative configurations to begin with
                zones = [zone for zone in self._geo_db.get_zones().values() if zone.has_alternative_configs()]

                # determine use_defaults flag
                fields = set_id.split(':')
                use_defaults = len(fields) == 2 or fields[1].lower() == 'true'

                # extract the caller zone config mappings
                mapping: Dict[int, int] = {}
                for item in fields[-1].split(','):
                    if '=' in item:
                        item = item.split('=')
                        mapping[int(item[0])] = int(item[1])

                # create config mapping, including only zones with alt configs
                zone_config_mapping = ZonesConfigurationMapping.empty()
                for zone in zones:
                    configs = zone.get_configs()

                    # do we have a custom mapping for this zone?
                    if zone.id in mapping:
                        # check if this config id exists in the first place for this zone
                        found = False
                        config_id = mapping[zone.id]
                        for config in configs:
                            if config.id == config_id:
                                zone_config_mapping.selection[zone.id] = config_id
                                found = True
                                break

                        if not found:
                            raise ExplorerRuntimeError(f"Configuration {config_id} referenced but not found for "
                                                       f"zone {zone.id}")

                    # if not, just use the default config for this zone
                    elif use_defaults:
                        zone_config_mapping.selection[zone.id] = configs[0].id

        return self._geo_db.geometries(geo_type, set_id, area, zone_config_mapping, use_cache)

    def network_as_geojson(self, network_id: str, use_cache: bool = True) -> CachedJSONObject:
        return self._geo_db.network_as_geojson(network_id, use_cache)

    def network(self, network_id) -> Network:
        return self._geo_db.network(network_id)

    def get_scenes(self) -> List[Scene]:
        with self._mutex:
            with self._session() as session:
                result = []
                for record in session.query(DBScene).all():
                    result.append(Scene.parse_obj({
                        'id': record.id,
                        'name': record.name,
                        'zone_config_mapping': record.zone_config_mapping,
                        'bld_footprint_hash': record.bld_footprint_hash,
                        'module_settings': record.module_settings
                    }))

                return result

    def get_scene(self, scene_id: str) -> Optional[Scene]:
        with self._mutex:
            with self._session() as session:
                record = session.query(DBScene).get(scene_id)
                return Scene.parse_obj({
                    'id': record.id,
                    'name': record.name,
                    'zone_config_mapping': record.zone_config_mapping,
                    'bld_footprint_hash': record.bld_footprint_hash,
                    'module_settings': record.module_settings
                }) if record else None

    def create_scene(self, name: str, zone_config_mapping: ZonesConfigurationMapping, module_settings: Dict) -> Scene:
        logger.info(f"create scene -> module settings = {module_settings}")

        # fix the zone config mapping
        zone_config_mapping = self._geo_db.fix_zones_config_mapping(zone_config_mapping)

        # determine scene id based on all parameters and check if already exists
        scene_id = make_scene_id(self._info.meta.id, zone_config_mapping, module_settings)

        # create (or update) the scene
        with self._session() as session:
            # is there already a scene with this id?
            record = session.query(DBScene).get(scene_id)
            if record is not None:
                raise ExplorerRuntimeError("A scene with the exact parameters already exists, please change some "
                                           "parameters to create a new scene.",
                                           details={
                                                'scene_id': record.id,
                                                'name': record.name
                                           })

            # determine the building footprint id (i.e., zone config mapping hash)
            bf_hash = hash_json_object(zone_config_mapping.dict()).hex()

            session.add(DBScene(id=scene_id, name=name, zone_config_mapping=zone_config_mapping.dict(),
                                bld_footprint_hash=bf_hash, module_settings=module_settings))
            session.commit()

            return Scene(id=scene_id, name=name, zone_config_mapping=zone_config_mapping, bld_footprint_hash=bf_hash,
                         module_settings=module_settings)

    def delete_scene(self, scene_id: str) -> Scene:
        with self._mutex:
            with self._session() as session:
                # get the scene
                record = session.query(DBScene).get(scene_id)
                if not record:
                    raise ExplorerRuntimeError(f"No scene found with id={scene_id}")

                # delete the record
                session.query(DBScene).filter(DBScene.id == scene_id).delete()
                session.commit()

                return Scene.parse_obj({
                    'id': record.id,
                    'name': record.name,
                    'zone_config_mapping': record.zone_config_mapping,
                    'bld_footprint_hash': record.bld_footprint_hash,
                    'module_settings': record.module_settings
                })

    def add_zone_configs(self, config_name: str, selected_zones: List[int],
                         datasets: Dict[GeometryType, str]) -> Dict[int, ZoneConfiguration]:

        # find the pending datasets and add them as temp geometries to the geo db
        content_paths: Dict[GeometryType, str] = {}
        missing: List[str] = []
        with self._mutex:
            for geo_type, object_id in datasets.items():
                if object_id in self._pending_datasets:
                    _, content_path, _ = self._pending_datasets.pop(object_id)
                    content_paths[geo_type] = content_path
                else:
                    missing.append(object_id)

        # do we have any missing data objects?
        if len(missing) > 0:
            raise ExplorerRuntimeError(f"Missing data objects ({missing}) when attempting to add zone config.")

        # load the geometries, extract the features and them as temporary geometries to the geo db
        group_ids: Dict[GeometryType, str] = {}
        for geo_type, content_path in content_paths.items():
            # read the file contents
            with open(content_path, 'r') as f:
                content = json.loads(f.read())
                features = content['features']
                group_id = self.geo_db.add_temporary_geometries(features)
                group_ids[geo_type] = group_id

            # delete the file
            os.remove(content_path)

        # import the geometries as zone configuration
        self.geo_db.import_geometries_as_zone_configuration(group_ids, config_name, eligible_zone_ids=selected_zones)

        # find the zone configurations in the selected zones
        result: Dict[int, ZoneConfiguration] = {}
        for zone_id, zone in self.geo_db.get_zones(selected_zones).items():
            configs: List[GeoZoneConfiguration] = zone.get_configs()
            configs: Dict[str, GeoZoneConfiguration] = {config.name: config for config in configs}
            if config_name in configs:
                config = configs[config_name]
                result[zone_id] = ZoneConfiguration(config_id=config.id, name=config.name,
                                                    landuse_ids=config.landuse_ids,
                                                    landcover_ids=config.landcover_ids,
                                                    building_ids=config.building_ids,
                                                    vegetation_ids=config.vegetation_ids)
        return result

    def get_zone_configs(self, zone_id: int) -> List[ZoneConfiguration]:
        zone = self._geo_db.get_zone(zone_id)
        return [
            ZoneConfiguration(config_id=config.id, name=config.name, landuse_ids=config.landuse_ids,
                              landcover_ids=config.landcover_ids, building_ids=config.building_ids,
                              vegetation_ids=config.vegetation_ids)
            for config in zone.get_configs()
        ]

    def delete_zone_config(self, config_id: int) -> ZoneConfiguration:
        config = self._geo_db.delete_zone_configuration(config_id)
        return ZoneConfiguration(config_id=config.id, name=config.name, landuse_ids=config.landuse_ids,
                                 landcover_ids=config.landcover_ids, building_ids=config.building_ids,
                                 vegetation_ids=config.vegetation_ids)

    def get_analysis_info(self, analysis_id: str) -> Optional[AnalysisInfo]:
        with self._session() as session:
            record = session.query(DBAnalysisRun).get(analysis_id)
            return make_analysis_info(record) if record else None

    def get_analyses(self, scene_id: str = None, group_id: str = None, status: str = None) -> List[AnalysisInfo]:
        with self._session() as session:
            records = session.query(DBAnalysisRun).all()
            result = []
            for record in records:
                if (scene_id and scene_id != record.scene_id) or (group_id and group_id != record.group_id) or \
                        (status and status != record.status):
                    continue

                result.append(make_analysis_info(record))

        return result

    def get_analyses_by_scene(self, include_details: bool = True) -> List[AnalysesByScene]:
        with self._session() as session:
            result = []
            for record in session.query(DBScene).all():
                result.append(AnalysesByScene.parse_obj({
                    'scene_id': record.id,
                    'scene_name': record.name,
                    # 'parameters': record0.parameters,
                    'analyses': self.get_analyses(scene_id=record.id) if include_details else []
                }))

            return result

    def get_analyses_by_configuration(self, include_details: bool = True) -> List[AnalysesByConfiguration]:
        with self._session() as session:
            result = []
            for record in session.query(DBAnalysisGroup).all():
                result.append(AnalysesByConfiguration.parse_obj({
                    'group_id': record.id,
                    'group_name': record.name,
                    'type': record.type,
                    'type_label': record.type_label,
                    'parameters': record.parameters,
                    'analyses': self.get_analyses(group_id=record.id) if include_details else []
                }))

            return result

    def get_analysis_group(self, group_id: str) -> Optional[AnalysisGroup]:
        with self._session() as session:
            record = session.query(DBAnalysisGroup).get(group_id)
            return AnalysisGroup(
                id=record.id,
                name=record.name,
                type=record.type,
                type_label=record.type_label,
                parameters=record.parameters
            ) if record else None

    def create_analysis_group(self, group_id: str, group_name: str, analysis: Analysis,
                              parameters: Dict) -> AnalysisGroup:
        with self._session() as session:
            # is there already a group with this id?
            record = session.query(DBAnalysisGroup).filter_by(id=group_id).first()
            if record is None:
                # if not, create a new one
                session.add(DBAnalysisGroup(id=group_id,
                                            name=group_name,
                                            type=analysis.name(),
                                            type_label=analysis.label(),
                                            parameters=parameters))
            else:
                # TODO: decide whether to update the record -> group id is determined based on analysis type and
                #  parameters only (in addition to project id):
                #  group_id = make_analysis_id(project_id, analysis_type, parameters)
                #  In principle the name of the group can change and could be updated here but that behaviour should
                #  be discussed to see if it makes sense. For now, we assume it does and update the record.
                record.name = group_name

            session.commit()

            return AnalysisGroup(id=group_id, name=group_name, type=analysis.name(), type_label=analysis.label(),
                                 parameters=parameters)

    def submit_analysis(self, analysis: Analysis, group: AnalysisGroup, scene: Scene, aoi_obj_id: str,
                        name: str, user: User, sdk: SDKContext) -> AnalysisInfo:

        # create analysis id and path
        analysis_id = make_analysis_id(group.id, scene.id, aoi_obj_id)
        analysis_path = os.path.join(self._info.analysis_path, analysis_id)
        os.makedirs(analysis_path, exist_ok=True)

        # create the analysis run record
        with self._session() as session:
            # does the db record exist? if so, delete it.
            record = session.query(DBAnalysisRun).get(analysis_id)
            if record is not None:
                session.query(DBAnalysisRun).filter_by(id=analysis_id).delete()
                session.commit()

            # create db record
            record = DBAnalysisRun(
                id=analysis_id, project_id=self.meta.id, group_id=group.id, scene_id=scene.id,
                aoi_obj_id=aoi_obj_id, name=name, type=analysis.name(), type_label=analysis.label(),
                username=user.login, t_created=get_timestamp_now(), status='initialised', progress=0,
                checkpoint=AnalysisContextImpl.Checkpoint(name='initialised', args={}).dict(),
                results={}
            )
            session.add(record)
            session.commit()

            # ensure the execution nodes know about the identity of the user
            # TODO: potentially wasteful and redundant to do here. there is probably a better way.
            sdk.publish_identity(user.identity)

            info = AnalysisInfo(
                analysis_id=analysis_id, group_id=group.id, scene_id=scene.id, aoi_obj_id=aoi_obj_id,
                name=name, analysis_type=analysis.name(), analysis_type_label=analysis.label(),
                username=user.login, t_created=record.t_created, status=record.status, progress=0,
                results=[], message=None
            )

            # create analysis context
            context = AnalysisContextImpl(self, analysis_id, aoi_obj_id, sdk, analysis, self._session)
            context.start()

            return info

    def resume_analysis(self, analysis_id: str, sdk: SDKContext) -> AnalysisInfo:
        with self._session() as session:
            # does the db record exist?
            record = session.query(DBAnalysisRun).get(analysis_id)
            if record is None:
                raise ExplorerRuntimeError(f"Analysis {analysis_id} not found.")

            # does the context exist?
            context = self._pending_analyses.get(analysis_id, None)

            # is the analysis in a state in which it should already be running?
            if record.status in [AnalysisStatus.RUNNING.value, AnalysisStatus.INITIALISED.value]:
                if context is None:
                    logger.warning(f"[analysis:{shorten_id(analysis_id)}:resume] is in state '{record.status}' but "
                                   f"context not found -> attempting to resume...")
                    resume = True
                else:
                    logger.info(f"[analysis:{shorten_id(analysis_id)}:resume] context already exists.")
                    resume = False

            # is the analysis in a resumable state?
            elif record.status in [AnalysisStatus.FAILED.value, AnalysisStatus.CANCELLED.value]:
                if context is None:
                    logger.info(f"[analysis:{shorten_id(analysis_id)}:resume] is in state '{record.status}' -> "
                                f"attempting to resume...")
                    resume = True
                else:
                    logger.info(f"[analysis:{shorten_id(analysis_id)}:resume] context already exists.")
                    resume = False

            else:
                logger.info(f"[analysis:{shorten_id(analysis_id)}:resume] is in state '{record.status}' -> "
                            f"cannot be resumed.")
                resume = False

            # resume?
            if resume:
                # get the analysis
                analysis = self._server.get_analysis_instance(record.type)
                if analysis is None:
                    raise ExplorerRuntimeError(f"[analysis:{shorten_id(analysis_id)}:resume] analysis type "
                                               f"'{record.type}' needed but not found.")

                # create analysis context
                context = AnalysisContextImpl(self, analysis_id, record.aoi_obj_id, sdk, analysis,
                                              self._session)
                context.start()

            return make_analysis_info(record)

    def cancel_analysis(self, analysis_id: str) -> AnalysisInfo:
        with self._session() as session:
            # does the db record exist?
            record = session.query(DBAnalysisRun).get(analysis_id)
            if record is None:
                raise ExplorerRuntimeError(f"Analysis {analysis_id} not found.")

            # does the context exist?
            context = self._pending_analyses.pop(analysis_id, None)

            # is the analysis in a state in which it can be cancelled?
            if record.status in [AnalysisStatus.RUNNING.value, AnalysisStatus.INITIALISED.value]:
                if context is None:
                    logger.warning(f"[analysis:{shorten_id(analysis_id)}:cancel] is in state '{record.status}' but "
                                   f"context not found.")
                else:
                    logger.info(f"[analysis:{shorten_id(analysis_id)}:cancel] context found -> attempting to cancel...")

                record.status = AnalysisStatus.CANCELLED.value
                session.commit()

            else:
                logger.info(f"[analysis:{shorten_id(analysis_id)}:cancel] is in  state '{record.status}' -> "
                            f"cancellation not possible.")

        return make_analysis_info(record)

    def delete_analysis(self, analysis_id: str, sdk: SDKContext, cascading_delete: bool = True) -> AnalysisInfo:
        with self._session() as session:
            # does the db record exist?
            record = session.query(DBAnalysisRun).get(analysis_id)
            if record is None:
                raise ExplorerRuntimeError(f"Analysis {analysis_id} not found.")

            # is the analysis in a state in which it cannot be deleted?
            if record.status in [AnalysisStatus.RUNNING.value, AnalysisStatus.INITIALISED.value]:
                raise ExplorerRuntimeError(f"Analysis {analysis_id} cannot be deleted while in "
                                           f"state '{record.status}'. Try to cancel first.")

            # does the context exist?
            context = self._pending_analyses.pop(analysis_id, None)
            if context is not None:
                logger.warning(f"[analysis:{shorten_id(analysis_id)}:delete] is in state '{record.status}' but "
                               f"context was found among pending analyses.")

            info = make_analysis_info(record)

            # delete record
            logger.info(f"[analysis:{shorten_id(analysis_id)}:delete] deleting db record.")
            session.delete(record)
            session.commit()

            # delete data objects associated with this analysis (if applicable)
            if cascading_delete:
                # handle building AH profiles (if any)
                for obj in sdk.find_data_objects(data_type='duct.building-ah-profile'):
                    if obj.meta.tags.get('analysis_id', '') == analysis_id:
                        profile_name = obj.meta.tags.get('profile_name', '(no name)')
                        logger.info(f"[analysis:{shorten_id(analysis_id)}:delete] associated building AH profile "
                                    f"'{profile_name}' -> delete.")
                        obj.delete()

                # handle results
                for result in info.results:
                    for key, obj_id in result.obj_id.items():
                        obj = sdk.find_data_object(obj_id)
                        if obj is not None:
                            logger.info(f"[analysis:{shorten_id(analysis_id)}:delete] associated result "
                                        f"'{result.name}/{key}/{result.obj_id}' -> delete.")
                            obj.delete()
                        else:
                            logger.warning(f"[analysis:{shorten_id(analysis_id)}:delete] associated result "
                                           f"'{result.name}/{key}/{result.obj_id}' -> not found.")

            return info

    def get_result(self, analysis: Analysis, analysis_id: str, result: AnalysisResult, parameters: dict,
                   sdk: SDKContext) -> (str, str):

        # create cache id
        cache_obj_id = hash_json_object({
            'analysis_id': analysis_id,
            'result_id': result.name,
            'parameters': parameters
        }).hex()

        # determine raw file extension and file paths
        export_path = os.path.join(self.info.temp_path, f"{result.name}_{cache_obj_id}.export")
        json_path = os.path.join(self.info.temp_path, f"{result.name}_{cache_obj_id}.json")

        # if either file does not exist, extract the feature from the result
        if not os.path.isfile(export_path) or not os.path.isfile(json_path):
            # find the content data objects
            obj_mapping = {'#': result.obj_id} if isinstance(result.obj_id, str) else result.obj_id
            content_paths = {}
            for key, obj_id in obj_mapping.items():
                obj: SDKCDataObject = sdk.find_data_object(obj_id)
                if not obj:
                    raise ExplorerRuntimeError(f"Result data object '{result.name}/{key}/{result.obj_id}' not found")

                # download the content
                content_path = os.path.join(self.info.temp_path, f"result_{analysis_id}_{result.name}_{key}")
                obj.download(content_path)

                content_paths[key] = content_path

            # add helper functions to the parameters
            def helper_generate_mask(bounding_box: BoundingBox, dimensions: Dimensions) -> np.ndarray:
                # do we have a reference to an AOI to be used as mask?
                if 'display_aoi_obj_id' in parameters:
                    aoi_path = os.path.join(self.info.analysis_path, analysis_id,
                                            f"aoi_{parameters['display_aoi_obj_id']}.geojson")

                    # is the domain supposed to be the city admin zones?
                    if parameters['display_aoi_obj_id'] == 'city-admin-zones':
                        return self._geo_db.zones_mask(bounding_box, dimensions)

                    # if not, try to find and download the AOI object by its id
                    aoi_obj = sdk.find_data_object(parameters['display_aoi_obj_id'])
                    if aoi_obj is not None:
                        aoi_obj.download(aoi_path)

                    # if the file exists, use it
                    if os.path.isfile(aoi_path):
                        return self.generate_aoi_mask(aoi_path, bounding_box, dimensions)

                # should we use a specific AOI as mask?
                elif 'display_aoi_mask' in parameters and parameters['display_aoi_mask']:
                    # if the file exists, use it
                    aoi_path = os.path.join(self.info.analysis_path, analysis_id, 'aoi.geojson')
                    if os.path.isfile(aoi_path):
                        return self.generate_aoi_mask(aoi_path, bounding_box, dimensions)

                # if we reach here, either the AOI couldn't be found or we are not supposed to use as mask
                # -> display the entire domain (== no masking)
                return np.ones(shape=(dimensions.height, dimensions.width))

            parameters['__helper_mask_generator'] = helper_generate_mask
            parameters['__analysis_path'] = os.path.join(self.info.analysis_path, analysis_id)

            # extract the feature into files
            analysis.extract_feature(content_paths, result, parameters, self, sdk, export_path, json_path)

            # delete the temp content files
            for content_path in content_paths.values():
                if os.path.isfile(content_path):
                    os.remove(content_path)

        return export_path, json_path

    def get_result_delta(self, analysis: Analysis, analysis_id0: str, analysis_id1: str,
                         result0: AnalysisResult, result1: AnalysisResult, parameters0: dict, parameters1: dict,
                         sdk: SDKContext) -> (str, str):

        # check if result id/name is identical
        if result0.name != result1.name:
            raise ExplorerRuntimeError(f"Cannot determine delta between different kinds of results: {result0.name} vs "
                                       f"{result1.name}")
        result_name = result0.name

        # create cache id
        cache_obj_id = hash_json_object({
            'result_id': result_name,
            'analysis_id0': analysis_id0,
            'analysis_id1': analysis_id1,
            'parameters0': parameters0,
            'parameters1': parameters1
        }).hex()

        # determine raw file extension and file paths
        export_path = os.path.join(self.info.temp_path, f"{result_name}-delta_{cache_obj_id}.export")
        json_path = os.path.join(self.info.temp_path, f"{result_name}-delta_{cache_obj_id}.json")

        # if either file does not exist, extract the feature from the result
        if not os.path.isfile(export_path) or not os.path.isfile(json_path):
            def download(analysis_id: str, result: AnalysisResult) -> Dict[str, str]:
                obj_mapping = {'#': result.obj_id} if isinstance(result.obj_id, str) else result.obj_id
                content_paths = {}
                for key, obj_id in obj_mapping.items():
                    # find the content data object
                    obj: SDKCDataObject = sdk.find_data_object(obj_id)
                    if not obj:
                        raise ExplorerRuntimeError(f"Result data object '{result.name}/{result.obj_id}' not found")

                    # download the content
                    content_path = os.path.join(self.info.temp_path, f"result_{analysis_id}_{result.name}_{key}")
                    obj.download(content_path)

                    content_paths[key] = content_path

                return content_paths

            # add helper functions to the parameters
            def helper_generate_mask(bounding_box: BoundingBox, dimensions: Dimensions) -> np.ndarray:
                # read aoi (if any)
                aoi_path0 = os.path.join(self.info.analysis_path, analysis_id0, 'aoi.geojson')
                aoi_path1 = os.path.join(self.info.analysis_path, analysis_id1, 'aoi.geojson')
                # mask results according to the AOI only if AOI is saved and 'display_aoi_mask' checkbox is checked
                if os.path.isfile(aoi_path0) and os.path.isfile(aoi_path1) and \
                        ('display_aoi_mask' in parameters0 and parameters0['display_aoi_mask']) and \
                        ('display_aoi_mask' in parameters1 and parameters1['display_aoi_mask']):
                    # pick one aoi because anyway you can compare the results with same aoi
                    return self.generate_aoi_mask(aoi_path0, bounding_box, dimensions)
                else:
                    return self._geo_db.zones_mask(bounding_box, dimensions)

            # download the data objects
            content_paths0 = download(analysis_id0, result0)
            content_paths1 = download(analysis_id1, result1)

            # create joined parameters
            parameters0['__helper_mask_generator'] = helper_generate_mask
            parameters1['__helper_mask_generator'] = helper_generate_mask

            # extract the feature
            parameters0['__analysis_path'] = os.path.join(self.info.analysis_path, analysis_id0)
            parameters1['__analysis_path'] = os.path.join(self.info.analysis_path, analysis_id1)
            analysis.extract_delta_feature(content_paths0, result0, parameters0, content_paths1, result1, parameters1,
                                           self, sdk, export_path, json_path)

            # delete the temp content file
            for content_path in content_paths0.values():
                if os.path.isfile(content_path):
                    os.remove(content_path)

            for content_path in content_paths1.values():
                if os.path.isfile(content_path):
                    os.remove(content_path)

        return export_path, json_path

    def upload_dataset(self, temp_content_path: str, dot: ImportableDataObjectType) -> (
            bool, DOTVerificationResult, List[Tuple[str, str, UploadPostprocessResult]]):
        try:
            # verify the data object content
            verification_result = dot.verify_content(temp_content_path)

            # convert verification messages
            verification_messages = [
                LogMessage(severity=m.severity, message=m.message) for m in verification_result.messages
            ]

            is_verified = verification_result.is_verified
            data_format = verification_result.data_format

        except Exception as e:
            verification_messages = [
                LogMessage(severity='error', message=f"Exception during verification: {e}")
            ]

            is_verified = False
            data_format = None

        # was verification successful?
        if is_verified:
            # run the DOT-specific upload post-processing routine (note: this function may split the original file
            # into multiple data objects)
            upload_results: List[Tuple[str, str, UploadPostprocessResult]] = \
                dot.upload_postprocess(self, temp_content_path)

            # store the dataset info objects in the pending dict
            with self._mutex:
                for obj_id, obj_path, result in upload_results:
                    self._pending_datasets[obj_id] = (
                        ExplorerDatasetInfo(name='unknown', type=dot.name(), type_label=dot.label(), format=data_format,
                                            obj_id=obj_id, extra=result.extra if result.extra else {}),
                        obj_path,
                        dot
                    )

            return True, verification_messages, upload_results

        else:
            return False, verification_messages, []

    def update_dataset(self, object_id: str, args: dict, geo_type: Optional[GeometryType]) -> UploadPostprocessResult:
        with self._mutex:
            # check if we have that object to begin with
            if object_id not in self._pending_datasets:
                raise ExplorerRuntimeError(f"No pending dataset '{object_id}'")
            dataset, temp_path, dot = self._pending_datasets.get(object_id)

            response: UploadPostprocessResult = dot.update_preimport(self, temp_path, args, geo_type=geo_type)
            return response

    def import_dataset(self, object_id: str, sdk: SDKContext, name: str) -> ExplorerDatasetInfo:

        with self._mutex:
            # check if we have that object to begin with
            if object_id not in self._pending_datasets:
                raise ExplorerRuntimeError(f"No pending dataset '{object_id}'")
            dataset, temp_path, dot = self._pending_datasets.pop(object_id)

        # set the name
        dataset.name = name

        # add the dataset to the library
        self.info.add_dataset(dataset, temp_path, sdk)

        # delete the temporary file
        if os.path.isfile(temp_path):
            os.remove(temp_path)

        return dataset

    def delete_dataset(self, object_id: str, sdk: SDKContext) -> ExplorerDatasetInfo:
        with self._mutex:
            # is it a pending data object?
            if object_id in self._pending_datasets:
                # remove from the pending data sets and delete file
                dataset, temp_path, _ = self._pending_datasets.pop(object_id)
                os.remove(temp_path)

                # also delete from the geo db (if applicable)
                self._geo_db.delete_temporary_geometries(object_id)

                return dataset

            # is it an already imported dataset?
            elif object_id in self.info.datasets:
                return self.info.remove_dataset(object_id, sdk)

            else:
                raise ExplorerRuntimeError(f"Dataset '{object_id}' not found (pending and imported)")

    def get_dataset(self, object_id: str, sdk: SDKContext) -> List[Dict]:
        with self._mutex:
            # is it a pending data object?
            if object_id in self._pending_datasets:
                info, content_path, dot = self._pending_datasets[object_id]
                return [
                    dot.extract_feature(content_path, {})
                ]

            # is it an already imported dataset?
            elif object_id in self.info.datasets:
                # find the object in the DOR
                obj = sdk.find_data_object(object_id)
                if obj is None:
                    raise ExplorerRuntimeError(f"Imported dataset '{object_id}' not found in DOR")

                # download it...
                content_path = os.path.join(self.info.temp_path, object_id)
                if not os.path.isfile(content_path):
                    obj.download(content_path)

                # is it a zone configuration
                info: ExplorerDatasetInfo = self.info.datasets[object_id]
                if info.type == 'zone-configuration':
                    with open(content_path, 'r') as f:
                        zone_configs: Dict[int, dict] = json.load(f)

                    set_id: str = ','.join([f"{zid}={cfg['config_id']}" for zid, cfg in zone_configs.items()])
                    set_id: str = f"zone_config:false:{set_id}"

                    geo_bf = self.geometries(GeometryType.building, set_id=set_id).content()
                    geo_lc = self.geometries(GeometryType.landcover, set_id=set_id).content()
                    geo_vg = self.geometries(GeometryType.vegetation, set_id=set_id).content()

                    result = []
                    if len(geo_bf['features']) > 0:
                        result.append(make_geojson_result('Buildings', geo_bf, BuildingsRenderer().get()))

                    if len(geo_lc['features']) > 0:
                        result.append(make_geojson_result('Land-cover', geo_lc, LandcoverRenderer().get()))

                    if len(geo_vg['features']) > 0:
                        result.append(make_geojson_result('Vegetation', geo_vg, VegetationRenderer().get()))

                    return result

                else:
                    # get the DOT
                    dot = self._server.get_dot(info.type)
                    if dot is None:
                        raise ExplorerRuntimeError(f"Data Object Type '{info.type}' not found")

                    return [
                        dot.extract_feature(content_path, {})
                    ]

            else:
                raise ExplorerRuntimeError(f"Dataset '{object_id}' not found (pending and imported)")

    def generate_aoi_mask(self, aoi_path: str, bounding_box: BoundingBox, dimensions: Dimensions) -> np.ndarray:
        # get geometries from saved aoi data
        with open(aoi_path, 'r') as infile:
            geojson = json.load(infile)

        with rasterio.Env():
            # calculate the transformation matrix using result bbox and dimensions
            transform = rasterio.transform.from_bounds(bounding_box.west, bounding_box.south,
                                                       bounding_box.east, bounding_box.north,
                                                       dimensions.width, dimensions.height)

            # rasterize AOI
            raster = rasterize([(feature['geometry'], 1) for feature in geojson['features']],
                               transform=transform, out_shape=(dimensions.height, dimensions.width), fill=0)
            return raster
