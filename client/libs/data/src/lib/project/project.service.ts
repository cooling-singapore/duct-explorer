import axios from 'axios';
import { InfoResponse, Project, ProjectForm } from './project.model';

export const createProject = (project: ProjectForm) =>
  axios.post(`/project`, project).then((res) => res.data);

export const getProjects = (): Promise<Project[]> =>
  axios
    .get(`/project`)
    .then((res) => (Array.isArray(res.data) ? res.data : []));

export const deleteProject = (projectId: string): Promise<string> =>
  axios.delete(`/project/${projectId}`).then((res) => res.data);

export const getCities = (): Promise<InfoResponse> =>
  axios.get(`/info`).then((res) => res.data);
