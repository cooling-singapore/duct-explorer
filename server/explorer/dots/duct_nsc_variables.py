import datetime
import math
from typing import Dict, List, Callable

import h5py
import numpy as np
import rasterio

from rasterio import CRS
from saas.core.logging import Logging

from explorer.exceptions import DUCTRuntimeError
from explorer.dots.dot import DataObjectType
from explorer.schemas import BoundingBox, Dimensions, WindVectorDetails

logger = Logging.get('explorer.dots.nsc_var')


def extract_nsc_data(content_path: str, parameters: dict, key: str = '') -> (BoundingBox, Dimensions, np.ndarray):
    if key == '':
        key = parameters['key']

    with h5py.File(content_path, "r") as f:
        # do we have that key?
        keys = f.keys()
        if key not in keys:
            raise DUCTRuntimeError(f"Unexpected key found: {key}", details={
                'key': key,
                'available_keys': keys,
                'parameters': parameters
            })

        # get the data
        data = f.get(key)

        # determine the bounding box
        bounding_box = data.attrs['bounding_box']
        bounding_box = BoundingBox(
            west=float(bounding_box[2]),
            east=float(bounding_box[3]),
            north=float(bounding_box[1]),
            south=float(bounding_box[0])
        )

        # determine the timestamp if interest
        datetime_0h: datetime.datetime = datetime.datetime.strptime(parameters['datetime_0h'], '%Y%m%d%H%M%S')

        # do we have 2 or 3 spatial dimensions?
        print(f"data.attrs['timestamps']={data.attrs['timestamps']}")
        print(f"data.shape={data.shape}")

        # get the timestamps contained in the data set and extract the timestamp of interest
        timestamps = data.attrs['timestamps']
        timestamps = [int(t) for t in timestamps]

        result_filter = parameters['result_filter'] if 'result_filter' in parameters else 'time'

        # extracts and processes hourly data according to the timestamp index
        def extract_hour_data(results, t_idx_value):
            if len(results.shape) == 3:
                if t_idx_value is not None and 0 <= t_idx_value < results.shape[0]:
                    # get the 2D raster for this time and flip it u/d
                    hour_result = results[t_idx_value]
                    hour_result = np.flipud(hour_result)
                else:
                    hour_result = np.full(fill_value=parameters['no_data'], shape=(results.shape[1], results.shape[2]))

            elif len(results.shape) == 4:
                if t_idx_value is not None and 0 <= t_idx_value < results.shape[0]:
                    # get the 2D raster for this time and flip it u/d
                    hour_result = results[t_idx_value][parameters['z_idx']]
                    hour_result = np.flipud(hour_result)
                else:
                    hour_result = np.full(fill_value=parameters['no_data'], shape=(results.shape[2], results.shape[3]))

            else:
                raise DUCTRuntimeError(f"Unexpected number of spatial dimensions in '{content_path}': "
                                       f"{len(results.shape)}")
            return hour_result

        # calculate data for a specific hour when creating line charts or when filtering results by time.
        if parameters.get('type', '') == 'duct.nsc_var.linechart' or (
                result_filter == 'time' and 'time' in parameters and 0 <= int(parameters['time']) <= 23):
            datetime_th: datetime.datetime = datetime_0h + datetime.timedelta(hours=int(parameters['time']))
            datetime_th: str = datetime_th.strftime('%Y%m%d%H%M%S')

            t_idx = timestamps.index(int(datetime_th)) if int(datetime_th) in timestamps else None
            # extract data for the timestamp index
            data = extract_hour_data(data, t_idx)

        # calculate the values according to the result filter
        elif result_filter in ['24_avg', '24_min', '24_max']:
            hourly_data = []

            # get data for each hour
            for hour in range(24):
                datetime_th = datetime_0h + datetime.timedelta(hours=hour)
                datetime_th_str = datetime_th.strftime('%Y%m%d%H%M%S')

                t_idx = timestamps.index(int(datetime_th_str)) if int(datetime_th_str) in timestamps else None

                # extract data for the hour
                hour_data = extract_hour_data(data, t_idx)

                hourly_data.append(hour_data)

            hourly_data = np.array(hourly_data)

            # check if hourly_data is empty
            if hourly_data.size == 0:
                raise ValueError("All hourly data arrays are empty")

            # mask no data value
            masked_hourly_data = np.ma.masked_equal(hourly_data, parameters['no_data'])

            # calculate results according to the results filter
            if result_filter == '24_avg':
                data = np.nanmean(masked_hourly_data, axis=0)
            elif result_filter == '24_min':
                data = np.nanmin(masked_hourly_data, axis=0)
            elif result_filter == '24_max':
                data = np.nanmax(masked_hourly_data, axis=0)

        # determine the dimensions
        dimensions = Dimensions(
            height=data.shape[0],
            width=data.shape[1]
        )

        return bounding_box, dimensions, data


