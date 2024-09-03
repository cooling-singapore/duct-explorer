import { Scene } from '../build/build.model';
import { PanelVisualizationType } from '../review/review.modal';
import { PairDatum } from '../utils/';

export interface Analysis {
  name: string;
  description: string;
  sample_image: string;
  further_information: string;
  label: string;
  ui_schema: object;
  parameters_schema: object;
  type: AnalysisScale;
}
export interface GroupedAnalyses {
  micro: Analysis[];
  meso: Analysis[];
}
export interface AnalysisHistoryResult {
  data: AnalysisHistoryItem[];
}

export interface AnalysisHistoryItem {
  approving_user: string;
  id: string;
  name: string;
  owner: string;
  progress: number;
  type: string;
}

export interface AnalysisStatus {
  pending: boolean;
}

export interface AnalysisCost {
  analysis_id: string;
  approval_required: boolean;
  cached_results_available: boolean;
  estimated_cost: string;
  estimated_time: string;
  messages: AnalysisMessage[];
}

export interface AnalysisMessage {
  severity: 'error' | 'warning' | 'info' | 'success';
  message: string;
}

export interface RangeValue {
  min: number;
  max: number;
}

export interface AnalysisConfigItemByScene {
  analyses: AnalysisListItem[];
  parameters: object;
  scene_id: string;
  scene_name: string;
}

export interface AnalysisResult {
  name: string;
  label?: string;
  obj_id: string;
  specification: AnalysisResultSpec;
  export_format: string;
}

export interface AnalysisResultSpec {
  description: string;
  target: AnalysisResultViewTarget;
  type: PanelVisualizationType;
  parameters: object;
}

export enum AnalysisResultViewTarget {
  PANEL = 'panel',
  MAP = 'map',
}

export interface AnalysisListItem {
  analysis_id: string;
  analysis_type: string;
  analysis_type_label: string;
  group_id: string;
  name: string;
  progress: number;
  results: AnalysisResult[];
  scene_id: string;
  status: AnalysisState;
  t_created: number;
  username: string;
  message?: AnalysisMessage;
  aoi_obj_id?: string;
}

export enum AnalysisState {
  TIMEOUT = 'timeout',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

// Interface for an analysis config on the Manage screen
export interface AnalysisConfigItemByConfig {
  analyses: SceneListItem[];
  group_id: string;
  group_name: string;
  parameters: object;
  type: string;
  type_label: string;
}

// Interface for a scene that would be listed under an analysis config
export interface SceneListItem {
  analysis_id: string;
  analysis_type: string;
  analysis_type_label: string;
  group_id: string;
  name: string;
  progress: number;
  results: AnalysisResult[];
  scene_id: string;
  status: AnalysisState;
  t_created: number;
  username: string;
  message?: string;
  aoi_obj_id?: string;
}

export interface AnalysisConfigResponse {
  id: string;
  name: string;
  type: string;
  type_labbel: string;
}

export interface AnalyseContext {
  analysisType: string;
  selectedSceneId: string;
  selectedSceneName: string;
  selectedAOIId?: string;
}

export enum AnalysisScale {
  MESO = 'meso',
  MICRO = 'micro',
}

export type AnalyseForm = {
  scale: AnalysisScale;
  analysis_name: string;
  aoi_obj_id?: string;
  scene: Scene;
  analysis: Analysis;
  analysisForm: AnalysisFormType;
};

export interface AnalysisFormType {
  name: string;
}
