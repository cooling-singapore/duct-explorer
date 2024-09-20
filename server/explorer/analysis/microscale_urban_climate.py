import json
import os
import shutil
from typing import List, Dict, Tuple

import pyproj
from saas.core.logging import Logging
from saas.sdk.base import SDKContext, SDKProductSpecification, SDKCDataObject, LogMessage
from shapely import Polygon

from duct.dots.duct_nsc_variables import NearSurfaceClimateVariableRaster, NearSurfaceClimateVariableLinechart, \
    WindVectorField
from duct.dots.duct_urban_geometries import UrbanGeometries
from duct.exceptions import DUCTRuntimeError
from explorer.analysis.base import Analysis, AnalysisContext, AnalysisStatus
from explorer.geodb import GeometryType
from explorer.project import Project
from explorer.renderer.base import hex_color_to_components
from explorer.schemas import AnalysisGroup, Scene, AnalysisResult, ExplorerRuntimeError, AnalysisSpecification, \
    BoundingBox, AnalysisCompareResults

logger = Logging.get('duct.analysis.microscale_urban_climate')

# LULC data is based on https://doi.org/10.3390/data4030116 / https://www.mdpi.com/2306-5729/4/3/116/htm
# CODE  DESCRIPTION
# ----  -----------
# 1     Buildings
# 2     Impervious surfaces
# 3     Non-vegetated pervious surfaces
# 4     Vegetation with limited human management (w Tree Canopy)
# 5     Vegetation with limited human management (w/o Tree Canopy)
# 6     Vegetation with structure dominated by human management (w Tree Canopy)
# 7     Vegetation with structure dominated by human management (w/o Tree Canopy)
# 8     Freshwater swamp forest
# 9     Freshwater marsh
# 10    Mangrove
# 11    Water courses
# 12    Water bodies
# 13    Marine

# UrbanDesignDOT landcover types are the following:
# VALUE          DESCRIPTION
# -----          -----------
# soil:1         coarse
# soil:2         medium
# soil:3         medium-fine
# soil:4         fine
# soil:5         very fine
# soil:6         organic
# vegetation:1   bare soil
# vegetation:2   crops, mixed farming
# vegetation:3   short grass
# vegetation:4   evergreen needleleaf trees
# vegetation:5   deciduous needleleaf trees
# vegetation:6   evergreen broadleaf trees
# vegetation:7   deciduous broadleaf trees
# vegetation:8   tall grass
# vegetation:9   desert
# vegetation:10  tundra
# vegetation:11  irrigated crops
# vegetation:12  semi desert
# vegetation:13  ice caps and glaciers
# vegetation:14  bogs and marshes
# vegetation:15  evergreen shrubs
# vegetation:16  deciduous shrubs
# vegetation:17  mixed forest/woodland
# vegetation:18  interrupted forest
# pavement:1     asphalt/concrete mix
# pavement:2     asphalt (asphalt concrete)
# pavement:3     concrete (Portland concrete)
# pavement:4     sett
# pavement:5     paving stones
# pavement:6     cobblestone
# pavement:7     metal
# pavement:8     wood
# pavement:9     gravel
# pavement:10    fine gravel
# pavement:11    pebblestone
# pavement:12    woodchips
# pavement:13    tartan (sports)
# pavement:14    artifical turf (sports)
# pavement:15    clay (sports)
# water:1        lake
# water:2        river
# water:3        ocean
# water:4        pond
# water:5        fountain

# mapping of duct.urban_design to LULC codes
UDLC_TO_LULC = {
    'soil:1': 3,
    'soil:2': 3,
    'soil:3': 3,
    'soil:4': 3,
    'soil:5': 3,
    'soil:6': 3,
    'vegetation:1': 3,
    'vegetation:2': 7,
    'vegetation:3': 3,
    'vegetation:4': 4,
    'vegetation:5': 4,
    'vegetation:6': 4,
    'vegetation:7': 4,
    'vegetation:8': 5,
    'vegetation:9': 3,
    'vegetation:10': 3,
    'vegetation:11': 7,
    'vegetation:12': 3,
    'vegetation:13': -1,
    'vegetation:14': 9,
    'vegetation:15': 5,
    'vegetation:16': 5,
    'vegetation:17': 4,
    'vegetation:18': 4,
    'pavement:1': 2,
    'pavement:2': 2,
    'pavement:3': 2,
    'pavement:4': 2,
    'pavement:5': 2,
    'pavement:6': 2,
    'pavement:7': 2,
    'pavement:8': 2,
    'pavement:9': 2,
    'pavement:10': 2,
    'pavement:11': 2,
    'pavement:12': 2,
    'pavement:13': 2,
    'pavement:14': 2,
    'pavement:15': 2,
    'water:1': 12,
    'water:2': 11,
    'water:3': 13,
    'water:4': 12,
    'water:5': -1
}

