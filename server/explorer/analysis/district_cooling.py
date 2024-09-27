import json
import os
import zipfile
from typing import List, Dict

import geopandas as gpd

from explorer.dots.duct_bemcea import SupplySystems, BuildingAHEmissions
from saas.core.logging import Logging
from shapely import Polygon

from explorer.analysis.building_energy_efficiency import DEFAULT_BUILDING_TYPE_MAP, PROJ_SYSTEM, \
    MAXIMUM_BOUNDING_AREA_KM2, DEFAULT_WEATHER, generate_building_ah_profiles, determine_building_footprints
from saas.sdk.base import SDKContext, LogMessage, SDKCDataObject, SDKProductSpecification

from explorer.exceptions import DUCTRuntimeError
from explorer.analysis.base import Analysis, AnalysisContext, AnalysisStatus
from explorer.project import Project
from explorer.schemas import AnalysisGroup, Scene, AnalysisResult, ExplorerRuntimeError, AnalysisSpecification, \
    AnalysisCompareResults

logger = Logging.get('explorer.analysis.district_cooling')


class DistrictCooling(Analysis):
    def name(self) -> str:
        return "district-cooling"

    def label(self) -> str:
        return "District Cooling"

    def type(self) -> str:
        return 'micro'

    def specification(self, project, sdk: SDKContext, aoi_obj_id: str = None,
                      scene_id: str = None) -> AnalysisSpecification:
        return AnalysisSpecification.parse_obj({
            "name": self.name(),
            "label": self.label(),
            "type": self.type(),
            "area_selection": True,
            "parameters_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "title": "Configuration Name"}
                },
                "required": ["name"],
            },
            "description": "This analysis determines a set of optimal energy system solutions for the selected "
                           "district, minimising the system's energy demand and heat emissions. The solutions consist "
                           "of district cooling networks for cold water distribution between the buildings and one "
                           "supply system per network, each holding multiple components working together to provide "
                           "cooling for the district.",
            "further_information": "This analysis is based on a model developed by "
                                   "<a href='mailto:mathias.niffeler@sec.ethz.ch'>Mathias Niffeler</a>. "
                                   "The SaaS adaptor for this model has been developed by"
                                   " <a href='mailto:reynold.mok@sec.ethz.ch'>Reynold Mok</a>."
                                   " For more information, please contact the respective authors.",
            "sample_image": self.name()+'.png',
            "ui_schema": {},
            "required_processors": ["bem-cea-gen", "dcn-cea-sim"],
            "required_bdp": [],
            "result_specifications": {}
        })

    @staticmethod
    def _submit_gen_job(context: AnalysisContext, building_footprints: SDKCDataObject,
                        bld_eff_standards: SDKCDataObject) -> str:
        # find the processor
        proc = context.sdk.find_processor_by_name('bem-cea-gen')
        if proc is None:
            raise DUCTRuntimeError(f"Processor 'bem-cea-gen' not found.")

        # submit the job
        inputs = {
            'parameters': {
                'building_type_mapping': DEFAULT_BUILDING_TYPE_MAP,
                "default_building_type": "MULTI_RES",
                "building_standard_mapping": {},
                "default_building_standard": "STANDARD1",
                'commit_id': '9e778e6b797e076bf24ab3bfbf5c2ebbeaf63a1e',
                "database_name": "SG",
                "terrain_height": 0,
                "weather": DEFAULT_WEATHER
            },
            'building_footprints': building_footprints,
            'bld_eff_standards': bld_eff_standards
        }

        outputs = {
            name: SDKProductSpecification(
                restricted_access=False,
                content_encrypted=False,
                target_node=context.sdk.dor()
            ) for name in ['cea_run_package', 'cea_databases']
        }

        job = proc.submit(inputs, outputs,
                          name=f"{context.analysis_id}.0",
                          description=f"job part of analysis {context.analysis_id}")

        return job.content.id

    @staticmethod
    def _submit_sim_job(context: AnalysisContext, cea_run_package: SDKCDataObject,
                        cea_databases: SDKCDataObject) -> str:
        # find the processor
        proc = context.sdk.find_processor_by_name('dcn-cea-sim')
        if proc is None:
            raise DUCTRuntimeError(f"Processor 'dcn-cea-sim' not found.")

        # submit the job
        inputs = {
            'cea_run_package': cea_run_package,
            'cea_databases': cea_databases,
        }

        outputs = {
            name: SDKProductSpecification(
                restricted_access=False,
                content_encrypted=False,
                target_node=context.sdk.dor()
            ) for name in ['supply_systems', 'ah_emissions']
        }

        job = proc.submit(inputs, outputs,
                          name=f"{context.analysis_id}.0",
                          description=f"job part of analysis {context.analysis_id}")

        return job.content.id

    def perform_analysis(self, group: AnalysisGroup, scene: Scene, context: AnalysisContext) -> List[AnalysisResult]:
        self_tracker_name = 'dcn.perform_analysis'
        context.add_update_tracker(self_tracker_name, 10)

        checkpoint, args, status = context.checkpoint()
        if status == AnalysisStatus.RUNNING and checkpoint == 'initialised':
            context.update_progress(self_tracker_name, 10)

            context.update_message(LogMessage(
                severity='info', message="DCN getting buildings for area of interest."
            ))

            # determine building footprints
            bf_obj = determine_building_footprints(context, context.area_of_interest(), scene)

            checkpoint, args, status = context.update_checkpoint('submit-gen-job', {
                'bf_obj_id': bf_obj.meta.obj_id,
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'submit-gen-job':
            context.update_progress(self_tracker_name, 30)
            context.update_message(LogMessage(
                severity='info', message="Submitting 'cea-gen' job..."
            ))

            # find the building footprints data object
            bf_obj = context.sdk.find_data_object(args['bf_obj_id'])

            # upload the (empty) bld eff package to the DOR
            bld_eff_std_path = os.path.join(context.analysis_path, f"bld_eff_std_package.zip")
            with zipfile.ZipFile(bld_eff_std_path, 'w') as f:
                pass
            bes_obj = context.sdk.upload_content(bld_eff_std_path, 'BEMCEA.BldEffStandards', 'zip', False)

            # submit the gen job
            job_id_gen = self._submit_gen_job(context, bf_obj, bes_obj)

            checkpoint, args, status = context.update_checkpoint('waiting-for-gen', {
                'bf_obj_id': bf_obj.meta.obj_id,
                'job_id_gen': job_id_gen
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'waiting-for-gen':
            context.update_progress(self_tracker_name, 50)
            job_id_gen = args['job_id_gen']
            context.update_message(LogMessage(
                severity='info', message=f"Waiting for 'cea-gen' job {job_id_gen}"
            ))

            context.add_update_tracker(f'job:{job_id_gen}', 100)

            def callback_progress(progress: int) -> None:
                context.update_progress(f'job:{job_id_gen}', progress)

            def callback_message(message: LogMessage) -> None:
                context.update_message(message)

            # find the job
            job = context.sdk.find_job(job_id_gen)
            if job is None:
                raise DUCTRuntimeError(f"Job {job_id_gen} cannot be found.")

            # wait for the job to be finished
            outputs = job.wait(callback_progress=callback_progress, callback_message=callback_message)

            checkpoint, args, status = context.update_checkpoint('submit-sim-job', {
                'bf_obj_id': args['bf_obj_id'],
                'cea_run_package': outputs['cea_run_package'].meta.obj_id,
                'cea_databases': outputs['cea_databases'].meta.obj_id
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'submit-sim-job':
            context.update_progress(self_tracker_name, 70)
            context.update_message(LogMessage(
                severity='info', message="Submitting for 'dcn-sim' job..."
            ))

            cea_run_package = context.sdk.find_data_object(args['cea_run_package'])
            if cea_run_package is None:
                raise DUCTRuntimeError(f"Required input for dcn-sim missing: cea_run_package")

            cea_databases = context.sdk.find_data_object(args['cea_databases'])
            if cea_databases is None:
                raise DUCTRuntimeError(f"Required input for dcn-sim missing: cea_databases")

            # submit the gen job
            job_id_sim = self._submit_sim_job(context, cea_run_package, cea_databases)

            checkpoint, args, status = context.update_checkpoint('waiting-for-sim', {
                'bf_obj_id': args['bf_obj_id'],
                'job_id_sim': job_id_sim
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'waiting-for-sim':
            context.update_progress(self_tracker_name, 80)
            job_id_sim = args['job_id_sim']
            context.update_message(LogMessage(
                severity='info', message=f"Waiting for 'dcn-sim' job {job_id_sim}"
            ))

            context.add_update_tracker(f'job:{job_id_sim}', 800)

            def callback_progress(progress: int) -> None:
                context.update_progress(f'job:{job_id_sim}', progress)

            def callback_message(message: LogMessage) -> None:
                context.update_message(message)

            # find the job
            job = context.sdk.find_job(job_id_sim)
            if job is None:
                raise DUCTRuntimeError(f"Job {job_id_sim} cannot be found.")

            # wait for the job to be finished
            outputs = job.wait(callback_progress=callback_progress, callback_message=callback_message)

            # generate the building AH profiles from the AH emissions result
            generate_building_ah_profiles(outputs['ah_emissions'], context, group, scene)

            checkpoint, args, status = context.update_checkpoint('simulation-done', {
                'bf_obj_id': args['bf_obj_id'],
                'supply_systems': outputs['supply_systems'].meta.obj_id,
                'ah_emissions': outputs['ah_emissions'].meta.obj_id
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'simulation-done':
            context.update_progress(self_tracker_name, 90)

            bf_obj_id = args['bf_obj_id']
            supply_systems_obj_id = args['supply_systems']
            ah_emissions_obj_id = args['ah_emissions']

            # generate choices based on the supply systems results
            supply_systems_path = os.path.join(context.analysis_path, f'supply_systems.json')
            supply_systems_obj = context.sdk.find_data_object(supply_systems_obj_id)
            supply_systems_obj.download(supply_systems_path)
            with open(supply_systems_path, 'r') as f:
                supply_systems = json.load(f)

            # determine eligible DCS and clusters (based on whether a network is available)
            sorted_dcs_names = sorted(supply_systems['DCS'].keys())
            dcs_cluster_names = {}
            for dcs_name in sorted_dcs_names:
                for cluster_name, info in supply_systems['DCS'][dcs_name].items():
                    if info['network'] is not None:
                        if dcs_name in dcs_cluster_names:
                            dcs_cluster_names[dcs_name].append(cluster_name)
                        else:
                            dcs_cluster_names[dcs_name] = [cluster_name]

            results = [
                AnalysisResult.parse_obj({
                    'name': 'supply_systems',
                    'obj_id': {'#': supply_systems_obj_id},
                    'label': 'District Cooling Network Components',
                    'specification': {
                        'description': 'The pie charts below display the components and their corresponding capacities '
                                       'installed in the supply system of the selected district cooling network. The '
                                       'components are divided into three categories: <br> '
                                       '<ul>'
                                       '<li>Primary Cooling Components: Components that provide cold water to the network.</li>'
                                       '<li>Supply Components: Components that provide the necessary inputs (heat or electric power) to the primary cooling components.</li>'
                                       '<li>Heat Rejections Components: Components that release the heat displaced by the thermodynamic cycles of the primary cooling components to the environment.</li>'
                                       '</ul>',
                        'parameters': {
                            'type': 'object',
                            'properties': {
                                'district_cooling_system': {
                                    'title': 'District Cooling System (if any)',
                                    'type': 'string',
                                    'enum': sorted_dcs_names,
                                    'default': sorted_dcs_names[0] if len(sorted_dcs_names) > 0 else '(none)'
                                },
                            },
                            'allOf': [{
                                "if": {
                                    "properties": {
                                        "district_cooling_system": {
                                            "const": dcs_name
                                        }
                                    }
                                },
                                "then": {
                                    "properties": {
                                        'cluster': {
                                            'title': 'Cluster',
                                            'type': 'string',
                                            'enum': sorted(cluster_names),
                                            'default': sorted(cluster_names)[0]
                                        },
                                    },
                                    "required": [
                                        "cluster"
                                    ]
                                }
                            } for dcs_name, cluster_names in dcs_cluster_names.items()],
                            'required': ['district_cooling_system']
                        }
                    },
                    'export_format': 'json',
                    'extras': {
                        'bf_obj_id': bf_obj_id
                    }
                }),
                AnalysisResult.parse_obj({
                    'name': 'ah_emissions',
                    'obj_id': {'#': ah_emissions_obj_id},
                    'label': 'Anthropogenic Heat Emissions',
                    'specification': {
                        'description': '',
                        'parameters': {
                            'type': 'object',
                            'properties': {
                                'district_cooling_system': {
                                    'title': 'District Cooling System (if any)',
                                    'type': 'string',
                                    'enum': ['base_TES', *sorted_dcs_names],
                                    'default': 'base_TES'
                                },
                                'hour': {
                                    'title': 'Hour',
                                    'type': 'number',
                                    'enum': [i for i in range(24)],
                                    'default': 1
                                }
                            },
                            'required': ['district_cooling_system', 'hour']
                        }
                    },
                    'export_format': 'geojson',
                    'extras': {
                        'bf_obj_id': bf_obj_id
                    }
                })
            ]

            # update the progress tracker for this function
            context.update_progress(self_tracker_name, 100)
            return results

        if status != AnalysisStatus.CANCELLED:
            raise DUCTRuntimeError(f"Encountered unexpected checkpoint: {checkpoint}")

    def extract_feature(self, content_paths: Dict[str, str], result: AnalysisResult, parameters: dict,
                        project: Project, sdk: SDKContext, export_path: str, json_path: str) -> None:

        def download_building_footprints():
            # download and read building footprints
            bf_obj_path = os.path.join(parameters['__analysis_path'], result.extras['bf_obj_id'])
            if not os.path.exists(bf_obj_path):
                bf_obj = sdk.find_data_object(result.extras['bf_obj_id'])
                bf_obj.download(bf_obj_path)

            # read the building footprints
            with open(bf_obj_path, 'r') as f:
                building_footprints = json.load(f)

            return building_footprints

        if result.name == 'supply_systems':
            parameters['building_footprints'] = download_building_footprints()
            with open(json_path, 'w') as f:
                assets = SupplySystems().extract_feature(content_paths['#'], parameters)
                f.write(json.dumps(assets))

            SupplySystems().export_feature(content_paths['#'], parameters, export_path, result.export_format)

        elif result.name == 'ah_emissions':
            parameters['building_footprints'] = download_building_footprints()
            parameters['variable'] = parameters['district_cooling_system']
            with open(json_path, 'w') as f:
                assets = BuildingAHEmissions().extract_feature(content_paths['#'], parameters)
                f.write(json.dumps(assets))

            BuildingAHEmissions().export_feature(content_paths['#'], parameters, export_path, result.export_format)

        else:
            raise ExplorerRuntimeError(f"Encountered unexpected/unsupported result '{result.name}'", details={
                'result': result.dict(),
                'parameters': parameters
            })

    def extract_delta_feature(self, content_paths0: Dict[str, str], result0: AnalysisResult, parameters0: dict,
                              content_paths1: Dict[str, str], result1: AnalysisResult, parameters1: dict,
                              project: Project, sdk: SDKContext, export_path: str, json_path: str) -> None:

        def download_building_footprints(result):
            # download and read building footprints
            bf_obj_path = os.path.join(parameters['__analysis_path'], result.extras['bf_obj_id'])
            if not os.path.exists(bf_obj_path):
                bf_obj = sdk.find_data_object(result.extras['bf_obj_id'])
                bf_obj.download(bf_obj_path)

            # read the building footprints
            with open(bf_obj_path, 'r') as f:
                building_footprints = json.load(f)

            return building_footprints

        # check if the result names are identical
        if result0.name != result1.name:
            raise DUCTRuntimeError(f"Mismatching result names: {result0.name} != {result1.name}")

        if result0.name == 'supply_systems':
            parameters = {
                'A': parameters0,
                'B': parameters1
            }

            with open(json_path, 'w') as f:
                assets = [
                    SupplySystems().extract_delta_feature(content_paths0['#'], content_paths1['#'], parameters)
                ]
                f.write(json.dumps(assets))

            SupplySystems().export_delta_feature(content_paths0['#'], content_paths1['#'],
                                                 parameters, export_path, result0.export_format)
        elif result0.name == 'ah_emissions':
            parameters0['building_footprints'] = download_building_footprints(result0)
            parameters0['variable'] = parameters0['district_cooling_system']

            parameters1['building_footprints'] = download_building_footprints(result1)
            parameters1['variable'] = parameters1['district_cooling_system']

            parameters = {
                'A': parameters0,
                'B': parameters1
            }

            with open(json_path, 'w') as f:
                assets = [
                    BuildingAHEmissions().extract_delta_feature(content_paths0['#'], content_paths1['#'], parameters)
                ]
                f.write(json.dumps(assets))

            BuildingAHEmissions().export_feature(content_paths0['#'], parameters, export_path, result0.export_format)
        else:
            raise ExplorerRuntimeError(f"Encountered unexpected/unsupported result '{result0.name}'/'{result1.name}'",
                                       details={
                                           'result0': result0.dict(),
                                           'result1': result1.dict(),
                                           'parameters0': parameters0,
                                           'parameters1': parameters1
                                       })

    def verify_parameters(self, project: Project, scene: Scene, parameters: dict,
                          aoi: Polygon = None) -> List[LogMessage]:
        out = []

        # do we have an area of interest?
        if aoi is None:
            out.append(LogMessage(severity='error', message=f"No area of interest."))
        else:
            # Reproject to Cylindrical equal-area for area in m2
            df = gpd.GeoDataFrame(geometry=[aoi], crs=PROJ_SYSTEM).to_crs({'proj': 'cea'})
            area = df.area[0] / 1e6  # m2 to km2

            if area > MAXIMUM_BOUNDING_AREA_KM2:
                out.append(LogMessage(severity='warning',
                                      message=f"Area selected is more than {MAXIMUM_BOUNDING_AREA_KM2},"
                                              f"the analysis might take longer than usual."))

        return out

    def get_compare_results(self, content0: dict, content1: dict) -> AnalysisCompareResults:
        normalised_results_list = list(self.normalise_parameters(content0, content1))

        # combine network results(normalised_results_list[*][0]) # and building footprint results(normalised_results_list[*][1])
        return AnalysisCompareResults(
            results0=[normalised_results_list[0][0], normalised_results_list[0][1]] if len(normalised_results_list[0]) > 1 else [normalised_results_list[0][0]],
            results1=[normalised_results_list[1][0], normalised_results_list[1][1]] if len(normalised_results_list[1]) > 1 else [normalised_results_list[1][0]],
            chart_results=[normalised_results_list[0][2]] if len(normalised_results_list[0]) > 2 else None
        )