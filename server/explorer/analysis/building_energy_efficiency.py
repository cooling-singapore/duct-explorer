import json
import os
import zipfile
from typing import List, Dict, Optional

import geopandas as gpd
from saas.core.logging import Logging
from saas.dor.schemas import DataObject
from saas.sdk.base import SDKContext, LogMessage, SDKProductSpecification, SDKCDataObject
from shapely.geometry import Polygon

from explorer.dots.duct_bemcea import BuildingAHEmissions, aggregate_ah_data, BuildingAnnualEnergy, BuildingAnnualGeneration
from explorer.dots.duct_bld_eff_std import BuildingEfficiencyStandard
from explorer.exceptions import DUCTRuntimeError
from explorer.analysis.base import Analysis, AnalysisContext, AnalysisStatus
from explorer.cache import CachedJSONObject
from explorer.geodb import GeometryType
from explorer.project import Project
from explorer.schemas import AnalysisGroup, Scene, AnalysisResult, ExplorerRuntimeError, AnalysisSpecification, \
    ExplorerDatasetInfo, AnalysisCompareResults

logger = Logging.get('explorer.analysis.building_energy_efficiency')

PROJ_SYSTEM = "epsg:4326"
MAXIMUM_BOUNDING_AREA_KM2 = 5.0
DEFAULT_WEATHER = "Singapore-Changi_1990_2010_TMY.epw"
DEFAULT_BUILDING_TYPE_MAP = {
    "COOLROOM": ["industrial:3"],
    "FOODSTORE": ["commercial:4"],
    "GYM": ["commercial:10"],
    "HOSPITAL": ["commercial:9"],
    "HOTEL": ["commercial:2"],
    "INDUSTRIAL": ["industrial:1"],
    "LAB": ["commercial:6"],
    "LIBRARY": ["commercial:8"],
    "MULTI_RES": ["residential:1"],
    "MUSEUM": ["commercial:8"],
    "OFFICE": ["commercial:1"],
    "PARKING": ["commercial:12"],
    "RESTAURANT": ["commercial:5"],
    "RETAIL": ["commercial:3"],
    "SCHOOL": ["commercial:7"],
    "SERVERROOM": ["industrial:2"],
    "SINGLE_RES": ["residential:2"],
    "SWIMMING": ["commercial:10"],
    "UNIVERSITY": ["commercial:6"]
}


def get_building_standard_by_input(building_type: str, efficiency_standards: Dict[str, str]) -> str:
    if building_type not in efficiency_standards:
        raise KeyError(f"Building type '{building_type}' doesn't support customized efficiency standards.")
    input_type = efficiency_standards[building_type]
    if input_type == 'high':
        if building_type.upper() == 'RESIDENTIAL':
            return 'RES_CONDO_SLE'
        else:
            return f'{building_type.upper()}_SLE'
    elif input_type.startswith('CUSTOM'):
        splitted_input_list = input_type.split(':')
        if len(splitted_input_list) != 2 or splitted_input_list[0] != 'CUSTOM':
            raise ValueError(f'Input value of a custom efficiency standard should be of pattern "CUSTOM:object ID", but {input_type} given.')
        return f'{building_type.upper()}_CUSTOM_{splitted_input_list[1]}'
    else:
        if building_type.upper() == 'RESIDENTIAL':
            return 'RES_CONDO_BASELINE'
        else:
            return f'{building_type.upper()}_BASELINE'


def generate_building_types(efficiency_standards: Dict[str, str]) -> Dict[str, str]:
    temp_dict = DEFAULT_BUILDING_TYPE_MAP.copy()

    office_type = get_building_standard_by_input('office', efficiency_standards)
    temp_dict[office_type] = temp_dict.pop('OFFICE')

    residential_type = get_building_standard_by_input('residential', efficiency_standards)
    temp_dict[residential_type] = temp_dict.pop('MULTI_RES')

    hotel_type = get_building_standard_by_input('hotel', efficiency_standards)
    temp_dict[hotel_type] = temp_dict.pop('HOTEL')

    retail_type = get_building_standard_by_input('retail', efficiency_standards)
    temp_dict[retail_type] = temp_dict.pop('RETAIL')

    return temp_dict


def generate_building_standards(efficiency_standards: Dict[str, str]) -> Dict[str, str]:
    office_standard = get_building_standard_by_input('office', efficiency_standards)
    residential_standard = get_building_standard_by_input('residential', efficiency_standards)
    hotel_standard = get_building_standard_by_input('hotel', efficiency_standards)
    retail_standard = get_building_standard_by_input('retail', efficiency_standards)

    return {
        office_standard: DEFAULT_BUILDING_TYPE_MAP["OFFICE"],
        residential_standard: DEFAULT_BUILDING_TYPE_MAP["MULTI_RES"],
        hotel_standard: DEFAULT_BUILDING_TYPE_MAP["HOTEL"],
        retail_standard: DEFAULT_BUILDING_TYPE_MAP["RETAIL"]
    }