class NearSurfaceClimateVariableLinechart(DataObjectType):
    DATA_TYPE = 'duct.nsc_var.linechart'

    def name(self) -> str:
        return self.DATA_TYPE

    def label(self) -> str:
        return 'Near-surface Climate Variable Raster'

    def supported_formats(self) -> List[str]:
        return ['hdf5']

    def extract_feature(self, content_path: str, parameters: dict) -> Dict:
        no_data = parameters['no_data']
        selected_hour = parameters['time']

        # get the statistics for all 24h
        mask = None
        values = {
            'Min': [],
            'Max': [],
            'Mean': []
        }
        times = []
        for h in range(24):
            # add label for time axis
            times.append(h)

            # extract the raster data for time h
            parameters['time'] = h
            parameters['type'] = self.DATA_TYPE
            bbox, dim, raster = extract_nsc_data(content_path, parameters)

            # do we have a mask?
            if mask is None:
                # do we have a mask generator?
                mask_generator: Callable[[BoundingBox, Dimensions], np.ndarray] = \
                    parameters.get('__helper_mask_generator')
                if mask_generator:
                    mask = mask_generator(bbox, dim)
                else:
                    mask = np.ones_like(raster, dtype=bool)

                # modify the mask to account for 'no_value' values
                mask = np.logical_and(mask, raster != no_data)

            data = raster[mask]
            if data.shape[0] > 0:
                v_avg = np.average(data)
                v_min = np.min(data)
                v_max = np.max(data)

                values['Mean'].append(float(v_avg))
                values['Min'].append(float(v_min))
                values['Max'].append(float(v_max))

        # resetting the time to the originally selected value
        parameters['time'] = selected_hour

        color_schema = [
            'rgb(247, 37, 133)',
            'rgb(181, 23, 158)',
            'rgb(114, 9, 183)',
            'rgb(86, 11, 173)',
            'rgb(72, 12, 168)',
            'rgb(58, 12, 163)',
            'rgb(63, 55, 201)',
            'rgb(67, 97, 238)',
            'rgb(72, 149, 239)',
            'rgb(76, 201, 240)'
        ]

        # assign color schema
        datasets: dict[str, (str, list[float])] = {}
        for i, label in enumerate(values.keys()):
            colors = color_schema[(i - 1) % len(color_schema)]
            data = values[label]
            datasets[label] = (colors, data)

        data = {
            'labels': [str(t) for t in times],
            'datasets': [{
                'label': label,
                'data': [value for value in d[1] if value != no_data],
                'borderColor': d[0],
                'backgroundColor': d[0],
                'pointRadius': 2
            } for label, d in datasets.items()]
        }

        return {
            'lib': 'chart.js',
            'type': 'line',
            'data': data,
            'options': {
                'aspectRatio': 1,
                'responsive': True,
                'plugins': {
                    'legend': {
                        'position': 'bottom',
                        'labels': {'boxHeight': 1}
                    },
                    'title': {'display': True, 'text': parameters['legend_title'], 'align': 'start'}
                },
                'scales': {
                    'y': {
                        'ticks': {
                            'autoSkip': False,
                            'suggestedMin': 0,
                            'suggestedMax': 100
                        },
                        'title': {'display': False, 'text': ''}
                    },
                    'x': {
                        'type': 'linear',
                        'ticks': {
                            'stepSize': 2,
                            'maxTicksLimit': 24,
                            'autoSkip': False,
                        },
                        'title': {'display': True, 'text': 'Time (hours)'}
                    }
                }
            }
        }

    def extract_delta_feature(self, content_path0: str, content_path1: str, parameters: dict) -> Dict:
        raise DUCTRuntimeError(f"Not implemented")

    def export_feature(self, content_path: str, parameters: dict, export_path: str, export_format: str) -> None:
        raise DUCTRuntimeError(f"Not implemented")

    def export_delta_feature(self, content_path0: str, content_path1: str, parameters: dict,
                             export_path: str, export_format: str) -> None:
        raise DUCTRuntimeError(f"Not implemented")


