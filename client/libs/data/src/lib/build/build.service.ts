import axios, { AxiosResponse } from 'axios';
import {
  GeojsonVisualization,
  HeatMapVisualization,
  MapVisualization,
  NetworkVisualization,
  PendingVisualization,
} from '../review/review.modal';
import {
  Scene,
  SaveSceneResponse,
  GeoType,
  SceneModule,
  SceneContext,
  ModuleUpdateResponse,
  LayerDefinition,
  ZoneConfig,
} from './build.model';

export const getGeometriesInArea = (
  projectId: string,
  geometryType: string,
  geometryId: string,
  area: string
): Promise<GeojsonVisualization> =>
  axios
    .get(
      `/geometries/${projectId}/${geometryType}?set_id=scene:${geometryId}&area=${area}`
    )
    .then((res) => res.data);

export const getGeometries = (
  signal: AbortSignal | undefined,
  projectId: string,
  geometryType: GeoType | string,
  geometryId: string | undefined,
  useCache: boolean
): Promise<GeojsonVisualization> => {
  const params = new URLSearchParams();

  if (geometryId) {
    params.append('set_id', geometryId);
  }

  if (!useCache) {
    params.append('use_cache', 'false');
  }

  return axios
    .get(`/geometries/${projectId}/${geometryType}?${params.toString()}`, {
      signal,
    })
    .then((res) => {
      // TODO: directly return string
      return res.data;
    });
};

export const getNetwork = (
  signal: AbortSignal | undefined,
  projectId: string,
  networkId: string
): Promise<NetworkVisualization> =>
  axios
    .get(`/networks/${projectId}/${networkId}`, { signal })
    .then((res) => res.data);

export const getScenes = (projectId: string): Promise<Scene[]> =>
  axios.get(`/scene/${projectId}`).then((res) => res.data);

export const saveScene = (
  projectId: string,
  name: string,
  // parameters: PairDatum,
  sceneContext: SceneContext
): Promise<SaveSceneResponse> => {
  let caz_alt_mapping = {};

  //remap zone versions to match backend
  sceneContext.zoneVersions?.forEach(
    (zone) =>
      (caz_alt_mapping = {
        ...caz_alt_mapping,
        [zone.zoneId]: zone.alternateIndex,
      })
  );

  return axios
    .post(`/scene/${projectId}`, {
      name,
      zone_config_mapping: { selection: caz_alt_mapping },
      module_settings: sceneContext.module_settings,
    })
    .then((res) => res.data);
};

export const getZoneVersions = (
  projectId: string,
  zoneId: number
): Promise<ZoneConfig[]> =>
  axios.get(`/zone_config/${projectId}/${zoneId}`).then((res) => res.data);

export const deleteScene = (
  projectId: string,
  sceneId: string
): Promise<SaveSceneResponse> =>
  axios.delete(`/scene/${projectId}/${sceneId}`).then((res) => res.data);

export const getModules = (projectId: string): Promise<SceneModule[]> =>
  axios
    .get(`/info/scene/${projectId}`)
    .then((res: AxiosResponse<SceneModule[]>) => {
      // order modules based on priority
      res.data.sort((a, b) => (a.priority < b.priority ? 1 : -1));
      return res.data;
    });

export const getModuleVisualization = (
  projectId: string,
  moduleName: string,
  parameters: SceneContext | undefined
): Promise<(MapVisualization | PendingVisualization)[]> => {
  const params = parameters
    ? { ...parameters, moduleVisLayer: undefined }
    : undefined;

  if (params) {
    const currentModule = params.module_settings[moduleName];
    if (!currentModule) {
      params.module_settings[moduleName] = {};
    }
  }

  return axios
    .get(`/module/${projectId}/${moduleName}/raster`, {
      params: { parameters: JSON.stringify(params) },
    })
    .then((res) => res.data);
};

export const updateModuleData = (
  projectId: string,
  moduleName: string,
  parameters: SceneContext | undefined
): Promise<ModuleUpdateResponse> => {
  const params = parameters
    ? { ...parameters, moduleVisLayer: undefined }
    : undefined;

  return axios
    .put(`/module/${projectId}/${moduleName}/update`, {
      parameters: params,
    })
    .then((res) => res.data);
};

export const getModuleChart = (
  projectId: string,
  moduleName: string,
  parameters: SceneContext | undefined
): Promise<HeatMapVisualization> => {
  const params = parameters
    ? { ...parameters, moduleVisLayer: undefined }
    : undefined;

  return axios
    .get(`/module/${projectId}/${moduleName}/chart`, {
      params: { parameters: JSON.stringify(params) },
    })
    .then((res) => res.data);
};

export const getView = (
  projectId: string,
  viewId: string,
  params?: URLSearchParams,
  signal?: AbortSignal
): Promise<MapVisualization[]> =>
  axios
    .get(`/view/${projectId}/${viewId}?${params?.toString()}`, { signal })
    .then((res) => res.data);
