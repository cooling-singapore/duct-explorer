import datetime
import json
import math
import os
import shutil
import subprocess
from logging import Logger
from typing import List, Dict, Tuple, Union
from zoneinfo import ZoneInfo

import h5py
import numpy as np
from saas.sdk.base import SDKContext, SDKCDataObject, SDKProductSpecification, LogMessage

from duct.dots import duct
from duct.dots.duct_nsc_variables import NearSurfaceClimateVariableLinechart, NearSurfaceClimateVariableRaster, \
    WindVectorField
from duct.exceptions import DUCTRuntimeError
from duct.modules.ah_module import export_traffic, export_power, export_others
from duct.modules.building_energy_model import BuildingEnergyEfficiencyModule
from explorer.analysis.base import Analysis, AnalysisContext, AnalysisStatus
from explorer.project import Project
from explorer.renderer.base import hex_color_to_components
from explorer.schemas import AnalysisGroup, Scene, AnalysisResult, ExplorerRuntimeError, AnalysisSpecification, \
    AnalysisCompareResults


def determine_time_period(logger: Logger, t_beginning: str, dt_warmup: int = 12, dt_sim: int = 24,
                          wrf_hist_interval: int = 10) -> (List[int], List[datetime.datetime],
                                                           Dict[str, str], Dict[str, str]):
    ti = [0, 0, 0, 0, 0]

    # what are the exact starting dates/times of Period of Interest (POI)?
    year = int(t_beginning[0:4])
    month = int(t_beginning[4:6])
    day = int(t_beginning[6:8])
    hour = int(t_beginning[8:10])
    ti[2] = datetime.datetime(year, month, day, hour, 0, 0)  # begin of POI
    ti[3] = ti[2] + datetime.timedelta(hours=dt_sim)  # end of POI

    # # consider the warm-up period (round down to the nearest 6h)
    ti[1] = ti[2]
    ti[0] = ti[1] - datetime.timedelta(hours=dt_warmup)  # begin warm-up period (WUP)
    dh0 = ti[1].hour - 6 * math.floor(ti[1].hour / 6)
    ti[0] = ti[0] - datetime.timedelta(hours=int(dh0))

    # round ending time up to nearest 6h --> Period of Useful Simulation (POUS)
    dh1 = 6 * math.ceil(ti[3].hour / 6) - ti[3].hour
    ti[4] = ti[3] + datetime.timedelta(hours=int(dh1))

    logger.info(f"determine_time_period: t_beginning={t_beginning} [UTC] dt_warmup={dt_warmup} dt_sim={dt_sim}")
    logger.info(f"begin WUP  -> {ti[0].strftime('%Y-%m-%d %H:%M:%S')} UTC")
    logger.info(f"begin POUS -> {ti[1].strftime('%Y-%m-%d %H:%M:%S')} UTC")
    logger.info(f"begin POI  -> {ti[2].strftime('%Y-%m-%d %H:%M:%S')} UTC")
    logger.info(f"end POI    -> {ti[3].strftime('%Y-%m-%d %H:%M:%S')} UTC")
    logger.info(f"end POUS   -> {ti[4].strftime('%Y-%m-%d %H:%M:%S')} UTC")

    # create time table: idx->datetime
    t = ti[0]
    t_table = []
    while t <= ti[4]:
        t_table.append(int(t.strftime("%Y%m%d%H%M%S")))
        t = t + datetime.timedelta(minutes=wrf_hist_interval)

    # create and return t_from and t_to
    t_from = {'date': ti[0].strftime("%Y-%m-%d"), 'time': ti[0].strftime("%H:%M:%S")}
    t_to = {'date': ti[4].strftime("%Y-%m-%d"), 'time': ti[4].strftime("%H:%M:%S")}
    return t_table, ti, t_from, t_to


def match_timestamps(timestamps: np.ndarray, t_table: list[int]) -> dict:
    indices = {}
    for i in range(timestamps.shape[0]):
        indices[timestamps[i]] = i

    mapping = {}
    for i, t_ref in enumerate(t_table):
        ttr = datetime.datetime.strptime(str(t_ref), '%Y%m%d%H%M%S').timestamp()

        closest = min(timestamps, key=lambda x: abs(x - t_ref))
        j0 = indices[closest]

        d = closest - t_ref
        if d == 0:
            mapping[t_ref] = [(j0, 1.0)]

        else:
            if d > 0:
                # closest > t_ref -> second point should thus be j = i-1
                j1 = j0 - 1
                if j1 < 0:
                    mapping[t_ref] = [(j0, 1.0)]
                    continue

            elif d < 0:
                # closest < t_ref -> second point should thus be j = i+1
                j1 = j0 + 1
                if j1 >= timestamps.shape[0]:
                    mapping[t_ref] = [(j0, 1.0)]
                    continue

            else:
                raise Exception("Can't happen")

            t0 = timestamps[j0]
            t1 = timestamps[j1]

            tt0 = datetime.datetime.strptime(str(t0), '%Y%m%d%H%M%S').timestamp()
            tt1 = datetime.datetime.strptime(str(t1), '%Y%m%d%H%M%S').timestamp()

            dt0r = abs(tt0 - ttr)
            dt1r = abs(tt1 - ttr)
            dtr = dt0r + dt1r

            w0 = 1 - dt0r / dtr
            w1 = 1 - dt1r / dtr

            mapping[t_ref] = [(j0, w0), (j1, w1)]

    return mapping


