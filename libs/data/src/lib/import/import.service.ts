import axios, { AxiosResponse } from 'axios';
import {
  AvailableDataset,
  DataSet,
  LayerDataSet,
  PendingSaveLayer,
  UploadVerificationResponse,
} from './import.model';
import { MapVisualization } from '../review/review.modal';

export const getImports = (projectId: string): Promise<DataSet> =>
  axios.get(`/dataset/${projectId}`).then((res) => res.data);

export const importGeoDataset = (
  projectId: string,
  name: string,
  selected_zones: number[],
  datasets?: LayerDataSet
) =>
  axios
    .post(`/zone_config/${projectId}`, {
      config_name: name,
      selected_zones,
      datasets,
    })
    .then((res) => res.data);

export const importLibDataset = (
  projectId: string,
  name: string,
  objId: string
): Promise<AvailableDataset> =>
  axios
    .post(`/dataset/${projectId}/${objId}`, {
      name,
    })
    .then((res) => res.data);

export const updateDataset = (
  projectId: string,
  layer: PendingSaveLayer,
  geo_type: string
) =>
  axios
    .put(`/dataset/${projectId}/${layer.objId}`, {
      geo_type,
      args: layer.geoJson,
    })
    .then((res) => res.data);

export const deleteLibImport = (projectId: string, importId: string) =>
  axios.delete(`/dataset/${projectId}/${importId}`).then((res) => res.data);

export const validateDataset = (
  projectId: string,
  file: File,
  data_type: string
): Promise<UploadVerificationResponse> => {
  const formData = new FormData();
  formData.append('attachment', file);
  formData.append(
    'body',
    JSON.stringify({
      data_type,
    })
  );

  return axios
    .post(`/dataset/${projectId}`, formData, {
      headers: {
        'content-type': 'multipart/form-data',
      },
    })
    .then((res) => res.data);
};

export const getLibItem = (
  projectId: string,
  objId: string,
  signal?: AbortSignal
): Promise<MapVisualization[]> =>
  axios
    .get(`/dataset/${projectId}/${objId}`, {
      signal,
    })
    .then((res) => res.data);

export const getAOIImports = (projectId: string): Promise<AvailableDataset[]> =>
  axios.get(`/dataset/${projectId}`).then((res: AxiosResponse<DataSet>) => {
    return res.data.available.filter(
      (dataset) => dataset.type === 'area_of_interest'
    );
  });
