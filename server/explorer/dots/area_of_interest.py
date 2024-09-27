import json
import os
import tempfile
import zipfile
import geopandas as gpd
from typing import Dict, List, Optional, Tuple

import pyproj
from saas.core.helpers import get_timestamp_now
from saas.core.logging import Logging

from explorer.exceptions import DUCTRuntimeError
from explorer.dots.dot import ImportableDataObjectType, UploadPostprocessResult, ImportTarget, DOTVerificationMessage, \
    DOTVerificationResult
from explorer.geodb import GeometryType
from explorer.renderer.aoi_renderer import AreaOfInterestRenderer
from explorer.schemas import ExplorerRuntimeError

logger = Logging.get('explorer.dots.area_of_interest')


class AreaOfInterest(ImportableDataObjectType):
    DATA_TYPE = 'area_of_interest'

    @staticmethod
    def read_as_shapefile(path: str, messages: List[DOTVerificationMessage] = None) -> Optional[dict]:
        try:
            with open(path, 'rb') as f:
                # peek into the file to determine if it's a zip file
                peek = f.read(4)
                if peek != b'\x50\x4B\x03\x04':
                    return None  # it's not, abort...

            with tempfile.TemporaryDirectory() as tmp_dir:
                # unzip the contents
                with zipfile.ZipFile(path, 'r') as zip:
                    zip.extractall(tmp_dir)
                    files = zip.namelist()

                # is there are shapefile?
                shp_files = [f for f in files if f.endswith('.shp')]
                if len(shp_files) == 0:
                    return None  # no shape file, abort...

                # more than one shapefile?
                shp_path = shp_files[0]
                if len(shp_files) > 1:
                    if messages is not None:
                        messages.append(DOTVerificationMessage(
                            severity='warning', message=f"Found {len(shp_files)} shapefiles. Only using {shp_path}")
                        )

                # read the shape file
                gdf = gpd.read_file(os.path.join(tmp_dir, shp_path))

                # define the source and target CRS (??? to EPSG:4326)
                source_crs = gdf.crs
                target_crs = pyproj.CRS.from_epsg(4326)
                transformer = pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)

                # extract all polygons
                polygons = []
                for _, entity in gdf.iterrows():
                    # get geometry
                    geometry = entity.geometry.__geo_interface__

                    # convert coordinate system
                    coordinates = []
                    if geometry['type'] == 'Polygon':
                        for polygon in geometry['coordinates']:
                            polygon = [transformer.transform(x, y) for x, y in polygon]
                            coordinates.append(polygon)

                    elif geometry['type'] == 'MultiPolygon':
                        for polygons in geometry['coordinates']:
                            polygons1 = []
                            for polygon in polygons:
                                polygon = [transformer.transform(x, y) for x, y in polygon]
                                polygons1.append(polygon)
                            coordinates.append(polygons1)

                    else:
                        continue
                    geometry['coordinates'] = coordinates

                    polygons.append(geometry)

                # no polygons found?
                if len(polygons) == 0:
                    if messages is not None:
                        messages.append(DOTVerificationMessage(
                            severity='error', message=f"No polygons found in shapefile {shp_path}")
                        )
                    return None

                # more than one polygon?
                polygon = polygons[0]
                if len(polygons) > 1:
                    if messages is not None:
                        messages.append(DOTVerificationMessage(
                            severity='warning', message=f"Found {len(polygons)} polygons in shapefile. Only using "
                                                        f"the first one.")
                        )

                # convert into geojson
                return {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "properties": {},
                            "geometry": polygon
                        }
                    ]
                }

        except Exception:
            return None  # we just assume it wasn't a shapefile at this point

    @staticmethod
    def read_as_geojson(path: str, messages: List[DOTVerificationMessage] = None) -> Optional[dict]:
        try:
            with open(path, 'r') as f:
                content = json.load(f)
                features = content['features']

            # define the source and target CRS (??? to EPSG:4326)
            crs_name = content['crs']['properties']['name']
            source_crs = pyproj.CRS.from_string(crs_name)
            target_crs = pyproj.CRS.from_epsg(4326)
            transformer = pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)

            # find polygon features
            polygon_features = []
            multipolygon_features = []
            for feature in features:
                # is it a polygon, convert coordinate system
                geometry = feature['geometry']
                if geometry['type'] == 'Polygon':
                    geometry['coordinates'] = [
                        [transformer.transform(x, y) for x, y in polygon] for polygon in geometry['coordinates']
                    ]
                    polygon_features.append(feature)

                elif geometry['type'] == 'MultiPolygon':
                    coordinates = []
                    for polygons in geometry['coordinates']:
                        coordinates.append([
                           [transformer.transform(x, y) for x, y in polygon] for polygon in polygons
                        ])
                    geometry['coordinates'] = coordinates
                    multipolygon_features.append(feature)

            # found any multi-polygons?
            if len(multipolygon_features) > 0:
                if messages is not None:
                    messages.append(DOTVerificationMessage(
                        severity='warning', message=f"Found {len(multipolygon_features)} multi-polygons in GeoJSON. "
                                                    f"They are not currently supported and ignored."))

            # no polygons found?
            if len(polygon_features) == 0:
                if messages is not None:
                    messages.append(DOTVerificationMessage(
                        severity='error', message=f"No polygons found in GeoJSON file.")
                    )
                return None
            # more than one polygon?
            elif len(polygon_features) > 1:
                if messages is not None:
                    messages.append(DOTVerificationMessage(
                        severity='warning', message=f"Found {len(polygon_features)} polygons in GeoJSON. "
                                                    f"Only using the first one."))

            return {
                "type": "FeatureCollection",
                "features": [polygon_features[0]]
            }

        except Exception:
            return None  # we just assume it wasn't a GeoJSON at this point

    def target(self) -> ImportTarget:
        return ImportTarget.library

    def name(self) -> str:
        return self.DATA_TYPE

    def label(self) -> str:
        return 'Area of Interest'

    def supported_formats(self) -> List[str]:
        return ['geojson', 'shp']

    def description(self) -> str:
        return ("Area of interest defined as a polygon. The acceptable formats and attributes are listed below. "
                "<br><br> <b>Accepted file formats:</b>"
                "<ul><li>geojson</li></ul>"
                "<ul><li>shp</li></ul>")

    def preview_image_url(self) -> str:
        return 'dot_area-of-interest.png'

    def upload_postprocess(self, project, temp_obj_path: str) -> List[Tuple[str, str, UploadPostprocessResult]]:
        from explorer.project import Project
        project: Project = project

        # load the area of interest (try as shapefile first, then GeoJSON)
        aoi = self.read_as_shapefile(temp_obj_path)
        if aoi is None:
            aoi = self.read_as_geojson(temp_obj_path)

        # it went through verification so we really should have an object here
        if aoi is None:
            raise ExplorerRuntimeError(f"area of interest couldn't be read from {temp_obj_path}")

        # load the geometries into the geo db
        obj_id = f"{self.name()}_{get_timestamp_now()}"
        obj_path = os.path.join(project.info.temp_path, obj_id)

        # we are not splitting, so just write the extracted area of interest
        with open(obj_path, 'w') as f_out:
            json.dump(aoi, f_out, indent=2)

        result = [(obj_id, obj_path, UploadPostprocessResult(title='Area of Interest', description='', mode='skip',
                                                             extra={}))]
        return result

    def update_preimport(self, project, obj_path: str, args: dict,
                         geo_type: Optional[GeometryType]) -> UploadPostprocessResult:
        return UploadPostprocessResult(title='Area of Interest', description='', mode='skip', extra={})

    def verify_content(self, content_path: str) -> DOTVerificationResult:
        # try to read as shapefile first. if that doesn't work, then try to read it as GeoJSON
        messages: List[DOTVerificationMessage] = []
        aoi, data_format = self.read_as_shapefile(content_path, messages), 'shp'
        if aoi is None:
            aoi, data_format = self.read_as_geojson(content_path, messages), 'geojson'

        # still no luck?
        if aoi is None:
            data_format = 'unknown'
            messages.append(DOTVerificationMessage(severity='error', message="File does not seem to be a valid"
                                                                             "shapefile or GeoJSON."))

        # do we have any error messages?
        is_verified = True
        for message in messages:
            if message.severity == 'error':
                is_verified = False
                break

        return DOTVerificationResult(messages=messages, is_verified=is_verified, data_format=data_format)

    def extract_feature(self, content_path: str, parameters: dict) -> Dict:
        with open(content_path, 'r') as f:
            content = json.load(f)

        renderer = AreaOfInterestRenderer()

        return {
            "type": "geojson",
            "title": "Area of Interest",
            "geojson": content,
            "renderer": renderer.get()
        }

    def extract_delta_feature(self, content_path0: str, content_path1: str, parameters: dict) -> Dict:
        raise DUCTRuntimeError(f"Not implemented")

    def export_feature(self, content_path: str, parameters: dict, export_path: str, export_format: str) -> None:
        raise DUCTRuntimeError(f"Not implemented")

    def export_delta_feature(self, content_path0: str, content_path1: str, parameters: dict,
                             export_path: str, export_format: str) -> None:
        raise DUCTRuntimeError(f"Not implemented")
