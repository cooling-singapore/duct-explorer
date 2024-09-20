from __future__ import annotations

import json
import os
from typing import Dict, List, Union, Set, Optional, Any

from pydantic import BaseModel
from saas.core.exceptions import SaaSRuntimeException
from saas.core.helpers import hash_string_object
from saas.core.logging import Logging
from saas.dor.schemas import DataObject
from saas.sdk.base import SDKContext, SDKCDataObject
from shapely import Polygon

logger = Logging.get('explorer.schemas')


class ExplorerRuntimeError(SaaSRuntimeException):
    pass


class BoundingBox(BaseModel):
    west: float
    north: float
    east: float
    south: float

    def as_str(self) -> str:
        return f"{self.west}, {self.north}, {self.east}, {self.south}"

    def check_sanity(self):
        if not (-180 <= self.west <= 180):
            raise ExplorerRuntimeError(f"Invalid western longitude: {self.west}")

        if not (-180 <= self.east <= 180):
            raise ExplorerRuntimeError(f"Invalid eastern longitude: {self.east}")

        if not (-90 <= self.south <= 90):
            raise ExplorerRuntimeError(f"Invalid southern latitude: {self.south}")

        if not (-90 <= self.north <= 90):
            raise ExplorerRuntimeError(f"Invalid northern latitude: {self.north}")

        if self.west > self.east:
            raise ExplorerRuntimeError(f"Invalid west-east relationship: west={self.west} east={self.east}")

        if self.south > self.north:
            raise ExplorerRuntimeError(f"Invalid south-north relationship: south={self.south} north={self.north}")

    def as_grid_bounds(self, grid_bbox: BoundingBox, grid_dim: Dimensions) -> dict:
        def convert_lat(lat: float) -> int:
            y = (lat - grid_bbox.south) / (grid_bbox.north - grid_bbox.south)
            y *= grid_dim.height
            return int(y)

        def convert_lon(lon: float) -> int:
            x = (lon - grid_bbox.west) / (grid_bbox.east - grid_bbox.west)
            x *= grid_dim.width
            return int(x)

        return {
            'west': convert_lon(self.west),
            'north': convert_lat(self.north),
            'east': convert_lon(self.west),
            'south': convert_lat(self.south)
        }

    def as_shapely_polygon(self) -> Polygon:
        return Polygon([(self.west, self.north), (self.east, self.north), (self.east, self.south),
                        (self.west, self.south), (self.west, self.north)])


class Dimensions(BaseModel):
    width: int
    height: int

    def as_str(self) -> str:
        return f"{self.width}, {self.height}"


class BaseDataPackage(BaseModel):
    name: str
    city_name: str
    bounding_box: BoundingBox
    grid_dimension: Dimensions
    timezone: str
    references: dict

    @property
    def id(self) -> str:
        return hash_string_object(f"{self.city_name}:{self.name}").hex()

    def download(self, context: SDKContext, folder: str) -> dict:
        # first, find all the base data objects
        objects: Dict[str, Union[str, SDKCDataObject]] = {}
        for name, obj_id in self.references.items():
            # do we have the data object?
            objects[name] = context.find_data_object(obj_id)
            if objects[name] is None:
                raise ExplorerRuntimeError(f"Base data object '{name}:{obj_id} not found")

        # then download all the base data objects and replace the object wrapper with the path
        for name, obj in objects.items():
            path = os.path.join(folder, name)
            obj.download(path)
            objects[name] = path

        return objects

    @classmethod
    def upload(cls, context: SDKContext, city: str, package_name: str, bounding_box: BoundingBox,
               grid_dimensions: Dimensions, timezone: str,
               bdp_mapping: dict[str, dict]) -> BaseDataPackage:

        # upload the data objects
        objects = {
            name: context.upload_content(
                content_path=i['path'],
                data_type=i['type'],
                data_format=i['format'],
                access_restricted=False
            ) for name, i in bdp_mapping.items()
        }

        # add labels to the data objects
        for component, obj in objects.items():
            obj.update_tags([
                DataObject.Tag(key='bdp-component', value=component),
                DataObject.Tag(key='bdp-name', value=f"{city}|{package_name}")
            ])

        # make the references dict
        references = {key: obj.meta.obj_id for key, obj in objects.items()}

        # make the BDP object
        bdp = BaseDataPackage.parse_obj({
            'name': package_name,
            'city_name': city,
            'bounding_box': bounding_box.dict(),
            'grid_dimension': grid_dimensions.dict(),
            'timezone': timezone,
            'references': references
        })

        return bdp


