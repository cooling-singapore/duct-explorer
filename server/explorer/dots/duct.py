import os
from shutil import copyfile
from typing import Dict, List, Callable

import numpy as np
import rasterio

from rasterio._base import DatasetBase
from saas.core.logging import Logging

from duct.exceptions import DUCTRuntimeError
from explorer.dots.dot import DataObjectType, DOTVerificationResult, DOTVerificationMessage
from explorer.geodb import GeoFeature
from explorer.schemas import BoundingBox, Dimensions

logger = Logging.get('duct.dots')


# TODO: the LU default mappings are specific to using ucm-wrf (which is fine because this analysis type makes
#  explicit use of the ucm-wrf-prep processors) AND the specific land cover values as used by the vegetation
#  land use file we are using currently. However, what happens if that particular data set is replaced with
#  another? In this case, the mapping here doesn't make sense. Another option would be to make the mapping
#  part of the base data package (which also contains the vegetation land cover mapping - so at least then it
#  would be consistent). However, the base data package shouldn't make any assumptions as to what analysis types
#  or processors (such as ucm-wrf-prep) are used. So either way, it doesn't quite fit...
default_lu_mapping = [
    {"source_value": 0, "lu_category": "0: Unclassified/Unknown/Undefined", "modis_value": "0: Undefined"},
    {"source_value": 1, "lu_category": "5: Built-up/Urban (e.g., buildings, pavements)",
     "modis_value": "13: Urban and Built-Up"},
    {"source_value": 2, "lu_category": "5: Built-up/Urban (e.g., buildings, pavements)",
     "modis_value": "13: Urban and Built-Up"},
    {"source_value": 3, "lu_category": "4: Vegetation (e.g., forests)", "modis_value": "10: Grasslands"},
    {"source_value": 4, "lu_category": "4: Vegetation (e.g., forests)", "modis_value": "4: Deciduous Broadleaf Forest"},
    {"source_value": 5, "lu_category": "4: Vegetation (e.g., forests)", "modis_value": "5: Mixed Forests"},
    {"source_value": 6, "lu_category": "4: Vegetation (e.g., forests)", "modis_value": "4: Deciduous Broadleaf Forest"},
    {"source_value": 7, "lu_category": "4: Vegetation (e.g., forests)", "modis_value": "5: Mixed Forests"},
    {"source_value": 8, "lu_category": "4: Vegetation (e.g., forests)", "modis_value": "11: Permanent wetlands"},
    {"source_value": 9, "lu_category": "2: Water (e.g., water bodies, rivers)",
     "modis_value": "11: Permanent wetlands"},
    {"source_value": 10, "lu_category": "2: Water (e.g., water bodies, rivers)",
     "modis_value": "11: Permanent wetlands"},
    {"source_value": 11, "lu_category": "2: Water (e.g., water bodies, rivers)",
     "modis_value": "11: Permanent wetlands"},
    {"source_value": 12, "lu_category": "2: Water (e.g., water bodies, rivers)",
     "modis_value": "11: Permanent wetlands"},
    {"source_value": 13, "lu_category": "1: Sea (e.g., oceans, large water bodies)", "modis_value": "17: Water"}
]

# TODO: the industry LUZ filter is specific to the land use zoning data used. In our case, that's the data from
#  the URA master plan. However, the analysis shouldn't have to make any assumptions as to what data is being used.
#  Similar issue as above, where to place the mapping? Here? Into the base data package?
default_industry_luz_filter = ["business 2"]

default_urb_veg_mapping = [
    {"modis_value": "4: Deciduous Broadleaf Forest", "weight": 1},
    {"modis_value": "5: Mixed Forests", "weight": 2}
]

default_cea_palm_building_type_mapping = {
    'MULTI_RES': '3',
    'SINGLE_RES': '3',
    'HOTEL': '6',
    'OFFICE': '6',
    'RETAIL': '6',
    'FOODSTORE': '6',
    'RESTAURANT': '6',
    'INDUSTRIAL': '5',
    'UNIVERSITY': '6',
    'SCHOOL': '6',
    'HOSPITAL': '6',
    'GYM': '6',
    'SWIMMING': '6',
    'SERVERROOM': '6',
    'PARKING': '6',
    'COOLROOM': '6',
    'LAB': '6',
    'MUSEUM': '6',
    'LIBRARY': '6'
}


