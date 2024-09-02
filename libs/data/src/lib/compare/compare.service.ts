import axios from 'axios';
import { MapVisualization, PanelVisualization } from '../review/review.modal';
import { CompareVisualization } from './compare.model';

export const getAnalysisCompareVisualizationData = (
  projectId: string,
  analysisId0: string,
  analysisId1: string,
  resultId: string,
  parameters: object | undefined
): Promise<CompareVisualization> => {
  const params = parameters ? JSON.stringify(parameters) : '';
  return axios
    .get(
      `/result/${projectId}/compare/${resultId}/${analysisId0}/${analysisId1}`,
      {
        params: {
          parameters0: params,
          parameters1: params,
        },
      }
    )
    .then((res) => res.data);
};

export const getDeltaCompareVisualizationData = (
  projectId: string,
  analysisId0: string,
  analysisId1: string,
  resultId: string,
  parameters: object | undefined
): Promise<Array<MapVisualization | PanelVisualization>> => {
  const params = parameters ? JSON.stringify(parameters) : '';
  return axios
    .get(`/result/${projectId}/delta/${resultId}/${analysisId0}/${analysisId1}`, {
      // TODO: pass once since params are the same?
      params: {
        parameters0: params,
        parameters1: params,
      },
    })
    .then((res) => res.data);
};

export const exportDeltaCompareVisualizationData = (
  projectId: string,
  analysisId0: string,
  analysisId1: string,
  resultId: string,
  parameters: object | undefined
): Promise<Blob> => {
  const params = parameters ? parameters : {};
  return axios
    .get(`/export/${projectId}/${resultId}/${analysisId0}/${analysisId1}`, {
      params: {
        parameters0: JSON.stringify(params),
        parameters1: JSON.stringify(params),
      },
      responseType: 'blob',
    })
    .then((res) => res.data);
};
