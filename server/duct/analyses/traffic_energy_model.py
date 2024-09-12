from typing import List, Dict

from saas.sdk.base import SDKContext, SDKProductSpecification, SDKCDataObject

from duct.exceptions import DUCTRuntimeError
from explorer.analysis.base import Analysis, AnalysisContext, AnalysisStatus
from explorer.project import Project
from explorer.schemas import AnalysisGroup, Scene, AnalysisResult, ExplorerRuntimeError, AnalysisSpecification


class TrafficEnergyModelAnalysis(Analysis):
    def name(self) -> str:
        return 'traffic-energy-model'

    def label(self) -> str:
        return 'Traffic Energy Model'

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
                    'am_input_id': {
                        'type': 'string',
                        'title': 'AM Inputs',
                    },
                    'op_input_id': {
                        'type': 'string',
                        'title': 'OP Inputs',
                    },
                    'pm_input_id': {
                        'type': 'string',
                        'title': 'PM Inputs',
                    },
                },
                'required': ['name']
            },
            'description': '',
            'further_information': '',
            'sample_image': self.name() + '.png',
            'ui_schema': {
                'am_input_id': {
                    'ui:widget': 'uploadValidator',
                    'ui:options': {
                        'accept': '.zip',
                        'data_type': 'EMMEInputPackage',
                        'data_format': 'zip'
                    }
                },
                'op_input_id': {
                    'ui:widget': 'uploadValidator',
                    'ui:options': {
                        'accept': '.zip',
                        'data_type': 'EMMEInputPackage',
                        'data_format': 'zip'
                    }
                },
                'pm_input_id': {
                    'ui:widget': 'uploadValidator',
                    'ui:options': {
                        'accept': '.zip',
                        'data_type': 'EMMEInputPackage',
                        'data_format': 'zip'
                    }
                }
            },
            'required_processors': ['tem-emme-assignment', 'tem-emme-local-roads-output', 'tem-emme-heat-estimation'],
            'required_bdp': [''],
            'result_specifications': {}
        })

    def _run_assignment_job(self, context: AnalysisContext,
                            functions: SDKCDataObject,
                            modes: SDKCDataObject,
                            network: SDKCDataObject,
                            turns: SDKCDataObject,
                            extra_links: SDKCDataObject,
                            extra_turns: SDKCDataObject,
                            extra_functions: SDKCDataObject,
                            matrices: SDKCDataObject,
                            simulation_parameters: SDKCDataObject,) -> Dict[str, SDKCDataObject]:
        proc_name = 'tem-emme-assignment'
        # find the processor
        proc = context.sdk.find_processor_by_name(proc_name)
        if proc is None:
            raise DUCTRuntimeError(f"Processor '{proc_name}' not found.")

        # submit the job
        inputs = {
            'functions': functions,
            'modes': modes,
            'network': network,
            'turns': turns,
            'extra_links': extra_links,
            'extra_turns': extra_turns,
            'extra_functions': extra_functions,
            'matrices': matrices,
            'simulation_parameters': simulation_parameters
        }

        outputs = {
            name: SDKProductSpecification(
                restricted_access=False,
                content_encrypted=False,
                target_node=context.sdk.dor()
            ) for name in ['link_volume', 'network_results']
        }

        job = proc.submit(inputs, outputs,
                          name=f"{context.analysis_id}.0",
                          description=f"job part of analysis {context.analysis_id}")
        context.add_update_tracker(f'job:{job.content.id}', 100)
        data_objs = job.wait(callback_progress=lambda x: context.update_progress(f'job:{job.content.id}', x),
                             callback_message=context.update_message)

        return data_objs

    def _run_local_roads_job(self, context: AnalysisContext,
                             network: SDKCDataObject,
                             local_roads: SDKCDataObject,
                             boundary: SDKCDataObject,
                             am_results: SDKCDataObject,
                             am_volume: SDKCDataObject,
                             op_results: SDKCDataObject,
                             op_volume: SDKCDataObject,
                             pm_results: SDKCDataObject,
                             pm_volume: SDKCDataObject) -> Dict[str, SDKCDataObject]:
        proc_name = 'tem-emme-local-roads-output'
        # find the processor
        proc = context.sdk.find_processor_by_name(proc_name)
        if proc is None:
            raise DUCTRuntimeError(f"Processor '{proc_name}' not found.")

        # submit the job
        inputs = {
            'network': network,
            'local_roads': local_roads,
            'boundary': boundary,
            'network_results_AM': am_results,
            'network_results_OP': op_results,
            'network_results_PM': pm_results,
            'link_volume_AM': am_volume,
            'link_volume_OP': op_volume,
            'link_volume_PM': pm_volume
        }

        outputs = {
            name: SDKProductSpecification(
                restricted_access=False,
                content_encrypted=False,
                target_node=context.sdk.dor()
            ) for name in ['main_roads', 'local_roads']
        }

        job = proc.submit(inputs, outputs,
                          name=f"{context.analysis_id}.0",
                          description=f"job part of analysis {context.analysis_id}")
        context.add_update_tracker(f'job:{job.content.id}', 300)
        data_objs = job.wait(callback_progress=lambda x: context.update_progress(f'job:{job.content.id}', x),
                             callback_message=context.update_message)

        return data_objs

    def _run_heat_estimation_job(self, context: AnalysisContext,
                                 main_roads_result: SDKCDataObject,
                                 local_roads_result: SDKCDataObject) -> Dict[str, SDKCDataObject]:
        proc_name = 'tem-emme-heat-estimation'
        # find the processor
        proc = context.sdk.find_processor_by_name(proc_name)
        if proc is None:
            raise DUCTRuntimeError(f"Processor '{proc_name}' not found.")

        # submit the job
        inputs = {
            'main_roads': main_roads_result,
            'local_roads': local_roads_result
        }

        outputs = {
            name: SDKProductSpecification(
                restricted_access=False,
                content_encrypted=False,
                target_node=context.sdk.dor()
            ) for name in ['heat_estimation']
        }

        job = proc.submit(inputs, outputs,
                          name=f"{context.analysis_id}.0",
                          description=f"job part of analysis {context.analysis_id}")
        context.add_update_tracker(f'job:{job.content.id}', 800)
        data_objs = job.wait(callback_progress=lambda x: context.update_progress(f'job:{job.content.id}', x),
                             callback_message=context.update_message)

        return data_objs

    def perform_analysis(self, group: AnalysisGroup, scene: Scene, context: AnalysisContext) -> List[AnalysisResult]:
        self_tracker_name = 'tem.perform_analysis'
        context.add_update_tracker(self_tracker_name, 10)

        # FIXME: Update with upload id
        functions = context.bdp.references['']
        modes = context.bdp.references['']
        network = context.bdp.references['']
        turns = context.bdp.references['']
        extra_links = context.bdp.references['']
        extra_turns = context.bdp.references['']
        extra_functions = context.bdp.references['']
        simulation_parameter = context.bdp.references['']

        am_matrices = context.bdp.references['']
        op_matrices = context.bdp.references['']
        pm_matrices = context.bdp.references['']

        local_roads = context.bdp.references['']
        boundary = context.bdp.references['']

        checkpoint, args, status = context.update_checkpoint('run-assignment-job-AM', {})

        if status == AnalysisStatus.RUNNING and checkpoint == 'run-assignment-job-AM':
            context.update_progress(self_tracker_name, 10)

            outputs = self._run_assignment_job(
                context,
                functions,
                modes,
                network,
                turns,
                extra_links,
                extra_turns,
                extra_functions,
                am_matrices,
                simulation_parameter
            )

            checkpoint, args, status = context.update_checkpoint('run-assignment-job-OP', {
                "AM": {
                    name: obj.meta.obj_id for name, obj in outputs.items()
                }
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'run-assignment-job-OP':
            context.update_progress(self_tracker_name, 20)

            outputs = self._run_assignment_job(
                context,
                functions,
                modes,
                network,
                turns,
                extra_links,
                extra_turns,
                extra_functions,
                op_matrices,
                simulation_parameter
            )

            checkpoint, args, status = context.update_checkpoint(
                'run-assignment-job-PM', args.update(
                    {
                        "OP": {
                            name: obj.meta.obj_id for name, obj in outputs.items()
                        }
                    }
                )
            )

        if status == AnalysisStatus.RUNNING and checkpoint == 'run-assignment-job-PM':
            context.update_progress(self_tracker_name, 30)

            outputs = self._run_assignment_job(
                context,
                functions,
                modes,
                network,
                turns,
                extra_links,
                extra_turns,
                extra_functions,
                pm_matrices,
                simulation_parameter
            )

            checkpoint, args, status = context.update_checkpoint(
                'run-local-roads-job', args.update(
                    {
                        "PM": {
                            name: obj.meta.obj_id for name, obj in outputs.items()
                        }
                    }
                )
            )

        if status == AnalysisStatus.RUNNING and checkpoint == 'run-local-roads-job':
            context.update_progress(self_tracker_name, 40)

            am_results = args["AM"]["network_results"]
            am_volume = args["AM"]["link_volume"]
            op_results = args["OP"]["network_results"]
            op_volume = args["OP"]["link_volume"]
            pm_results = args["PM"]["network_results"]
            pm_volume = args["PM"]["link_volume"]

            outputs = self._run_local_roads_job(
                context,
                network,
                local_roads,
                boundary,
                am_results,
                am_volume,
                op_results,
                op_volume,
                pm_results,
                pm_volume
            )

            checkpoint, args, status = context.update_checkpoint('run-heat-estimation-job', {
                name: obj.meta.obj_id for name, obj in outputs.items()
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'run-heat-estimation-job':
            context.update_progress(self_tracker_name, 50)

            main_roads_result = args["main_roads"]
            local_roads_result = args["local_roads"]
            outputs = self._run_heat_estimation_job(context, main_roads_result, local_roads_result)

            checkpoint, args, status = context.update_checkpoint('simulation-done', {
                name: obj.meta.obj_id for name, obj in outputs.items()
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'simulation-done':
            context.update_progress(self_tracker_name, 80)

            heat_estimation = args['heat_estimation']

            # prepare analysis results
            results = [
                AnalysisResult.parse_obj({
                    'name': 'heat_estimation',
                    'obj_id': {'#': heat_estimation},
                    'label': 'Anthropogenic Heat Estimation for Road Network',
                    'specification': {
                        'description': '',
                        'parameters': {}
                    },
                    'export_format': 'geojson'
                })
            ]

            context.update_progress(self_tracker_name, 100)
            return results

        if status != AnalysisStatus.CANCELLED:
            raise DUCTRuntimeError(f"Encountered unexpected checkpoint: {checkpoint}")

    def extract_feature(self, content_paths: Dict[str, str], result: AnalysisResult, parameters: dict,
                        project: Project, sdk: SDKContext, export_path: str, json_path: str) -> None:
        if result.name in ['heat_estimation']:
            pass
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

        if result0.name in ['heat_estimation']:
            pass
        else:
            raise ExplorerRuntimeError(f"Encountered unexpected/unsupported result '{result0.name}'/'{result1.name}'",
                                       details={
                                           'result0': result0.dict(),
                                           'result1': result1.dict(),
                                           'parameters0': parameters0,
                                           'parameters1': parameters1
                                       })
