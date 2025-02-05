import os
from shutil import copyfile
from typing import Dict, List, Tuple, Optional

import numpy as np
import rasterio
from saas.core.helpers import get_timestamp_now

from saas.core.logging import Logging

from explorer.exceptions import DUCTRuntimeError
from explorer.dots.dot import ImportableDataObjectType, UploadPostprocessResult, ImportTarget, DOTVerificationResult, \
    DOTVerificationMessage
from explorer.geodb import GeometryType
from explorer.schemas import BoundingBox, Dimensions

logger = Logging.get('explorer.dots.lcz')


class LocalClimateZoneMap(ImportableDataObjectType):
    DATA_TYPE = 'duct.lcz_map'

    LEGEND = [
        {'value': 1, 'color': [0, 72, 0, 255], 'label': 'Evergreen Needleleaf Forest'},
        {'value': 2, 'color': [31, 103, 9, 255], 'label': 'Evergreen Broadleaf Forest'},
        {'value': 3, 'color': [1, 153, 1, 255], 'label': 'Deciduous Needleleaf Forest'},
        {'value': 4, 'color': [0, 195, 0, 255], 'label': 'Deciduous Broadleaf Forest'},
        {'value': 5, 'color': [50, 179, 73, 255], 'label': 'Mixed Forests'},
        {'value': 6, 'color': [165, 58, 42, 255], 'label': 'Closed Shrublands'},
        {'value': 7, 'color': [101, 129, 41, 255], 'label': 'Open Shrublands'},
        {'value': 8, 'color': [186, 92, 54, 255], 'label': 'Woody Savannas'},
        {'value': 9, 'color': [238, 129, 59, 255], 'label': 'Savannas'},
        {'value': 10, 'color': [188, 217, 124, 255], 'label': 'Grasslands'},
        {'value': 11, 'color': [16, 0, 79, 255], 'label': 'Permanent wetlands'},
        {'value': 12, 'color': [208, 170, 78, 255], 'label': 'Croplands'},
        {'value': 13, 'color': [255, 0, 0, 255], 'label': 'Urban and Built-Up'},
        {'value': 14, 'color': [154, 138, 1, 255], 'label': 'Cropland/Natural Vegetation Mosaic'},
        {'value': 15, 'color': [230, 230, 250, 255], 'label': 'Snow and Ice'},
        {'value': 16, 'color': [2, 2, 0, 255], 'label': 'Barren or Sparse'},
        {'value': 17, 'color': [44, 99, 180, 255], 'label': 'Water'},
        {'value': 18, 'color': [191, 191, 191, 255], 'label': 'Wooded Tundra'},
        {'value': 19, 'color': [164, 192, 153, 255], 'label': 'Mixed Tundra'},
        {'value': 20, 'color': [158, 191, 202, 255], 'label': 'Barren Tundra'},
        {'value': 31, 'color': [138, 4, 1, 255], 'label': 'Compact high-rise'},
        {'value': 32, 'color': [209, 10, 5, 255], 'label': 'Compact mid-rise'},
        {'value': 33, 'color': [245, 14, 10, 255], 'label': 'Compact low-rise'},
        {'value': 34, 'color': [196, 71, 9, 255], 'label': 'Open high-rise'},
        {'value': 35, 'color': [246, 101, 2, 255], 'label': 'Open mid-rise'},
        {'value': 36, 'color': [248, 153, 92, 255], 'label': 'Open low-rise'},
        {'value': 37, 'color': [246, 241, 5, 255], 'label': 'Lightweight low-rise'},
        {'value': 38, 'color': [188, 189, 191, 255], 'label': 'Large low-rise'},
        {'value': 39, 'color': [251, 205, 165, 255], 'label': 'Sparsely built'},
        {'value': 40, 'color': [89, 84, 88, 255], 'label': 'Heavy industry'}
    ]

    def name(self) -> str:
        return self.DATA_TYPE

    def label(self) -> str:
        return 'Local Climate Zone Map'

    def supported_formats(self) -> List[str]:
        return ['geotiff']

    def target(self) -> ImportTarget:
        return ImportTarget.library

    def description(self) -> str:
        return "Local Climate Zone (LCZ) map represents the classification of urban areas into discrete local " \
               "climates by morphological and land cover characteristics as defined by Stewart and Oke, " \
               "2012. <br><br> " \
               "<b>Accepted file formats:</b>" \
               "<ul><li>tiff</li></ul>"

    def preview_image_url(self) -> str:
        return 'dot_lcz_map.png'

    def upload_postprocess(self, project, temp_obj_path: str) -> List[Tuple[str, str, UploadPostprocessResult]]:
        from explorer.project import Project
        project: Project = project

        # load the geometries into the geo db
        obj_id = f"{self.name()}_{get_timestamp_now()}_lcz"
        obj_path = os.path.join(project.info.temp_path, obj_id)

        # we just copy the file
        copyfile(temp_obj_path, obj_path)

        result = [(obj_id, obj_path, UploadPostprocessResult(title='...',
                                                             description='...',
                                                             mode='skip', extra={}))]
        return result

    def update_preimport(self, project, obj_path: str, args: dict,
                         geo_type: Optional[GeometryType]) -> UploadPostprocessResult:
        return UploadPostprocessResult(title='...', description='...', mode='skip', extra={})

    def verify_content(self, content_path: str) -> DOTVerificationResult:
        messages = []
        is_verified = True
        data_format = 'geotiff'

        try:
            with rasterio.Env():
                with rasterio.open(content_path) as src:
                    dataset = src.read(1)

                    # do we have any values outside of the range?
                    if not np.all((dataset >= 0) & (dataset <= 40)):
                        messages.append(DOTVerificationMessage(severity='error', message=f'Invalid values found.'))
                        is_verified = False

        except Exception as e:
            messages.append(DOTVerificationMessage(severity='error', message=f'Exception: {e}'))
            is_verified = False
            data_format = 'unknown'

        return DOTVerificationResult(
            messages=messages,
            is_verified=is_verified,
            data_format=data_format
        )

    def extract_feature(self, content_path: str, parameters: dict) -> Dict:
        with rasterio.open(content_path) as dataset:
            # extract bounding box
            bounding_box = BoundingBox(
                west=dataset.bounds.left,
                east=dataset.bounds.right,
                north=dataset.bounds.top,
                south=dataset.bounds.bottom
            )

            # extract dimensions
            dimensions = Dimensions(
                height=dataset.height,
                width=dataset.width
            )

            # get the no-data value
            no_data = 0

            # load data and translate the LULC category values to index values
            data = dataset.read(1)
            translated = np.full(shape=data.shape, dtype=np.uint8, fill_value=no_data)
            unique_values = set(np.unique(data).astype(int))
            color_schema = [{'value': 0, 'color': [0, 0, 0, 255], 'label': ''}]
            index = 1
            for line in self.LEGEND:
                # example line: {'value': 17, 'color': [44, 99, 180, 255], 'label': 'Water'},

                # if this LULC value is not found in the dataset, skip it
                lulc_value = int(line['value'])
                if lulc_value not in unique_values:
                    continue

                # translate LULC value to the current index value
                translated[(data == lulc_value)] = index
                color_schema.append({'value': index, 'color': line['color'], 'label': line['label']})
                index += 1

            # convert to JSON format
            json_data = []
            for y in reversed(range(dataset.height)):
                for x in range(dataset.width):
                    json_data.append(int(translated[y][x]))

            # create the heatmap
            return {
                'type': 'heatmap',
                'subtype': 'discrete',
                'area': bounding_box.dict(),
                'grid': dimensions.dict(),
                'legend': 'Land-use/Land-cover Categories',
                'colors': color_schema,
                'data': json_data,
                'no_data': no_data
            }

    def export_feature(self, content_path: str, parameters: dict, export_path: str, export_format: str) -> None:
        if export_format == 'tiff':
            copyfile(content_path, export_path)

        else:
            raise DUCTRuntimeError(f"Format not supported for export: {export_format}")

    def extract_delta_feature(self, content_path0: str, content_path1: str, parameters: dict) -> Dict:
        raise DUCTRuntimeError(f"Not implemented")

    def export_delta_feature(self, content_path0: str, content_path1: str, parameters: dict,
                             export_path: str, export_format: str) -> None:
        raise DUCTRuntimeError(f"Not implemented")