def _result_specification() -> dict:
    alpha = 255
    return {
        'pet': {
            'legend_title': 'Physiologically Equivalent Temperature (in ˚C)',
            'statistics_table_description': 'Outdoor thermal comfort index derived from human energy balance, '
                                            'estimated from the air temperature, wind speed, relative humidity and mean'
                                            ' radiant temperature at 2.5m (in ˚C)',
            'color_schema': [
                {'value': 20, 'color': hex_color_to_components('#313695', alpha), 'label': '20˚C'},
                {'value': 25, 'color': hex_color_to_components('#ABD9E9', alpha), 'label': ''},
                {'value': 30, 'color': hex_color_to_components('#FFFFBF', alpha), 'label': '30˚C'},
                {'value': 35, 'color': hex_color_to_components('#FDAE61', alpha), 'label': ''},
                {'value': 40, 'color': hex_color_to_components('#D73027', alpha), 'label': '40˚C'},
                {'value': 45, 'color': hex_color_to_components('#6A0018', alpha), 'label': ''},
                {'value': 50, 'color': hex_color_to_components('#311165', alpha), 'label': '50˚C'}
            ],
            'no_data': -9999
        },
        'pet-delta': {
            'legend_title': 'Difference in Physiologically Equivalent Temperature (in Δ˚C)',
            'statistics_table_description': 'Outdoor thermal comfort index derived from human energy balance, '
                                            'estimated from the air temperature, wind speed, relative humidity and mean'
                                            ' radiant temperature at 2.5m (in ˚C)',
            'color_schema': [
                {'value': -5, 'color': hex_color_to_components('#2c7bb6', alpha), 'label': 'B > A'},
                {'value': 0.0, 'color': hex_color_to_components('#000000', alpha), 'label': 'A == B'},
                {'value': 5, 'color': hex_color_to_components('#d7191c', alpha), 'label': 'A > B'}
            ],
            'no_data': -9999
        },
        'air_temperature': {
            'legend_title': 'Air Temperature (in ˚C)',
            'statistics_table_description': 'Near-surface (2.5m) air temperature (in ˚C)',
            'color_schema': [
                {'value': 24, 'color': hex_color_to_components('#313695', alpha), 'label': '24˚C'},
                {'value': 26, 'color': hex_color_to_components('#ABD9E9', alpha), 'label': ''},
                {'value': 28, 'color': hex_color_to_components('#FFFFBF', alpha), 'label': '28˚C'},
                {'value': 30, 'color': hex_color_to_components('#FDAE61', alpha), 'label': ''},
                {'value': 32, 'color': hex_color_to_components('#D73027', alpha), 'label': '32˚C'},
                {'value': 34, 'color': hex_color_to_components('#6A0018', alpha), 'label': ''},
                {'value': 36, 'color': hex_color_to_components('#311165', alpha), 'label': '36˚C'},
            ],
            'no_data': -9999
        },
        'air_temperature-delta': {
            'legend_title': 'Difference in Air Temperature (in Δ˚C)',
            'statistics_table_description': 'Near-surface (2.5m) air temperature (in ˚C)',
            'color_schema': [
                {'value': -5, 'color': hex_color_to_components('#2c7bb6', alpha), 'label': 'B > A'},
                {'value': 0.0, 'color': hex_color_to_components('#000000', alpha), 'label': 'A == B'},
                {'value': 5, 'color': hex_color_to_components('#d7191c', alpha), 'label': 'A > B'}
            ],
            'no_data': -9999
        },
        'surface_temperature': {
            'legend_title': 'Surface Temperature (in ˚C)',
            'statistics_table_description': 'Temperature at the top surface, such as ground and roof (in ˚C)',
            'color_schema': [
                {'value': 20, 'color': hex_color_to_components('#313695', alpha), 'label': '20˚C'},
                {'value': 25, 'color': hex_color_to_components('#ABD9E9', alpha), 'label': ''},
                {'value': 30, 'color': hex_color_to_components('#FFFFBF', alpha), 'label': '30˚C'},
                {'value': 35, 'color': hex_color_to_components('#FDAE61', alpha), 'label': ''},
                {'value': 40, 'color': hex_color_to_components('#D73027', alpha), 'label': '40˚C'},
                {'value': 45, 'color': hex_color_to_components('#6A0018', alpha), 'label': ''},
                {'value': 50, 'color': hex_color_to_components('#311165', alpha), 'label': '50˚C'}
            ],
            'no_data': -9999
        },
        'surface_temperature-delta': {
            'legend_title': 'Difference in Surface Temperature (in Δ˚C)',
            'statistics_table_description': 'Temperature at the top surface, such as ground and roof (in ˚C)',
            'color_schema': [
                {'value': -10, 'color': hex_color_to_components('#2c7bb6', alpha), 'label': 'B > A'},
                {'value': 0.0, 'color': hex_color_to_components('#000000', alpha), 'label': 'A == B'},
                {'value': 10, 'color': hex_color_to_components('#d7191c', alpha), 'label': 'A > B'}
            ],
            'no_data': -9999
        },
        'relative_humidity': {
            'legend_title': 'Relative Humidity (in %)',
            'statistics_table_description': 'Near-surface (2.5m) relative humidity (in %)',
            'color_schema': [
                {'value': 0, 'color': hex_color_to_components('#E5F5F9', alpha), 'label': '0'},
                {'value': 20, 'color': hex_color_to_components('#99D8C9', alpha), 'label': '20'},
                {'value': 40, 'color': hex_color_to_components('#41AE76', alpha), 'label': '40'},
                {'value': 60, 'color': hex_color_to_components('#006D2C', alpha), 'label': '60'},
                {'value': 80, 'color': hex_color_to_components('#033D18', alpha), 'label': '80'},
                {'value': 100, 'color': hex_color_to_components('#02250e', alpha), 'label': '100'}
            ],
            'no_data': -9999
        },
        'relative_humidity-delta': {
            'legend_title': 'Difference in Relative Humidity (in Δ%)',
            'statistics_table_description': 'Near-surface (2.5m) relative humidity (in %)',
            'color_schema': [
                {'value': -20, 'color': hex_color_to_components('#2c7bb6', alpha), 'label': 'B > A'},
                {'value': 0.0, 'color': hex_color_to_components('#ffffff', 0), 'label': 'A == B'},
                {'value': 20, 'color': hex_color_to_components('#d7191c', alpha), 'label': 'A > B'}
            ],
            'no_data': -9999
        },
        'wind_speed': {
            'legend_title': 'Wind Speed (in m/s)',
            'statistics_table_description': 'Near-surface (2.5m) wind speed (in m/s)',
            'color_schema': [
                {'value': 0, 'color': hex_color_to_components('#4196FF', alpha), 'label': '0.0'},
                {'value': 0.2, 'color': hex_color_to_components('#18DEC0', alpha), 'label': '0.2'},
                {'value': 0.4, 'color': hex_color_to_components('#75FE5C', alpha), 'label': '0.4'},
                {'value': 0.6, 'color': hex_color_to_components('#D4E735', alpha), 'label': '0.6'},
                {'value': 0.8, 'color': hex_color_to_components('#FEA130', alpha), 'label': '0.8'},
                {'value': 1, 'color': hex_color_to_components('#E5470B', alpha), 'label': '1.0'},
                {'value': 2, 'color': hex_color_to_components('#9B0F01', alpha), 'label': '2.0'}
            ],
            'no_data': -9999
        },
        'wind_speed-delta': {
            'legend_title': 'Difference in Wind Speed (in Δm/s)',
            'statistics_table_description': 'Near-surface (2.5m) wind speed (in m/s)',
            'color_schema': [
                {'value': -5, 'color': hex_color_to_components('#2c7bb6', alpha), 'label': 'B > A'},
                {'value': 0.0, 'color': hex_color_to_components('#ffffff', 0), 'label': 'A == B'},
                {'value': 5, 'color': hex_color_to_components('#d7191c', alpha), 'label': 'A > B'}
            ],
            'no_data': -9999
        },
        'wind_direction': {
            'legend_title': 'Predominant Wind Direction (˚)',
            'statistics_table_description': 'Near-surface (2.5m) wind direction (in ˚)',
            'color_schema': [
                {'value': 0, 'color': hex_color_to_components('#d92b30', alpha), 'label': '0'},
                {'value': 90, 'color': hex_color_to_components('#C27c31', alpha), 'label': '90'},
                {'value': 180, 'color': hex_color_to_components('#ffdf3a', alpha), 'label': '180'},
                {'value': 270, 'color': hex_color_to_components('#3cccb4', alpha), 'label': '270'},
                {'value': 360, 'color': hex_color_to_components('#d92b30', alpha), 'label': '360'}
            ],
            'no_data': -9999
        },
        'wind_direction-delta': {
            'legend_title': 'Difference in Predominant Wind Direction (Δ˚)',
            'statistics_table_description': 'Near-surface (2.5m) wind direction (in ˚)',
            'color_schema': [
                {'value': -180, 'color': hex_color_to_components('#2c7bb6', alpha), 'label': 'B > A'},
                {'value': 0.0, 'color': hex_color_to_components('#ffffff', 0), 'label': 'A == B'},
                {'value': 180, 'color': hex_color_to_components('#d7191c', alpha), 'label': 'A > B'}
            ],
            'no_data': -9999
        },
        'wind_speed_and_direction': {
            'legend_title': 'Wind direction',
            'statistics_table_description': 'Near-surface (2.5m) wind speed and direction',
            'color_schema': [
                {'value': 0, 'color': [65, 150, 255, 1], 'label': '0.0', 'size': 50},
                {'value': 0.2, 'color': [24, 222, 192, 1], 'label': '0.2', 'size': 55},
                {'value': 0.4, 'color': [117, 254, 92, 1], 'label': '0.4', 'size': 60},
                {'value': 0.6, 'color': [212, 231, 53, 1], 'label': '0.6', 'size': 65},
                {'value': 0.8, 'color': [254, 161, 48, 1], 'label': '0.8', 'size': 70},
                {'value': 1, 'color': [299, 71, 11, 1], 'label': '1.0', 'size': 80},
                {'value': 2, 'color': [155, 15, 1, 1], 'label': '2.0', 'size': 90}
            ],
            'no_data': -9999
        },
        'wind_speed_and_direction-delta': {
            'legend_title': 'Difference in Wind Speed (in Δm/s)',
            'statistics_table_description': 'Near-surface (2.5m) wind speed (in m/s)',
            'color_schema': [
                {'value': -5, 'color': hex_color_to_components('#2c7bb6', alpha), 'label': 'B > A'},
                {'value': 0.0, 'color': hex_color_to_components('#ffffff', 0), 'label': 'A == B'},
                {'value': 5, 'color': hex_color_to_components('#d7191c', alpha), 'label': 'A > B'}
            ],
            'no_data': -9999
        }
    }