def determine_building_footprints(context: AnalysisContext, area: Polygon, scene: Scene) -> SDKCDataObject:
    """
    Determine area of interest as polygon and obtain the building footprint for this area
    """

    geojson = context.geometries(GeometryType.building, f'scene:{scene.id}', area=area)

    # sort features into eligible/ineligible features
    eligible_features = []
    ineligible_features = []
    for feature in geojson['features']:
        # use building id as 'name' since CEA treats names as ids
        feature['properties']['actual_name'] = feature['properties']['name']
        feature['properties']['name'] = str(feature['properties']['id'])

        # filter eligible geometries
        geometry = feature['geometry']
        if geometry['type'] == 'MultiPolygon':
            if len(geometry['coordinates']) == 1:
                geometry['type'] = 'Polygon'
                geometry['coordinates'] = geometry['coordinates'][0]

                eligible_features.append(feature)
            else:
                logger.warning(f"multipolygon building feature cannot be converted: {feature}")
                ineligible_features.append(feature)

        elif geometry['type'] == 'Polygon':
            eligible_features.append(feature)

        else:
            logger.error(f"unsupported geometry type in building feature: {feature}")

    # use eligible features only
    geojson['features'] = eligible_features

    # store the ineligible features
    with open(os.path.join(context.analysis_path, 'ineligible_buildings.json'), 'w') as f:
        json.dump(ineligible_features, f, indent=2)

    # store the geojson with eligible features only
    building_footprints_path = os.path.join(context.analysis_path, 'eligible_buildings.geojson')
    with open(building_footprints_path, 'w') as f:
        json.dump(geojson, f, indent=2)

    # upload the building geometries to the DOR
    bf_obj: SDKCDataObject = context.sdk.upload_content(
        building_footprints_path, 'DUCT.GeoVectorData', 'geojson', False
    )

    return bf_obj


def generate_building_ah_profiles(bld_ah_obj: SDKCDataObject, context: AnalysisContext,
                                  group: AnalysisGroup, scene: Scene) -> None:

    # download the data
    bld_ah_path = os.path.join(context.analysis_path, f"{bld_ah_obj.meta.obj_id}_ah_emissions.csv")
    bld_ah_obj.download(bld_ah_path)

    # aggregate the data
    data: Dict[str, Dict[str, List[float]]] = aggregate_ah_data(bld_ah_path)

    # write the various profiles
    for profile_name in data.keys():
        profile_path = os.path.join(context.analysis_path, f"{profile_name}.bld_ah_profile.csv")
        with open(profile_path, 'w') as f:
            f.write(f"building_id, AH_0:KW, AH_1:KW, AH_2:KW, AH_3:KW, AH_4:KW, AH_5:KW, AH_6:KW, AH_7:KW, AH_8:KW, "
                    f"AH_9:KW, AH_10:KW, AH_11:KW, AH_12:KW, AH_13:KW, AH_14:KW, AH_15:KW, AH_16:KW, AH_17:KW, "
                    f"AH_18:KW, AH_19:KW, AH_20:KW, AH_21:KW, AH_22:KW, AH_23:KW\n")

            buildings: Dict[str, List[float]] = data[profile_name]
            for bld_id, profile in buildings.items():
                profile = [str(v) for v in profile]
                profile = ', '.join(profile)
                f.write(f"{bld_id}, {profile}\n")

        # upload to DOR and tag accordingly
        profile_obj = context.sdk.upload_content(profile_path, 'duct.building-ah-profile', 'csv', False, False)
        profile_obj.update_tags([
            DataObject.Tag(key='aoi_obj_id', value=context.aoi_obj_id()),
            DataObject.Tag(key='group_name', value=group.name),
            DataObject.Tag(key='scene_id', value=scene.id),
            DataObject.Tag(key='analysis_id', value=context.analysis_id),
            DataObject.Tag(key='scene_name', value=scene.name),
            DataObject.Tag(key='profile_name', value=profile_name)
        ])


