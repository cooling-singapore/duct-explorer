import Graphic from '@arcgis/core/Graphic';
import Point from '@arcgis/core/geometry/Point';
import GraphicsLayer from '@arcgis/core/layers/GraphicsLayer';
import PointSymbol3D from '@arcgis/core/symbols/PointSymbol3D';
import SceneView from '@arcgis/core/views/SceneView';
import { WindDirectionVisualization } from '@duct-core/data';
import { useEffect, useRef } from 'react';
// import { createRoot } from 'react-dom/client';
// import LegendHeatmap from '../legends/legend-heatmap';

interface WindDirectionLayerProps {
  view: SceneView;
  visible: boolean;
  data: WindDirectionVisualization;
  stopZoomInOnLoad?: boolean;
}

function WindDirectionLayer(props: WindDirectionLayerProps) {
  const { visible, data, view, stopZoomInOnLoad } = props;

  const layer = useRef<GraphicsLayer | undefined>(undefined);
  // let legend: HTMLElement | null = null;

  useEffect(() => {
    if (visible && view) {
      const graphicsLayer = new GraphicsLayer({
        title: data.title,
      });
      const graphics = data.data.map((feature) => {
        const point = new Point({
          latitude: feature.coordinates[0],
          longitude: feature.coordinates[1],
        });

        return new Graphic({
          geometry: point,
          symbol: new PointSymbol3D({
            symbolLayers: [
              {
                type: 'object', // autocasts as new ObjectSymbol3DLayer()
                resource: {
                  href: '../../../assets/models/arrow.gltf',
                },
                width: feature.width,
                heading: feature.direction,
                height: 0,
                material: {
                  color: feature.color,
                },
                castShadows: false,
              },
            ],
          }),
        });
      });

      if (graphics.length) {
        graphicsLayer.addMany(graphics);
      }

      view.map.add(graphicsLayer);

      // graphicsLayer.on('layerview-create', () => {
      //   // some layers dont need to fit to view. its annoying
      //   if (!stopZoomInOnLoad) {
      //     view
      //       .goTo(graphicsLayer.fullExtent, {
      //         duration: 3000,
      //       })
      //       .catch(errorCallback);
      //   }
      // });

      // legend = document.getElementById('customLegend');
      // if (!legend) {
      //   legend = document.createElement('div');
      //   legend.id = 'customLegend';
      //   createRoot(legend).render(
      //     <LegendHeatmap
      //       title={data.title}
      //       labels={data.colors}
      //       subtype={data.legendType}
      //     />
      //   );

      //   view.ui.add(legend, { position: 'bottom-left', index: 0 });
      // }

      layer.current = graphicsLayer;
    }
    return () => {
      if (view && view.map && layer.current) {
        view.map.remove(layer.current);
        layer.current = undefined;
      }
    };
  }, [visible, data]);

  return null;
}

export default WindDirectionLayer;