class NetworkNode(BaseModel):
    id: str
    lat: float
    lon: float
    properties: dict[str, Any]


class NetworkLink(BaseModel):
    id: str
    from_node: str
    to_node: str
    properties: dict[str, Any]


class Network(BaseModel):
    nodes: Dict[str, NetworkNode]
    links: Dict[str, NetworkLink]

    def has_contents(self) -> bool:
        return len(self.nodes) > 0 and len(self.links) > 0


class TimestampHistogram(BaseModel):
    bucket_size: float
    buckets: Dict[int, Set[int]]

    def filter(self, eligible: Set[int]) -> TimestampHistogram:
        result = TimestampHistogram(bucket_size=self.bucket_size, buckets={}, n=0)

        for idx, bucket in self.buckets.items():
            b = set(bucket).intersection(eligible)
            if len(b) > 0:
                result.buckets[idx] = b

        return result

    @property
    def key_range(self) -> (float, float):
        return (
            min(self.buckets.keys()) * self.bucket_size,
            max(self.buckets.keys()) * self.bucket_size
        )

    @property
    def n(self) -> int:
        n = 0
        for s in self.buckets.values():
            n += len(s)
        return n

    def get(self, key_range: (float, float)) -> Set[int]:
        # convert key range into index range
        half_size = self.bucket_size / 2.0
        idx_range = (
            int((key_range[0] + half_size) / self.bucket_size),
            int((key_range[1] + half_size) / self.bucket_size)
        )

        # determine the result, i.e., all timestamps that are in buckets within the key range
        result = set()
        if idx_range[0] <= idx_range[1]:
            for idx in range(idx_range[0], idx_range[1] + 1):
                result = result.union(self.buckets[idx]) if idx in self.buckets else result

        else:
            for idx in range(idx_range[0], max(self.buckets.keys()) + 1):
                result = result.union(self.buckets[idx]) if idx in self.buckets else result

            for idx in range(min(self.buckets.keys()), idx_range[1] + 1):
                result = result.union(self.buckets[idx]) if idx in self.buckets else result

        return result

    def add(self, key: float, timestamp: int) -> None:
        idx = int((key + self.bucket_size / 2.0) / self.bucket_size)
        if idx in self.buckets:
            self.buckets[idx].add(timestamp)
        else:
            self.buckets[idx] = {timestamp}


class BDPInfo(BaseModel):
    id: str
    name: str
    city: str
    bounding_box: BoundingBox
    timezone: str
    description: str


class BDPsByCity(BaseModel):
    city: str
    packages: List[BDPInfo]


class AnalysisSpecification(BaseModel):
    name: str
    label: str
    type: str
    area_selection: bool
    parameters_schema: Dict
    description: str
    further_information: str
    sample_image: str
    ui_schema: Dict
    required_processors: List[str]
    required_bdp: List[str]
    result_specifications: Dict


class BuildModuleSpecification(BaseModel):
    name: str
    label: str
    type: str
    priority: int
    description: str
    parameters_schema: Dict
    has_raster_map: bool
    has_update_map: bool
    has_area_selector: bool
    hide_settings_accordion: bool
    editable: bool
    editorConfig: Dict
    ui_schema: Dict
    icon: str
    settings_description: Optional[str]
    settings_image: Optional[str]


class PrioritisedItem(BaseModel):
    priority: int
    name: str


class ExplorerPublicInformation(BaseModel):
    server_version: str


class ExplorerInformation(BaseModel):
    build_modules: List[str]
    analyses_types: List[str]
    dots: List[str]
    bdps: List[BDPsByCity]
    core_version: str


class ProjectMeta(BaseModel):
    id: str
    name: str
    state: str
    bounding_box: BoundingBox


class ExplorerDatasetInfo(BaseModel):
    name: str
    type: str
    type_label: str
    format: str
    obj_id: Optional[str]
    extra: Dict[str, str]


