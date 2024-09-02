import {
  MapVisualization,
  PanelVisualization,
  PanelVisualizationType,
} from '@duct-core/data';

export function filterPanelResults(
  results: Array<MapVisualization | PanelVisualization>
): PanelVisualization[] {
  const panelResults = results.filter(
    (element) =>
      element.type === PanelVisualizationType.Bar ||
      element.type === PanelVisualizationType.Pie ||
      element.type === PanelVisualizationType.ErrorBar ||
      element.type === PanelVisualizationType.Line ||
      element.type === PanelVisualizationType.Scatter ||
      element.type === PanelVisualizationType.FlowChart ||
      element.type === PanelVisualizationType.Markdown
  );
  return panelResults as PanelVisualization[];
}

export function filterMapResults(
  results: Array<MapVisualization | PanelVisualization>
): MapVisualization[] {
  const mapResults = results.filter(
    (element) =>
      element.type === 'heatmap' ||
      element.type === 'geojson' ||
      element.type === 'network' ||
      element.type === 'wind-direction'
  );
  return mapResults as MapVisualization[];
}

export function randomId() {
  return '' + Math.random().toString(16).slice(2);
}