class LandUseMap(DataObjectType):
    DATA_TYPE = 'duct.LandUseMap'

    def name(self) -> str:
        return self.DATA_TYPE

    def label(self) -> str:
        return 'Land-use Map'

    def supported_formats(self) -> List[str]:
        return ['tiff']

    def verify_content(self, content_path: str) -> DOTVerificationResult:
        messages = []
        is_verified = True

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

        return DOTVerificationResult(
            messages=messages,
            is_verified=is_verified
        )

    def extract_feature(self, content_path: str, parameters: dict) -> Dict:
        with rasterio.open(content_path) as dataset:
            # extract bounding box and dimensions
            bounding_box, dimensions = _extract_bbox_and_dim(dataset)

            # get the no-data value
            no_data = parameters['no_data']

            # get the mask generator (if any)
            mask_generator: Callable[[BoundingBox, Dimensions], np.ndarray] = parameters.get('__helper_mask_generator')

            # generate a mask (if needed)
            mask: np.ndarray = mask_generator(bounding_box, dimensions) if mask_generator else None

            # load data and convert to JSON format
            data = dataset.read(1)
            json_data = []
            for y in reversed(range(dataset.height)):
                for x in range(dataset.width):
                    if mask is not None and mask[y][x] == 0:
                        json_data.append(no_data)
                    else:
                        json_data.append(float(data[y][x]))

            alpha = 255
            color_schema = [
                {'value': 1, 'color': [  0,  72,   0, alpha], 'label': 'Evergreen Needleleaf Forest'},
                {'value': 2, 'color': [ 31, 103,   9, alpha], 'label': 'Dense trees'},
                {'value': 3, 'color': [  1, 153,   1, alpha], 'label': 'Deciduous Needleleaf Forest'},
                {'value': 4, 'color': [  0, 195,   0, alpha], 'label': 'Deciduous Broadleaf Forest'},
                {'value': 5, 'color': [ 50, 179,  73, alpha], 'label': 'Mixed Forests'},
                {'value': 6, 'color': [165,  58,  42, alpha], 'label': 'Closed Shrublands'},
                {'value': 7, 'color': [101, 129,  41, alpha], 'label': 'Bush, scrub'},
                {'value': 8, 'color': [186,  92,  54, alpha], 'label': 'Woody Savannas'},
                {'value': 9, 'color': [238, 129,  59, alpha], 'label': 'Savannas'},
                {'value': 10, 'color': [188, 217, 124, alpha], 'label': 'Low plants'},
                {'value': 11, 'color': [ 16,   0,  79, alpha], 'label': 'Permanent wetlands'},
                {'value': 12, 'color': [208, 170,  78, alpha], 'label': 'Croplands'},
                {'value': 13, 'color': [255,   0,   0, alpha], 'label': 'Urban and Built-Up'},
                {'value': 14, 'color': [154, 138,   1, alpha], 'label': 'Cropland/Natural Vegetation Mosaic'},
                {'value': 15, 'color': [230, 230, 250, alpha], 'label': 'Snow and Ice'},
                {'value': 16, 'color': [  2,   2,   0, alpha], 'label': 'Bare rock or paved'},
                {'value': 17, 'color': [ 44,  99, 180, alpha], 'label': 'Water'},
                {'value': 18, 'color': [191, 191, 191, alpha], 'label': 'Wooded Tundra'},
                {'value': 19, 'color': [164, 192, 153, alpha], 'label': 'Mixed Tundra'},
                {'value': 20, 'color': [158, 191, 202, alpha], 'label': 'Barren Tundra'},
                {'value': 31, 'color': [138,   4,   1, alpha], 'label': 'Compact high-rise'},
                {'value': 32, 'color': [209,  10,   5, alpha], 'label': 'Compact mid-rise'},
                {'value': 33, 'color': [245,  14,  10, alpha], 'label': 'Compact low-rise'},
                {'value': 34, 'color': [196,  71,   9, alpha], 'label': 'Open high-rise'},
                {'value': 35, 'color': [246, 101,   2, alpha], 'label': 'Open mid-rise'},
                {'value': 36, 'color': [248, 153,  92, alpha], 'label': 'Open low-rise'},
                {'value': 37, 'color': [246, 241,   5, alpha], 'label': 'Lightweight low-rise'},
                {'value': 38, 'color': [188, 189, 191, alpha], 'label': 'Large low-rise'},
                {'value': 39, 'color': [251, 205, 165, alpha], 'label': 'Sparsely built'},
                {'value': 40, 'color': [ 89,  84,  88, alpha], 'label': 'Heavy industry'}
            ]

            # create the heatmap
            return {
                'type': 'heatmap',
                'sub_type': 'continuous',
                'area': bounding_box.dict(),
                'grid': dimensions.dict(),
                'legend': parameters['legend_title'],
                'colors': color_schema,
                'data': json_data,
                'no_data': no_data
            }

    def extract_delta_feature(self, content_path0: str, content_path1: str, parameters: dict) -> Dict:
        raise DUCTRuntimeError(f"Not implemented")

    def export_feature(self, content_path: str, parameters: dict, export_path: str, export_format: str) -> None:
        raise DUCTRuntimeError(f"Not implemented")

    def export_delta_feature(self, content_path0: str, content_path1: str, parameters: dict,
                             export_path: str, export_format: str) -> None:
        raise DUCTRuntimeError(f"Not implemented")