def result_specification() -> dict:
    alpha = 255
    return {
        '2m_air_temperature_uhi': {
            'legend_title': 'Urban Heat Island Intensity (in Δ˚C)',
            'statistics_table_description': 'The Urban Heat Island (UHI) effect, represented by the difference in 2m air temperature '
                           'between urban grids and a designated rural area in southwestern Johor Bahru. '
                           'For the exact grid locations used, refer to the Visual Validation package.',
            'color_schema': [
                {'value': -4, 'color': hex_color_to_components('#2c7bb6', alpha), 'label': '-4˚C'},
                {'value': -2, 'color': hex_color_to_components('#abd9e9', alpha), 'label': '-2˚C'},
                {'value': 0, 'color': hex_color_to_components('#FFFFBF', alpha), 'label': '0˚C'},
                {'value': 4, 'color': hex_color_to_components('#fdae61', alpha), 'label': '+4˚C'},
                {'value': 8, 'color': hex_color_to_components('#d7191c', alpha), 'label': '+8˚C'},
            ],
            'no_data': 999
        },
        '2m_air_temperature_uhi-delta': {
            'legend_title': 'Difference in Urban Heat Island Intensity (in ΔUHI[˚C])',
            'statistics_table_description': 'The Urban Heat Island (UHI) effect, represented by the difference in 2m air temperature '
                           'between urban grids and a designated rural area in southwestern Johor Bahru. '
                           'For the exact grid locations used, refer to the Visual Validation package.',
            'color_schema': [
                {'value': -4, 'color': hex_color_to_components('#EB1C24', alpha), 'label': '-4˚C'},
                {'value': -2, 'color': hex_color_to_components('#BA3450', alpha), 'label': '-2˚C'},
                {'value': 0, 'color': hex_color_to_components('#303030', 127), 'label': '0˚C'},
                {'value': 4, 'color': hex_color_to_components('#3491C6', alpha), 'label': '+4˚C'},
                {'value': 8, 'color': hex_color_to_components('#00ACED', alpha), 'label': '+8˚C'},
            ],
            'no_data': 999
        },
        'wet_bulb_globe_temperature': {
            'legend_title': 'Wet Bulb Globe Temperature (in ˚C)',
            'statistics_table_description': 'Near-surface (2m) Wet Bulb Globe Temperature (WBGT) (in ˚C), estimated from simulated '
                           'temperature, humidity, radiation and wind speed.',
            'color_schema': [
                {'value': 24, 'color': hex_color_to_components('#313695', alpha), 'label': '24˚C'},
                {'value': 26, 'color': hex_color_to_components('#ABD9E9', alpha), 'label': ''},
                {'value': 28, 'color': hex_color_to_components('#FFFFBF', alpha), 'label': '28˚C'},
                {'value': 30, 'color': hex_color_to_components('#FDAE61', alpha), 'label': ''},
                {'value': 32, 'color': hex_color_to_components('#D73027', alpha), 'label': '32˚C'},
                {'value': 34, 'color': hex_color_to_components('#6A0018', alpha), 'label': ''},
                {'value': 36, 'color': hex_color_to_components('#311165', alpha), 'label': '36˚C'},
            ],
            'no_data': 999
        },
        'wet_bulb_globe_temperature-delta': {
            'legend_title': 'Difference in Wet Bulb Globe Temperature (in Δ˚C)',
            'statistics_table_description': 'Near-surface (2m) Wet Bulb Globe Temperature (WBGT) (in ˚C), estimated from simulated '
                           'temperature, humidity, radiation and wind speed.',
            'color_schema': [
                {'value': -5, 'color': hex_color_to_components('#EB1C24', alpha), 'label': 'B > A'},
                {'value': 0.0, 'color': hex_color_to_components('#303030', 127), 'label': 'A == B'},
                {'value': 5, 'color': hex_color_to_components('#00ACED', alpha), 'label': 'A > B'}
            ],
            'no_data': 999
        },
        '2m_air_temperature': {
            'legend_title': 'Air Temperature (in ˚C)',
            'statistics_table_description': 'Near-surface (2m) air temperature (in ˚C)',
            'color_schema': [
                {'value': 24, 'color': hex_color_to_components('#313695', alpha), 'label': '24˚C'},
                {'value': 26, 'color': hex_color_to_components('#ABD9E9', alpha), 'label': ''},
                {'value': 28, 'color': hex_color_to_components('#FFFFBF', alpha), 'label': '28˚C'},
                {'value': 30, 'color': hex_color_to_components('#FDAE61', alpha), 'label': ''},
                {'value': 32, 'color': hex_color_to_components('#D73027', alpha), 'label': '32˚C'},
                {'value': 34, 'color': hex_color_to_components('#6A0018', alpha), 'label': ''},
                {'value': 36, 'color': hex_color_to_components('#311165', alpha), 'label': '36˚C'},
            ],
            'no_data': 999
        },
        '2m_air_temperature-delta': {
            'legend_title': 'Difference in Air Temperature (in Δ˚C)',
            'statistics_table_description': 'Near-surface (2m) air temperature (in ˚C)',
            'color_schema': [
                {'value': -5, 'color': hex_color_to_components('#EB1C24', alpha), 'label': 'B > A'},
                {'value': 0.0, 'color': hex_color_to_components('#303030', 127), 'label': 'A == B'},
                {'value': 5, 'color': hex_color_to_components('#00ACED', alpha), 'label': 'A > B'}
            ],
            'no_data': 999
        },
        '2m_relative_humidity': {
            'legend_title': 'Relative Humidity (in %)',
            'statistics_table_description': 'Near-surface (2m) relative humidity (in %)',
            'color_schema': [
                {'value': 0, 'color': hex_color_to_components('#E5F5F9', alpha), 'label': '60'},
                {'value': 25, 'color': hex_color_to_components('#99D8C9', alpha), 'label': '70'},
                {'value': 50, 'color': hex_color_to_components('#41AE76', alpha), 'label': '80'},
                {'value': 75, 'color': hex_color_to_components('#006D2C', alpha), 'label': '90'},
                {'value': 100, 'color': hex_color_to_components('#033D18', alpha), 'label': '100'}
            ],
            'no_data': 999
        },
        '2m_relative_humidity-delta': {
            'legend_title': 'Difference in Relative Humidity (in Δ%)',
            'statistics_table_description': 'Near-surface (2m) relative humidity (in %)',
            'color_schema': [
                {'value': -20, 'color': hex_color_to_components('#EB1C24', alpha), 'label': 'B > A'},
                {'value': 0.0, 'color': hex_color_to_components('#303030', 127), 'label': 'A == B'},
                {'value': 20, 'color': hex_color_to_components('#00ACED', alpha), 'label': 'A > B'}
            ],
            'no_data': 999
        },
        '10m_wind_speed': {
            'legend_title': 'Wind Speed (in m/s)',
            'statistics_table_description': 'Near-surface (10m) wind speed (in m/s)',
            'color_schema': [
                {'value': 0, 'color': hex_color_to_components('#4196FF', alpha), 'label': '0.0'},
                {'value': 1, 'color': hex_color_to_components('#18DEC0', alpha), 'label': '1.0'},
                {'value': 2, 'color': hex_color_to_components('#75FE5C', alpha), 'label': '2.0'},
                {'value': 3, 'color': hex_color_to_components('#D4E735', alpha), 'label': '3.0'},
                {'value': 4, 'color': hex_color_to_components('#FEA130', alpha), 'label': '4.0'},
                {'value': 6, 'color': hex_color_to_components('#E5470B', alpha), 'label': '6.0'},
                {'value': 8, 'color': hex_color_to_components('#9B0F01', alpha), 'label': '8.0'}
            ],
            'no_data': -1
        },
        '10m_wind_speed-delta': {
            'legend_title': 'Difference in Wind Speed (in Δm/s)',
            'statistics_table_description': 'Near-surface (10m) wind speed (in m/s)',
            'color_schema': [
                {'value': -10, 'color': hex_color_to_components('#EB1C24', alpha), 'label': 'B > A'},
                {'value': 0.0, 'color': hex_color_to_components('#303030', 127), 'label': 'A == B'},
                {'value': 10, 'color': hex_color_to_components('#00ACED', alpha), 'label': 'A > B'}
            ],
            'no_data': 999
        },
        '10m_wind_direction': {
            'legend_title': 'Predominant Wind Direction (˚)',
            'statistics_table_description': 'Near-surface (10m) wind direction (in ˚)',
            'color_schema': [
                {'value': 0, 'color': hex_color_to_components('#d92b30', alpha), 'label': '0'},
                {'value': 90, 'color': hex_color_to_components('#C27c31', alpha), 'label': '90'},
                {'value': 180, 'color': hex_color_to_components('#ffdf3a', alpha), 'label': '180'},
                {'value': 270, 'color': hex_color_to_components('#3cccb4', alpha), 'label': '270'},
                {'value': 360, 'color': hex_color_to_components('#d92b30', alpha), 'label': '360'}
            ],
            'no_data': 999
        },
        '10m_wind_direction-delta': {
            'legend_title': 'Difference in Predominant Wind Direction (Δ˚)',
            'statistics_table_description': 'Near-surface (10m) wind direction (in ˚)',
            'color_schema': [
                {'value': -180, 'color': hex_color_to_components('#EB1C24', alpha), 'label': 'B > A'},
                {'value': 0.0, 'color': hex_color_to_components('#303030', 127), 'label': 'A == B'},
                {'value': 180, 'color': hex_color_to_components('#00ACED', alpha), 'label': 'A > B'}
            ],
            'no_data': 999
        },
        '10m_wind_speed_and_direction': {
            'legend_title': 'Wind direction',
            'statistics_table_description': 'Wind field calculated at a height of 2.5m, visualised for the specific '
                                            'time step selected below.',
            'color_schema': [
                {'value': 0, 'color': [65, 150, 255, 1], 'label': '0.0', 'size': 500},
                {'value': 1, 'color': [24, 222, 192, 1], 'label': '1.0', 'size': 600},
                {'value': 2, 'color': [117, 254, 92, 1], 'label': '2.0', 'size': 700},
                {'value': 3, 'color': [212, 231, 53, 1], 'label': '3.0', 'size': 800},
                {'value': 4, 'color': [254, 161, 48, 1], 'label': '4.0', 'size': 900},
                {'value': 6, 'color': [299, 71, 11, 1], 'label': '6.0', 'size': 1200},
                {'value': 8, 'color': [155, 15, 1, 1], 'label': '8.0', 'size': 1500}
            ],
            'no_data': -1
        },
        '10m_wind_speed_and_direction-delta': {
            'legend_title': 'Difference in Wind Speed (in Δm/s)',
            'statistics_table_description': 'Near-surface (10m) wind speed (in m/s)',
            'color_schema': [
                {'value': -10, 'color': hex_color_to_components('#EB1C24', alpha), 'label': 'B > A'},
                {'value': 0.0, 'color': hex_color_to_components('#303030', 127), 'label': 'A == B'},
                {'value': 10, 'color': hex_color_to_components('#00ACED', alpha), 'label': 'A > B'}
            ],
            'no_data': 999
        }
    }


