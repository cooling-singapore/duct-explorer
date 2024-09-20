from typing import List, Dict

from shapely import Polygon

from explorer.geodb import GeometryType
from explorer.project import Project
from explorer.renderer.base import make_geojson_result
from explorer.renderer.zone_renderer import ZoneRenderer
from explorer.view.base import View


class DefaultView(View):
    def name(self) -> str:
        return 'default'

    def generate(self, project: Project, set_id: str = None, area: Polygon = None,
                 use_cache: bool = True) -> List[Dict]:

        #  make zone layer
        geojson = project.geometries(GeometryType.zone, set_id=set_id, area=area, use_cache=use_cache).content()
        renderer = ZoneRenderer()
        return [
            make_geojson_result('Zones', geojson, renderer.get())
        ]
