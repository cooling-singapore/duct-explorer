import json
import os
import shutil
from typing import List, Dict, Tuple

import pyproj
from saas.core.logging import Logging
from saas.sdk.base import SDKContext, SDKProductSpecification, SDKCDataObject, LogMessage
from shapely import Polygon

from explorer.dots.duct_nsc_variables import NearSurfaceClimateVariableRaster, NearSurfaceClimateVariableLinechart
from explorer.exceptions import DUCTRuntimeError
from explorer.analysis.base import Analysis, AnalysisContext, AnalysisStatus
from explorer.geodb import GeometryType
from explorer.project import Project
from explorer.renderer.base import hex_color_to_components
from explorer.schemas import AnalysisGroup, Scene, AnalysisResult, ExplorerRuntimeError, AnalysisSpecification, \
    BoundingBox, AnalysisCompareResults

logger = Logging.get('duct.analysis.microscale_urban_climate_scout')


def _result_specification() -> dict:
    alpha = 255
    return {
        'air_temperature': {
            'legend_title': 'Air Temperature (in ˚C)',
            'statistics_table_description': 'Near-surface (2.5m) air temperature (in ˚C)',
            'color_schema': [
                {'value': 20, 'color': hex_color_to_components('#313695', alpha), 'label': '20˚C'},
                {'value': 23, 'color': hex_color_to_components('#ABD9E9', alpha), 'label': ''},
                {'value': 26, 'color': hex_color_to_components('#FFFFBF', alpha), 'label': '26˚C'},
                {'value': 30, 'color': hex_color_to_components('#FDAE61', alpha), 'label': ''},
                {'value': 33, 'color': hex_color_to_components('#D73027', alpha), 'label': '33˚C'},
                {'value': 36, 'color': hex_color_to_components('#6A0018', alpha), 'label': ''},
                {'value': 40, 'color': hex_color_to_components('#311165', alpha), 'label': '40˚C'},
            ],
            'no_data': -999999
        },
        'air_temperature-delta': {
            'legend_title': 'Difference in Air Temperature (in Δ˚C)',
            'statistics_table_description': 'Near-surface (2.5m) air temperature (in ˚C)',
            'color_schema': [
                {'value': -5, 'color': hex_color_to_components('#2c7bb6', alpha), 'label': '-5˚C (B > A)'},
                {'value': 0.0, 'color': hex_color_to_components('#000000', alpha), 'label': '0 (A == B)'},
                {'value': 5, 'color': hex_color_to_components('#d7191c', alpha), 'label': '+5˚C (A > B)'}
            ],
            'no_data': -999999
        },
    }


def _make_result(name: str, label: str, obj_id: str) -> AnalysisResult:
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
                        'enum': ['time'], # , '24_avg', '24_min', '24_max'],
                        'enumNames': ['Time of day'], # , '24 hour average', '24 hour minimum', '24 hour maximum'],
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
                                    'title': 'Time',
                                    'type': 'integer',
                                    'enum': [
                                        1, 3, 6, 9, 12, 15,
                                        18, 21, 24, 27, 30, 33,
                                        36
                                    ],
                                    'enumNames': [
                                        "12:00", "12:30", "13:00", "13:30", "14:00", "14:30",
                                        "15:00", "15:30", "16:00", "16:30", "17:00", "17:30",
                                        "18:00"
                                    ],
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
            # 'datetime_0h': datetime_0h,
            # 'z_idx': 1
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


