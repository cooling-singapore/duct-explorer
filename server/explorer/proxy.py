import json
import os
import tempfile
from typing import List, Dict, Optional

from saas.rest.proxy import EndpointProxy
from saas.sdk.app.auth import User

from explorer.dots.dot import UploadPostprocessResult
from explorer.geodb import GeometryType
from explorer.meta import __endpoint_prefix__
from explorer.schemas import ExplorerInformation, ProjectMeta, Scene, AnalysesByScene, AnalysisGroup, \
    AnalysesByConfiguration, AnalysisInfo, AnalysisSpecification, BuildModuleSpecification, ExplorerDatasetInfo, \
    ZonesConfigurationMapping, ZoneConfiguration, ExplorerPublicInformation
from explorer.server import EnquireAnalysisResponse, DeleteProjectResponse, UploadDatasetResponse, \
    FetchDatasetsResponse


class ExplorerProxy(EndpointProxy):
    def __init__(self, remote_address: (str, int), user: User, password: str):
        super().__init__(__endpoint_prefix__, remote_address, (user.login, password))

        self._authority = user.keystore

    def public_info(self) -> ExplorerPublicInformation:
        results = self.get(f"public_info")
        return ExplorerPublicInformation.parse_obj(results)

    def info(self) -> ExplorerInformation:
        results = self.get(f"info")
        return ExplorerInformation.parse_obj(results)

    def get_info_analyses(self, project_id: str, scale: str = None, aoi_obj_id: str = None,
                          scene_id: str = None) -> List[AnalysisSpecification]:
        results = self.get(f"analysis/{project_id}/info", parameters={
            'scale': scale,
            'aoi_obj_id': aoi_obj_id,
            'scene_id': scene_id
        })
        return [AnalysisSpecification.parse_obj(result) for result in results]

    def get_info_scene(self, project_id: str) -> List[BuildModuleSpecification]:
        results = self.get(f"info/scene/{project_id}")
        return [BuildModuleSpecification.parse_obj(result) for result in results]

    def get_projects(self) -> List[ProjectMeta]:
        results = self.get(f"project")
        return [ProjectMeta.parse_obj(result) for result in results]

    def create_project(self, city: str, bdp_id: str, name: str) -> ProjectMeta:
        results = self.post(f"project", body={
            'city': city,
            'bdp_id': bdp_id,
            'name': name
        })
        return ProjectMeta.parse_obj(results)

    def delete_project(self, project_id: str) -> DeleteProjectResponse:
        result = self.delete(f"project/{project_id}")
        return DeleteProjectResponse.parse_obj(result)

    def fetch_datasets(self, project_id: str) -> FetchDatasetsResponse:
        result = self.get(f"dataset/{project_id}")
        return FetchDatasetsResponse.parse_obj(result)

    def get_datasets(self, project_id: str, object_id: str) -> List[Dict]:
        result = self.get(f"dataset/{project_id}/{object_id}")
        return result

    def upload_dataset(self, project_id: str, content_path: str, data_type: str) -> UploadDatasetResponse:
        body = {
            'data_type': data_type,
        }
        result = self.post(f"dataset/{project_id}", body=body, attachment_path=content_path, use_snappy=False)
        return UploadDatasetResponse.parse_obj(result)

    def update_dataset(self, project_id: str, object_id: str, args: dict,
                       geo_type: Optional[GeometryType]) -> UploadPostprocessResult:
        body = {
            'args': args,
            'geo_type': geo_type.value
        }
        result = self.put(f"dataset/{project_id}/{object_id}", body=body)
        return UploadPostprocessResult.parse_obj(result)

    def import_dataset(self, project_id: str, object_id: str, name: str,
                       args: Optional[dict] = None) -> ExplorerDatasetInfo:
        result = self.post(f"dataset/{project_id}/{object_id}", body={
            'name': name,
            'args': args
        })
        return ExplorerDatasetInfo.parse_obj(result)

    def delete_dataset(self, project_id: str, object_id: str) -> ExplorerDatasetInfo:
        result = self.delete(f"dataset/{project_id}/{object_id}")
        return ExplorerDatasetInfo.parse_obj(result)

    def add_zone_configs(self, project_id: str, config_name: str, selected_zones: List[int],
                         datasets: Dict[GeometryType, str]) -> Dict[int, ZoneConfiguration]:
        results = self.post(f"zone_config/{project_id}", body={
            'config_name': config_name,
            'selected_zones': selected_zones,
            'datasets': {key.value: value for key, value in datasets.items()}
        })
        return {int(key): ZoneConfiguration.parse_obj(value) for key, value in results['configs'].items()}

    def get_zone_configs(self, project_id: str, zone_id: int) -> List[ZoneConfiguration]:
        results = self.get(f"zone_config/{project_id}/{zone_id}")
        return [ZoneConfiguration.parse_obj(result) for result in results]

    def delete_zone_config(self, project_id: str, config_id: int) -> ZoneConfiguration:
        result = self.delete(f"zone_config/{project_id}/{config_id}")
        return ZoneConfiguration.parse_obj(result)

    def download_geometries(self, project_id: str, content_path: str, geo_type: GeometryType, set_id: str = None,
                            bbox_area: dict = None, free_area: list = None, dot: str = None,
                            use_cache: bool = True) -> None:
        if bbox_area:
            area = f"bbox:{bbox_area['west']}:{bbox_area['north']}:{bbox_area['east']}:{bbox_area['south']}"

        elif free_area:
            temp = [f"{p[0]}:{p[1]}" for p in free_area]
            area = f"free:{len(temp)}:{':'.join(temp)}"

        else:
            area = None

        self.get(f"geometries/{project_id}/{geo_type.value}", parameters={
            'set_id': set_id,
            'area': area,
            'dot': dot,
            'use_cache': str(use_cache)
        }, download_path=content_path)

    def download_network(self, project_id: str, content_path: str, network_id: str, use_cache: bool = True) -> None:
        self.get(f"networks/{project_id}/{network_id}", parameters={
            'use_cache': str(use_cache)
        }, download_path=content_path)

    def get_view(self, project_id: str, view_id: str, set_id: str = None, bbox_area: dict = None,
                 free_area: list = None, use_cache: bool = True) -> List[dict]:
        if bbox_area:
            area = f"bbox:{bbox_area['west']}:{bbox_area['north']}:{bbox_area['east']}:{bbox_area['south']}"

        elif free_area:
            temp = [f"{p[0]}:{p[1]}" for p in free_area]
            area = f"free:{len(temp)}:{':'.join(temp)}"

        else:
            area = None

        with tempfile.TemporaryDirectory() as tempdir:
            content_path = os.path.join(tempdir, 'view.json')
            self.get(f"view/{project_id}/{view_id}", parameters={
                'set_id': set_id,
                'area': area,
                'use_cache': str(use_cache)
            }, download_path=content_path)

            with open(content_path) as f:
                result = json.load(f)

        return result

    def create_scene(self, project_id: str, name: str, zone_config_mapping: ZonesConfigurationMapping,
                     module_settings: Dict) -> Scene:
        result = self.post(f"scene/{project_id}", body={
            'name': name,
            'zone_config_mapping': zone_config_mapping.dict(),
            'module_settings': module_settings
        })
        return Scene.parse_obj(result)

    def get_scenes(self, project_id: str) -> List[Scene]:
        results = self.get(f"scene/{project_id}")
        return [Scene.parse_obj(result) for result in results]

    def delete_scene(self, project_id: str, scene_id: str) -> Scene:
        result = self.delete(f"scene/{project_id}/{scene_id}")
        return Scene.parse_obj(result)

    def update_module_data(self, project_id: str, module_id: str, parameters: dict) -> dict:
        result = self.put(f"module/{project_id}/{module_id}/update", body={
            'parameters': parameters
        })
        return result

    def upload_module_data(self, project_id: str, module_id: str, attachment_path: str) -> dict:
        result = self.put(f"module/{project_id}/{module_id}/upload", attachment_path=attachment_path, use_snappy=False)
        return result

    def get_module_raster_image(self, project_id: str, module_id: str, parameters: Dict) -> List[dict]:
        parameters = json.dumps(parameters)
        result = self.get(f"module/{project_id}/{module_id}/raster", parameters={
            'parameters': parameters
        })
        return result

    def get_analyses_by_scene(self, project_id: str) -> List[AnalysesByScene]:
        results = self.get(f"analysis/{project_id}/scene")
        return [AnalysesByScene.parse_obj(result) for result in results]

    def get_analyses_by_configuration(self, project_id: str) -> List[AnalysesByConfiguration]:
        results = self.get(f"analysis/{project_id}/configuration")
        return [AnalysesByConfiguration.parse_obj(result) for result in results]

    def create_analysis_group(self, project_id: str, analysis_type: str, group_name: str,
                              parameters: Dict) -> AnalysisGroup:
        result = self.post(f"analysis/{project_id}", body={
            'analysis_type': analysis_type,
            'group_name': group_name,
            'parameters': parameters
        })
        return AnalysisGroup.parse_obj(result)

    def enquire_analysis(self, project_id: str, analysis_type: str, scene_id: str,
                         parameters: dict) -> EnquireAnalysisResponse:
        result = self.get(f"analysis/{project_id}/enquire", parameters={
            'p': json.dumps({
                'analysis_type': analysis_type,
                'parameters': parameters,
                'scene_id': scene_id
            })
        })
        return EnquireAnalysisResponse.parse_obj(result)

    def submit_analysis(self, project_id: str, group_id: str, scene_id: str, name: str) -> AnalysisInfo:
        result = self.post(f"analysis/{project_id}/submit", body={
            'group_id': group_id,
            'scene_id': scene_id,
            'name': name
        })
        return AnalysisInfo.parse_obj(result)

    def get_analysis(self, project_id: str, analysis_id: str) -> Optional[AnalysisInfo]:
        result = self.get(f"analysis/{project_id}/{analysis_id}")
        return AnalysisInfo.parse_obj(result) if result else None

    def resume_analysis(self, project_id: str, analysis_id: str) -> AnalysisInfo:
        result = self.put(f"analysis/{project_id}/{analysis_id}/resume")
        return AnalysisInfo.parse_obj(result)

    def cancel_analysis(self, project_id: str, analysis_id: str) -> AnalysisInfo:
        result = self.put(f"analysis/{project_id}/{analysis_id}/cancel")
        return AnalysisInfo.parse_obj(result)

    def delete_analysis(self, project_id: str, analysis_id: str) -> Optional[AnalysisInfo]:
        result = self.delete(f"analysis/{project_id}/{analysis_id}")
        return AnalysisInfo.parse_obj(result) if result else None

    def get_group_config(self, project_id: str, group_id: str) -> AnalysisGroup:
        result = self.get(f"analysis/{project_id}/{group_id}/config")
        return AnalysisGroup.parse_obj(result) if result else None

    def get_result(self, project_id: str, analysis_id: str, result_id: str, parameters: dict) -> Dict:
        parameters = json.dumps(parameters)

        result = self.get(f"result/{project_id}/{analysis_id}/{result_id}", parameters={
            'parameters': parameters
        })
        return result

    def get_result_delta(self, project_id: str, result_id: str, analysis_id0: str, analysis_id1: str,
                         parameters0: dict, parameters1: dict) -> Dict:
        parameters0 = json.dumps(parameters0)
        parameters1 = json.dumps(parameters1)

        result = self.get(f"result/{project_id}/delta/{result_id}/{analysis_id0}/{analysis_id1}", parameters={
            'parameters0': parameters0,
            'parameters1': parameters1
        })
        return result

    def get_result_compare(self, project_id: str, result_id: str, analysis_id0: str, analysis_id1: str,
                           parameters0: dict, parameters1: dict) -> Dict:
        parameters0 = json.dumps(parameters0)
        parameters1 = json.dumps(parameters1)

        result = self.get(f"result/{project_id}/compare/{result_id}/{analysis_id0}/{analysis_id1}", parameters={
            'parameters0': parameters0,
            'parameters1': parameters1
        })
        return result

    def export_result(self, project_id: str, analysis_id: str, result_id: str, parameters: dict,
                      download_path: str) -> None:
        parameters = json.dumps(parameters)
        self.get(f"export/{project_id}/{analysis_id}/{result_id}", parameters={
            'parameters': parameters
        }, download_path=download_path)

    def export_result_delta(self, project_id: str, result_id: str, analysis_id0: str, analysis_id1: str,
                            parameters0: dict, parameters1: dict, download_path: str) -> None:
        parameters0 = json.dumps(parameters0)
        parameters1 = json.dumps(parameters1)
        self.get(f"export/{project_id}/{result_id}/{analysis_id0}/{analysis_id1}", parameters={
            'parameters0': parameters0,
            'parameters1': parameters1
        }, download_path=download_path)
