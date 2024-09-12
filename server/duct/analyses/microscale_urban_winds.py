import json
import os
from typing import List, Dict

from saas.sdk.base import SDKContext, SDKProductSpecification, LogMessage
from shapely.geometry import Polygon

from duct.dots import duct
from duct.exceptions import DUCTRuntimeError
from explorer.analysis.base import Analysis, AnalysisContext, AnalysisStatus
from explorer.geodb import GeometryType
from explorer.project import Project
from explorer.renderer.base import hex_color_to_components
from explorer.schemas import AnalysisGroup, Scene, AnalysisResult, ExplorerRuntimeError, AnalysisSpecification


class MicroscaleUrbanWindsAnalysis(Analysis):
    def name(self) -> str:
        return 'microscale-urban-winds'

    def label(self) -> str:
        return 'Microscale Urban Winds'

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
                'type': 'object',
                'properties': {
                    'name': {'type': 'string', 'title': 'Configuration Name'},
                    'wind_direction': {
                        "type": "number",
                        "title": "Wind Direction (in degrees)",
                        "default": 0.0
                    },
                    'wind_speed': {
                        "type": "number",
                        "title": "Wind Speed (in m/s)",
                        "default": 1.0
                    }
                },
                'required': ['name', 'wind_direction', 'wind_speed']
            },
            'description': 'This feature provides an analysis of urban winds on district (micro) scale.',
            'further_information': 'This analysis is based on the IEMSim software, developed by <a '
                                   'href="mailto:loujing@ihpc.a-star.edu.sg">A*STAR</a>. For more information, '
                                   'please contact the authors.',
            'sample_image': self.name()+'.png',
            'ui_schema': {},
            'required_processors': ['ucm-iem-prep', 'ucm-iem-sim'],
            'required_bdp': [],
            'result_specifications': {
                'wind-speed': {
                    'legend_title': 'Wind Speed (in m/s)',
                    'color_schema': [
                        {'value': 0.0, 'color': hex_color_to_components('#000000', 127), 'label': '0.0'},
                        {'value': 0.5, 'color': hex_color_to_components('#d7191c', 127), 'label': '0.5'},
                        {'value': 1.0, 'color': hex_color_to_components('#fdae61', 127), 'label': '1.0'},
                        {'value': 1.5, 'color': hex_color_to_components('#ffffbf', 127), 'label': '1.5'},
                        {'value': 2.0, 'color': hex_color_to_components('#abd9e9', 127), 'label': '2.0'},
                        {'value': 2.5, 'color': hex_color_to_components('#2c7bb6', 127), 'label': '2.5'}
                    ],
                    'no_data': -1
                },
                'wind-speed-delta': {
                    'legend_title': 'Difference in Wind Speed (in Δm/s)',
                    'color_schema': [
                        {'value': -2.5, 'color': hex_color_to_components('#2c7bb6', 127), 'label': 'B > A'},
                        {'value': 0.0, 'color': hex_color_to_components('#000000', 255), 'label': 'A == B'},
                        {'value': 2.5, 'color': hex_color_to_components('#d7191c', 127), 'label': 'A > B'}
                    ],
                    'no_data': 999
                },
                'wind-direction': {
                    'legend_title': 'Wind Direction (in ˚)',
                    'color_schema': [
                        {'value': 0, 'color': hex_color_to_components('#ff0000', 127), 'label': '0'},
                        {'value': 90, 'color': hex_color_to_components('#00ff00', 127), 'label': '90'},
                        {'value': 180, 'color': hex_color_to_components('#00ff00', 127), 'label': '180'},
                        {'value': 270, 'color': hex_color_to_components('#0000ff', 127), 'label': '270'},
                        {'value': 360, 'color': hex_color_to_components('#ff0000', 127), 'label': '360'}
                    ],
                    'no_data': 999
                },
                'wind-direction-delta': {
                    'legend_title': 'Difference in Wind Direction (in Δ˚)',
                    'color_schema': [
                        {'value': -180, 'color': hex_color_to_components('#2c7bb6', 127), 'label': 'B > A'},
                        {'value': 0.0, 'color': hex_color_to_components('#000000', 255), 'label': 'A == B'},
                        {'value': 180, 'color': hex_color_to_components('#d7191c', 127), 'label': 'A > B'}
                    ],
                    'no_data': 999
                }
            }
        })

    def _submit_prep_job(self, context: AnalysisContext, group: AnalysisGroup, area: dict, bf_obj_id: str) -> str:
        # find the processor
        proc = context.sdk.find_processor_by_name('ucm-iem-prep')
        if proc is None:
            raise DUCTRuntimeError(f"Processor 'ucm-iem-prep' not found.")

        # submit the job
        inputs = {
            'parameters': {
                'settings': {
                    "wind_direction": group.parameters["wind_direction"],
                    "wind_speed": group.parameters["wind_speed"]
                },
                'scaling': {
                    "lon": 111000,
                    "lat": 111000,
                    "height": 1
                },
                'area': area
            },
            'building-footprints': context.sdk.find_data_object(bf_obj_id)
        }

        outputs = {name: SDKProductSpecification(
            restricted_access=False,
            content_encrypted=False,
            target_node=context.sdk.dor()
            # owner=context.sdk.authority.identity
        ) for name in ['iem-run-package']}

        job = proc.submit(inputs, outputs, name=f"{context.analysis_id}.0",
                          description=f"job part of analysis {context.analysis_id}")

        return job.content.id

    def _submit_sim_job(self, context: AnalysisContext, iem_run_pkg_obj_id: str) -> str:
        # find the processor
        proc = context.sdk.find_processor_by_name('ucm-iem-sim')
        if proc is None:
            raise DUCTRuntimeError(f"Processor 'ucm-iem-sim' not found.")

        # submit the job
        inputs = {
            'parameters': {
                'pbs_project_id': '21120261',
                'pbs_queue': 'normal',
                'pbs_nnodes': 1,
                'pbs_ncpus': 24,
                'pbs_mpiprocs': 24,
                'pbs_mem': '96GB',
                'walltime': '06:00:00'
            },
            'iem-run-package': context.sdk.find_data_object(iem_run_pkg_obj_id)
        }

        outputs = {name: SDKProductSpecification(
            restricted_access=False,
            content_encrypted=False,
            target_node=context.sdk.dor()
            # owner=context.sdk.authority.identity
        ) for name in ['air-temperature', 'wind-speed', 'wind-direction']}

        job = proc.submit(inputs, outputs, name=f"{context.analysis_id}.0",
                          description=f"job part of analysis {context.analysis_id}")

        return job.content.id

    def perform_analysis(self, group: AnalysisGroup, scene: Scene, context: AnalysisContext) -> List[AnalysisResult]:
        # add a progress tracker for this function
        self_tracker_name = 'muw.perform_analysis'
        context.add_update_tracker(self_tracker_name, 10)

        checkpoint, args, status = context.checkpoint()
        if status == AnalysisStatus.RUNNING and checkpoint == 'initialised':
            context.update_progress(self_tracker_name, 15)

            # convert free area
            # example: free:5:103.82992083051145:1.2986383380117843:103.83631090544554:1.2986383380117843:103.836310905...
            temp = group.parameters["bounding_box"]
            temp = temp.split(':')
            lons = []
            lats = []
            if temp[0] == 'free':
                free_area = []
                for i in range(int(temp[1])):
                    lon = float(temp[i * 2 + 2])
                    lat = float(temp[i * 2 + 3])
                    free_area.append((lon, lat))
                    lons.append(lon)
                    lats.append(lat)
            else:
                raise ExplorerRuntimeError(f"Encountered unexpected bounding box format: {temp}")

            # store building footprints for area of interest to DOR
            bf_content = context.geometries(GeometryType.building, scene.id, area=Polygon(free_area))
            bf_path = os.path.join(context.analysis_path, 'selected_building_footprints.geojson')
            with open(bf_path, 'w') as f:
                f.write(json.dumps(bf_content))
            bf_obj = context.sdk.upload_content(bf_path, 'DUCT.GeoVectorData', 'geojson', False)
            os.remove(bf_path)

            checkpoint, args, status = context.update_checkpoint('ready-for-preparation', {
                'area': {
                    'west': min(lons),
                    'east': max(lons),
                    'south': min(lats),
                    'north': max(lats)
                },
                'bf_obj_id': bf_obj.meta.obj_id
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'ready-for-preparation':
            context.update_progress(self_tracker_name, 30)

            job_id = self._submit_prep_job(context, group, args['area'], args['bf_obj_id'])

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
                'iem-run-package': outputs['iem-run-package'].meta.obj_id
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'ready-for-simulation':
            context.update_progress(self_tracker_name, 60)

            job_id = self._submit_sim_job(context, args['iem-run-package'])

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
                'air-temperature': outputs['air-temperature'].meta.obj_id,
                'wind-speed': outputs['wind-speed'].meta.obj_id,
                'wind-direction': outputs['wind-direction'].meta.obj_id
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'simulation-done':
            context.update_progress(self_tracker_name, 90)

            # prepare analysis results
            results = [
                AnalysisResult.parse_obj({
                    'name': 'wind-speed',
                    'label': 'Wind Speed',
                    'obj_id': {'#': args['wind-speed']},
                    'specification': {
                        'description': 'The results show the speed of winds at a given, location 10 meters above ground.',
                        'parameters': {}
                    },
                    'export_format': 'tiff'
                }),
                AnalysisResult.parse_obj({
                    'name': 'wind-direction',
                    'label': 'Wind Direction',
                    'obj_id': {'#': args['wind-direction']},
                    'specification': {
                        'description': 'The results show the direction of winds at a given location, 10 meters above ground.',
                        'parameters': {}
                    },
                    'export_format': 'tiff'
                })
            ]

            context.update_progress(self_tracker_name, 100)
            return results

        if status != AnalysisStatus.CANCELLED:
            raise DUCTRuntimeError(f"Encountered unexpected checkpoint: {checkpoint}")

    def extract_feature(self, content_paths: Dict[str, str], result: AnalysisResult, parameters: dict,
                        project: Project, sdk: SDKContext, export_path: str, json_path: str) -> None:
        if result.name in ['wind-speed', 'wind-direction']:
            spec = self.specification(project, sdk).result_specifications[result.name]
            parameters['legend_title'] = spec['legend_title']
            parameters['color_schema'] = spec['color_schema']
            parameters['no_data'] = spec['no_data']

            with open(json_path, 'w') as f:
                assets = [
                    duct.GeoRasterData().extract_feature(content_paths['#'], parameters)
                ]
                f.write(json.dumps(assets))

            duct.GeoRasterData().export_feature(content_paths['#'], parameters, export_path, result.export_format)

        else:
            raise ExplorerRuntimeError(f"Encountered unexpected/unsupported result '{result.name}'", details={
                'result': result.dict(),
                'parameters': parameters
            })

    def extract_delta_feature(self, content_paths0: Dict[str, str], result0: AnalysisResult, parameters0: dict,
                              content_paths1: Dict[str, str], result1: AnalysisResult, parameters1: dict,
                              project: Project, sdk: SDKContext, export_path: str, json_path: str) -> None:

        # check if the result names are identical
        if result0.name != result1.name:
            raise DUCTRuntimeError(f"Mismatching result names: {result0.name} != {result1.name}")

        if result0.name in ['wind-speed', 'wind-direction']:
            # add the wind-corridors spec to the parameters
            spec = self.specification(project, sdk).result_specifications[f"{result0.name}-delta"]

            parameters = {
                'common': {
                    'legend_title': spec['legend_title'],
                    'color_schema': spec['color_schema'],
                    'no_data': spec['no_data']
                },
                'A': parameters0,
                'B': parameters1
            }

            with open(json_path, 'w') as f:
                assets = [
                    duct.GeoRasterData().extract_delta_feature(content_paths0['#'], content_paths1['#'], parameters)
                ]
                f.write(json.dumps(assets))

            duct.GeoRasterData().export_delta_feature(content_paths0['#'], content_paths1['#'], parameters,
                                                      export_path, result0.export_format)

        else:
            raise ExplorerRuntimeError(f"Encountered unexpected/unsupported result '{result0.name}'/'{result1.name}'",
                                       details={
                                           'result0': result0.dict(),
                                           'result1': result1.dict(),
                                           'parameters0': parameters0,
                                           'parameters1': parameters1
                                       })