def _make_result(name: str, label: str, obj_id: str, datetime_0h: str) -> AnalysisResult:
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
                    },
                    'display_aoi_mask': {
                        'title': 'Display only area of interest',
                        'type': 'boolean',
                        'default': False
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
                                    'type': 'integer',
                                    'title': 'Hour of Day (0h - 23h)',
                                    'minimum': 0,
                                    'multipleOf': 1,
                                    'maximum': 23,
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
            'datetime_0h': datetime_0h,
            'z_idx': 1
        }
    })


def coord_32648_to_4326(p_xy: (float, float)) -> (float, float):
    in_proj = pyproj.Proj('epsg:32648')
    out_proj = pyproj.Proj('epsg:4326')
    temp = pyproj.transform(in_proj, out_proj, x=p_xy[0], y=p_xy[1])
    return temp[1], temp[0]


def coord_4326_to_32648(p_xy: (float, float)) -> (float, float):
    in_proj = pyproj.Proj('epsg:4326')
    out_proj = pyproj.Proj('epsg:32648')
    return pyproj.transform(in_proj, out_proj, x=p_xy[1], y=p_xy[0])


def convert_area_to_bounding_box(area: Polygon, resolution: (float, float), dimension: (int, int)) \
        -> (Tuple[float, float], BoundingBox):

    # calculate the center lon/lat based on the bounding box of the area of interest
    # -> to be used as center point for the simulation domain
    lon, lat = area.exterior.coords.xy
    lon = (min(lon) + max(lon)) / 2
    lat = (min(lat) + max(lat)) / 2

    # convert lon/lat from degrees to meters
    lon_m, lat_m, = coord_4326_to_32648((lon, lat))

    # calculate half-dimensions in meters
    rx = resolution[0]
    ry = resolution[1]
    nx = dimension[1]
    ny = dimension[0]
    hx = (nx * rx) / 2
    hy = (ny * ry) / 2

    # determine bounding box for simulation domain (in degrees)
    west, north = coord_32648_to_4326((lon_m - hx, lat_m + hy))
    east, south = coord_32648_to_4326((lon_m + hx, lat_m - hy))

    return (lon, lat), BoundingBox(north=north, east=east, south=south, west=west)