class NearSurfaceClimateVariableRaster(DataObjectType):
    DATA_TYPE = 'duct.nsc_var.raster'

    def name(self) -> str:
        return self.DATA_TYPE

    def label(self) -> str:
        return 'Near-surface Climate Variable Raster'

    def supported_formats(self) -> List[str]:
        return ['hdf5']

    def extract_feature(self, content_path: str, parameters: dict) -> Dict:
        # extract the raster data
        parameters['type'] = self.DATA_TYPE
        bbox, dimensions, raster = extract_nsc_data(content_path, parameters)

        # get the mask generator (if any)
        mask_generator: Callable[[BoundingBox, Dimensions], np.ndarray] = parameters.get('__helper_mask_generator')

        # generate a mask (if needed)
        mask: np.ndarray = mask_generator(bbox, dimensions) if mask_generator else None

        no_data = parameters['no_data']
        color_schema = list(parameters['color_schema'])

        # # determine min/max color in schema and a 'outlier' value (outlier value is just a value outside the normal
        # # range defined by the colors and that is not the no_data value either).
        # min_color_value = color_schema[0]['value']
        # max_color_value = color_schema[-1]['value']
        # outlier_value = int(max(no_data, max_color_value) + 1)
        # print(f"min_color_value: {min_color_value}")
        # print(f"max_color_value: {max_color_value}")
        # print(f"no_data: {no_data}")
        # print(f"outlier_value: {outlier_value}")
        #
        # # do we have outliers below/above the defined color schema?
        # value_mask = raster != no_data
        # min_value = np.min(raster[value_mask])
        # max_value = np.max(raster[value_mask])
        # print(f"min_value: {min_value}")
        # print(f"max_value: {max_value}")
        # if min_value < min_color_value or max_value > max_color_value:
        #     # determine the outlier mask, i.e., all values that are outliers
        #     outlier_mask = ((raster < min_color_value) | (raster > max_color_value)) & (raster != no_data)
        #     raster[outlier_mask] = outlier_value
        #
        #     # add an outlier color
        #     color_schema.append(
        #         {'value': outlier_value, 'color': hex_color_to_ints('#ff00ff', 255), 'label': 'Outliers'}
        #     )
        # print(f"color_schema: {color_schema}")

        # convert to JSON format
        json_data = []
        for y in reversed(range(dimensions.height)):
            for x in range(dimensions.width):
                if mask is not None and mask[y][x] == 0:
                    json_data.append(no_data)
                else:
                    if not (math.isinf(raster[y][x]) or math.isnan(raster[y][x])):
                        json_data.append(float(raster[y][x]))
                    else:
                        json_data.append(no_data)

        # create the heatmap
        heatmap_result = {
            'type': 'heatmap',
            'area': bbox.dict(),
            'grid': dimensions.dict(),
            'legend': parameters['legend_title'],
            'colors': color_schema,
            'data': json_data,
            'no_data': no_data
        }

        # calculate overall statistic data
        if 'result_filter' in parameters:
            # modify the mask to account for 'no_value' values
            mask = np.logical_and(mask, raster != no_data)

            # get the values in two decimal points
            overall_avg = f"{round(float(np.average(raster[mask])), 2):.2f}"
            overall_min = f"{round(float(np.min(raster[mask])), 2):.2f}"
            overall_max = f"{round(float(np.max(raster[mask])), 2):.2f}"

            table_description = f"_{parameters.get('statistics_table_description', '')}_"

            markdown_table = f"""### {parameters['legend_title']}  \n  |||\n|:------------------ | -------------------------------:|\n|{table_description}||\n|||\n|||\n| Average    | {overall_avg} |\n| Minimum    | {overall_min} |\n| Maximum    | {overall_max} |"""
            overall_statistic_table_markdown_result = {
                'title': parameters['legend_title'],
                'subtitle': '',
                'table_description': table_description,
                'type': 'markdown',
                'data_values': {
                    'overall_avg': overall_avg,
                    'overall_min': overall_min,
                    'overall_max': overall_max
                },
                'data': markdown_table
            }
        else:
            overall_statistic_table_markdown_result = {}

        return heatmap_result, overall_statistic_table_markdown_result

    def extract_delta_feature(self, content_path0: str, content_path1: str, parameters: dict) -> Dict:
        # extract the raster data
        parameters['A']['type'] = parameters['B']['type'] = self.DATA_TYPE
        bbox0, dimensions0, raster0 = extract_nsc_data(content_path0, parameters['A'])
        bbox1, dimensions1, raster1 = extract_nsc_data(content_path1, parameters['B'])

        # verify they are the same
        if bbox0.as_str() != bbox1.as_str() or dimensions0.as_str() != dimensions1.as_str():
            raise DUCTRuntimeError(f"mismatching boundingx box and/or dimension: "
                                   f"bbox0={bbox0.as_str()} bbox1={bbox1.as_str()} "
                                   f"dim0={dimensions0.as_str()} dim1={dimensions1.as_str()} ")

        # get the mask generators (if any)
        mask_generator0: Callable[[BoundingBox, Dimensions], np.ndarray] = \
            parameters['A'].get('__helper_mask_generator')
        mask_generator1: Callable[[BoundingBox, Dimensions], np.ndarray] = \
            parameters['B'].get('__helper_mask_generator')

        # generate a mask (if needed)
        mask0: np.ndarray = mask_generator0(bbox0, dimensions0) if mask_generator0 else None
        mask1: np.ndarray = mask_generator1(bbox1, dimensions1) if mask_generator1 else None

        # convert to JSON format
        no_data = parameters['common']['no_data']
        json_data = []
        for y in reversed(range(dimensions0.height)):
            for x in range(dimensions0.width):
                if (mask0 is not None and mask0[y][x] == 0) or (mask1 is not None and mask1[y][x] == 0):
                    json_data.append(no_data)
                else:
                    json_data.append(float(raster0[y][x]) - float(raster1[y][x]))

        # create the heatmap
        return {
            'type': 'heatmap',
            'area': bbox0.dict(),
            'grid': dimensions0.dict(),
            'legend': parameters['common']['legend_title'],
            'colors': parameters['common']['color_schema'],
            'data': json_data,
            'no_data': no_data
        }

    def export_feature(self, content_path: str, parameters: dict, export_path: str, export_format: str) -> None:
        if export_format == 'tiff':
            # extract the raster data
            parameters['type'] = self.DATA_TYPE
            bbox, dimensions, raster = extract_nsc_data(content_path, parameters)

            # get the mask generator (if any)
            mask_generator: Callable[[BoundingBox, Dimensions], np.ndarray] = parameters.get('__helper_mask_generator')

            # if we have a mask generator, then generate and apply mask
            if mask_generator:
                mask: np.ndarray = mask_generator(bbox, dimensions)
                mask = (mask == 0)
                raster[mask] = parameters['no_data']

            # store as TIFF
            with rasterio.open(export_path, 'w', driver='GTiff', height=raster.shape[0], width=raster.shape[1],
                               count=1, crs=CRS().from_epsg(4326), dtype=np.float32,
                               transform=rasterio.transform.from_bounds(west=bbox.west, south=bbox.south,
                                                                        east=bbox.east, north=bbox.north,
                                                                        width=raster.shape[1], height=raster.shape[0])
                               ) as dst:
                dst.write(raster, 1)

        else:
            raise DUCTRuntimeError(f"Format not supported for export: {export_format}")

    def export_delta_feature(self, content_path0: str, content_path1: str, parameters: dict,
                             export_path: str, export_format: str) -> None:
        if export_format == 'tiff':
            # extract the raster data
            parameters['type'] = self.DATA_TYPE
            bbox0, dimensions0, raster0 = extract_nsc_data(content_path0, parameters['A'])
            bbox1, dimensions1, raster1 = extract_nsc_data(content_path1, parameters['B'])

            # verify they are the same
            if bbox0.as_str() != bbox1.as_str() or dimensions0.as_str() != dimensions1.as_str():
                raise DUCTRuntimeError(f"mismatching boundingx box and/or dimension: "
                                       f"bbox0={bbox0.as_str()} bbox1={bbox1.as_str()} "
                                       f"dim0={dimensions0.as_str()} dim1={dimensions1.as_str()} ")

            # get the mask generators (if any)
            mask_generator0: Callable[[BoundingBox, Dimensions], np.ndarray] = \
                parameters['A'].get('__helper_mask_generator')
            mask_generator1: Callable[[BoundingBox, Dimensions], np.ndarray] = \
                parameters['B'].get('__helper_mask_generator')

            # if we have a mask generator, then generate and apply the masks
            raster = raster0 - raster1
            if mask_generator0:
                mask0 = mask_generator0(bbox0, dimensions0)
                mask0 = (mask0 == 0)
                raster[mask0] = parameters['common']['no_data']
            if mask_generator1:
                mask1 = mask_generator1(bbox1, dimensions1)
                mask1 = (mask1 == 0)
                raster[mask1] = parameters['common']['no_data']

            # store as TIFF
            with rasterio.open(export_path, 'w', driver='GTiff', height=raster.shape[0], width=raster.shape[1],
                               count=1, crs=CRS().from_epsg(4326), dtype=np.float32,
                               transform=rasterio.transform.from_bounds(west=bbox0.west, south=bbox0.south,
                                                                        east=bbox0.east, north=bbox0.north,
                                                                        width=raster.shape[1], height=raster.shape[0])
                               ) as dst:
                dst.write(raster, 1)

        else:
            raise DUCTRuntimeError(f"Format not supported for export: {export_format}")


