import SceneView from '@arcgis/core/views/SceneView';

export interface PairDatum {
  [key: string]: number | string | boolean;
}

export interface ViewContext {
  view: SceneView | undefined;
}

export interface SBSViewContext {
  leftView: SceneView | undefined;
  rightView: SceneView | undefined;
}
