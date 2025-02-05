import axios from 'axios';
import { MapVisualization, PanelVisualization } from './review.modal';

export const getAnalysisVisualizationData = (
  projectId: string,
  analysisId: string,
  resultId: string,
  parameters: object | undefined
): Promise<Array<MapVisualization | PanelVisualization>> => {
  const params = parameters ? parameters : {};
  return axios
    .get(`/result/${projectId}/${analysisId}/${resultId}`, {
      params: { parameters: JSON.stringify(params) },
    })
    .then((res) => res.data);
};

export const exportAnalysisVisualizationData = (
  projectId: string,
  analysisId: string,
  resultId: string,
  parameters: object | undefined
): Promise<Blob> => {
  const params = parameters ? parameters : {};
  return axios
    .get(`/export/${projectId}/${analysisId}/${resultId}`, {
      params: { parameters: JSON.stringify(params) },
      responseType: 'blob',
    })
    .then((res) => res.data);
};
