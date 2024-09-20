from typing import List, Dict, Any, Optional

from saas.sdk.base import SDKContext

from explorer.project import Project
from explorer.schemas import BuildModuleSpecification
from abc import ABC, abstractmethod


class BuildModule(ABC):
    _assets: Dict[str, Any] = {}

    @classmethod
    def has_asset(cls, asset_id: str) -> bool:
        return asset_id in cls._assets

    @classmethod
    def get_asset(cls, asset_id: str) -> Optional[Any]:
        return cls._assets.get(asset_id)

    @classmethod
    def set_asset(cls, asset_id: str, asset: Any) -> None:
        cls._assets[asset_id] = asset

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
    def specification(self, project: Project) -> BuildModuleSpecification:
        ...

    def default_config(self, project: Project) -> dict:
        default_config: dict[str, str] = {}

        module_specification_properties = self.specification(project).parameters_schema['properties']
        for prop in module_specification_properties:
            if module_specification_properties[prop].get('default') is not None:
                default_config[prop] = module_specification_properties[prop]['default']
            if module_specification_properties[prop].get('defaultValue') is not None:
                default_config[prop] = module_specification_properties[prop]['defaultValue']
        return default_config

    def upload(self, project: Project, content: dict, sdk: SDKContext) -> dict:
        return {}

    def update(self, project: Project, parameters: dict, sdk: SDKContext) -> dict:
        return {}

    @abstractmethod
    def raster_image(self, project: Project, parameters: dict, sdk: SDKContext) -> List[dict]:
        ...

    @abstractmethod
    def chart(self, project: Project, parameters: dict, sdk: SDKContext) -> dict:
        ...
