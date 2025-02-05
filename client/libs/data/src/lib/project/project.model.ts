import { object, string } from 'yup';

export interface ProjectForm {
  name: string;
  city: string;
  bdp_id: string;
}

export interface ProjectMember {
  user_id: string;
  role: string;
}

export interface Project {
  id: string;
  name: string;
  state: ProjectState;
  bounding_box: {
    east: number;
    north: number;
    south: number;
    west: number;
  };
}

export enum ProjectState {
  INITIALISING = 'initialising',
  INITIALIZED = 'initialised',
  BROKEN = 'broken',
}

export const projectFormSchema = object().shape({
  name: string().required('Project name is required'),
  city: string().required('Please select a city'),
  bdp_id: string().required('Please select a dataset'),
});

export interface CityPackage {
  id: string;
  name: string;
  city_name: string;
  bounding_box: {
    west: number;
    north: number;
    east: number;
    south: number;
  };
  default_zoom: number;
  description?: string;
}

export interface City {
  city: string;
  packages: CityPackage[];
}

export interface InfoResponse {
  analyses: string[];
  bdps: City[];
}
