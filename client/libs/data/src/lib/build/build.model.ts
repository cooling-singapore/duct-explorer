import { ZoneVersion } from '../import/import.model';
import { MapVisualization } from '../review/review.modal';
import { PairDatum } from '../utils';
import { UiSchema } from '@rjsf/utils';
import Geometry from '@arcgis/core/geometry/Geometry';

export interface Feature {
  type: string;
  geometry: Geometry;
  properties: PairDatum;
}

export interface GeoJSON {
  features: Feature[];
}

export interface Scene {
  name: string;
  id: string;
  bld_footprint_hash: string;
  module_settings: Record<string, any>;
  caz_alt_mapping: [];
}

export interface SaveSceneResponse {
  id: string;
  name: string;
  bld_footprint_hash: string;
}

export enum SceneCreationStage {
  Default = 1,
  AreaSelection,
  ZoneVersionSeletion,
  Editable,
}

export interface BuildContext {
  // global state
  selectedSceneId?: string;
  selectedSceneName?: string;
  mapType: SceneCreationStage;
  editorConfig?: EditLayerConfig;
  moduleVisLayers: MapVisualization[];
}

export interface SceneContext {
  sceneType: SceneType;
  zoneVersions: ZoneVersion[];
  module_settings: Record<string, any>;
  errors: Set<string>;
}

export interface HeatEmissionItem {
  sh_emissions: number;
  lh_emissions: number;
  name: string;
  area: string;
}

export enum SceneType {
  Islandwide = 'islandwide',
  District = 'district',
}

export interface BuildingFootprintContext {
  data: boolean;
}

export enum GeoType {
  TEMP = 'temp',
  LANDUSE = 'landuse',
  ZONE = 'zone',
  BUILDING = 'building',
}

export interface SceneModule {
  priority: number;
  name: string;
  label: string;
  type: string;
  description: string;
  parameters_schema: object;
  ui_schema?: UiSchema;
  icon: string;
  has_raster_map: boolean;
  has_update_map?: boolean;
  has_area_selector: boolean;
  settings_description?: string;
  settings_image?: string;
  editable?: boolean;
  editorConfig?: EditLayerConfig;
  hide_settings_accordion?: boolean;
}

export interface EditLayerConfig {
  objectIdField: string;
  fields: object[];
  allowedWorkflows: string[]; //Possible Values:"create-features"|"create"|"update"
  moduleName: string;
  geometryType: 'point' | 'polygon' | 'polyline' | 'multipoint';
}

export interface MultiSliderProps {
  module_name: string;
  multi_select_label: string;
  slider_total_should_be_100: boolean;
  options: MultiSliderSelectItem[];
  slider_config: {
    min: number;
    max: number;
    step: number;
  };
}

export interface MultiSliderSelectItem {
  value: string;
  label: string;
  color?: string;
}

export interface DemandChartProps {
  module_name: string;
}

export interface ModuleUpdateResponse {
  asset_id: string;
}

export interface LayerDefinition {
  type: string;
  parameters: LayerDefinitionGeometryParams | LayerDefinitionNetworkParams;
}

export interface LayerDefinitionGeometryParams {
  geo_type: GeoType;
  set_id: string;
}

export interface LayerDefinitionNetworkParams {
  network_id: string;
}

export interface ZoneConfig {
  name: string;
  config_id: number;
}