class WindVectorField(DataObjectType):
    DATA_TYPE = 'duct.nsc_var.raster'

    def name(self) -> str:
        return self.DATA_TYPE

    def label(self) -> str:
        return 'Wind Vector Field Raster'

    def supported_formats(self) -> List[str]:
        return ['hdf5']

    def extract_feature(self, content_path: str, parameters: dict) -> Dict:
        parameters['type'] = self.DATA_TYPE

        output_values = {}
        bbox = dimensions = None
        # extract the raster data
        for key in parameters['key']:
            bbox, dimensions, raster = extract_nsc_data(content_path, parameters, key)
            if 'speed' in key:
                output_values['wind_speed'] = raster
            elif 'direction' in key:
                output_values['wind_direction'] = raster

        # get the mask generator (if any)
        mask_generator: Callable[[BoundingBox, Dimensions], np.ndarray] = parameters.get('__helper_mask_generator')

        # generate a mask (if needed)
        mask: np.ndarray = mask_generator(bbox, dimensions) if mask_generator else None
        no_data = parameters['no_data']
        color_schema = parameters['color_schema']

        #  calculate the degree per unit for horizontal and vertical dimensions
        horizontal_unit_degree = (abs(bbox.east - bbox.west) / dimensions.width)
        vertical_unit_degree = (abs(bbox.north - bbox.south) / dimensions.height)

        wind_vector_details: list(WindVectorDetails) = []
        next_feature_id = 0

        # set the interval for drawing arrows based on the resolution (micro-scale: 12, meso-scale: 3)
        arrow_interval = 12 if dimensions.height > 300 else 3

        for y in reversed(range(0, dimensions.height, arrow_interval)):
            for x in range(0, dimensions.width, arrow_interval):
                wind_speed = no_data
                wind_direction = no_data
                # if valid data, then get the wind speed and direction
                if mask is not None and mask[y][x] != 0 and not (math.isnan(output_values['wind_speed'][y][x]) or math.isnan(output_values['wind_direction'][y][x])):
                    wind_speed = float(output_values['wind_speed'][y][x])
                    wind_direction = float(output_values['wind_direction'][y][x])

                if wind_speed != no_data and wind_direction != no_data:
                    wind_details = WindVectorDetails(
                        id=next_feature_id,
                        lat=bbox.north - vertical_unit_degree * y,
                        lon=bbox.west + horizontal_unit_degree * x,
                        wind_speed=wind_speed,
                        wind_direction=wind_direction
                    )

                    wind_vector_details.append(wind_details)
                next_feature_id += 1

        # get visual attributes based on wind speed
        def get_visual_attributes_for_speed(speed):
            for i in range(len(color_schema) - 1):
                if color_schema[i]['value'] <= speed < color_schema[i + 1]['value']:
                    return color_schema[i]['color'], color_schema[i]['size']
            return color_schema[-1]['color'], color_schema[i]['size']

        # create wind speed and direction data sets
        wind_vector_results = {
            'type': 'wind-direction',
            'title': parameters['legend_title'],
            'legendTitle': parameters['legend_title'],
            'legendType': 'discrete',
            'colors': color_schema,
            'data': []
        }

        features = []

        for wind_details in wind_vector_details:
            speed_rounded = round(wind_details.wind_speed, 2)
            direction_rounded = round(wind_details.wind_direction, 2)
            visual_attributes = get_visual_attributes_for_speed(speed_rounded)

            # wind arrow generation
            wind_vector_results['data'].append({
                'coordinates': [wind_details.lat, wind_details.lon],
                'width': visual_attributes[1],
                'height': 10,
                'direction': direction_rounded,
                'speed': speed_rounded,
                'color': '#000000'
            })

            # wind heatmap generation
            features.append({
                "type": "Feature",
                "id": wind_details.id,
                "latitude": wind_details.lat,
                "longitude": wind_details.lon,
                "speed": speed_rounded,
                "properties": {
                    "speed": speed_rounded
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [wind_details.lon, wind_details.lat]
                },
            })

        # set the density based on the resolution (micro-scale, meso-scale)
        if dimensions.height > 300:
            max_density = 0.7
            radius = 1
        else:
            max_density = 0.02
            radius = 20

        # create the wind speed heatmap
        wind_speed_heatmap_results = {
            "type": "geojson",
            "title": "Wind speed (m/s)",
            "geojson": {
                "type": "FeatureCollection",
                "features": features
            },
            "renderer": {
                "type": "heatmap",
                "field": "speed",
                "colorStops": [
                    {"color": "rgba(63, 40, 102, 0)", "ratio": 0},
                    {"color": "#4196FF", "ratio": 0.1},
                    {"color": "#18DEC0", "ratio": 0.2},
                    {"color": "#75FE5C", "ratio": 0.3},
                    {"color": "#D4E735", "ratio": 0.4},
                    {"color": "#FEA130", "ratio": 0.6},
                    {"color": "#E5470B", "ratio": 0.8},
                    {"color": "#9B0F01", "ratio": 1}
                ],
                "maxDensity": max_density,
                "minDensity": 0,
                "referenceScale": 165000,
                "radius": radius,
                "legendOptions": {
                    "title": " ",
                    "maxLabel": "Max wind speed",
                    "minLabel": "Min wind speed",
                }
            }
        }

        # calculate overall statistic data
        # (wind direction will be ignored from the calculation. overall stats will be calculated only for wind speed)
        if 'result_filter' in parameters:
            # modify the mask to account for 'no_value' values
            mask = np.logical_and(mask, output_values['wind_speed'] != no_data)

            # get the values in two decimal points
            overall_avg = f"{round(float(np.average(output_values['wind_speed'][mask])), 2):.2f}"
            overall_min = f"{round(float(np.min(output_values['wind_speed'][mask])), 2):.2f}"
            overall_max = f"{round(float(np.max(output_values['wind_speed'][mask])), 2):.2f}"

            table_description = f"_{parameters.get('statistics_table_description', '')}_"

            markdown_table = f"""### {parameters['legend_title']}  \n  |||\n|:------------------ | -------------------------------:|\n|{table_description}||\n|||\n|||\n| Average    | {overall_avg} |\n| Minimum    | {overall_min} |\n| Maximum    | {overall_max} |"""
            overall_statistic_table_markdown_result = {
                'title': parameters['legend_title'],
                'subtitle': '',
                'table_description': table_description,
                'type': 'markdown',
                'data_values': {
                    'overall_avg': overall_avg,
                    'overall_min': overall_min,
                    'overall_max': overall_max
                },
                'data': markdown_table
            }
        else:
            overall_statistic_table_markdown_result = {}

        return wind_vector_results, overall_statistic_table_markdown_result, wind_speed_heatmap_results

    def extract_delta_feature(self, content_path0: str, content_path1: str, parameters: dict,
                              export_path: str, export_format: str) -> Dict:
        pass

    def export_feature(self, content_path: str, parameters: dict, export_path: str, export_format: str) -> None:
        if export_format == 'tiff':
            output_values = {}
            bbox = dimensions = None
            # extract the raster data
            for key in parameters['key']:
                bbox, dimensions, raster = extract_nsc_data(content_path, parameters, key)
                if 'speed' in key:
                    output_values['wind_speed'] = raster
                elif 'direction' in key:
                    output_values['wind_direction'] = raster

            # stack the rasters as different bands
            rasters = np.stack((output_values['wind_speed'], output_values['wind_direction']))

            # get the mask generator (if any)
            mask_generator: Callable[[BoundingBox, Dimensions], np.ndarray] = parameters.get('__helper_mask_generator')

            # if we have a mask generator, then generate and apply mask
            if mask_generator:
                mask: np.ndarray = mask_generator(bbox, dimensions)
                mask = (mask == 0)
                rasters[:, mask] = parameters['no_data']

            # store as TIFF
            with rasterio.open(export_path, 'w', driver='GTiff', height=rasters.shape[1], width=rasters.shape[2],
                               count=rasters.shape[0], crs=CRS().from_epsg(4326), dtype=np.float32,
                               transform=rasterio.transform.from_bounds(west=bbox.west, south=bbox.south,
                                                                        east=bbox.east, north=bbox.north,
                                                                        width=rasters.shape[2], height=rasters.shape[1])
                               ) as dst:
                for i in range(rasters.shape[0]):
                    dst.write(rasters[i], i + 1)

        else:
            raise DUCTRuntimeError(f"Format not supported for export: {export_format}")

    def export_delta_feature(self, content_path0: str, content_path1: str, parameters: dict,
                             export_path: str, export_format: str) -> None:
        pass
