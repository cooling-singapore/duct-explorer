import axios from 'axios';
import {
  AnalyseForm,
  Analysis,
  AnalysisConfigItemByConfig,
  AnalysisConfigItemByScene,
  AnalysisConfigResponse,
  AnalysisCost,
  AnalysisFormType,
  AnalysisListItem,
  AnalysisScale,
  AnalysisStatus,
  GroupedAnalyses,
} from './analysis.model';

export const getAnalyses = (
  projectId: string,
  params?: AnalyseForm
): Promise<GroupedAnalyses> => {
  let mappedParams = undefined;
  if (params?.aoi_obj_id && params?.scene.id) {
    mappedParams = {
      scale: params.scale,
      scene_id: params.scene.id,
      aoi_obj_id: params.aoi_obj_id,
    };
  }

  return axios
    .get<Analysis[]>(`/analysis/${projectId}/info`, { params: mappedParams })
    .then((res) => {
      const mesoAnalyses: Analysis[] = [];
      const microAnalyses: Analysis[] = [];
      res.data.forEach((analysis) => {
        if (analysis.type === AnalysisScale.MESO) {
          mesoAnalyses.push(analysis);
        } else {
          microAnalyses.push(analysis);
        }
      });
      return { meso: mesoAnalyses, micro: microAnalyses };
    });
};

export const submitAnalysis = (
  projectId: string,
  group_id: string,
  name: string,
  scene_id: string,
  aoi_obj_id?: string
) =>
  axios
    .post(`/analysis/${projectId}/submit`, {
      name,
      scene_id,
      group_id,
      aoi_obj_id,
    })
    .then((res) => res.data);

export const createAnalysisConfiguration = (
  projectId: string,
  group_name: string,
  analysisType: string,
  parameters: AnalysisFormType
): Promise<AnalysisConfigResponse> =>
  axios
    .post(`/analysis/${projectId}`, {
      group_name,
      analysis_type: analysisType,
      parameters,
    })
    .then((res) => res.data);

export const getAnalysisStatus = (
  analysisID: string
): Promise<AnalysisStatus> =>
  axios.get(`/status/${analysisID}`).then((res) => res.data);

export const getAnalysisCost = (
  projectId: string,
  params: object
): Promise<AnalysisCost> =>
  axios
    .get(`/analysis/${projectId}/enquire`, {
      params: { p: JSON.stringify(params) },
    })
    .then((res) => res.data);

export const getAnalysisConfigGroupedByConfig = (
  projectId: string
): Promise<AnalysisConfigItemByConfig[]> =>
  axios.get(`/analysis/${projectId}/configuration`).then((res) => res.data);

export const getAnalysisConfigGroupedByScene = (
  projectId: string
): Promise<AnalysisConfigItemByScene[]> =>
  axios.get(`/analysis/${projectId}/scene`).then((res) => res.data);

export const extractCompletedAnalyses = (
  list: AnalysisConfigItemByScene[]
): AnalysisListItem[] => {
  const newList = list.map((scene) => scene.analyses);
  const flatList = newList.flat();
  // return only analyses that have completed
  return flatList.filter((analysis) => analysis.status === 'completed');
};

export const deleteAnalysis = (projectId: string, analysisId: string) =>
  axios.delete(`/analysis/${projectId}/${analysisId}`).then((res) => res.data);

export const cancelAnalysis = (projectId: string, analysisId: string) =>
  axios
    .put(`/analysis/${projectId}/${analysisId}/cancel`)
    .then((res) => res.data);

export const getAnalysisConfig = (
  projectId: string,
  groupId: string
): Promise<AnalysisStatus> =>
  axios.get(`/analysis/${projectId}/${groupId}/config`).then((res) => res.data);
