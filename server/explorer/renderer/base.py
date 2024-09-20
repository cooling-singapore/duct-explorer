from abc import ABC, abstractmethod
from typing import Optional, Union


def hex_color_to_components(color: str, alpha: Union[float, int] = None) -> (int, int, int, Union[float, int]):
    if alpha is None:
        alpha = 1.0
    elif isinstance(alpha, float):
        if alpha < 0.0:
            alpha = 0.0
        elif alpha > 1.0:
            alpha = 1.0
    else:
        if alpha < 0:
            alpha = 0
        elif alpha > 255:
            alpha = 255

    color = color.lstrip('#')
    return [
        int(color[0:2], 16),
        int(color[2:4], 16),
        int(color[4:6], 16),
        alpha
    ]


class GeometriesRenderer(ABC):
    @abstractmethod
    def get(self) -> dict:
        ...


class NetworkRenderer(ABC):

    @abstractmethod
    def type(self) -> str:
        ...

    @abstractmethod
    def title(self) -> str:
        ...

    @abstractmethod
    def point_title(self) -> str:
        ...

    @abstractmethod
    def line_title(self) -> str:
        ...

    @abstractmethod
    def line_color(self) -> str:
        ...

    def line_thickness(self) -> str:
        return '2'

    @abstractmethod
    def point_renderer(self) -> dict:
        ...

    def line_renderer(self, field: Optional[str] = None) -> dict:
        return {
            "type": "simple",
            "symbol": {
                "type": "simple-line",
                "color": self.line_color(),
                "width": self.line_thickness(),
                "style": "solid"
            }
        }


class Renderer(ABC):

    @abstractmethod
    def type(self) -> str:
        ...

    @abstractmethod
    def title(self) -> str:
        ...

    @abstractmethod
    def renderer(self, title, field, legend_title, show_outline) -> dict:
        ...


def make_geojson_result(title: str, geojson: dict, renderer: dict) -> dict:
    return {
        "type": "geojson",
        "title": title,
        "geojson": geojson,
        "renderer": renderer
    }