class MicroscaleUrbanClimateScoutAnalysis(Analysis):
    resolution = [5, 5, 5]
    # grid_dim = [599, 595, 240]
    # grid_dim = [384, 384, 240]
    grid_dim = [192, 192, 240]

    def name(self) -> str:
        return 'microscale-urban-climate-scout'

    def label(self) -> str:
        return 'Scout-based Microscale Urban Climate'

    def type(self) -> str:
        return 'micro'

    def specification(self, project, sdk: SDKContext, aoi_obj_id: str = None,
                      scene_id: str = None) -> AnalysisSpecification:
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
                        "enum": ["600", "3600", "21600"],
                        "enumNames": ["10 minutes", "1 hour", "6 hours"],
                        "default": "600"
                    },
                },
                "required": ["name", "dt_sim"]
            },
            'description': 'This analysis uses a micro-scale urban climate model to estimate the local climatic '
                           'conditions in terms of air temperature over a time period of up to 12 hours.',
            'further_information': 'This analysis is based on the OpenFOAM-based A*STAR SCOUT solver. The SaaS '
                                   'adapters for this model has been developed by '
                                   '<a href="mailto:heiko.aydt@arch.ethz.ch">Heiko Aydt</a> with modelling support '
                                   'from <a href="mailto:jerin.benny@sec.ethz.ch">Jerin Benny</a>. For more '
                                   'information, please contact the respective people.',
            'sample_image': self.name()+'.png',
            'ui_schema': {
                'ui:order': ['name', 'dt_sim']
            },
            'required_bdp': [],
            'required_processors': ['ucm-scout'],
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

    @staticmethod
    def _store_aoi_in_analysis_dir(context: AnalysisContext):
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
    def _prepare_input_data(context: AnalysisContext, scene: Scene, area: Polygon) -> SDKCDataObject:
        # determine the set id
        set_id = f'scene:{scene.id}'

        # get the building geometries for the area of interest
        bld_geos = context.geometries(GeometryType.building, set_id=set_id, area=area)

        # store buildings as GeoJSON file and upload to DOR
        bld_path = os.path.join(context.analysis_path, 'buildings.geojson')
        with open(bld_path, 'w') as f:
            json.dump(bld_geos, f, indent=2)
        bld_obj: SDKCDataObject = context.sdk.upload_content(bld_path, "DUCT.GeoVectorData", 'geojson', False)

        return bld_obj

    @staticmethod
    def _submit_job(context: AnalysisContext, bbox: dict, bld_obj_id: str, scene: Scene, group: AnalysisGroup) -> str:
        # find the processor
        proc = context.sdk.find_processor_by_name('ucm-scout')
        if proc is None:
            raise DUCTRuntimeError(f"Processor 'ucm-scout' not found.")

        # determine dt_sim
        dt_sim: int = int(group.parameters['dt_sim'])

        # submit the job
        inputs = {
            'parameters': {
                "name": context.analysis_id[:8],
                "end_time": dt_sim,
                "area": bbox
            },
            # 'information': {
            #     'project_id': context.project.meta.id,
            #     'analysis_id': context.analysis_id,
            #     'scene': scene.dict(),
            #     'group': group.dict()
            # },
            'building-footprints': context.sdk.find_data_object(bld_obj_id)
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
        self_tracker_name = 'miucs.perform_analysis'
        context.add_update_tracker(self_tracker_name, 10)

        checkpoint, args, status = context.checkpoint()
        if status == AnalysisStatus.RUNNING and checkpoint == 'initialised':
            context.update_progress(self_tracker_name, 15)

            # determine the location and the simulation domain
            location, bbox = self._determine_domain(context)

            # store AOI to disk in the analysis directory
            self._store_aoi_in_analysis_dir(context)

            # prepare the input data
            bld_obj = self._prepare_input_data(context, scene, bbox.as_shapely_polygon())

            checkpoint, args, status = context.update_checkpoint('ready-for-sim', {
                'bounding_box': bbox.dict(),
                'bld_obj_id': bld_obj.meta.obj_id
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'ready-for-sim':
            context.update_progress(self_tracker_name, 30)

            job_id = self._submit_job(context, args['bounding_box'], args['bld_obj_id'], scene, group)

            checkpoint, args, status = context.update_checkpoint('waiting-for-sim', {
                'job_id': job_id
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'waiting-for-sim':
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

            checkpoint, args, status = context.update_checkpoint('simulation-done', {
                'climatic-variables': outputs['climatic-variables'].meta.obj_id,
                'vv-package': outputs['vv-package'].meta.obj_id
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'simulation-done':
            context.update_progress(self_tracker_name, 90)

            # prepare analysis results
            results = [
                _make_result(name, label, args['climatic-variables'])
                for name, label in [
                    ('air_temperature', 'Air Temperature')
                ]
            ]

            context.update_progress(self_tracker_name, 100)
            return results

        if status != AnalysisStatus.CANCELLED:
            raise DUCTRuntimeError(f"Encountered unexpected checkpoint: {checkpoint}")

    def extract_feature(self, content_paths: Dict[str, str], result: AnalysisResult, parameters: dict,
                        project: Project, sdk: SDKContext, export_path: str, json_path: str) -> None:

        supported_variables = ['air_temperature']

        if result.name in supported_variables:
            # add spec to the parameters
            spec = _result_specification()[result.name]
            parameters['key'] = result.name
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

        supported_variables = ['air_temperature']

        # check if the result names are identical
        if result0.name != result1.name:
            raise DUCTRuntimeError(f"Mismatching result names: {result0.name} != {result1.name}")

        # do we have the result name in our variable mapping?
        if result0.name in supported_variables:
            # add spec  to the parameters
            spec = _result_specification()[f"{result0.name}-delta"]

            parameters0['key'] = result0.name
            parameters1['key'] = result1.name
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