def normalise(input_path: str, output_path: str, t_table: List[int], t_poi: Tuple[int, int],
              tz_correction: int) -> None:
    with h5py.File(output_path, "w") as f_out:
        with h5py.File(input_path, "r") as f_in:
            # normalise each variable...
            variables = f_in.keys()
            for v in variables:
                source = f_in.get(v)

                # normalisation step 1: if timestamps are not perfectly matching to what is in t_table, calculate
                # the proximity of the normal timesteps in t_table to the nearset two frames, assign weights to the
                # two frames and calculate a normalised frame.
                timestamps = source.attrs['timestamps']
                matches = match_timestamps(timestamps, t_table)
                hourly_buckets = {}
                for i, t in enumerate(t_table):
                    weights = matches[t]

                    # generate a normalised frame: case 1 -> exact timestamp: just use the data from the source as
                    # is; case 2 -> between two frames: calculate the frame as a weighted combination of those two
                    # frames based on the timestamps proximity to each frame's timestamps
                    if len(weights) == 1:
                        idx = weights[0][0]
                        frame = source[idx]

                    else:
                        idx0 = weights[0][0]
                        idx1 = weights[1][0]
                        w0 = weights[0][1]
                        w1 = weights[1][1]

                        frame0 = source[idx0]
                        frame1 = source[idx1]
                        frame = frame0 * w0 + frame1 * w1

                    # sort the frames into hourly buckets. all frames with a timestamp that belong to the same hour
                    # are put into the same bucket. the full timestamp (year, month, day, hour, minute, second) is
                    # truncated to only include the year, month, day, hour (i.e., the first 10 digits).
                    t_truncated = int(str(t)[:10])
                    if t_truncated in hourly_buckets:
                        hourly_buckets[t_truncated].append(frame)
                    else:
                        hourly_buckets[t_truncated] = [frame]

                # normalisation step 2: timestamps come at a sub-hour resolution (e.g., 10 minute resolution). we
                # want to normalise to an hourly resolution. for this purpose all frames belonging to an hour slot
                # are aggregated by a descriptive statistic.
                normalised_timestamps = []
                n_count = []
                m_frames = []
                v_frames = []
                for t, frames in sorted(hourly_buckets.items()):
                    # skip frames that are not within the period of interest
                    if not t_poi[0] <= t*10000 < t_poi[1]:
                        continue

                    # the normalised timestamp is converted into full format: year, month, day, hour, minute, second
                    # and then corrected to local time (e.g., Singapore is UTC+8).
                    t_datetime_utc = datetime.datetime.strptime(str(t), '%Y%m%d%H')
                    t_datetime_sgt = t_datetime_utc + datetime.timedelta(hours=tz_correction)
                    t = int(t_datetime_sgt.strftime('%Y%m%d%H%M%S'))
                    normalised_timestamps.append(t)

                    stacked = np.stack(frames)
                    mean = np.mean(stacked, axis=0)
                    var = np.var(stacked, axis=0)

                    n_count.append(len(frames))
                    m_frames.append(mean)
                    v_frames.append(var)

                data_mean = np.stack(m_frames)
                data_var = np.stack(v_frames)

                # write mean dataset
                destination = f_out.create_dataset(v, data=data_mean, track_times=False)
                destination.attrs['n'] = n_count
                destination.attrs['unit'] = source.attrs['unit']
                destination.attrs['shape'] = data_mean.shape
                destination.attrs['timestamps'] = normalised_timestamps
                destination.attrs['timezone'] = 'UTC+8 (Singapore)'
                destination.attrs['bounding_box'] = source.attrs['bounding_box']

                # write mean dataset
                destination = f_out.create_dataset(f"{v}:variance", data=data_var, track_times=False)
                destination.attrs['n'] = n_count
                destination.attrs['unit'] = source.attrs['unit']
                destination.attrs['shape'] = data_var.shape
                destination.attrs['timestamps'] = normalised_timestamps
                destination.attrs['timezone'] = 'UTC+8 (Singapore)'
                destination.attrs['bounding_box'] = source.attrs['bounding_box']


def create_ah_profile_data_objects(context: AnalysisContext, filenames: List[str], archive_name: str) -> SDKCDataObject:
    # create the archive
    archive_path = os.path.join(context.analysis_path, archive_name)
    result = subprocess.run(['tar', 'czf', archive_path, *filenames], capture_output=True, cwd=context.analysis_path)
    if result.returncode != 0:
        raise ExplorerRuntimeError(f"Failed to pack AH files", details={
            'stdout': result.stdout.decode('utf-8'),
            'stderr': result.stderr.decode('utf-8')
        })

    # upload the archive and delete the temp file
    obj = context.sdk.upload_content(archive_path, 'DUCT.AHProfile', 'archive(tar.gz)', False)

    return obj


def make_result(name: str, label: str, obj_id: str, datetime_0h: str) -> AnalysisResult:
    return AnalysisResult.parse_obj({
        'name': name,
        'label': label,
        'obj_id': {'#': obj_id},
        'specification': {
            'description': '',
            'parameters': {
                'type': 'object',
                'properties': {
                    'result_filter': {
                        'title': 'Filter results by',
                        'type': 'string',
                        'enum': ['time', '24_avg', '24_min', '24_max'],
                        'enumNames': ['Hour of day', '24 hour average', '24 hour minimum', '24 hour maximum'],
                        'default': 'time'
                    }
                },
                'allOf': [
                    {
                        'if': {
                            'properties': {
                                'result_filter': {
                                    'const': 'time'
                                }
                            }
                        },
                        'then': {
                            'properties': {
                                'time': {
                                    'title': 'Hour of Day (0h - 23h)',
                                    'type': 'integer',
                                    'enum': list(range(24)),
                                    'enumNames': [str(i) for i in range(11)],
                                    'default': 0
                                }
                            },
                            'required': ['time']
                        }
                    }
                ],
                'required': ['result_filter']
            }
        },
        'export_format': 'tiff',
        'extras': {
            'datetime_0h': datetime_0h
        }
    })


def resolve_date(option: dict) -> str:
    # resolve date. examples:
    # {'option': {'met-condition': 'high-temperature'}, 'type': 'mesoscale-urban-climate', 'name': 'muw-1'}
    if 'met-condition' in option:
        if option['met-condition'] == 'high-temperature':
            # https://www.straitstimes.com/singapore/spore-does-not-get-high-pressure-system-behind-europes-heatwaves-more-affected-by-el-nino-experts
            # http://www.weather.gov.sg/media-advisory-warm-temperature/

            # Singapore, 20 April 2016 – As forecast in Meteorological Service Singapore’s (MSS) fortnightly weather
            # outlook issued on 15 April 2016, Singapore has been experiencing significantly warmer temperatures over
            # many parts of the island in the past few days. On 17 and 18 April 2016, the daily maximum temperatures
            # recorded at weather stations islandwide ranged between 31.4°C and 36.4°C and between 31.3°C and 35.8°C
            # respectively. The highest daily maximum temperature recorded yesterday was 36°C and as of 3pm today it
            # was 35.1°C. Both were recorded at Choa Chu Kang.
            return '2016-08-07'

        elif option['met-condition'] == 'median-temperature':
            # https://www.straitstimes.com/singapore/environment/five-day-cool-spell-was-singapores-longest-in-a-decade
            return '2017-04-29'

        elif option['met-condition'] == 'northeast-monsoon':
            # https://www.straitstimes.com/singapore/askst-why-is-singapore-so-windy-in-recent-months#:~:text=A%3A%20The%20stronger%20winds%20in,over%20the%20South%20China%20Sea
            return '2018-02-12'

        elif option['met-condition'] == 'southwest-monsoon':
            # https://www.straitstimes.com/singapore/askst-why-is-singapore-so-windy-in-recent-months#:~:text=A%3A%20The%20stronger%20winds%20in,over%20the%20South%20China%20Sea
            return '2019-08-07'

        elif option['met-condition'] == 'warm-night':
            # https://www.straitstimes.com/singapore/askst-why-is-singapore-so-windy-in-recent-months#:~:text=A%3A%20The%20stronger%20winds%20in,over%20the%20South%20China%20Sea
            return '2019-05-28'

        elif option['met-condition'] == 'high-mrt-day':
            # https://www.straitstimes.com/singapore/askst-why-is-singapore-so-windy-in-recent-months#:~:text=A%3A%20The%20stronger%20winds%20in,over%20the%20South%20China%20Sea
            return '2020-04-22'

        elif option['met-condition'] == 'high-wbgt':
            # https://www.straitstimes.com/singapore/askst-why-is-singapore-so-windy-in-recent-months#:~:text=A%3A%20The%20stronger%20winds%20in,over%20the%20South%20China%20Sea
            return '2019-04-24'

        else:
            raise ExplorerRuntimeError(f"Encountered unexpected/unsupported met condition '{option['met-condition']}'")

    else:
        raise ExplorerRuntimeError(f"Encountered unexpected/unsupported option '{option}'")