def _extract_bbox_and_dim(dataset: DatasetBase) -> (BoundingBox, Dimensions):
    bounding_box = BoundingBox(
        west=dataset.bounds.left,
        east=dataset.bounds.right,
        north=dataset.bounds.top,
        south=dataset.bounds.bottom
    )

    dimensions = Dimensions(
        height=dataset.height,
        width=dataset.width
    )

    return bounding_box, dimensions


def _make_feature_collection(records: List[GeoFeature]) -> dict:
    return {
        'type': 'FeatureCollection',
        'features': [
            {
                'type': 'Feature',
                'id': record.id,
                'geometry': dict(record.geometry),
                'properties': dict(record.properties)
            } for record in records
        ]
    }


class GeoRasterData(DataObjectType):
    DATA_TYPE = 'duct.GeoRasterData'

    def name(self) -> str:
        return self.DATA_TYPE

    def label(self) -> str:
        return 'Geo Raster Data'

    def supported_formats(self) -> List[str]:
        return ['tiff']

    def extract_feature(self, content_path: str, parameters: dict) -> Dict:
        with rasterio.open(content_path) as dataset:
            # extract bounding box and dimensions
            bounding_box, dimensions = _extract_bbox_and_dim(dataset)

            # get the no-data value
            no_data = parameters['no_data']

            # get the mask generator (if any)
            mask_generator: Callable[[BoundingBox, Dimensions], np.ndarray] = parameters.get('__helper_mask_generator')

            # generate a mask (if needed)
            mask: np.ndarray = mask_generator(bounding_box, dimensions) if mask_generator else None

            # load data and convert to JSON format
            data = dataset.read(1)
            json_data = []
            for y in reversed(range(dataset.height)):
                for x in range(dataset.width):
                    if mask is not None and mask[y][x] == 0:
                        json_data.append(no_data)
                    else:
                        json_data.append(float(data[y][x]))

        # create the heatmap
        return {
            'type': 'heatmap',
            'sub_type': 'continuous',
            'area': bounding_box.dict(),
            'grid': dimensions.dict(),
            'legend': parameters['legend_title'],
            'colors': parameters['color_schema'],
            'data': json_data,
            'no_data': no_data
        }

    def extract_delta_feature(self, content_path0: str, content_path1: str, parameters: dict) -> Dict:
        with rasterio.open(content_path0) as dataset0:
            with rasterio.open(content_path1) as dataset1:
                # extract bounding boxes and dimensions
                bounding_box0, dimension0 = _extract_bbox_and_dim(dataset0)
                bounding_box1, dimension1 = _extract_bbox_and_dim(dataset1)

                # verify they are the same
                if bounding_box0.as_str() != bounding_box1.as_str() or dimension0.as_str() != dimension1.as_str():
                    raise DUCTRuntimeError(f"mismatching boundingx box and/or dimension: "
                                           f"bbox0={bounding_box0.as_str()} bbox1={bounding_box1.as_str()} "
                                           f"dim0={dimension0.as_str()} dim1={dimension1.as_str()} ")

                # get the no-data value
                no_data = parameters['common']['no_data']

                # get the mask generators (if any)
                mask_generator0: Callable[[BoundingBox, Dimensions], np.ndarray] = \
                    parameters['A'].get('__helper_mask_generator')
                mask_generator1: Callable[[BoundingBox, Dimensions], np.ndarray] = \
                    parameters['B'].get('__helper_mask_generator')

                # generate a mask (if needed)
                mask0: np.ndarray = mask_generator0(bounding_box0, dimension0) if mask_generator0 else None
                mask1: np.ndarray = mask_generator1(bounding_box1, dimension1) if mask_generator1 else None

                # load data, generate delta and convert to JSON format
                data0 = dataset0.read(1)
                data1 = dataset1.read(1)
                json_data = []
                for y in reversed(range(dataset0.height)):
                    for x in range(dataset0.width):
                        if (mask0 is not None and mask0[y][x] == 0) or (mask1 is not None and mask1[y][x] == 0):
                            json_data.append(no_data)
                        else:
                            json_data.append(float(data0[y][x]) - float(data1[y][x]))

                # create the heatmap
                return {
                    'type': 'heatmap',
                    'sub_type': 'continuous',
                    'area': bounding_box0.dict(),
                    'grid': dimension0.dict(),
                    'legend': parameters['common']['legend_title'],
                    'colors': parameters['common']['color_schema'],
                    'data': json_data,
                    'no_data': no_data
                }

    def export_feature(self, content_path: str, parameters: dict, export_path: str, export_format: str) -> None:
        if export_format == 'tiff':
            copyfile(content_path, export_path)
            with rasterio.open(export_path, mode='r+') as dataset:
                # extract bounding box and dimensions
                bounding_box, dimensions = _extract_bbox_and_dim(dataset)

                # get the no-data value
                no_data = parameters['no_data']

                # get the mask generator (if any)
                mask_generator: Callable[[BoundingBox, Dimensions], np.ndarray] = parameters.get(
                    '__helper_mask_generator')

                # generate a mask (if needed)
                mask: np.ndarray = mask_generator(bounding_box, dimensions) if mask_generator else None

                # load data and convert to JSON format
                data = dataset.read(1)
                for y in reversed(range(dataset.height)):
                    for x in range(dataset.width):
                        if mask is not None and mask[y][x] == 0:
                            data[y][x] = no_data

                dataset.write(data, 1)

        else:
            raise DUCTRuntimeError(f"Format not supported for export: {export_format}")

    def export_delta_feature(self, content_path0: str, content_path1: str, parameters: dict,
                             export_path: str, export_format: str) -> None:
        if export_format == 'tiff':
            # create a copy of dataset0
            pending_path = export_path+".pending"
            copyfile(content_path0, pending_path)
            with rasterio.open(pending_path, mode='r+') as dataset0:
                with rasterio.open(content_path1) as dataset1:
                    # extract bounding boxes and dimensions
                    bounding_box0, dimension0 = _extract_bbox_and_dim(dataset0)
                    bounding_box1, dimension1 = _extract_bbox_and_dim(dataset1)

                    # verify they are the same
                    if bounding_box0.as_str() != bounding_box1.as_str() or dimension0.as_str() != dimension1.as_str():
                        raise DUCTRuntimeError(f"mismatching boundingx box and/or dimension: "
                                               f"bbox0={bounding_box0.as_str()} bbox1={bounding_box1.as_str()} "
                                               f"dim0={dimension0.as_str()} dim1={dimension1.as_str()} ")

                    # get the no-data value
                    no_data = parameters['common']['no_data']

                    # get the mask generators (if any)
                    mask_generator0: Callable[[BoundingBox, Dimensions], np.ndarray] = \
                        parameters['A'].get('__helper_mask_generator')
                    mask_generator1: Callable[[BoundingBox, Dimensions], np.ndarray] = \
                        parameters['B'].get('__helper_mask_generator')

                    # generate a mask (if needed)
                    mask0: np.ndarray = mask_generator0(bounding_box0, dimension0) if mask_generator0 else None
                    mask1: np.ndarray = mask_generator1(bounding_box1, dimension1) if mask_generator1 else None

                    # load data, generate delta
                    data0 = dataset0.read(1)
                    data1 = dataset1.read(1)
                    data0 = data0 - data1
                    for y in reversed(range(dataset0.height)):
                        for x in range(dataset0.width):
                            if (mask0 is not None and mask0[y][x] == 0) or (mask1 is not None and mask1[y][x] == 0):
                                data0[y][x] = no_data

                    dataset0.write(data0, 1)

            os.rename(pending_path, export_path)


        else:
            raise DUCTRuntimeError(f"Format not supported for export: {export_format}")
