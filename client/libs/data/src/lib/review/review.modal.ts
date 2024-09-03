import { ChartData, Point } from 'chart.js';
import {
  AnalysisResult,
  AnalysisResultSpec,
  AnalysisScale,
} from '../analysis/analysis.model';
import { GeoJSON } from '../build/build.model';
import { PairDatum } from '../utils';

export enum PanelVisualizationType {
  Bar = 'bar',
  Pie = 'pie',
  Line = 'line',
  ErrorBar = 'error-bar',
  FlowChart = 'flow_chart',
  Scatter = 'scatter',
  Markdown = 'markdown',
}

export interface AnalysisColor {
  color: number[];
  label: string;
  value: number;
}

export enum VisualizationStatus {
  PENDING = 'pending',
  READY = 'ready',
}

export interface PendingVisualization {
  status: VisualizationStatus;
  retry_recommendation: number;
}

export interface MapVisualization {
  type: 'heatmap' | 'geojson' | 'feature' | 'network' | 'wind-direction';
  title: string;
}

export enum LegendSubtype {
  CONTINUOUS = 'continuous',
  DISCRETE = 'discrete',
}

export interface HeatMapVisualization extends MapVisualization {
  subtype: LegendSubtype;
  legend: string;
  grid: {
    height: number;
    width: number;
  };
  area: {
    east: number;
    west: number;
    north: number;
    south: number;
  };
  no_data: number;
  colors: AnalysisColor[];
  data: number[] | number[][];
}

export interface WindDirectionVisualization extends MapVisualization {
  legendTitle: string;
  colors: AnalysisColor[];
  legendType: LegendSubtype;
  data: WindDirectionPoint[];
}

export interface WindDirectionPoint {
  coordinates: [number, number];
  width: number;
  direction: number; // clockwise rotation of the symbol in the horizontal plane (i.e., around the z axis). The rotation is specified in degrees and is relative to the y-axis.
  color: [number, number, number];
}

export interface GeojsonVisualization extends MapVisualization {
  renderer: object;
  geojson: GeoJSON;
  popupTemplate?: object;
  labelingInfo?: __esri.LabelClassProperties[];
}

export interface NetworkVisualization extends MapVisualization {
  pointData: GeojsonVisualization;
  lineData: GeojsonVisualization;
}

export interface FeatureVisualization extends MapVisualization {
  renderer: object;
}

export interface PanelVisualization {
  title: string;
  subtitle: string;
  type: PanelVisualizationType;
  data: PairDatum[];
  color: string;
}

export interface PanelMarkdown
  extends Omit<PanelVisualization, 'data' | 'color'> {
  data: string;
}

export interface PanelBarChart extends Omit<PanelVisualization, 'data'> {
  data: ChartData<'bar'>;
  options: object;
}

export interface PanelErrorBarChart extends Omit<PanelVisualization, 'data'> {
  data: ChartData;
  options: object;
}

export interface PanelLineChart extends Omit<PanelVisualization, 'data'> {
  data: ChartData<'line'>;
  options: object;
}

export interface PanelPieChart extends Omit<PanelVisualization, 'data'> {
  data: ChartData<'pie'>;
  options: object;
}

export interface PanelScatterChart extends Omit<PanelVisualization, 'data'> {
  data: ChartData<'scatter', (number | Point | null)[], unknown>;
  options: object;
}

export interface PanelFlowChart extends Omit<PanelVisualization, 'data'> {
  data: PanelFlowChartData;
}

export interface PanelFlowChartData {
  nodes: PanelFlowChartNode[];
  edges: PanelFlowChartEdge[];
}

export interface PanelFlowChartEdge {
  id: string;
  source: string;
  target: string;
}

export interface PanelFlowChartNode {
  id: string;
  data: {
    label: string;
    capacity_kW: number;
    description: string;
  };
  parentNode?: string;
}

export interface ReviewContext {
  sceneId: string;
  showBuildingFootprint: boolean;
}

export type ReviewForm = {
  scale: AnalysisScale;
  selectedAnalysisName: string;
  selectedAnalysisId?: string;
  selectedAnalysisResults?: AnalysisResult[];
  selectedResultName?: string;
  selectedResultFormat?: string;
  selectedResultSpecification?: AnalysisResultSpec;
  selectedAoiId?: string;
  paramForm?: object;
};
