import { AnalysisMessage } from '../analysis/analysis.model';
import { GeoJSON } from '../build/build.model';

export interface DataSet {
  available: AvailableDataset[];
  pending: [];
  supported: SupportedDataset[];
}

export interface SupportedDataset {
  data_type: string;
  data_type_label: string;
  preview_image_url: string;
  description: string;
}

export interface AvailableDataset {
  format: string;
  name: string;
  obj_id: string;
  type: string;
  type_label: string;
}

export interface ImportWorkflowState {
  activeStep: number;
  loading: boolean;
  selectedDataType: undefined | SupportedDataset;
  importName: string | undefined;
  fixMode: FixMode;
}

export enum ImportWorkflowAction {
  SET_ACTIVE_STEP = 'SET_ACTIVE_STEP',
  SET_LOADING = 'SET_LOADING',
  SET_SELECTED_DATATYPE = 'SET_SELECTED_DATATYPE',
  SET_IMPORT_NAME = 'SET_IMPORT_NAME',
  SET_FIX_MODE = 'SET_FIX_MODE',
}

export interface ImportLandingContext {
  selectedImportId?: string;
}

export interface ImportContext {
  uploadResponse?: UploadVerificationResponse;
  selectedZones?: Set<number>;
  zoneVersions?: ZoneVersion[];
  importStage?: ImportStage;
  editorConfig?: EditImportLayerConfig;
  layersToSave: { [geoType: string]: PendingSaveLayer };
  currentTarget: UploadDatasetTarget;
  objId?: string;
  showAreaSelection: boolean;
  areaGeoJson?: string;
}

export interface PendingSaveLayer {
  objId: string;
  geoJson: GeoJSON;
}

export interface ZoneVersion {
  zoneName: string;
  zoneId: number;
  alternateIndex: number;
  alternateName: string;
}

export enum ImportStage {
  Default = 1,
  ZoneSelection,
  ZoneVersionSeletion,
}

export interface UploadVerificationResponse {
  verification_messages: AnalysisMessage[];
  datasets: UploadVerificationDataset[];
  mode: FixMode;
}

export interface UploadVerificationDataset {
  obj_id?: string;
  info: UploadEditorConfig;
  target: UploadDatasetTarget;
}

export enum UploadDatasetTarget {
  GEODB = 'geodb',
  LIBRARY = 'library',
}

export interface UploadEditorConfig {
  editor_config?: EditImportLayerConfig;
  title: string;
  description: string;
  geo_type: string;
}

export interface LayerDataSet {
  [geoType: string]: string;
}

export enum FixMode {
  PICK = 'pick',
  FIX_AND_PICK = 'fix-attr-and-pick',
  FIX_AND_SKIP = 'fix-attr-and-skip',
  SKIP = 'skip',
}

export interface EditImportLayerConfig {
  objectIdField: string;
  fields: object[];
  allowedWorkflows: string[]; //Possible Values:"create-features"|"create"|"update"
}
