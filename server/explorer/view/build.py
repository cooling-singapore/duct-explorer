from typing import List, Dict

from shapely import Polygon

from explorer.geodb import GeometryType
from explorer.project import Project
from explorer.renderer.base import make_geojson_result
from explorer.renderer.buildings_renderer import BuildingsRenderer
from explorer.renderer.landcover_renderer import LandcoverRenderer
from explorer.renderer.vegetation_renderer import VegetationRenderer
from explorer.renderer.zone_renderer import ZoneRenderer
from explorer.view.base import View


class BuildView(View):
    def name(self) -> str:
        return 'build'

    def generate(self, project: Project, set_id: str = None, area: Polygon = None,
                 use_cache: bool = True) -> List[Dict]:

        geojson_z = project.geometries(GeometryType.zone, set_id=set_id, area=area, use_cache=use_cache).content()
        renderer_z = ZoneRenderer()

        if set_id:
            geojson_l = project.geometries(GeometryType.landcover, set_id=set_id, area=area, use_cache=use_cache).content()
            geojson_b = project.geometries(GeometryType.building, set_id=set_id, area=area, use_cache=use_cache).content()
            geojson_v = project.geometries(GeometryType.vegetation, set_id=set_id, area=area, use_cache=use_cache).content()

            renderer_l = LandcoverRenderer()
            renderer_b = BuildingsRenderer()
            renderer_v = VegetationRenderer()

            return [
                make_geojson_result('Zones with Alternative Configurations', geojson_z, renderer_z.get()),
                make_geojson_result('Land-use', geojson_l, renderer_l.get()),
                make_geojson_result('Buildings', geojson_b, renderer_b.get()),
                make_geojson_result('Vegetation', geojson_v, renderer_v.get()),
            ]

        else:
            return [
                make_geojson_result('Zones' if set_id else 'Zones', geojson_z, renderer_z.get()),
            ]

