from typing import List, Dict

from shapely import Polygon

from explorer.geodb import GeometryType
from explorer.project import Project
from explorer.renderer.aoi_renderer import AreaOfInterestRenderer
from explorer.renderer.base import make_geojson_result
from explorer.renderer.buildings_renderer import BuildingsRenderer
from explorer.renderer.landcover_renderer import LandcoverRenderer
from explorer.renderer.vegetation_renderer import VegetationRenderer
from explorer.view.base import View


class AnalyseView(View):
    def name(self) -> str:
        return 'analyse'

    def generate(self, project: Project, set_id: str = None, area: Polygon = None,
                 use_cache: bool = True) -> List[Dict]:
        result = []

        # do we also have an area of interest?
        if area is not None:
            geojson_a = {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "properties": {},
                    "geometry": area.__geo_interface__
                }]
            }
            renderer_a = AreaOfInterestRenderer()
            result.append(
                make_geojson_result('Area of Interest', geojson_a, renderer_a.get()),
            )

            # do we also have a set id?
            if set_id is not None:
                geojson_l = project.geometries(GeometryType.landcover, set_id=set_id, area=area, use_cache=use_cache).content()
                geojson_b = project.geometries(GeometryType.building, set_id=set_id, area=area, use_cache=use_cache).content()
                geojson_v = project.geometries(GeometryType.vegetation, set_id=set_id, area=area, use_cache=use_cache).content()

                renderer_l = LandcoverRenderer()
                renderer_b = BuildingsRenderer()
                renderer_v = VegetationRenderer()

                result.append(make_geojson_result('Land-cover', geojson_l, renderer_l.get()))
                result.append(make_geojson_result('Buildings', geojson_b, renderer_b.get()))
                result.append(make_geojson_result('Vegetation', geojson_v, renderer_v.get()))

        return result