class ProjectInfo(BaseModel):
    meta: ProjectMeta
    users: List[str]
    owner: str
    folder: str
    bdp: BaseDataPackage
    bld_footprints_by_hash: Dict[str, str]
    datasets: Dict[str, ExplorerDatasetInfo]

    def store(self, indent: int = 4) -> str:
        path = os.path.join(self.folder, 'info.json')
        with open(path, 'w') as f:
            json.dump(self.dict(), f, indent=indent)
        return path

    def update(self, state: str = None) -> None:
        self.meta.state = state if state else self.meta.state
        self.store()

    def add_dataset(self, dataset: ExplorerDatasetInfo, content_path: str, sdk: SDKContext) -> ExplorerDatasetInfo:
        # add the object to the DOR
        obj = sdk.upload_content(content_path, dataset.type, dataset.format, False, False)
        dataset.obj_id = obj.meta.obj_id

        # update the project info
        if self.datasets is None:
            self.datasets = {dataset.obj_id: dataset}
        else:
            self.datasets[dataset.obj_id] = dataset

        self.store()
        return dataset

    def remove_dataset(self, object_id: str, sdk: SDKContext) -> ExplorerDatasetInfo:
        # check if we have this dataset
        if self.datasets is None or object_id not in self.datasets:
            raise ExplorerRuntimeError(f"Dataset {object_id} not found")
        dataset = self.datasets.pop(object_id)

        # find the dataset object in the DOR
        obj = sdk.find_data_object(dataset.obj_id)
        if obj is None:
            raise ExplorerRuntimeError(f"Data object {dataset.obj_id} not found in DOR")
        obj.delete()

        self.store()
        return dataset

    @property
    def cache_path(self) -> str:
        return os.path.join(self.folder, 'cache')

    @property
    def temp_path(self) -> str:
        return os.path.join(self.folder, 'temp')

    @property
    def analysis_path(self) -> str:
        return os.path.join(self.folder, 'analyses')

    @property
    def prj_db_path(self) -> str:
        return os.path.join(self.folder, 'project.db')

    @property
    def geo_db_path(self) -> str:
        return os.path.join(self.folder, 'geometries.db')


class ZonesConfigurationMapping(BaseModel):
    selection: Dict[int, int]

    @classmethod
    def empty(cls) -> ZonesConfigurationMapping:
        return ZonesConfigurationMapping(selection={})


class ZoneConfiguration(BaseModel):
    config_id: int
    name: str
    landuse_ids: List[int]
    landcover_ids: List[int]
    building_ids: List[int]
    vegetation_ids: List[int]


class Scene(BaseModel):
    id: str
    name: str
    zone_config_mapping: ZonesConfigurationMapping
    bld_footprint_hash: str
    module_settings: Dict[str, dict]


class AnalysisResult(BaseModel):
    class Specification(BaseModel):
        description: str
        parameters: Dict

    name: str
    label: Optional[str]
    obj_id: Union[str, Dict[str, str]]  # TODO: 'str' is for backward compatibility -> remove at some point.
    specification: AnalysisResult.Specification
    export_format: str
    extras: Optional[Dict]


class AnalysisInfo(BaseModel):
    analysis_id: str
    group_id: str
    scene_id: str
    aoi_obj_id: Optional[str]
    name: str
    analysis_type: str
    analysis_type_label: str
    username: str
    t_created: int
    status: str
    progress: int
    results: List[AnalysisResult]
    message: Optional[dict]


class AnalysesByScene(BaseModel):
    scene_id: str
    scene_name: str
    analyses: List[AnalysisInfo]


class AnalysesByConfiguration(BaseModel):
    group_id: str
    group_name: str
    type: str
    type_label: str
    parameters: Dict
    analyses: List[AnalysisInfo]


class AnalysisGroup(BaseModel):
    id: str
    name: str
    type: str
    type_label: str
    parameters: Dict


class AnalysisCompareResults(BaseModel):
    results0: List[dict]
    results1: List[dict]
    chart_results: Optional[List[dict]]


class WindVectorDetails(BaseModel):
    id: str
    lat: float
    lon: float
    wind_speed: float
    wind_direction: float