class BuildingEnergyEfficiency(Analysis):
    def name(self) -> str:
        return "building-energy-and-photovoltaics"

    def label(self) -> str:
        return "Building Energy & Photovoltaics"

    def type(self) -> str:
        return 'micro'

    def specification(self, project, sdk: SDKContext, aoi_obj_id: str = None,
                      scene_id: str = None) -> AnalysisSpecification:
        # define default efficiency standards
        eff_standards = {
            "office": {
                "type": "string",
                "title": "Office building efficiency",
                "enum": ["standard", "high"],
                "enumNames": ["Standard Efficiency", "High Efficiency"],
                "default": "standard"
            },
            "residential": {
                "type": "string",
                "title": "Residential building efficiency",
                "enum": ["standard", "high"],
                "enumNames": ["Standard Efficiency", "High Efficiency"],
                "default": "standard"
            },
            "commercial": {
                "type": "string",
                "title": "Commercial building efficiency",
                "enum": ["standard", "high"],
                "enumNames": ["Standard Efficiency", "High Efficiency"],
                "default": "standard"
            },
            "hotel": {
                "type": "string",
                "title": "Hotel building efficiency",
                "enum": ["standard", "high"],
                "enumNames": ["Standard Efficiency", "High Efficiency"],
                "default": "standard"
            },
            "retail": {
                "type": "string",
                "title": "Retail building efficiency",
                "enum": ["standard", "high"],
                "enumNames": ["Standard Efficiency", "High Efficiency"],
                "default": "standard"
            },
            "other": {
                "type": "string",
                "title": "Other building efficiency",
                "enum": ["standard", "high"],
                "enumNames": ["Standard Efficiency", "High Efficiency"],
                "default": "standard"
            }
        }

        # get all available BuildingEfficiencyStandard datasets and process them
        available: List[ExplorerDatasetInfo] = list(project.info.datasets.values()) if project.info.datasets else []
        for dataset in available:
            # skip irrelevant datasets
            if dataset.type != BuildingEfficiencyStandard.DATA_TYPE:
                continue

            # determine building type
            building_type = dataset.extra.get('building_type')
            if building_type is None:
                logger.warning(f"No building type specified in dataset '{dataset.name}' -> ignoring")
                continue

            # is it a supported building type?
            if building_type not in eff_standards:
                logger.warning(f"Building type '{building_type}' not supported by analysis -> ignoring")
                continue

            # add the efficiency standard
            eff_standards[building_type]['enum'].append(f"obj_id:{dataset.obj_id}")
            eff_standards[building_type]['enumNames'].append(dataset.name)

        return AnalysisSpecification.parse_obj({
            "name": self.name(),
            "label": self.label(),
            "type": self.type(),
            "area_selection": True,
            "parameters_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "title": "Configuration Name"},
                    "efficiency_standards": {
                        "title": "Efficiency Standards",
                        "description": "",
                        "type": "object",
                        "properties": eff_standards,
                        "required": []
                    },
                    "pv": {
                        "title": "Add photovoltaic (PV) panels",
                        "type": "boolean",
                        "default": False
                    }
                },
                "allOf": [
                    {
                        "if": {
                            "properties": {
                                "pv": {
                                    "const": True
                                }
                            }
                        },
                        "then": {
                            "properties": {
                                "pv_parameters": {
                                    "title": "PV parameters",
                                    "type": "object",
                                    "properties": {
                                        "roof": {
                                            "title": "PV on Roof",
                                            "description": "If panels are considered on roof surfaces",
                                            "type": "boolean",
                                            "default": True
                                        },
                                        "walls": {
                                            "title": "PV on Walls",
                                            "description": "If panels are considered on wall surfaces",
                                            "type": "boolean",
                                            "default": True
                                        },
                                        "annual_radiation_threshold": {
                                            "title": "Annual Radiation Threshold",
                                            "description": "Only consider panels on surfaces that receive radiation above the defined threshold [kWh/m2/yr]",
                                            "type": "number",
                                            "default": 800
                                        },
                                        "custom_tilt_angle": {
                                            "title": "Custom Tilt Angle",
                                            "description": "Calculate solar panel potential based on a user-specified panel tilt angle. If False, the optimal tilt angle will be used for the calculation.",
                                            "type": "boolean",
                                            "default": False
                                        },
                                        "tilt_angle": {
                                            "title": "Tilt Angle",
                                            "description": "Solar panel tilt angle if using user-defined tilt angle. Only considered if `custom_tilt_angle` parameter is True.",
                                            "type": "number",
                                            "default": 10
                                        },
                                        "max_roof_coverage": {
                                            "title": "Maximum Roof Coverage",
                                            "description": "Maximum panel coverage [m2/m2] of roof surfaces that reach minimum irradiation threshold (valid values between 0 and 1).",
                                            "type": "number",
                                            "default": 1.0
                                        },
                                        "type_pv": {
                                            "title": "Type of PV",
                                            "description": "",
                                            "type": "string",
                                            "enum": [
                                                "Generic monocrystalline",
                                                "Generic polycrystalline",
                                                "Generic amorphous silicon"
                                            ],
                                            "default": "Generic monocrystalline"
                                        }
                                    },
                                }
                            }
                        }
                    }
                ],
                "required": ["name", "efficiency_standards", "pv"],
            },
            "description": "This feature estimates the energy efficiency of different building designs in a selected "
                           "area. Based on the building`s attributes (3D geometry, type, and standard), "
                           "a physics-based building energy model is used to calculate the annual building energy "
                           "demand. The final output of this analysis includes derived energy efficiency metrics ("
                           "e.g., Energy Use Intensity and Energy Efficiency Index) at the building and district "
                           "levels. The tool can be used to compare building energy of different scenes, as well as "
                           "to evaluate the criteria of guidelines and standards (e.g., Green Marks, SLE).<br><br>"
                           "To view more information about the database behind each building type and "
                           "their efficiency standards, please click "
                           "<a href='./assets/efficiency-standard-defs/energy-efficiency-database.pdf' target='_blank'>here</a>.",
            "further_information": "This analysis is based on a model developed by <a "
                                   "href='mailto:luis.santos@tum-create.edu.sg'>Luis Santos</a> and <a "
                                   "href='mailto:reynold.mok@sec.ethz.ch'>Reynold Mok</a>. The SaaS adapter for this "
                                   "model has been developed by <a href='mailto:reynold.mok@sec.ethz.ch'>Reynold "
                                   "Mok</a>. For more information, please contact the respective authors.",
            "sample_image": self.name()+'.png',
            "ui_schema": {
                "pv_parameters": {
                    "roof": {
                        "ui:widget": "select"
                    },
                    "walls": {
                        "ui:widget": "select"
                    },
                    "custom_tilt_angle": {
                        "ui:widget": "select"
                    }
                }
            },
            "required_processors": ["bem-cea-gen", "bem-cea-sim"],
            "required_bdp": [],
            "result_specifications": {}
        })

    @staticmethod
    def _submit_gen_job(context: AnalysisContext, efficiency_standards: dict,
                        building_footprints: SDKCDataObject, bld_eff_standards: SDKCDataObject) -> str:
        # find the processor
        proc = context.sdk.find_processor_by_name('bem-cea-gen')
        if proc is None:
            raise DUCTRuntimeError(f"Processor 'bem-cea-gen' not found.")

        # submit the job
        inputs = {
            'parameters': {
                'building_type_mapping': generate_building_types(efficiency_standards),
                "default_building_type": "MULTI_RES",
                "building_standard_mapping": generate_building_standards(efficiency_standards),
                "default_building_standard": "STANDARD1",
                'commit_id': '9e778e6b797e076bf24ab3bfbf5c2ebbeaf63a1e',  # branch: CEA-for-DUCT-DC-module
                "database_name": "SG_SLE",
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
                          name=f"{context.analysis_id}.gen",
                          description=f"job part of analysis {context.analysis_id}")

        return job.content.id

    @staticmethod
    def _submit_sim_job(context: AnalysisContext, cea_run_package: SDKCDataObject,
                        cea_databases: SDKCDataObject, pv_parameters: Optional[Dict]) -> str:
        # find the processor
        proc = context.sdk.find_processor_by_name('bem-cea-sim')
        if proc is None:
            raise DUCTRuntimeError(f"Processor 'bem-cea-sim' not found.")

        # submit the job
        inputs = {
            'cea_run_package': cea_run_package,
            'cea_databases': cea_databases,
            'parameters': {
                'pv': pv_parameters
            } if pv_parameters is not None else {}
        }

        outputs = {
            name: SDKProductSpecification(
                restricted_access=False,
                content_encrypted=False,
                target_node=context.sdk.dor()
            ) for name in ['annual_energy_demand', 'pv_potential', 'ah_emissions']
        }

        job = proc.submit(inputs, outputs,
                          name=f"{context.analysis_id}.sim",
                          description=f"job part of analysis {context.analysis_id}")

        return job.content.id

    def perform_analysis(self, group: AnalysisGroup, scene: Scene, context: AnalysisContext) -> List[AnalysisResult]:
        self_tracker_name = 'bee.perform_analysis'
        context.add_update_tracker(self_tracker_name, 10)

        checkpoint, args, status = context.checkpoint()
        if status == AnalysisStatus.RUNNING and checkpoint == 'initialised':
            context.update_progress(self_tracker_name, 10)

            # determine eff standards and pv parameters
            efficiency_standards = group.parameters["efficiency_standards"]
            pv_parameters = group.parameters["pv_parameters"] if group.parameters["pv"] else None

            context.update_message(LogMessage(
                severity='info', message=f"BEE using PV parameters: {'yes' if pv_parameters else 'no'}"
            ))

            # determine building footprints
            bf_obj = determine_building_footprints(context, context.area_of_interest(), scene)

            checkpoint, args, status = context.update_checkpoint('submit-gen-job', {
                'bf_obj_id': bf_obj.meta.obj_id,
                'pv_parameters': pv_parameters if pv_parameters else {},
                'efficiency_standards': efficiency_standards
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'submit-gen-job':
            context.update_progress(self_tracker_name, 20)
            context.update_message(LogMessage(
                severity='info', message="Submitting 'cea-gen' job..."
            ))

            # find the building footprints data object
            bf_obj = context.sdk.find_data_object(args['bf_obj_id'])

            # check if any of the standards are custom
            bld_eff_std_path = os.path.join(context.analysis_path, f"bld_eff_std_package.zip")
            with zipfile.ZipFile(bld_eff_std_path, 'w') as f:
                for category in ['office', 'residential', 'hotel', 'retail']:
                    name = args['efficiency_standards'][category]
                    if name.startswith('obj_id:'):
                        # find the object
                        _, obj_id = name.split(':')
                        obj = context.sdk.find_data_object(obj_id)
                        if obj is None:
                            raise ExplorerRuntimeError(f"Energy efficiency standard object '{obj_id}' not found.")

                        # download the object
                        download_path = os.path.join(context.analysis_path, f"{obj.meta.obj_id}.csv")
                        obj.download(download_path)

                        # add it to the zip file
                        f.write(download_path, os.path.basename(download_path))

                        # replace the object id with the file path
                        args['efficiency_standards'][category] = f"CUSTOM:{obj.meta.obj_id}"

            # upload the bld eff package to the DOR
            bes_obj = context.sdk.upload_content(bld_eff_std_path, 'BEMCEA.BldEffStandards', 'zip', False)

            # submit the gen job
            job_id_gen = self._submit_gen_job(context, args['efficiency_standards'], bf_obj, bes_obj)

            checkpoint, args, status = context.update_checkpoint('waiting-for-gen', {
                'bf_obj_id': bf_obj.meta.obj_id,
                'pv_parameters': args['pv_parameters'],
                'job_id_gen': job_id_gen
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'waiting-for-gen':
            context.update_progress(self_tracker_name, 30)
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
                'pv_parameters': args['pv_parameters'],
                'cea_run_package': outputs['cea_run_package'].meta.obj_id,
                'cea_databases': outputs['cea_databases'].meta.obj_id
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'submit-sim-job':
            context.update_progress(self_tracker_name, 40)
            context.update_message(LogMessage(
                severity='info', message="Submitting for 'cea-sim' job..."
            ))

            pv_parameters = args['pv_parameters'] if args['pv_parameters'] else None

            cea_run_package = context.sdk.find_data_object(args['cea_run_package'])
            if cea_run_package is None:
                raise DUCTRuntimeError(f"Required input for cea-sim missing: cea_run_package")

            cea_databases = context.sdk.find_data_object(args['cea_databases'])
            if cea_databases is None:
                raise DUCTRuntimeError(f"Required input for cea-sim missing: cea_databases")

            # submit the gen job
            job_id_sim = self._submit_sim_job(context, cea_run_package, cea_databases, pv_parameters)

            checkpoint, args, status = context.update_checkpoint('waiting-for-sim', {
                'bf_obj_id': args['bf_obj_id'],
                'pv_parameters': pv_parameters if pv_parameters else {},
                'job_id_sim': job_id_sim
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'waiting-for-sim':
            context.update_progress(self_tracker_name, 50)
            job_id_sim = args['job_id_sim']
            context.update_message(LogMessage(
                severity='info', message=f"Waiting for 'cea-sim' job {job_id_sim}"
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
                'pv_parameters': args['pv_parameters'],
                'annual_energy_demand': outputs['annual_energy_demand'].meta.obj_id,
                'pv_potential': outputs['pv_potential'].meta.obj_id,
                'ah_emissions': outputs['ah_emissions'].meta.obj_id
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'simulation-done':
            context.update_progress(self_tracker_name, 80)
            context.update_message(LogMessage(
                severity='info', message="Collecting results..."
            ))

            # do we have all the expected outputs?
            missing = []
            for expected in ['bf_obj_id', 'annual_energy_demand', 'pv_parameters', 'ah_emissions']:
                if expected not in args:
                    missing.append(expected)
            if missing:
                raise DUCTRuntimeError(f"Expected outputs missing: {missing}")

            # get the object ids
            bf_obj_id = args['bf_obj_id']
            annual_energy_demand_obj_id = args['annual_energy_demand']
            pv_potential_obj_id = args['pv_potential'] if args['pv_potential'] else None
            ah_emissions_obj_id = args['ah_emissions']

            results = [
                AnalysisResult.parse_obj({
                    'name': 'energy_consumption',
                    'obj_id': {'#': annual_energy_demand_obj_id},
                    'label': 'Annual Energy Consumption',
                    'specification': {
                        'description': 'The annual energy consumption can be used as an indicator of the building’s '
                                       'energy efficiency.',
                        'parameters': {}
                    },
                    'export_format': 'geojson',
                    'extras': {
                        'bf_obj_id': bf_obj_id
                    }
                }),
                AnalysisResult.parse_obj({
                    'name': 'energy_use_intensity',
                    'obj_id': {'#': annual_energy_demand_obj_id},
                    'label': 'Energy Use Intensity (EUI)',
                    'specification': {
                        'description': 'Energy Use Intensity (EUI) is the normalization of annual energy consumption '
                                       'by the GFA of the building.',
                        'parameters': {}
                    },
                    'export_format': 'geojson',
                    'extras': {
                        'bf_obj_id': bf_obj_id
                    }
                }),
                AnalysisResult.parse_obj({
                    'name': 'energy_efficiency_index',
                    'obj_id': {'#': annual_energy_demand_obj_id},
                    'label': 'Energy Efficiency Index (EEI)',
                    'specification': {
                        'description': 'Energy Efficiency Index (EEI) is the normalization of EUI by weekly operating '
                                       'hours of commercial spaces.',
                        'parameters': {}
                    },
                    'export_format': 'geojson',
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
                                'hour': {
                                    'title': 'Hour',
                                    'type': 'number',
                                    'enum': [i for i in range(24)],
                                    'default': 1
                                },
                            },
                            'required': ['hour']
                        }
                    },
                    'export_format': 'geojson',
                    'extras': {
                        'bf_obj_id': bf_obj_id
                    }
                }),
            ]

            if pv_potential_obj_id is not None:
                results.extend([
                    AnalysisResult.parse_obj({
                        'name': 'energy_generation',
                        'obj_id': {'#': pv_potential_obj_id},
                        'label': 'Annual Energy Generation',
                        'specification': {
                            'description': 'The total annual energy generation per building from photovoltaic (PV) '
                                           'panels.',
                            'parameters': {}
                        },
                        'export_format': 'geojson',
                        'extras': {
                            'bf_obj_id': bf_obj_id
                        }
                    }),
                    AnalysisResult.parse_obj({
                        'name': 'energy_generation_intensity',
                        'obj_id': {'#': pv_potential_obj_id},
                        'label': 'Energy Generation Intensity (EGI)',
                        'specification': {
                            'description': 'Energy Generation Intensity (EGI) is EGI is the normalization of annual '
                                           'energy generation by its GFA.',
                            'parameters': {}
                        },
                        'export_format': 'geojson',
                        'extras': {
                            'bf_obj_id': bf_obj_id
                        }
                    }),
                    AnalysisResult.parse_obj({
                        'name': 'generation_consumption_ratio',
                        'obj_id': {'#': pv_potential_obj_id},
                        'label': 'Generation/Consumption Ratio',
                        'specification': {
                            'description': 'Generation/Consumption is EGI/EUI',
                            'parameters': {}
                        },
                        'export_format': 'geojson',
                        'extras': {
                            'bf_obj_id': bf_obj_id
                        }
                    })
                ])

            context.update_progress(self_tracker_name, 100)
            context.update_message(LogMessage(
                severity='info', message="Done."
            ))

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

        if result.name in ['energy_consumption', 'energy_use_intensity', 'energy_efficiency_index']:
            parameters['building_footprints'] = download_building_footprints()
            parameters['variable'] = result.name
            with open(json_path, 'w') as f:
                assets = BuildingAnnualEnergy().extract_feature(content_paths['#'], parameters)
                f.write(json.dumps(assets))

            BuildingAnnualEnergy().export_feature(content_paths['#'], parameters, export_path, result.export_format)

        elif result.name in ['energy_generation', 'energy_generation_intensity', 'generation_consumption_ratio']:
            parameters['building_footprints'] = download_building_footprints()
            parameters['variable'] = result.name
            with open(json_path, 'w') as f:
                assets = BuildingAnnualGeneration().extract_feature(content_paths['#'], parameters)
                f.write(json.dumps(assets))

            BuildingAnnualGeneration().export_feature(content_paths['#'], parameters, export_path, result.export_format)

        elif result.name == 'ah_emissions':
            parameters['building_footprints'] = download_building_footprints()
            parameters['variable'] = 'base_TES'
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
        # check if the result names are identical
        if result0.name != result1.name:
            raise DUCTRuntimeError(f"Mismatching result names: {result0.name} != {result1.name}")

        if result0.name in ['energy_consumption', 'energy_use_intensity', 'energy_efficiency_index']:
            parameters = {
                'A': parameters0,
                'B': parameters1
            }

            # download and read building footprints
            bf_obj_path0 = os.path.join(project.info.temp_path, result0.extras['bf_obj_id'])
            bf_obj0 = sdk.find_data_object(result0.extras['bf_obj_id'])
            bf_obj0.download(bf_obj_path0)

            bf_obj_path1 = os.path.join(project.info.temp_path, result1.extras['bf_obj_id'])
            bf_obj1 = sdk.find_data_object(result1.extras['bf_obj_id'])
            bf_obj1.download(bf_obj_path1)

            with open(bf_obj_path0, 'r') as f:
                parameters['A']['building_footprints'] = json.load(f)
                parameters['A']['variable'] = result0.name

            # delete the temporary file
            os.remove(bf_obj_path0)

            with open(bf_obj_path1, 'r') as f:
                parameters['B']['building_footprints'] = json.load(f)
                parameters['B']['variable'] = result0.name
            # delete the temporary file
            os.remove(bf_obj_path1)

            with open(json_path, 'w') as f:
                assets = [
                    BuildingAnnualEnergy().extract_delta_feature(content_paths0['#'], content_paths1['#'],
                                                                      parameters)
                ]
                f.write(json.dumps(assets))

            BuildingAnnualEnergy().export_delta_feature(content_paths0['#'], content_paths1['#'],
                                                        parameters, export_path, result0.export_format)

        elif result0.name in ['energy_generation', 'energy_generation_intensity', 'generation_consumption_ratio']:
            parameters = {
                'A': parameters0,
                'B': parameters1
            }

            # download and read building footprints
            bf_obj_path0 = os.path.join(project.info.temp_path, result0.extras['bf_obj_id'])
            bf_obj0 = sdk.find_data_object(result0.extras['bf_obj_id'])
            bf_obj0.download(bf_obj_path0)

            bf_obj_path1 = os.path.join(project.info.temp_path, result1.extras['bf_obj_id'])
            bf_obj1 = sdk.find_data_object(result1.extras['bf_obj_id'])
            bf_obj1.download(bf_obj_path1)

            with open(bf_obj_path0, 'r') as f:
                parameters['A']['building_footprints'] = json.load(f)
                parameters['A']['variable'] = result0.name
            # delete the temporary file
            os.remove(bf_obj_path0)

            with open(bf_obj_path1, 'r') as f:
                parameters['B']['building_footprints'] = json.load(f)
                parameters['B']['variable'] = result0.name
            # delete the temporary file
            os.remove(bf_obj_path1)

            with open(json_path, 'w') as f:
                assets = [
                    BuildingAnnualGeneration().extract_delta_feature(content_paths0['#'],
                                                                          content_paths1['#'],
                                                                          parameters)
                ]
                f.write(json.dumps(assets))

            BuildingAnnualGeneration().export_delta_feature(content_paths0['#'], content_paths1['#'],
                                                            parameters, export_path, result0.export_format)

        elif result0.name == 'ah_emissions':
            parameters = {
                'A': parameters0,
                'B': parameters1
            }

            # download and read building footprints
            bf_obj_path0 = os.path.join(project.info.temp_path, result0.extras['bf_obj_id'])
            bf_obj0 = sdk.find_data_object(result0.extras['bf_obj_id'])
            bf_obj0.download(bf_obj_path0)

            bf_obj_path1 = os.path.join(project.info.temp_path, result1.extras['bf_obj_id'])
            bf_obj1 = sdk.find_data_object(result1.extras['bf_obj_id'])
            bf_obj1.download(bf_obj_path1)

            with open(bf_obj_path0, 'r') as f:
                parameters['A']['building_footprints'] = json.load(f)
                parameters['A']['variable'] = 'base_TES'
            # delete the temporary file
            os.remove(bf_obj_path0)

            with open(bf_obj_path1, 'r') as f:
                parameters['B']['building_footprints'] = json.load(f)
                parameters['B']['variable'] = 'base_TES'
            # delete the temporary file
            os.remove(bf_obj_path1)

            with open(json_path, 'w') as f:
                assets = [
                    BuildingAHEmissions().extract_delta_feature(content_paths0['#'], content_paths1['#'],
                                                                     parameters)
                ]
                f.write(json.dumps(assets))

            BuildingAHEmissions().export_delta_feature(content_paths0['#'], content_paths1['#'],
                                                       parameters, export_path, result0.export_format)

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
            # check the number of buildings
            buildings: CachedJSONObject = project.geometries(GeometryType.building, f'scene:{scene.id}', area=aoi)
            buildings: dict = buildings.content()
            buildings: List[dict] = buildings['features']
            if len(buildings) > 100:
                out.append(LogMessage(severity='warning',
                                      message=f"Area of interest includes {len(buildings)} buildings. The simulation "
                                              f"may fail. Consider using an area of interest with less than 100 "
                                              f"buildings."))

            # Reproject to Cylindrical equal-area for area in m2
            df = gpd.GeoDataFrame(geometry=[aoi], crs=PROJ_SYSTEM).to_crs({'proj': 'cea'})
            area = df.area[0] / 1e6  # m2 to km2

            if area > MAXIMUM_BOUNDING_AREA_KM2:
                out.append(LogMessage(severity='warning',
                                      message=f"Area selected is more than {MAXIMUM_BOUNDING_AREA_KM2},"
                                              f"the analysis might take longer than usual."))

        return out

    def normalise_parameters(self, content0: dict, content1: dict) -> (Dict, Dict):
        existing_range_values = []

        # get existing min/ max values from the results
        def get_range_values(content: dict):
            for item in content:
                if item['type'] == 'geojson':
                    for variable in item['renderer']['visualVariables']:
                        if variable['type'] == 'color':
                            for stop in variable['stops']:
                                existing_range_values.append(stop['value'])
                        else:
                            continue
                else:
                    continue

        # update the results with normalised min/ max values
        def update_range_values(content: tuple, min: int, max: int):
            for item in content:
                if item['type'] == 'geojson':
                    for variable in item['renderer']['visualVariables']:
                        if variable['type'] == 'color':
                            if variable['stops'][0]['value'] > variable['stops'][1]['value']:
                                variable['stops'][0]['value'] = max
                                variable['stops'][0]['label'] = max
                                variable['stops'][1]['value'] = min
                                variable['stops'][1]['label'] = min
                            else:
                                variable['stops'][0]['value'] = min
                                variable['stops'][0]['label'] = min
                                variable['stops'][1]['value'] = max
                                variable['stops'][1]['label'] = max
                        else:
                            continue
                else:
                    continue

        # get min/ max values of results
        get_range_values(content0)
        get_range_values(content1)

        # update the results only there are existing range values
        # (existing range values will be available only if contents are geojsons)
        if len(existing_range_values) > 0:
            # extract maximum range from the existing min/ max values
            min_value = min(existing_range_values)
            max_value = max(existing_range_values)

            # update the results with new min/ max values
            update_range_values(content0, min_value, max_value)
            update_range_values(content1, min_value, max_value)

        return content0, content1

    def get_compare_results(self, content0: dict, content1: dict) -> AnalysisCompareResults:
        all_chart_results = []

        normalised_results_list = list(self.normalise_parameters(content0, content1))

        # if both A and B results have charts, merge charts to represent results in a single chart
        if len(normalised_results_list[0]) > 1 and len(normalised_results_list[1]) > 1:
            # get bar chart datasets
            chart_1_data = normalised_results_list[0][1]['data']['datasets']
            chart_2_data = normalised_results_list[1][1]['data']['datasets']

            # update bar chart style and legend labels according to the result suffix
            def update_line_chart_labels_and_style(chart_data: dict, suffix: str):
                for dataset in chart_data:
                    # add suffix to legend labels to differentiate A and B
                    dataset['label'] = f'Analysis Run {suffix}'
                    # change bar colours to displayed result B in a different colour
                    if suffix == 'B':
                        dataset['backgroundColor'] = '#75e8b9'

                return chart_data

            combined_result_chart = normalised_results_list[0][1]
            combined_result_chart['options']['plugins']['title']['text'] = chart_1_data[0]['label']

            # merge both datasets to display both results in a single chart
            combined_result_chart['data']['datasets'] = update_line_chart_labels_and_style(chart_1_data, 'A') + \
                                                        update_line_chart_labels_and_style(chart_2_data, 'B')

            all_chart_results.append(combined_result_chart)

        return AnalysisCompareResults(
            results0=[normalised_results_list[0][0]],
            results1=[normalised_results_list[1][0]],
            chart_results=all_chart_results
        )