class MicroscaleUrbanClimateAnalysis(Analysis):
    resolution = [5, 5, 5]
    # grid_dim = [599, 595, 240]
    grid_dim = [384, 384, 240]

    def name(self) -> str:
        return 'microscale-urban-climate'

    def label(self) -> str:
        return 'Microscale Urban Climate'

    def type(self) -> str:
        return 'micro'

    def specification(self, project, sdk: SDKContext, aoi_obj_id: str = None,
                      scene_id: str = None) -> AnalysisSpecification:
        # find all building AH profiles (if any)
        availableNames = ['None']
        availableKeys = ['none']
        for obj in sdk.find_data_objects(data_type='duct.building-ah-profile'):
            # do we have all required tags?
            if all(key in obj.meta.tags for key in ['aoi_obj_id', 'group_name', 'scene_id', 'scene_name',
                                                    'profile_name', 'analysis_id']):
               # does AOI and scene ids match?
                if obj.meta.tags['aoi_obj_id'] == aoi_obj_id and obj.meta.tags['scene_id'] == scene_id:
                    group_name = obj.meta.tags['group_name']
                    scene_name = obj.meta.tags['scene_name']
                    profile_name = obj.meta.tags['profile_name']
                    analysis_id = obj.meta.tags['analysis_id'][:5]
                    availableNames.append(f"{analysis_id} {group_name}.{scene_name} ({profile_name})")
                    availableKeys.append(obj.meta.obj_id)

        return AnalysisSpecification.parse_obj({
            'name': self.name(),
            'label': self.label(),
            'type': self.type(),
            'area_selection': True,
            'parameters_schema': {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "title": "Configuration Name"},
                    "dt_sim": {
                        "type": "string",
                        "title": "Runtime",
                        "enum": ["2", "6", "24"],
                        "enumNames": ["2h (test)", "6h (preview)", "24h (full run)"],
                        "default": "24"
                    },
                    "bld_ah_profile": {
                        "type": "string",
                        "title": "Building AH Profile (if any)",
                        "enum": availableKeys,
                        "enumNames": availableNames,
                        "default": 'none'
                    },
                    "dd_profile": {
                        "type": "string",
                        "title": "Weather Condition",
                        "enum": ['NEmonsoon', 'SWmonsoon',
                                 'highmrt', 'highwbgt',
                                 'hightemp', 'mediantemp',
                                 'warmnight', 'default'],
                        "enumNames": ['North-East Monsoon', 'South-West Monsoon',
                                      'High MRT Day', 'High WBGT Day',
                                      'High Temperature Day', 'Median Temperature Day',
                                      'Warm Night Day', 'Default'],
                        "default": 'default'
                    }

                },
                "required": ["name", "dt_sim", "bld_ah_profile", "dd_profile"]
            },
            'description': 'This analysis uses a micro-scale urban climate model to estimate the outdoor thermal '
                           'comfort and local climatic conditions in terms of air temperature, relative humidity, and '
                           'wind flow over a 24 hour period. The model considers some the key urban elements, such as '
                           'buildings, vegetation, water surface as well as the anthropogenic heat emitted from '
                           'buildings. This is recommended for urban planners to gain in-depth understanding of '
                           'urban climate performance on the neighbourhood level.',
            'further_information': 'This analysis is based on a workflow using the '
                                   '<a href="https://palm.muk.uni-hannover.de/trac/wiki/palm4u">PALM-4U model</a>. The '
                                   'framework as well as the validation work for PALM-4U model has been carried out by '
                                   'Adelia Sukma, Ido Nevat and Vivek Singh, supervised by Juan Acero and '
                                   'Tobias Gronemeier. The static driver automation script for input data preparation '
                                   'has been developed by Luis Santos, and the post-processing script has been '
                                   'developed by Luis Santos and Adelia Sukma. The SaaS adapters for this model has '
                                   'been developed by Heiko Aydt. For more information, please contact the respective '
                                   'authors.',
            'sample_image': self.name()+'.png',
            'ui_schema': {
                'ui:order': ['name', 'dt_sim', 'bld_ah_profile', 'dd_profile']
            },
            'required_bdp': [],
            'required_processors': ['ucm-palm-prep', 'ucm-palm-sim'],
            'result_specifications': _result_specification()
        })

    def _determine_domain(self, context: AnalysisContext) -> Tuple[Tuple[float, float], BoundingBox]:
        # get the area of interest
        area = context.area_of_interest()
        if area is None:
            raise DUCTRuntimeError(f"No area of interest")

        # determine the bounding box
        shape = (self.grid_dim[1], self.grid_dim[0])
        res = (self.resolution[1], self.resolution[0])
        location, bbox = convert_area_to_bounding_box(area, res, shape)
        context.logger.info(f"area selection: {area}")
        context.logger.info(f"use location: {location}")
        context.logger.info(f"use bounding box: {bbox.dict()}")

        return location, bbox

    def _store_aoi_in_analysis_dir(self, context: AnalysisContext):
        aoi = context.area_of_interest()
        content_path = os.path.join(context.analysis_path, 'aoi.geojson')
        with open(content_path, 'w') as outfile:
            json.dump({
                'type': 'FeatureCollection',
                'features': [{
                    'type': 'Feature',
                    'properties': {
                        'id': 1
                    },
                    'geometry': aoi.__geo_interface__
                }]
            }, outfile, indent=4)

    @staticmethod
    def _prepare_input_data(context: AnalysisContext, scene: Scene, area: Polygon, ah_profile_obj_id: str) \
            -> Tuple[SDKCDataObject, SDKCDataObject, SDKCDataObject]:
        # determine the set id
        set_id = f'scene:{scene.id}'

        ah_profiles: Dict[str, Dict[str, float]] = {}
        if ah_profile_obj_id != 'none':
            # find and download the AH data object
            sh_obj = context.sdk.find_data_object(ah_profile_obj_id)
            if sh_obj is None:
                raise DUCTRuntimeError(f"Building AH profile data object {ah_profile_obj_id} not found.")
            sh_csv_path = os.path.join(context.analysis_path, f'{sh_obj.meta.obj_id}_bld_ah_profile.csv')
            sh_obj.download(sh_csv_path)

            # read SH profile
            with open(sh_csv_path, 'r') as f:
                header = f.readline().strip().split(',')
                header = [field.strip() for field in header]
                while (line := f.readline().strip()) not in [None, '']:
                    line = line.split(',')
                    line = [value.strip() for value in line]

                    profile: Dict[str, float] = {}
                    for h in range(24):
                        key = header[1+h]
                        value = float(line[1+h])
                        profile[key] = value

                    ah_profiles[line[0]] = profile

        # update the building geometries
        bld_geos = context.geometries(GeometryType.building, set_id=set_id, area=area)
        for bld in bld_geos['features']:
            bld_properties = bld['properties']

            bld_id = str(bld_properties['id'])
            if bld_id in ah_profiles:
                profile = ah_profiles[bld_id]
                for h in range(24):
                    key = f'AH_{h}:KW'
                    value = profile[key]
                    bld_properties[f'AH_{h}:KW'] = value
            else:
                logger.warning(f"building {bld_id} does not have a AH profile -> assuming zero AH emissions.")
                for h in range(24):
                    bld_properties[f'AH_{h}:KW'] = 0

        # store the landcover as GeoTIFF file and upload to DOR
        lc_geos = context.geometries(GeometryType.landcover, set_id=set_id, area=area)
        lc_path = os.path.join(context.analysis_path, 'landcover.geojson')
        with open(lc_path, 'w') as f:
            json.dump(lc_geos, f, indent=2)
        lc_obj: SDKCDataObject = context.sdk.upload_content(lc_path, UrbanGeometries.DATA_TYPE, 'geojson', False)

        # store buildings as GeoJSON file and upload to DOR
        bld_path = os.path.join(context.analysis_path, 'buildings.geojson')
        with open(bld_path, 'w') as f:
            json.dump(bld_geos, f, indent=2)
        bld_obj: SDKCDataObject = context.sdk.upload_content(bld_path, UrbanGeometries.DATA_TYPE, 'geojson', False)

        # store vegetation as GeoJSON file and upload to DOR
        veg_geos = context.geometries(GeometryType.vegetation, set_id=set_id, area=area)
        veg_path = os.path.join(context.analysis_path, 'vegetation.geojson')
        with open(veg_path, 'w') as f:
            json.dump(veg_geos, f, indent=2)
        veg_obj: SDKCDataObject = context.sdk.upload_content(veg_path, UrbanGeometries.DATA_TYPE, 'geojson', False)

        return lc_obj, bld_obj, veg_obj

    def _submit_prep_job(self, context: AnalysisContext, bbox: dict, lc_obj_id: str, bld_obj_id: str, veg_obj_id: str,
                         scene: Scene, group: AnalysisGroup) -> str:
        # find the processor
        proc = context.sdk.find_processor_by_name('ucm-palm-prep')
        if proc is None:
            raise DUCTRuntimeError(f"Processor 'ucm-palm-prep' not found.")

        # determine dt_sim
        dt_sim: float = int(group.parameters['dt_sim']) * 3600.0

        # determine dynamic driver profile
        dd_profile: str = group.parameters['dd_profile']

        # submit the job
        inputs = {
            'parameters': {
                "name": context.analysis_id[:8],
                "bbox": bbox,
                "resolution": self.resolution,
                "grid_dim": self.grid_dim,
                "dt_sim": dt_sim,
                "dd_profile": dd_profile,
                "ah_profile": group.parameters['bld_ah_profile'] != 'none'
            },
            'information': {
                'project_id': context.project.meta.id,
                'analysis_id': context.analysis_id,
                'scene': scene.dict(),
                'group': group.dict()
            },
            'landcover': context.sdk.find_data_object(lc_obj_id),
            'buildings': context.sdk.find_data_object(bld_obj_id),
            'vegetation': context.sdk.find_data_object(veg_obj_id)
        }

        outputs = {name: SDKProductSpecification(
            restricted_access=False,
            content_encrypted=False,
            target_node=context.sdk.dor()
            # owner=context.sdk.authority.identity
        ) for name in ['palm-run-package', 'vv-package']}

        job = proc.submit(inputs, outputs, name=f"{context.analysis_id}.0",
                          description=f"analysis:{context.analysis_id}")

        return job.content.id

    @staticmethod
    def _submit_sim_job(context: AnalysisContext, palm_run_package_obj_id: str,
                        scene: Scene, group: AnalysisGroup) -> str:
        # find the processor
        proc = context.sdk.find_processor_by_name('ucm-palm-sim')
        if proc is None:
            raise DUCTRuntimeError(f"Processor 'ucm-palm-sim' not found.")

        # submit the job
        inputs = {
            'parameters': {
                "name": context.analysis_id[:8],
                "datetime_offset": "2020-07-01 22:00:00",
                "resolution": [5, 5, 5]
            },
            'information': {
                'project_id': context.project.meta.id,
                'analysis_id': context.analysis_id,
                'scene': scene.dict(),
                'group': group.dict()
            },
            'palm-run-package': context.sdk.find_data_object(palm_run_package_obj_id)
        }

        outputs = {name: SDKProductSpecification(
            restricted_access=False,
            content_encrypted=False,
            target_node=context.sdk.dor()
            # owner=context.sdk.authority.identity
        ) for name in ['climatic-variables', 'vv-package']}

        job = proc.submit(inputs, outputs, name=f"{context.analysis_id}.0",
                          description=f"analysis:{context.analysis_id}")

        return job.content.id

    def perform_analysis(self, group: AnalysisGroup, scene: Scene, context: AnalysisContext) -> List[AnalysisResult]:
        # add a progress tracker for this function
        self_tracker_name = 'miuc.perform_analysis'
        context.add_update_tracker(self_tracker_name, 10)

        # the PALM4U adapter currently uses hardcoded '2020-07-01 22:00:00 +08' as starting time.
        # add 2h for warmup (i.e., data that is thrown away), gets us to 2020-07-02 00:00:00 +08'.
        # not sure if it makes any difference though...
        datetime_0h = "20200702000000"

        checkpoint, args, status = context.checkpoint()
        if status == AnalysisStatus.RUNNING and checkpoint == 'initialised':
            context.update_progress(self_tracker_name, 15)

            # determine the location and the simulation domain
            location, bbox = self._determine_domain(context)

            # store AOI to disk in the analysis directory
            self._store_aoi_in_analysis_dir(context)

            # prepare the input data
            lc_obj, bld_obj, veg_obj = self._prepare_input_data(context, scene, bbox.as_shapely_polygon(),
                                                                group.parameters['bld_ah_profile'])

            checkpoint, args, status = context.update_checkpoint('ready-for-preparation', {
                'location': location,
                'bounding_box': bbox.dict(),
                'lc_obj_id': lc_obj.meta.obj_id,
                'bld_obj_id': bld_obj.meta.obj_id,
                'veg_obj_id': veg_obj.meta.obj_id
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'ready-for-preparation':
            context.update_progress(self_tracker_name, 30)

            job_id = self._submit_prep_job(context, args['bounding_box'], args['lc_obj_id'], args['bld_obj_id'],
                                           args['veg_obj_id'], scene, group)

            checkpoint, args, status = context.update_checkpoint('waiting-for-preparation', {
                'job_id': job_id,
                'bounding_box': args['bounding_box']
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
                'palm-run-package': outputs['palm-run-package'].meta.obj_id
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'ready-for-simulation':
            context.update_progress(self_tracker_name, 60)

            job_id = self._submit_sim_job(context, args['palm-run-package'], scene, group)

            checkpoint, args, status = context.update_checkpoint('waiting-for-simulation', {
                'job_id': job_id
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'waiting-for-simulation':
            context.update_progress(self_tracker_name, 75)
            job_id = args['job_id']

            context.add_update_tracker(f'job:{job_id}', 400)

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
                'climatic-variables': outputs['climatic-variables'].meta.obj_id,
                'vv-package': outputs['vv-package'].meta.obj_id
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'simulation-done':
            context.update_progress(self_tracker_name, 90)

            # prepare analysis results
            results = [
                _make_result(name, label, args['climatic-variables'], datetime_0h)
                for name, label in [
                    ('air_temperature', 'Air Temperature'),
                    ('relative_humidity', 'Relative Humidity'),
                    ('surface_temperature', 'Surface Temperature'),
                    ('pet', 'Physiological Equivalent Temperature (PET)'),
                    ('wind_speed', 'Wind Speed'),
                    ('wind_direction', 'Wind Direction'),
                    ('wind_speed_and_direction', 'Wind Speed and Direction')
                ]
            ]

            context.update_progress(self_tracker_name, 100)
            return results

        if status != AnalysisStatus.CANCELLED:
            raise DUCTRuntimeError(f"Encountered unexpected checkpoint: {checkpoint}")

    def extract_feature(self, content_paths: Dict[str, str], result: AnalysisResult, parameters: dict,
                        project: Project, sdk: SDKContext, export_path: str, json_path: str) -> None:

        supported_variables = ['wind_speed', 'wind_direction', 'relative_humidity', 'air_temperature',
                               'surface_temperature', 'pet']

        if result.name in supported_variables:
            # add spec to the parameters
            spec = _result_specification()[result.name]
            parameters['key'] = result.name
            parameters['datetime_0h'] = result.extras['datetime_0h']
            parameters['z_idx'] = result.extras['z_idx']
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

        elif result.name == 'wind_speed_and_direction':
            # add spec to the parameters
            spec = _result_specification()[result.name]
            parameters['key'] = ['wind_speed', 'wind_direction']
            parameters['datetime_0h'] = result.extras['datetime_0h']
            parameters['no_data'] = spec['no_data']
            parameters['z_idx'] = result.extras['z_idx']
            parameters['legend_title'] = spec['legend_title']
            parameters['color_schema'] = spec['color_schema']
            parameters['statistics_table_description'] = spec['statistics_table_description']

            with open(json_path, 'w') as f:
                vector_field_results, overall_statistic_table_result, heatmap_result = WindVectorField().extract_feature(content_paths['#'],
                                                                                                   parameters)
                # the wind direction is not considered for chart generation.Charts will be generated only for wind speed
                parameters['key'] = 'wind_speed'
                linechart_result = NearSurfaceClimateVariableLinechart().extract_feature(content_paths['#'], parameters)
                assets = [
                    vector_field_results,
                    linechart_result,
                    overall_statistic_table_result,
                    heatmap_result
                ]
                f.write(json.dumps(assets))

            # both wind speed and direction results will be exported
            parameters['key'] = ['wind_speed', 'wind_direction']
            WindVectorField().export_feature(content_paths['#'], parameters, export_path, result.export_format)

        elif result.name == 'vv-package':
            with open(json_path, 'w') as f:
                f.write(json.dumps({}))
            shutil.move(content_paths['#'], export_path)

        else:
            raise ExplorerRuntimeError(f"Encountered unexpected/unsupported result '{result.name}'", details={
                'result': result.dict(),
                'parameters': parameters
            })

    def extract_delta_feature(self, content_paths0: Dict[str, str], result0: AnalysisResult, parameters0: dict,
                              content_paths1: Dict[str, str], result1: AnalysisResult, parameters1: dict,
                              project: Project, sdk: SDKContext, export_path: str, json_path: str) -> None:

        supported_variables = ['wind_speed', 'wind_direction', 'relative_humidity', 'air_temperature',
                               'surface_temperature', 'pet']

        # check if the result names are identical
        if result0.name != result1.name:
            raise DUCTRuntimeError(f"Mismatching result names: {result0.name} != {result1.name}")

        # do we have the result name in our variable mapping?
        if result0.name in supported_variables:
            # add spec  to the parameters
            spec = _result_specification()[f"{result0.name}-delta"]

            parameters0['key'] = result0.name
            parameters0['datetime_0h'] = result0.extras['datetime_0h']
            parameters0['z_idx'] = result0.extras['z_idx']

            parameters1['key'] = result1.name
            parameters1['datetime_0h'] = result1.extras['datetime_0h']
            parameters1['z_idx'] = result1.extras['z_idx']

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

        elif result0.name == 'wind_speed_and_direction':
            # add spec  to the parameters
            spec = _result_specification()[f"{result0.name}-delta"]

            # the wind direction is not considered for delta. Delta will be generated only for wind speed
            parameters0['key'] = 'wind_speed'
            parameters0['datetime_0h'] = result0.extras['datetime_0h']
            parameters0['z_idx'] = result0.extras['z_idx']

            parameters1['key'] = 'wind_speed'
            parameters1['datetime_0h'] = result1.extras['datetime_0h']
            parameters1['z_idx'] = result1.extras['z_idx']

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
