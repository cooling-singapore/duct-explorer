import {
  Analysis,
  AnalysisResult,
  AnalysisScale,
  SceneListItem,
} from '../analysis/analysis.model';
import { MapVisualization, PanelVisualization } from '../review/review.modal';
import { PairDatum } from '../utils';

export interface ResultCompareState {
  scale: AnalysisScale;
  selectedAnalysis: Analysis | undefined;
  analysisRuns: SceneListItem[] | undefined;
  rightRunList: SceneListItem[] | undefined;
  leftRun: SceneListItem | undefined;
  rightRun: SceneListItem | undefined;
  leftResult: MapVisualization[] | undefined;
  rightResult: MapVisualization[] | undefined;
  isDeltaCompare: boolean | undefined;
  deltaResult: MapVisualization[] | undefined;
  paramForm: PairDatum;
  formComplete: boolean | undefined;
  selectedResult: AnalysisResult | undefined;
  panelResults: PanelVisualization[] | undefined;
}

export enum CompareActionKind {
  SET_SELECTED_ANALYSIS = 'SET_SELECTED_ANALYSIS',
  SET_LEFT_RUN = 'SET_LEFT_RUN',
  SET_RIGHT_RUN = 'SET_RIGHT_RUN',
  SET_RESULT = 'SET_RESULT',
  SET_COMPARE_MODE = 'SET_COMPARE_MODE',
  SET_DELTA_RESULT = 'SET_DELTA_RESULT',
  SET_FORM = 'SET_FORM',
  SET_FORM_COMPLETED = 'SET_FORM_COMPLETED',
  SET_SELECTED_RESULT = 'SET_SELECTED_RESULT',
  SET_PANEL_RESULT = 'SET_PANEL_RESULT',
  SET_SCALE = 'SET_SCALE',
}

export interface CompareVisualization {
  results0: MapVisualization[]; //left
  results1: MapVisualization[]; //right
  chart_results: PanelVisualization[];
}
