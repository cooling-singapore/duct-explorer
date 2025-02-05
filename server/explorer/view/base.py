from abc import ABC, abstractmethod
from typing import List, Dict

from shapely import Polygon

from explorer.project import Project


class View(ABC):
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def generate(self, project: Project, set_id: str = None, area: Polygon = None,
                 use_cache: bool = True) -> List[Dict]:
        ...
