import abc
from enum import Enum
from typing import Optional, List, Tuple, Dict, Literal

from pydantic import BaseModel
from saas.core.exceptions import ExceptionContent
from saas.core.helpers import generate_random_string

from explorer.geodb import GeometryType


class UploadPostprocessResult(BaseModel):
    title: str
    description: str
    geo_type: Optional[str]
    mode: str
    editor_config: Optional[dict]
    extra: Dict[str, str]


class UploadDatasetResponseItem(BaseModel):
    obj_id: str
    info: UploadPostprocessResult
    target: str


class ImportTarget(Enum):
    geodb = 'geodb'
    library = 'library'


class DOTRuntimeError(Exception):
    def __init__(self, reason: str, details: dict = None):
        self._content = ExceptionContent(id=generate_random_string(16), reason=reason, details=details)

    @property
    def id(self):
        return self._content.id

    @property
    def reason(self):
        return self._content.reason

    @property
    def details(self):
        return self._content.details

    @property
    def content(self) -> ExceptionContent:
        return self._content


class DOTVerificationMessage(BaseModel):
    severity: Literal['info', 'warning', 'error']
    message: str


class DOTVerificationResult(BaseModel):
    messages: List[DOTVerificationMessage]
    is_verified: bool
    data_format: str


class DataObjectType(abc.ABC):
    @abc.abstractmethod
    def name(self) -> str:
        pass

    @abc.abstractmethod
    def label(self) -> str:
        pass

    @abc.abstractmethod
    def supported_formats(self) -> List[str]:
        pass

    def verify_content(self, content_path: str) -> DOTVerificationResult:
        return DOTVerificationResult(
            messages=[
                DOTVerificationMessage(severity='error', message=f'verify_content() not implemented for {self.name()}')
            ],
            is_verified=False
        )

    @abc.abstractmethod
    def extract_feature(self, content_path: str, parameters: dict) -> Dict:
        pass

    @abc.abstractmethod
    def extract_delta_feature(self, content_path0: str, content_path1: str, parameters: dict) -> Dict:
        pass

    @abc.abstractmethod
    def export_feature(self, content_path: str, parameters: dict, export_path: str, export_format: str) -> None:
        pass

    @abc.abstractmethod
    def export_delta_feature(self, content_path0: str, content_path1: str, parameters: dict,
                             export_path: str, export_format: str) -> None:
        pass


class ImportableDataObjectType(DataObjectType):
    @abc.abstractmethod
    def target(self) -> ImportTarget:
        pass

    @abc.abstractmethod
    def description(self) -> str:
        pass

    @abc.abstractmethod
    def preview_image_url(self) -> str:
        pass

    @abc.abstractmethod
    def upload_postprocess(self, project, temp_obj_path: str) -> List[Tuple[str, str, UploadPostprocessResult]]:
        pass

    @abc.abstractmethod
    def update_preimport(self, project, obj_path: str, args: dict,
                         geo_type: Optional[GeometryType]) -> UploadPostprocessResult:
        pass