class MesoscaleUrbanClimateAnalysis(Analysis):
    def name(self) -> str:
        return 'mesoscale-urban-climate'

    def label(self) -> str:
        return 'Mesoscale Urban Climate'

    def type(self) -> str:
        return 'meso'

    def specification(self, project, sdk: SDKContext, aoi_obj_id: str = None,
                      scene_id: str = None) -> AnalysisSpecification:
        return AnalysisSpecification.parse_obj({
            'name': self.name(),
            'label': self.label(),
            'type': self.type(),
            'area_selection': False,
            'parameters_schema': {
              "type": "object",
              "properties": {
                  "name": {"type": "string", "title": "Configuration Name"},
                  "option": {
                    "type": "object",
                    "title": "Meteorological Condition",
                    "properties": {
                      "met-condition": {
                        "title": "Condition",
                        "type": "string",
                        "enum": ["high-temperature", "median-temperature", "northeast-monsoon", "southwest-monsoon",
                                 "warm-night", "high-mrt-day", "high-wbgt"],
                        "enumNames": ["High Temperature", "Median Temperature", "Northeast Monsoon",
                                      "Southwest Monsoon", "Warm night", "High MRT day", "High WBGT"],
                        "default": "high-temperature"
                      }
                    },
                    "allOf": [
                        {

                            "if": {
                                "properties": {
                                    "met-condition": {
                                        "const": "high-temperature"
                                    }
                                }
                            },
                            "then": {
                                "properties": {
                                    "high-temperature-description": {
                                        "type": "string",
                                        "data": "A day that represents the top 10% of average daily temperature values at pedestrian level (2m).  \nDate: 07 Aug 2016  \n\n**Temperature (°C)**\n*   Minimum: 27.00\n*   Maximum: 31.73\n*   Average: 28.92\n\n**Relative Humidity (%)**\n*   Minimum: 61.43\n*   Maximum: 88.69\n*   Average: 76.67\n\n**Wind Speed (m/s)**\n*   Minimum: 0.38\n*   Maximum: 1.90\n*   Average: 1.17"

                                    }
                                }
                            }
                        },
                        {

                            "if": {
                                "properties": {
                                    "met-condition": {
                                        "const": "median-temperature"
                                    }
                                }
                            },
                            "then": {
                                "properties": {
                                    "median-temperature-description": {
                                        "type": "string",
                                        "data": "A day that represents the average daily temperature values at pedestrian level (2m).  \nDate: 29-Apr-2017  \n\n**Temperature (°C)**    \n*   Minimum: 25.90  \n*   Maximum: 30.64  \n*   Average: 27.99  \n\n**Relative Humidity (%)**    \n*   Minimum: 27.99  \n*   Maximum: 89.28  \n*   Average: 80.92  \n\n**Wind Speed (m/s)**    \n*   Minimum: 0.30  \n*   Maximum: 1.72  \n*   Average: 0.98"
                                    }
                                }
                            }
                        },
                        {

                            "if": {
                                "properties": {
                                    "met-condition": {
                                        "const": "northeast-monsoon"
                                    }
                                }
                            },
                            "then": {
                                "properties": {
                                    "northeast-monsoon-description": {
                                        "type": "string",
                                        "data": "A day that represents the top 10% of average daily wind speed values during the Northeast Monsoon season.  \nDate: 12-Feb-2018  \n\n**Temperature (°C)**    \n*   Minimum: 23.62  \n*   Maximum: 29.50  \n*   Average: 25.71  \n\n**Relative Humidity (%)**    \n*   Minimum: 56.85  \n*   Maximum: 82.32  \n*   Average: 74.26  \n\n**Wind Speed (m/s)**    \n*   Minimum: 3.72  \n*   Maximum: 2.86  \n*   Average: 3.31"

                                    }
                                }
                            }
                        },
                        {

                            "if": {
                                "properties": {
                                    "met-condition": {
                                        "const": "southwest-monsoon"
                                    }
                                }
                            },
                            "then": {
                                "properties": {
                                    "southwest-monsoon-description": {
                                        "type": "string",
                                        "data": "A day that represents the top 10% of average daily wind speed values during the Southwest Monsoon season.  \nDate: 07-Aug-2019  \n\n**Temperature (°C)**    \n*   Minimum: 26.27  \n*   Maximum: 29.66  \n*   Average: 27.61  \n\n**Relative Humidity (%)**    \n*   Minimum: 69.81  \n*   Maximum: 86.42  \n*   Average: 79.59  \n\n**Wind Speed (m/s)**    \n*   Minimum: 1.96  \n*   Maximum: 3.20  \n*   Average: 2.42"
                                    }
                                }
                            }
                        },
                        {

                            "if": {
                                "properties": {
                                    "met-condition": {
                                        "const": "warm-night"
                                    }
                                }
                            },
                            "then": {
                                "properties": {
                                    "warm-night-description": {
                                        "type": "string",
                                        "data": "A day that represents the average daily minimum temperature exceeding 26.3 °C. (based on the definition by the CCRS.)  \nDate: 28-May-2019  \n\n**Temperature (°C)**    \n*   Minimum: 27.73  \n*   Maximum: 31.49  \n*   Average: 29.31  \n\n**Relative Humidity (%)**    \n*   Minimum: 66.06  \n*   Maximum: 85.67  \n*   Average: 77.13  \n\n**Wind Speed (m/s)**    \n*   Minimum: 1.40  \n*   Maximum: 2.42  \n*   Average: 1.90"
                                    }
                                }
                            }
                        },
                        {

                            "if": {
                                "properties": {
                                    "met-condition": {
                                        "const": "high-mrt-day"
                                    }
                                }
                            },
                            "then": {
                                "properties": {
                                    "high-mrt-day-description": {
                                        "type": "string",
                                        "data": "A day that represents the top 10% of average daily Mean Radiant Temperature (MRT) values.  \nDate: 22-Apr-2020  \n\n**Temperature (°C)**    \n*   Minimum: 27.06  \n*   Maximum: 31.12  \n*   Average: 28.73  \n\n**Relative Humidity (%)**    \n*   Minimum: 67.22  \n*   Maximum: 88.22  \n*   Average: 78.78  \n\n**Wind Speed (m/s)**    \n*   Minimum: 0.38  \n*   Maximum: 1.90  \n*   Average: 1.17"
                                    }
                                }
                            }
                        },
                        {
                            "if": {
                                "properties": {
                                    "met-condition": {
                                        "const": "high-wbgt"
                                    }
                                }
                            },
                            "then": {
                                "properties": {
                                    "high-wbgt-description": {
                                        "type": "string",
                                        "data": "A day with high wet-bulb globe temperatures (at least one hour with WBGT >33°C).  \nDate: 24 Apr 2019  \n\n**Temperature (°C)**\n*   Minimum: 27.34\n*   Maximum: 32.09\n*   Average: 29.21\n\n**Relative Humidity (%)**\n*   Minimum: 63.82\n*   Maximum: 87.85\n*   Average: 77.62\n\n**Wind Speed (m/s)**\n*   Minimum: 0.56\n*   Maximum: 1.70\n*   Average: 1.09"

                                    }
                                }
                            }
                        }
                    ],
                    "required": ["met-condition"]
                  },
                  "dt_sim_warmup": {
                      "type": "string",
                      "title": "Runtime",
                      "enum": ["1_0", "24_12"],
                      "enumNames": ["1h test (no warm-up)", "24h full run (12h warm-up)"],
                      "default": "24"
                  }
              },
              "required": ["name", "option", "dt_sim_warmup"]
            },
            'description': 'This analysis uses a meso-scale urban climate model to estimate the local climatic '
                           'conditions in terms of air temperature, relative humidity, wind speed and direction over '
                           'a 24 hour period. The meteorological conditions of the selected date will be used to '
                           'drive simulations. This is recommened for urban planners to gain in-depth understanding '
                           'of urban climate performance.',
            'further_information': 'This analysis is based on a workflow using the <a '
                                   'href="https://github.com/cooling-singapore/mWRF_SG">mWRF_SG</a> model (a Cooling '
                                   'Singapore fork of the <a href="https://github.com/wrf-model/WRF">Weather Research '
                                   'and Forecasting (WRF)</a>) developed by <a '
                                   'href="mailto:muhammad.omer@sec.ethz.ch">Omer Mughal</a>. The SaaS adapters for '
                                   'this model has been developed by <a href="mailto:aydt@arch.ethz.ch">Heiko '
                                   'Aydt</a>. For more information, please contact the respective authors.',
            'sample_image': self.name()+'.png',
            'ui_schema': {
                'ui:order': ['name', 'option', 'dt_sim_warmup'],
                'option': {
                    'high-temperature-description': {
                        'ui:widget': 'markdown'
                    },
                    'median-temperature-description': {
                        'ui:widget': 'markdown'
                    },
                    'northeast-monsoon-description': {
                        'ui:widget': 'markdown'
                    },
                    'southwest-monsoon-description': {
                        'ui:widget': 'markdown'
                    },
                    'warm-night-description': {
                        'ui:widget': 'markdown'
                    },
                    'high-mrt-day-description': {
                        'ui:widget': 'markdown'
                    },
                    'high-wbgt-description': {
                        'ui:widget': 'markdown'
                    }
                }
            },
            'required_processors': ['ucm-wrf-prep', 'ucm-wrf-sim'],
            'required_bdp': [],
            'result_specifications': result_specification()
        })

    def _submit_prep_job(self, context: AnalysisContext, scene: Scene, group: AnalysisGroup,
                         args: Dict[str, Union[str, int, float, bool, list, dict]]) -> str:
        # find the processor
        proc = context.sdk.find_processor_by_name('ucm-wrf-prep')
        if proc is None:
            raise DUCTRuntimeError(f"Processor 'ucm-wrf-prep' not found.")

        wrfprep_parameters = {
            'name': context.analysis_id[:8],
            't_from': args['t_from'],
            't_to': args['t_to'],
            'settings': {
                'pbs_project_id': '21120261',
                'pbs_queue': 'normal'
            }
        }

        vf_settings = scene.module_settings['vegetation-fraction']
        for i in range(10):
            vf = vf_settings[f'p_lcz{i+1}']
            vf /= 100.0
            wrfprep_parameters[f'frc_urb{i+1}'] = 1.0 - vf

        # submit the job
        inputs = {
            'parameters': wrfprep_parameters,
            'information': {
                'project_id': context.project.meta.id,
                'analysis_id': context.analysis_id,
                'scene': scene.dict(),
                'group': group.dict()
            },
            'bem-parameters': context.sdk.find_data_object(args['bem_parameters_obj_id']),
            'lcz-map': context.sdk.find_data_object(args['lcz_obj_id']),
            'vegfra-map': context.sdk.find_data_object(args['vf_obj_id']),
            'lh-profile': context.sdk.find_data_object(args['lh_obj_id']),
            'sh-profile': context.sdk.find_data_object(args['sh_obj_id'])
        }

        outputs = {name: SDKProductSpecification(
            restricted_access=False,
            content_encrypted=False,
            target_node=context.sdk.dor()
            # owner=context.sdk.authority.identity
        ) for name in ['wrf-run-package', 'vv-package']}

        job = proc.submit(inputs, outputs, name=f"{context.analysis_id}.0",
                          description=f"job part of analysis {context.analysis_id}")

        return job.content.id

    def _submit_sim_job(self, context: AnalysisContext, scene: Scene, group: AnalysisGroup,
                        args: Dict[str, Union[str, int, float, bool, list, dict]]) -> str:
        # find the processor
        proc = context.sdk.find_processor_by_name('ucm-wrf-sim')
        if proc is None:
            raise DUCTRuntimeError(f"Processor 'ucm-wrf-sim' not found.")

        # submit the job
        inputs = {
            'parameters': {
                'name': context.analysis_id[:8],
                'settings': {
                    'pbs_project_id': '21120261',
                    'pbs_queue': 'normal'
                }
            },
            'information': {
                'project_id': context.project.meta.id,
                'analysis_id': context.analysis_id,
                'scene': scene.dict(),
                'group': group.dict()
            },
            'wrf-prep-vv-package': context.sdk.find_data_object(args['vv-package']),
            'wrf-run-package': context.sdk.find_data_object(args['wrf-run-package'])
        }

        outputs = {name: SDKProductSpecification(
            restricted_access=False,
            content_encrypted=False,
            target_node=context.sdk.dor()
            # owner=context.sdk.authority.identity
        ) for name in ['d04-near-surface-climate', 'vv-package']}

        job = proc.submit(inputs, outputs, name=f"{context.analysis_id}.0",
                          description=f"job part of analysis {context.analysis_id}")

        return job.content.id

    def perform_analysis(self, group: AnalysisGroup, scene: Scene, context: AnalysisContext) -> List[AnalysisResult]:
        # add a progress tracker for this function
        self_tracker_name = 'muc.perform_analysis'
        context.add_update_tracker(self_tracker_name, 10)

        checkpoint, args, status = context.checkpoint()
        if status == AnalysisStatus.RUNNING and checkpoint == 'initialised':
            context.update_progress(self_tracker_name, 15)

            # determine the paths
            sh_traffic_path = os.path.join(context.analysis_path, 'sh_traffic.json')
            sh_power_path = os.path.join(context.analysis_path, 'sh_power.json')
            lh_power_path = os.path.join(context.analysis_path, 'lh_power.json')
            sh_others_path = os.path.join(context.analysis_path, 'sh_others.json')
            lh_others_path = os.path.join(context.analysis_path, 'lh_others.json')
            lcz_path = os.path.join(context.analysis_path, 'lcz_map.tiff')
            vf_path = os.path.join(context.analysis_path, 'vf_map.tiff')

            # extract parameters
            module_settings = scene.module_settings['anthropogenic-heat']
            p_ev = module_settings['p_ev'] / 100.0
            p_demand = (100 + module_settings['p_demand']) / 100.0
            base_demand = module_settings['base_demand']
            ev100_demand = module_settings['ev100_demand']
            renewables = module_settings['renewables']
            imports = module_settings['imports']

            # determine the AH profiles based on the scene information
            export_traffic(p_ev, sh_traffic_path, context.project, context.sdk)
            export_power(base_demand, ev100_demand, p_ev, p_demand, renewables, imports,
                         sh_power_path, lh_power_path, context.project, context.sdk)
            ohe_obj_id = module_settings['others']
            export_others(ohe_obj_id, sh_others_path, lh_others_path, context.project, context.sdk)

            # export LCZ and VF maps
            context.project.vf_mixer.export_lcz_and_vf(scene.module_settings, lcz_path, vf_path, context.sdk)

            # create the SH/LH profile objects
            sh_obj = create_ah_profile_data_objects(context, ['sh_traffic.json', 'sh_power.json', 'sh_others.json'],
                                                    'sh_all.tar.gz')
            lh_obj = create_ah_profile_data_objects(context, ['lh_power.json', 'lh_others.json'],
                                                    'lh_all.tar.gz')

            lcz_obj = context.sdk.upload_content(lcz_path, 'DUCT.GeoRasterData', 'tiff', False)
            vf_obj = context.sdk.upload_content(vf_path, 'DUCT.GeoRasterData', 'tiff', False)

            # get the BEM parameters
            profile_name = scene.module_settings['building-energy-efficiency']['profile']
            bem_parameters = {profile['name']: profile['parameters'] for profile in
                              BuildingEnergyEfficiencyModule.profiles}
            bem_parameters = bem_parameters[profile_name]

            # create the BEM parameters object
            bem_parameters_path = os.path.join(context.analysis_path, 'bem-parameters.txt')
            with open(bem_parameters_path, 'w') as f:
                for key, values in bem_parameters.items():
                    f.write(f"{key}: {values}\n")
            bem_parameters = context.sdk.upload_content(bem_parameters_path, 'DUCT.WRFBEMParameters', 'txt', False)

            # determine some technical parameters:
            # {'dt_sim_warmup': '24_12', ...}
            dt_sim_warmup: str = str(group.parameters['dt_sim_warmup']) if 'dt_sim_warmup' in group.parameters else '24_12'
            dt_sim, dt_warmup = map(int, dt_sim_warmup.split('_'))

            # determine time periods. examples:
            # {'option': {'met-condition': 'high-temperature'}, ...}
            # {'option': {'selected-date': '2023-07-20'}, ...}
            date = resolve_date(group.parameters['option'])

            # TODO: the timezone info should come from the project meta information (probably via the BDP package)
            t_local = date.split('-')
            t_local = datetime.datetime(int(t_local[0]), int(t_local[1]), int(t_local[2]), 0, 0, 0, 0,
                                        tzinfo=ZoneInfo('Asia/Singapore'))

            t_utc = t_local.astimezone(ZoneInfo('UTC'))
            t_utc = t_utc.strftime('%Y%m%d%H%M%S')
            context.logger.info(f"t_local={t_local} | t_utc={t_utc}")

            t_table, ti, t_from, t_to = determine_time_period(context.logger, t_utc, dt_warmup=dt_warmup, dt_sim=dt_sim)
            context.logger.info(f"t_table={t_table}")
            context.logger.info(f"ti={ti}")
            context.logger.info(f"t_from={t_from}")
            context.logger.info(f"t_to={t_to}")

            # EXAMPLE:
            # t_local=2016-04-18 00:00:00+08:00 | t_utc=20160417160000
            # t_beginning=20160417160000 [UTC] dt_warmup=12 dt_sim=24
            # begin WUP  -> 2016-04-17 00:00:00 UTC -> t[0]=20160417000000
            # begin POUS -> 2016-04-17 16:00:00 UTC
            # begin POI  -> 2016-04-17 16:00:00 UTC -> t[2]=20160417160000
            # end POI    -> 2016-04-18 16:00:00 UTC -> t[3]=20160418160000
            # end POUS   -> 2016-04-18 18:00:00 UTC -> t[4]=20160418180000
            # t_table=[20160417000000 20160417010000 20160417020000 20160417030000 ... 20160418180000]

            checkpoint, args, status = context.update_checkpoint('ready-for-preparation', {
                't_from':  t_from,
                't_to': t_to,
                'bem_parameters_obj_id': bem_parameters.meta.obj_id,
                'sh_obj_id': sh_obj.meta.obj_id,
                'lh_obj_id': lh_obj.meta.obj_id,
                'lcz_obj_id': lcz_obj.meta.obj_id,
                'vf_obj_id': vf_obj.meta.obj_id
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'ready-for-preparation':
            context.update_progress(self_tracker_name, 30)

            job_id = self._submit_prep_job(context, scene, group, args)

            checkpoint, args, status = context.update_checkpoint('waiting-for-preparation', {
                'job_id': job_id
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'waiting-for-preparation':
            context.update_progress(self_tracker_name, 45)
            job_id = args['job_id']

            context.add_update_tracker(f'job:{job_id}', 100)

            def callback_progress(progress: int) -> None:
                context.update_progress(f'job:{job_id}', progress)

            def callback_message(message: LogMessage) -> None:
                context.update_message(message)

            # find the job
            job = context.sdk.find_job(job_id)
            if job is None:
                raise DUCTRuntimeError(f"Job {job_id} cannot be found.")

            # wait for the job to be finished
            outputs = job.wait(callback_progress=callback_progress, callback_message=callback_message)

            checkpoint, args, status = context.update_checkpoint('ready-for-simulation', {
                'wrf-run-package': outputs['wrf-run-package'].meta.obj_id,
                'vv-package': outputs['vv-package'].meta.obj_id
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'ready-for-simulation':
            context.update_progress(self_tracker_name, 60)

            job_id = self._submit_sim_job(context, scene, group, args)

            checkpoint, args, status = context.update_checkpoint('waiting-for-simulation', {
                'job_id': job_id
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'waiting-for-simulation':
            context.update_progress(self_tracker_name, 75)
            job_id = args['job_id']

            context.add_update_tracker(f'job:{job_id}', 900)

            def callback_progress(progress: int) -> None:
                context.update_progress(f'job:{job_id}', progress)

            def callback_message(message: LogMessage) -> None:
                context.update_message(message)

            # find the job
            job = context.sdk.find_job(job_id)
            if job is None:
                raise DUCTRuntimeError(f"Job {job_id} cannot be found.")

            # wait for the job to be finished
            outputs = job.wait(callback_progress=callback_progress, callback_message=callback_message)

            checkpoint, args, status = context.update_checkpoint('simulation-done', {
                'd04-near-surface-climate': outputs['d04-near-surface-climate'].meta.obj_id,
                'vv-package': outputs['vv-package'].meta.obj_id
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'simulation-done':
            context.update_progress(self_tracker_name, 90)

            # retrieve the original NSC data
            obj_orig = context.sdk.find_data_object(args['d04-near-surface-climate'])
            obj_orig_path = os.path.join(context.analysis_path, 'd04-near-surface-climate.original')
            obj_orig.download(obj_orig_path)

            # re-determine some technical parameters
            # TODO: keep this in args instead (it's already determined in the first checkpoint
            dt_sim_warmup: str = str(group.parameters['dt_sim_warmup']) if 'dt_sim_warmup' in group.parameters else '24_12'
            dt_sim, dt_warmup = map(int, dt_sim_warmup.split('_'))

            date = resolve_date(group.parameters['option'])
            t_local = date.split('-')
            t_local = datetime.datetime(int(t_local[0]), int(t_local[1]), int(t_local[2]), 0, 0, 0, 0,
                                        tzinfo=ZoneInfo('Asia/Singapore'))
            t_utc = t_local.astimezone(ZoneInfo('UTC'))
            t_utc = t_utc.strftime('%Y%m%d%H%M%S')
            t_table, ti, _, _ = determine_time_period(context.logger, t_utc, dt_warmup=dt_warmup, dt_sim=dt_sim)

            # normalise the NSC data and store in DOR
            obj_path = os.path.join(context.analysis_path, 'd04-near-surface-climate.normalised')
            t_poi = (int(ti[2].strftime("%Y%m%d%H%M%S")), int(ti[3].strftime("%Y%m%d%H%M%S")))
            context.logger.info(f"t_poi={t_poi}")
            normalise(obj_orig_path, obj_path, t_table, t_poi, 8)
            obj = context.sdk.upload_content(obj_path, 'DUCT.NearSurfaceClimateVariables', 'hdf5', False)
            context.logger.info(f"normalised: obj={obj.meta.obj_id}")

            # prepare analysis results
            results = [
                make_result(i[0], i[1], obj.meta.obj_id, t_local.strftime("%Y%m%d%H%M%S")) for i in [
                    ('2m_air_temperature', 'Air Temperature'),
                    ('2m_relative_humidity', 'Relative Humidity'),
                    ('2m_air_temperature_uhi', 'Air Temperature UHI'),
                    ('wet_bulb_globe_temperature', 'Wet Bulb Globe Temperature'),
                    ('10m_wind_speed', 'Wind Speed'),
                    ('10m_wind_direction', 'Wind Direction'),
                    ('10m_wind_speed_and_direction', 'Wind Speed and Direction')
                ]
            ]

            results.append(AnalysisResult.parse_obj({
                'name': 'vv-package',
                'label': 'Visual Validation Data',
                'obj_id': {'#': args['vv-package']},
                'specification': {
                    'description': 'Visual validation data. This includes a variety of GeoTIFF files providing maps '
                                   'showing variables of interest at different stages of the WRF pre-processing pipeline. '
                                   'More specifically: GEOGRID/REAL variables LU, GF, SH_EXT, LH_EXT (before and after '
                                   'update/injection of AH data and LCZ/vegetation Fraction data). For simulation results, '
                                   'GeoTIFFs are included for all timesteps and all climatic variables '
                                   '(2m_air_temperature, 2m_air_temperature_uhi, 2m_relative_humidity, 10m_wind_direction,'
                                   '10m_wind_speed). Furthermore, for debugging purposes, log files of the WRF run are '
                                   'included as well. Please note that export may take a while as the file is '
                                   'large (~100 MB)',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'product': {
                                'type': 'string',
                                'title': 'Product',
                                'enum': ['geogrid-LU.d04', 'geogrid-GF.d04', 'real-LU.d01', 'real-LU.d02',
                                         'real-LU.d03', 'real-LU.d04', 'real-VF.d01', 'real-VF.d02',
                                         'real-VF.d03', 'real-VF.d04', 'uhi-mask-urban', 'uhi-mask-ref'],
                                'default': 'geogrid-LU.d04'
                            }
                        },
                        'required': ['product']
                    }
                },
                'export_format': 'tar.gz'
            }))

            context.update_progress(self_tracker_name, 100)
            return results

        if status != AnalysisStatus.CANCELLED:
            raise DUCTRuntimeError(f"Encountered unexpected checkpoint: {checkpoint}")

    def extract_feature(self, content_paths: Dict[str, str], result: AnalysisResult, parameters: dict,
                        project: Project, sdk: SDKContext, export_path: str, json_path: str) -> None:

        supported_variables = ['10m_wind_direction', '10m_wind_speed', '2m_air_temperature', '2m_air_temperature_uhi',
                               '2m_relative_humidity', 'wet_bulb_globe_temperature']

        if result.name in supported_variables:
            # add spec to the parameters
            spec = result_specification()[result.name]
            parameters['key'] = result.name
            parameters['datetime_0h'] = result.extras['datetime_0h']
            parameters['no_data'] = spec['no_data']
            parameters['legend_title'] = spec['legend_title']
            parameters['color_schema'] = spec['color_schema']
            parameters['statistics_table_description'] = spec['statistics_table_description']

            with open(json_path, 'w') as f:
                heatmap_result, overall_statistic_table_result = NearSurfaceClimateVariableRaster().extract_feature(content_paths['#'], parameters)
                linechart_result = NearSurfaceClimateVariableLinechart().extract_feature(content_paths['#'], parameters)
                assets = [
                    heatmap_result,
                    linechart_result,
                    overall_statistic_table_result
                ]
                f.write(json.dumps(assets))

            NearSurfaceClimateVariableRaster().export_feature(content_paths['#'], parameters, export_path,
                                                              result.export_format)

        elif result.name == '10m_wind_speed_and_direction':
            # add spec to the parameters
            spec = result_specification()[result.name]
            parameters['key'] = ['10m_wind_speed', '10m_wind_direction']
            parameters['datetime_0h'] = result.extras['datetime_0h']
            parameters['no_data'] = spec['no_data']
            parameters['legend_title'] = spec['legend_title']
            parameters['color_schema'] = spec['color_schema']
            parameters['statistics_table_description'] = spec['statistics_table_description']

            with open(json_path, 'w') as f:
                vector_field_results, overall_statistic_table_result, heatmap_result = WindVectorField().extract_feature(content_paths['#'], parameters)
                # the wind direction is not considered for chart generation.Charts will be generated only for wind speed
                parameters['key'] = '10m_wind_speed'
                linechart_result = NearSurfaceClimateVariableLinechart().extract_feature(content_paths['#'], parameters)
                assets = [
                    vector_field_results,
                    linechart_result,
                    overall_statistic_table_result,
                    heatmap_result
                ]
                f.write(json.dumps(assets))

            # both wind speed and direction results will be exported
            parameters['key'] = ['10m_wind_speed', '10m_wind_direction']
            WindVectorField().export_feature(content_paths['#'], parameters, export_path, result.export_format)

        elif result.name == 'vv-package':
            # create a temporary working directory for the vv-package contents
            temp_path = os.path.join(project.info.temp_path, 'vv-package-contents')
            if os.path.isdir(temp_path):
                shutil.rmtree(temp_path)
            os.makedirs(temp_path)

            # copy and unpack the vv-package
            shutil.copy(content_paths['#'], os.path.join(temp_path, 'vv-package.tar.gz'))
            proc_result = subprocess.run(['tar', 'xzf', 'vv-package.tar.gz'], cwd=temp_path, capture_output=True)
            if proc_result.returncode != 0:
                raise ExplorerRuntimeError(f"Failed to unpack vv-package", details={
                    'stderr': proc_result.stderr.decode('utf-8'),
                    'stdout': proc_result.stdout.decode('utf-8')
                })

            # even if a mask is provided, for the visual validation package, we do not want to use it
            parameters['__helper_mask_generator'] = None

            # map products to their respective files
            file_mapping = {
                'geogrid-LU.d04': os.path.join(temp_path, 'geogrid', 'injected_LU.d04.tiff'),
                'geogrid-GF.d04': os.path.join(temp_path, 'geogrid', 'injected_GF.d04.tiff'),
                'real-LU.d01': os.path.join(temp_path, 'real', 'LU.d01.tiff'),
                'real-LU.d02': os.path.join(temp_path, 'real', 'LU.d02.tiff'),
                'real-LU.d03': os.path.join(temp_path, 'real', 'LU.d03.tiff'),
                'real-LU.d04': os.path.join(temp_path, 'real', 'LU.d04.tiff'),
                'real-VF.d01': os.path.join(temp_path, 'real', 'VF.d01.tiff'),
                'real-VF.d02': os.path.join(temp_path, 'real', 'VF.d02.tiff'),
                'real-VF.d03': os.path.join(temp_path, 'real', 'VF.d03.tiff'),
                'real-VF.d04': os.path.join(temp_path, 'real', 'VF.d04.tiff'),
                'uhi-mask-urban': os.path.join(temp_path, 'wrfrun', 'uhi_mask_urban.tiff'),
                'uhi-mask-ref': os.path.join(temp_path, 'wrfrun', 'uhi_mask_ref.tiff')
            }

            if parameters['product'] in ['geogrid-LU.d04', 'real-LU.d01', 'real-LU.d02',
                                         'real-LU.d03', 'real-LU.d04']:
                parameters['no_data'] = 999
                parameters['legend_title'] = 'Land-use Categories'

                assets = [
                    duct.LandUseMap().extract_feature(file_mapping[parameters['product']], parameters)
                ]

            elif parameters['product'] in ['geogrid-GF.d04']:
                parameters['no_data'] = 999
                parameters['legend_title'] = 'Vegetation Fraction'
                parameters['color_schema'] = [
                    {'value': 0.0, 'color': hex_color_to_components('#993404', 255), 'label': '0%'},
                    {'value': 0.5, 'color': hex_color_to_components('#f7fcf5', 255), 'label': '50%'},
                    {'value': 1.0, 'color': hex_color_to_components('#00441b', 255), 'label': '100%'}
                ]

                assets = [
                    duct.GeoRasterData().extract_feature(file_mapping[parameters['product']], parameters)
                ]

            elif parameters['product'] in ['real-VF.d01', 'real-VF.d02', 'real-VF.d03', 'real-VF.d04']:
                parameters['no_data'] = 999
                parameters['legend_title'] = 'Vegetation Fraction'
                parameters['color_schema'] = [
                    {'value': 0, 'color': hex_color_to_components('#993404', 255), 'label': '0%'},
                    {'value': 50, 'color': hex_color_to_components('#f7fcf5', 255), 'label': '50%'},
                    {'value': 100, 'color': hex_color_to_components('#00441b', 255), 'label': '100%'}
                ]

                assets = [
                    duct.GeoRasterData().extract_feature(file_mapping[parameters['product']], parameters)
                ]

            elif parameters['product'] == 'uhi-mask-urban':
                parameters['no_data'] = 0
                parameters['legend_title'] = 'UHI Mask'
                parameters['color_schema'] = [
                    {'value': 0, 'color': hex_color_to_components('#ffffff', 0), 'label': '-'},
                    {'value': 1, 'color': hex_color_to_components('#dd1111', 192), 'label': 'Urban'},
                ]

                assets = [
                    duct.GeoRasterData().extract_feature(file_mapping[parameters['product']], parameters)
                ]

            elif parameters['product'] == 'uhi-mask-ref':
                parameters['no_data'] = 0
                parameters['legend_title'] = 'UHI Mask'
                parameters['color_schema'] = [
                    {'value': 0, 'color': hex_color_to_components('#ffffff', 0), 'label': '-'},
                    {'value': 1, 'color': hex_color_to_components('#11dd11', 192), 'label': 'Largest Rural/Natural Cluster'},
                ]

                assets = [
                    duct.GeoRasterData().extract_feature(file_mapping[parameters['product']], parameters)
                ]

            else:
                raise ExplorerRuntimeError(f"Encountered unexpected/unsupported vv-package product "
                                           f"'{parameters['product']}'",
                                           details={'result': result.dict(), 'parameters': parameters})

            with open(json_path, 'w') as f:
                f.write(json.dumps(assets))

            shutil.copy(content_paths['#'], export_path)
            shutil.rmtree(temp_path)

        else:
            raise ExplorerRuntimeError(f"Encountered unexpected/unsupported result '{result.name}'", details={
                'result': result.dict(),
                'parameters': parameters
            })

    def extract_delta_feature(self, content_paths0: Dict[str, str], result0: AnalysisResult, parameters0: dict,
                              content_paths1: Dict[str, str], result1: AnalysisResult, parameters1: dict,
                              project: Project, sdk: SDKContext, export_path: str, json_path: str) -> None:

        supported_variables = ['10m_wind_direction', '10m_wind_speed', '2m_air_temperature', '2m_relative_humidity',
                               'wet_bulb_globe_temperature']

        # check if the result names are identical
        if result0.name != result1.name:
            raise DUCTRuntimeError(f"Mismatching result names: {result0.name} != {result1.name}")

        # do we have the result name in our variable mapping?
        if result0.name in supported_variables:
            # add spec  to the parameters
            spec = result_specification()[f"{result0.name}-delta"]

            parameters0['key'] = result0.name
            parameters0['datetime_0h'] = result0.extras['datetime_0h']

            parameters1['key'] = result1.name
            parameters1['datetime_0h'] = result1.extras['datetime_0h']

            parameters = {
                'A': parameters0,
                'B': parameters1,
                'common': {
                    'no_data': spec['no_data'],
                    'legend_title': spec['legend_title'],
                    'color_schema': spec['color_schema']
                }
            }

            with open(json_path, 'w') as f:
                heatmap_result = NearSurfaceClimateVariableRaster().extract_delta_feature(content_paths0['#'],
                                                                                          content_paths1['#'],
                                                                                          parameters)
                assets = [
                    heatmap_result
                ]
                f.write(json.dumps(assets))

            NearSurfaceClimateVariableRaster().export_delta_feature(content_paths0['#'], content_paths1['#'],
                                                                    parameters, export_path, result0.export_format)

        elif result0.name == '10m_wind_speed_and_direction':
            # add spec  to the parameters
            spec = result_specification()[f"{result0.name}-delta"]

            # the wind direction is not considered for delta. Delta will be generated only for wind speed
            parameters0['key'] = '10m_wind_speed'
            parameters0['datetime_0h'] = result0.extras['datetime_0h']

            parameters1['key'] = '10m_wind_speed'
            parameters1['datetime_0h'] = result1.extras['datetime_0h']

            parameters = {
                'A': parameters0,
                'B': parameters1,
                'common': {
                    'no_data': spec['no_data'],
                    'legend_title': spec['legend_title'],
                    'color_schema': spec['color_schema']
                }
            }

            with open(json_path, 'w') as f:
                assets = [
                    NearSurfaceClimateVariableRaster().extract_delta_feature(content_paths0['#'],
                                                            content_paths1['#'],
                                                            parameters)
                ]
                f.write(json.dumps(assets))

            NearSurfaceClimateVariableRaster().export_delta_feature(content_paths0['#'], content_paths1['#'],
                                                   parameters, export_path, result0.export_format)

        else:
            raise ExplorerRuntimeError(f"Encountered unexpected/unsupported result '{result0.name}'/'{result1.name}'",
                                       details={
                                           'result0': result0.dict(),
                                           'result1': result1.dict(),
                                           'parameters0': parameters0,
                                           'parameters1': parameters1
                                       })

    def get_compare_results(self, content0: dict, content1: dict) -> AnalysisCompareResults:
        all_chart_results = []

        normalised_results_list = list(self.normalise_parameters(content0, content1))

        # if both A and B results have charts, merge charts to represent results in a single chart
        if len(normalised_results_list[0]) > 1 and len(normalised_results_list[1]) > 1:
            # get chart datasets
            chart_1_data = normalised_results_list[0][1]['data']['datasets']
            chart_2_data = normalised_results_list[1][1]['data']['datasets']

            # update line style and legend labels according to the result suffix
            def update_line_chart_labels_and_style(chart_data: dict, suffix: str):
                for dataset in chart_data:
                    # add suffix to legend labels to differentiate A and B
                    dataset['label'] += suffix
                    # add borderDash to displayed result B in dash lines
                    if suffix == '_B':
                        dataset['borderDash'] = [2, 2]

                return chart_data

            combined_result_chart = normalised_results_list[0][1]
            # merge both datasets to display both results in a single chart
            combined_result_chart['data']['datasets'] = update_line_chart_labels_and_style(chart_1_data, '_A') + \
                                                        update_line_chart_labels_and_style(chart_2_data, '_B')
            all_chart_results.append(combined_result_chart)

        # if both A and B results have statistic table, merge tables to represent results in a single table
        if len(normalised_results_list[0]) > 2 and len(normalised_results_list[1]) > 2:
            # get statistics tables
            statistics_table_1_data = normalised_results_list[0][2]
            statistics_table_2_data = normalised_results_list[1][2]

            if statistics_table_1_data and statistics_table_2_data:
                merged_markdown_table = f"""### {statistics_table_1_data['title']}  \n  |||||\n|:-------------- | -------------------:|----------|---------------------:|\n|{statistics_table_1_data['table_description']}||||\n||**A**||**B**|\n| Average    | {statistics_table_1_data['data_values']['overall_avg']} | | {statistics_table_2_data['data_values']['overall_avg']} |\n| Minimum    | {statistics_table_2_data['data_values']['overall_min']} | | {statistics_table_2_data['data_values']['overall_min']} |\n| Maximum    | {statistics_table_2_data['data_values']['overall_max']} | | {statistics_table_2_data['data_values']['overall_max']} |"""

                combined_statistic_table_markdown_result = {
                    'title': statistics_table_1_data['title'],
                    'type': 'markdown',
                    'data': merged_markdown_table
                }
                all_chart_results.append(combined_statistic_table_markdown_result)

        results0 = [normalised_results_list[0][0]]
        # adding wind speed direction heatmap if available
        if len(normalised_results_list[0]) > 3:
            results0.append(normalised_results_list[0][3])

        results1 = [normalised_results_list[1][0]]
        #  adding wind speed direction heatmap if available
        if len(normalised_results_list[1]) > 3:
            results1.append(normalised_results_list[1][3])

        return AnalysisCompareResults(
            results0=results0,
            results1=results1,
            chart_results=all_chart_results
        )
