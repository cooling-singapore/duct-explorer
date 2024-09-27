import json
import os
import subprocess
import time
from typing import List, Dict

from saas.rti.schemas import JobStatus
from saas.sdk.base import SDKContext, SDKProductSpecification, LogMessage, SDKCDataObject

from explorer.dots import duct
from explorer.exceptions import DUCTRuntimeError
from explorer.analysis.base import Analysis, AnalysisContext, AnalysisStatus
from explorer.project import Project
from explorer.renderer.base import hex_color_to_components
from explorer.schemas import AnalysisGroup, Scene, AnalysisResult, ExplorerRuntimeError, AnalysisSpecification


class WindCorridorPotentialAnalysis(Analysis):
    def name(self) -> str:
        return 'wind-corridor-potential'

    def label(self) -> str:
        return 'Wind Corridor Potential'

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
                'type': 'object',
                'properties': {
                    'name': {'type': 'string', 'title': 'Configuration Name'},
                    'spatial_resolution': {
                        'title': 'Spatial Resolution (m\u00b2)',
                        'type': 'integer',
                        'enum': [50, 100, 200, 300],
                        'enumNames': ['50m (slowest)', '100m', '200m', '300m (fastest)'],
                        'default': 300
                    }
                },
                'required': ['name', 'spatial_resolution']
            },
            'description': 'This analysis provides a multi-level local and global wind corridor analysis on the '
                           'island-wide scale. Both local and global wind corridor models use the 3D geometry model '
                           'of the city as an input. <br>'
                           'On the local level, the model calculates the local spatial '
                           'resistance of the urban features in a small spatial region, or cluster, to allow wind '
                           'movement. The model assumes the cluster size of 3 x 3 cells with the threshold of 95% '
                           'confidence level. The output of this analysis provides a spatial map of wind ventilation '
                           'potential intensity regions. <br>'
                           'On the global level, the model calculates the global '
                           'intensity of various ventilation paths, based on their capability to allow wind '
                           'penetration and urban friction. The analysis is based on spatio-directional calculations '
                           'and provides results in eight different directions, dividing the spatial plane into '
                           'segments of 45 degrees. The output of this analysis provides directional wind corridors '
                           'maps.',
            'further_information': 'This analysis is based on a model developed by <a '
                                   'href="mailto:ido.nevat@tum-create.edu.sg">Ido Nevat</a> and <a '
                                   'href="mailto:adelia.sukma@sec.ethz.ch">Adelia Sukma</a>. The SaaS adapter for '
                                   'this model has been developed by <a href="mailto:aydt@arch.ethz.ch">Heiko '
                                   'Aydt</a>. For more information, please contact the respective authors.',
            'sample_image': self.name()+'.png',
            'ui_schema': {},
            'required_processors': ['ucm-mva-uwc', 'ucm-mva-uvp'],
            'required_bdp': ['city-admin-zones'],
            'result_specifications': {
                'hotspots': {
                    'legend_title': 'Likelihood of Hotspot Occurrence',
                    'color_schema': [
                        {'value': 0.00, 'color': hex_color_to_components('#2c7bb6', 200), 'label': 'Lowest'},
                        {'value': 0.25, 'color': hex_color_to_components('#abd9e9', 200), 'label': 'Low'},
                        {'value': 0.50, 'color': hex_color_to_components('#ffffbf', 200), 'label': 'Neutral'},
                        {'value': 0.75, 'color': hex_color_to_components('#fdae61', 200), 'label': 'High'},
                        {'value': 1.00, 'color': hex_color_to_components('#d7191c', 200), 'label': 'Highest'}
                    ],
                    'no_data': -1
                },
                'hotspots-delta': {
                    'legend_title': 'Difference in likelihood of wind penetration',
                    'color_schema': [
                        {'value': -1.00, 'color': hex_color_to_components('#EB1C24', 255),
                         'label': 'Reduced potential'},
                        {'value': -0.50, 'color': hex_color_to_components('#BA3450', 255), 'label': ''},
                        {'value': 0.00, 'color': hex_color_to_components('#303030', 127), 'label': 'No change'},
                        {'value': 0.50, 'color': hex_color_to_components('#3491C6', 255), 'label': ''},
                        {'value': 1.00, 'color': hex_color_to_components('#00ACED', 255),
                         'label': 'Increased potential'}
                    ],
                    'no_data': 999
                },
                'wind-corridors': {
                    'legend_title': 'Wind Corridor Potential',
                    'color_schema': [
                        {
                            'value': 0,
                            'color': hex_color_to_components('#2c7bb6', 200),
                            'label': 'Lowest'
                        },
                        {
                            'value': 0.25,
                            'color': hex_color_to_components('#abd9e9', 255),
                            'label': 'Low'
                        },
                        {
                            'value': 0.5,
                            'color': hex_color_to_components('#ffffbf', 255),
                            'label': 'Neutral'
                        },
                        {
                            'value': 0.75,
                            'color': hex_color_to_components('#fdae61', 255),
                            'label': 'High'
                        },
                        {
                            'value': 1,
                            'color': hex_color_to_components('#d7191c', 255),
                            'label': 'Highest'
                        }
                    ],
                    'no_data': -1
                },
                'wind-corridors-delta': {
                    'legend_title': 'Difference in likelihood of wind corridor potential',
                    'color_schema': [
                        {'value': -1.00, 'color': hex_color_to_components('#EB1C24', 255), 'label': 'Reduced potential'},
                        {'value': -0.50, 'color': hex_color_to_components('#BA3450', 255), 'label': ''},
                        {'value': 0.00, 'color': hex_color_to_components('#303030', 127), 'label': 'No change'},
                        {'value': 0.50, 'color': hex_color_to_components('#3491C6', 255), 'label': ''},
                        {'value': 1.00, 'color': hex_color_to_components('#00ACED', 255), 'label': 'Increased potential'}
                    ],
                    'no_data': 999
                }
            }
        })

    def _submit_uwc_job(self, context: AnalysisContext, resolution: int,
                        lm_obj: SDKCDataObject, bf_obj: SDKCDataObject) -> str:
        # find the processor
        proc = context.sdk.find_processor_by_name('ucm-mva-uwc')
        if proc is None:
            raise DUCTRuntimeError(f"Processor 'ucm-mva-uwc' not found.")

        # submit the job
        inputs = {
            'parameters': {
                'bounding_box': context.bdp.bounding_box.dict(),
                'resolution': resolution
            },
            'land-mask': lm_obj,
            'building-footprints': bf_obj
        }

        outputs = {name: SDKProductSpecification(
            restricted_access=False,
            content_encrypted=False,
            target_node=context.sdk.dor()
            # owner=context.sdk.authority.identity
        ) for name in ['wind-corridors-ns', 'wind-corridors-ew', 'wind-corridors-nwse', 'wind-corridors-nesw',
                       'building-footprints', 'land-mask']}

        job = proc.submit(inputs, outputs, name=f"{context.analysis_id}.uwc",
                          description=f"job part of analysis {context.analysis_id}")

        return job.content.id

    def _submit_uvp_job(self, context: AnalysisContext, resolution: int, lm_obj: SDKCDataObject,
                        bf_obj: SDKCDataObject) -> str:
        # find the processor
        proc = context.sdk.find_processor_by_name('ucm-mva-uvp')
        if proc is None:
            raise DUCTRuntimeError(f"Processor 'ucm-mva-uvp' not found.")

        # submit the job
        inputs = {
            'parameters': {
                'bounding_box': context.bdp.bounding_box.dict(),
                'resolution': resolution
            },
            'land-mask': lm_obj,
            'building-footprints': bf_obj
        }

        outputs = {name: SDKProductSpecification(
            restricted_access=False,
            content_encrypted=False,
            target_node=context.sdk.dor()
            # owner=context.sdk.authority.identity
        ) for name in ['hotspots']}

        job = proc.submit(inputs, outputs, name=f"{context.analysis_id}.uvp",
                          description=f"job part of analysis {context.analysis_id}")

        return job.content.id

    def perform_analysis(self, group: AnalysisGroup, scene: Scene, context: AnalysisContext) -> List[AnalysisResult]:
        # add a progress tracker for this function
        self_tracker_name = 'uwp.perform_analysis'
        context.add_update_tracker(self_tracker_name, 10)

        checkpoint, args, status = context.checkpoint()
        if status == AnalysisStatus.RUNNING and checkpoint == 'initialised':
            context.update_progress(self_tracker_name, 30)

            # get the spatial resolution
            resolution = group.parameters['spatial_resolution']

            # NOTE: the model doesn't work with an actual land mask, instead the CA zones should be used to indicate
            # areas that are the city of interest. In case of Singapore, the surrounding Johor land mass north of
            # Singapore 'confuses' the model.
            # 'land-mask': context.bdp.references['land-mask'],
            lm_obj = context.sdk.find_data_object(context.bdp.references['city-admin-zones'])

            # find the building footprints data object
            bf_obj = context.sdk.find_data_object(context.bld_footprint_obj_id())

            job_id_uvp = self._submit_uvp_job(context, resolution, lm_obj, bf_obj)
            job_id_uwc = self._submit_uwc_job(context, resolution, lm_obj, bf_obj)

            checkpoint, args, status = context.update_checkpoint('waiting-for-simulations', {
                'job_id_uvp': job_id_uvp,
                'job_id_uwc': job_id_uwc
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'waiting-for-simulations':
            context.update_progress(self_tracker_name, 60)

            # find the UVP job
            job_id_uvp = args['job_id_uvp']
            job_uvp = context.sdk.find_job(job_id_uvp)
            if job_uvp is None:
                raise DUCTRuntimeError(f"Job {job_id_uvp} cannot be found.")

            # find the UWC job
            job_id_uwc = args['job_id_uwc']
            job_uwc = context.sdk.find_job(job_id_uwc)
            if job_uwc is None:
                raise DUCTRuntimeError(f"Job {job_id_uwc} cannot be found.")

            context.add_update_tracker(f'job:{job_id_uvp}', 100)
            context.add_update_tracker(f'job:{job_id_uwc}', 100)

            def callback_progress_uvp(progress: int) -> None:
                context.update_progress(f'job:{job_id_uvp}', progress)

            def callback_progress_uwc(progress: int) -> None:
                context.update_progress(f'job:{job_id_uwc}', progress)

            def callback_message(message: LogMessage) -> None:
                context.update_message(message)

            job_callbacks = {
                job_uwc: callback_progress_uwc,
                job_uvp: callback_progress_uvp,
            }
            job_prev = {
                job_uwc: (0, None),
                job_uvp: (0, None)
            }
            outputs = {}
            failed = []
            while len(job_callbacks) > 0:
                time.sleep(5.0)
                for job, callback_progress in dict(job_callbacks).items():
                    status = job.status
                    if status is not None:
                        prev_progress, prev_message = job_prev[job]

                        if prev_progress != status.progress:
                            callback_progress(status.progress)
                            prev_progress = status.progress

                        if status.message is not None and prev_message != status.message:
                            callback_message(
                                LogMessage(severity=status.message.severity, message=status.message.content)
                            )
                            prev_message = status.message

                        job_prev[job] = (prev_progress, prev_message)

                    # are we done?
                    if status.state == JobStatus.State.SUCCESSFUL:
                        job_callbacks.pop(job)
                        results = job.wait(pace=0)  # this should return immediately with the results
                        outputs.update(results)

                    elif status.state in [JobStatus.State.FAILED, JobStatus.State.CANCELLED]:
                        job_callbacks.pop(job)
                        failed.append(job)

            # did any job fail?
            if len(failed) > 0:
                raise DUCTRuntimeError(f"Jobs failed: {[job.content.id for job in failed]}")

            # all outputs available?
            required = ['hotspots', 'wind-corridors-ns', 'wind-corridors-ew', 'wind-corridors-nwse',
                        'wind-corridors-nesw', 'building-footprints', 'land-mask']
            if not all(key in outputs for key in required):
                raise DUCTRuntimeError(f"Incomplete required outputs: {list(outputs.keys())}")

            checkpoint, args, status = context.update_checkpoint('simulation-done', {
                key: outputs[key].meta.obj_id for key in required
            })

        if checkpoint == 'simulation-done':
            context.update_progress(self_tracker_name, 90)

            # prepare analysis results
            results = [
                AnalysisResult.parse_obj({
                    'name': 'hotspots',
                    'label': 'Hotspots',
                    'obj_id': {'#': args['hotspots']},
                    'specification': {
                        'description': 'The results provide a local measure (micro-scale) of the urban roughness and friction. They are indicative of the high/low potential of wind to move freely in the hot/cold spot regions. The results can guide urban planners as to which of the interior parts of the city have good/bad potential to let wind flow across. Moreover, the results can direct urban designer how to create wind corridors by modifying urban features to allow wind to flow freely, thus, creating new wind corridors.',
                        'parameters': {}
                    },
                    'export_format': 'tiff'
                }),
                AnalysisResult.parse_obj({
                    'name': 'wind-corridors-ns',
                    'label': 'North-South Wind Corridor',
                    'obj_id': {'#': args['wind-corridors-ns']},
                    'specification': {
                        'description': 'The results provide a global measure (meso-scale) of directional connectivity (North - South) in terms of roughness (friction) of the urban features from one end of the city across to the other end. The results are indicative of the urban ventilation potential paths (wind corridors), which in tandem with information of the regional prevailing winds (eg. wind rose) provide city planners information regarding wind penetration into and across the city.',
                        'parameters': {}
                    },
                    'export_format': 'zip',
                    'extras': {
                        'building-footprints': args['building-footprints'],
                        'land-mask': args['land-mask']
                    }
                }),
                AnalysisResult.parse_obj({
                    'name': 'wind-corridors-ew',
                    'label': 'East-West Wind Corridor',
                    'obj_id': {'#': args['wind-corridors-ew']},
                    'specification': {
                        'description': 'The results provide a global measure (meso-scale) of directional connectivity (East - West) in terms of roughness (friction) of the urban features from one end of the city across to the other end. The results are indicative of the urban ventilation potential paths (wind corridors), which in tandem with information of the regional prevailing winds (eg. wind rose) provide city planners information regarding wind penetration into and across the city.',
                        'parameters': {}
                    },
                    'export_format': 'zip',
                    'extras': {
                        'building-footprints': args['building-footprints'],
                        'land-mask': args['land-mask']
                    }
                }),
                AnalysisResult.parse_obj({
                    'name': 'wind-corridors-nwse',
                    'label': 'North-West -- South-East Wind Corridor',
                    'obj_id': {'#': args['wind-corridors-nwse']},
                    'specification': {
                        'description': 'The results provide a global measure (meso-scale) of directional connectivity (North-West - South-East) in terms of roughness (friction) of the urban features from one end of the city across to the other end. The results are indicative of the urban ventilation potential paths (wind corridors), which in tandem with information of the regional prevailing winds (eg. wind rose) provide city planners information regarding wind penetration into and across the city.',
                        'parameters': {}
                    },
                    'export_format': 'zip',
                    'extras': {
                        'building-footprints': args['building-footprints'],
                        'land-mask': args['land-mask']
                    }
                }),
                AnalysisResult.parse_obj({
                    'name': 'wind-corridors-nesw',
                    'label': 'North-East -- South-West Wind Corridor',
                    'obj_id': {'#': args['wind-corridors-nesw']},
                    'specification': {
                        'description': 'The results provide a global measure (meso-scale) of directional connectivity (North-East - South-West) in terms of roughness (friction) of the urban features from one end of the city across to the other end. The results are indicative of the urban ventilation potential paths (wind corridors), which in tandem with information of the regional prevailing winds (eg. wind rose) provide city planners information regarding wind penetration into and across the city.',
                        'parameters': {}
                    },
                    'export_format': 'zip',
                    'extras': {
                        'building-footprints': args['building-footprints'],
                        'land-mask': args['land-mask']
                    }
                })
            ]

            context.update_progress(self_tracker_name, 100)
            return results

        if status != AnalysisStatus.CANCELLED:
            raise DUCTRuntimeError(f"Encountered unexpected checkpoint: {checkpoint}")

    def extract_feature(self, content_paths: Dict[str, str], result: AnalysisResult, parameters: dict,
                        project: Project, sdk: SDKContext, export_path: str, json_path: str) -> None:

        if result.name in ['hotspots', 'wind-corridors-ns', 'wind-corridors-ew', 'wind-corridors-nwse',
                           'wind-corridors-nesw']:
            spec_name = 'hotspots' if result.name == 'hotspots' else 'wind-corridors'
            spec = self.specification(project, sdk).result_specifications[spec_name]
            parameters['legend_title'] = spec['legend_title']
            parameters['color_schema'] = spec['color_schema']
            parameters['no_data'] = spec['no_data']

            with open(json_path, 'w') as f:
                assets = [
                    duct.GeoRasterData().extract_feature(content_paths['#'], parameters)
                ]
                f.write(json.dumps(assets))

            result_path = os.path.join(parameters['__analysis_path'], f"{result.name}.tiff")
            duct.GeoRasterData().export_feature(content_paths['#'], parameters, result_path, 'tiff')

            # zip it up
            r = subprocess.run(['zip', export_path, 'building-footprints.tiff', 'land-mask.tiff',
                                f"{result.name}.tiff"], capture_output=True, cwd=parameters['__analysis_path'])
            if r.returncode != 0:
                raise ExplorerRuntimeError(f"Failed to create zip file with export results", details={
                    'stdout': r.stdout.decode('utf-8'),
                    'stderr': r.stdout.decode('utf-8')
                })

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

        if result0.name in ['hotspots', 'wind-corridors-ns', 'wind-corridors-ew', 'wind-corridors-nwse',
                            'wind-corridors-nesw']:

            spec_name = 'hotspots-delta' if result0.name == 'hotspots' else 'wind-corridors-delta'
            spec = self.specification(project, sdk).result_specifications[spec_name]

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

            temp_result_path = os.path.join(parameters0['__analysis_path'], f"{result0.name}.tiff")
            duct.GeoRasterData().export_delta_feature(content_paths0['#'], content_paths1['#'], parameters,
                                                      temp_result_path, 'tiff')

            # get the land-mask and the building-footprint objects
            analysis_path = parameters0['__analysis_path']
            obj_path_mappings = [
                (result0.extras['land-mask'], 'land-mask-0.tiff'),
                (result1.extras['land-mask'], 'land-mask-1.tiff'),
                (result0.extras['building-footprints'], 'building-footprints-0.tiff'),
                (result1.extras['building-footprints'], 'building-footprints-1.tiff')
            ]
            for obj_id, obj_filename in obj_path_mappings:
                # find the object
                obj = sdk.find_data_object(obj_id)
                if obj is None:
                    raise DUCTRuntimeError(f"Could not find object {obj_id} for {obj_filename}")

                # download it
                obj.download(os.path.join(analysis_path, obj_filename))

            # zip it up
            r = subprocess.run(['zip', export_path, 'building-footprints-0.tiff', 'building-footprints-1.tiff',
                                'land-mask-0.tiff', 'land-mask-1.tiff', f"{result0.name}.tiff"],
                               capture_output=True, cwd=analysis_path)
            if r.returncode != 0:
                raise ExplorerRuntimeError(f"Failed to create zip file with export results", details={
                    'stdout': r.stdout.decode('utf-8'),
                    'stderr': r.stdout.decode('utf-8')
                })

            # delete temporary files
            for obj_id, obj_filename in obj_path_mappings:
                path = os.path.join(analysis_path, obj_filename)
                os.remove(path)

        else:
            raise ExplorerRuntimeError(f"Encountered unexpected/unsupported result '{result0.name}'/'{result1.name}'",
                                       details={
                                           'result0': result0.dict(),
                                           'result1': result1.dict(),
                                           'parameters0': parameters0,
                                           'parameters1': parameters1
                                       })
