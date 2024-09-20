from __future__ import annotations

import os
import threading
from enum import Enum
from logging import Logger
from typing import Dict, List, Union, Optional

from abc import ABC, abstractmethod

from explorer.geodb import GeometryType
from saas.core.logging import Logging
from saas.sdk.base import SDKContext, LogMessage
from shapely import Polygon

from explorer.schemas import AnalysisResult, Scene, AnalysisGroup, BaseDataPackage, AnalysisSpecification, \
    AnalysisCompareResults

logger = Logging.get('explorer.analysis')


class AnalysisStatus(Enum):
    INITIALISED = 'initialised'
    RUNNING = 'running'
    CANCELLED = 'cancelled'
    FAILED = 'failed'
    COMPLETED = 'completed'


class AnalysisContext(threading.Thread, ABC):
    def __init__(self, project, analysis_id: str, sdk: SDKContext) -> None:
        super().__init__(name=f"analysis:{analysis_id}")

        self._logger = Logging.get('duct.analysis.muc')
        self._project = project
        self._analysis_id = analysis_id
        self._bdp: BaseDataPackage = project.info.bdp
        self._sdk = sdk

    @property
    def logger(self) -> Logger:
        return self._logger

    @property
    def project(self):
        return self._project

    @property
    def analysis_id(self) -> str:
        return self._analysis_id

    @property
    def analysis_path(self) -> str:
        return os.path.join(self._project.info.analysis_path, self._analysis_id)

    @property
    def bdp(self) -> BaseDataPackage:
        return self._bdp

    @property
    def sdk(self) -> SDKContext:
        return self._sdk

    @abstractmethod
    def aoi_obj_id(self) -> str:
        ...

    @abstractmethod
    def area_of_interest(self) -> Optional[Polygon]:
        ...

    @abstractmethod
    def bld_footprint_obj_id(self) -> str:
        ...

    @abstractmethod
    def geometries(self, geo_type: GeometryType, set_id: str = None, area: Polygon = None,
                   use_cache: bool = True) -> Union[dict, list]:
        ...

    @abstractmethod
    def add_update_tracker(self, tracker_id: str, weight: int) -> None:
        ...

    @abstractmethod
    def update_progress(self, tracker_id: str, progress: int) -> None:
        ...

    @abstractmethod
    def update_message(self, message: LogMessage) -> None:
        ...

    @abstractmethod
    def checkpoint(self) -> (str, Dict[str, Union[str, int, float, bool, list, dict]], AnalysisStatus):
        ...

    @abstractmethod
    def update_checkpoint(self, name: str, args: Dict[str, Union[str, int, float, bool, list, dict]]) -> (
            str, Dict[str, Union[str, int, float, bool, list, dict]], AnalysisStatus):
        ...


class Analysis(ABC):
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def label(self) -> str:
        ...

    @abstractmethod
    def type(self) -> str:
        ...

    @abstractmethod
    def specification(self, project, sdk: SDKContext, aoi_obj_id: str = None,
                      scene_id: str = None) -> AnalysisSpecification:
        ...

    @abstractmethod
    def perform_analysis(self, group: AnalysisGroup, scene: Scene, context: AnalysisContext) -> List[AnalysisResult]:
        ...

    @abstractmethod
    def extract_feature(self, content_paths: Dict[str, str], result: AnalysisResult, parameters: dict,
                        project, sdk: SDKContext, export_path: str, json_path: str) -> None:
        ...

    @abstractmethod
    def extract_delta_feature(self, content_paths0: Dict[str, str], result0: AnalysisResult, parameters0: dict,
                              content_paths1: Dict[str, str], result1: AnalysisResult, parameters1: dict,
                              project, sdk: SDKContext, export_path: str, json_path: str) -> None:
        ...

    def verify_parameters(self, project, scene: Scene, parameters: dict, aoi: Polygon = None) -> List[LogMessage]:
        return []

    def get_compare_results(self, content0: dict, content1: dict) -> AnalysisCompareResults:
        normalised_results_list = list(self.normalise_parameters(content0, content1))
        return AnalysisCompareResults(
            results0=[normalised_results_list[0][0]],
            results1=[normalised_results_list[1][0]],
            chart_results=[normalised_results_list[0][1]] if len(normalised_results_list[0]) > 1 else None
        )

    def normalise_parameters(self, content0: dict, content1: dict) -> (Dict, Dict):
        return content0, content1
