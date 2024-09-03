import { add, remove } from '@arcgis/core/views/3d/externalRenderers';
import { lazy, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import SceneView from '@arcgis/core/views/SceneView';
import Extent from '@arcgis/core/geometry/Extent';
import SpatialReference from '@arcgis/core/geometry/SpatialReference';

import { HeatMapVisualization } from '@duct-core/data';
import HeatmapRenderer from './renderers/heatmap-renderer';
import { errorCallback } from '../../helpers/arcgis-helpers';

const LegendHeatmap = lazy(() => import('../../ui/legends/legend-heatmap'));

interface HeatMapLayerProps {
  data: HeatMapVisualization;
  visible: boolean;
  view: SceneView;
  stopZoomInOnLoad?: boolean;
  hideLegend?: boolean;
}

function HeatMapLayer(props: HeatMapLayerProps) {
  const { data, visible, view, hideLegend, stopZoomInOnLoad } = props;

  useEffect(() => {
    let dataLayer: HeatmapRenderer | undefined = undefined;
    let legend: HTMLElement | null = null;

    if (view && visible && data) {
      const heatmapRenderer = new HeatmapRenderer(view, data.subtype);
      heatmapRenderer.setData(data);
      view.on('pointer-down', function (evt) {
        heatmapRenderer.pickData({ x: evt.x, y: evt.y });
      });

      add(view, heatmapRenderer);

      // 751: sometimes doing things the caveman way just works
      if (!stopZoomInOnLoad) {
        setTimeout(() => {
          view
            .goTo(
              new Extent({
                xmin: data.area.west,
                ymin: data.area.north,
                xmax: data.area.east,
                ymax: data.area.south,
                spatialReference: new SpatialReference({ wkid: 4326 }),
              })
            )
            .catch(errorCallback);
        }, 500);
      }

      if (!hideLegend) {
        legend = document.getElementById('customLegend');
        if (!legend) {
          legend = document.createElement('div');
          legend.id = 'customLegend';
          createRoot(legend).render(
            <LegendHeatmap
              title={data.legend}
              labels={data.colors}
              subtype={data.subtype}
            />
          );
        }

        view.ui.add(legend, { position: 'bottom-left', index: 0 });
      }

      dataLayer = heatmapRenderer;
      // requestRender(view);
    }

    return () => {
      if (view && view.ui) {
        if (legend) {
          legend.remove();
        }

        if (dataLayer) {
          remove(view, dataLayer);
          dataLayer = undefined;
        }
      }
    };
  }, [data, visible]);

  return null;
}

export default HeatMapLayer;
