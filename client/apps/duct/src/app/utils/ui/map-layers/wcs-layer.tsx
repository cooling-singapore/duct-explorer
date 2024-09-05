import { useEffect, useRef } from 'react';
import SceneView from '@arcgis/core/views/SceneView';
import WCSLayer from '@arcgis/core/layers/WCSLayer';
import { useView } from '../../../context/view.context';
import RasterStretchRenderer from '@arcgis/core/renderers/RasterStretchRenderer';
interface GeoJsonFillLayerProps {
  view?: SceneView;
  visible: boolean;
  url: string;
}

function WCSLayers(props: GeoJsonFillLayerProps) {
  const { visible, view: viewProp, url } = props;
  const viewContext = useView();
  const view = viewProp || viewContext?.context.view;
  const layer = useRef<WCSLayer | undefined>(undefined);

  const cleanUp = () => {
    if (view && view.ui) {
      if (layer.current) {
        view.map.remove(layer.current);
        layer.current = undefined;
      }
    }
  };

  useEffect(() => {
    cleanUp();
    if (visible && view) {
      const renderer = new RasterStretchRenderer({
        stretchType: 'histogram-equalization',
        statistics: [[0, 1]],
        numberOfStandardDeviations: 1,
        colorRamp: {
          type: 'multipart',
          colorRamps: [
            {
              fromColor: [0, 0, 0, 0],
              toColor: [171, 217, 233],
            },
            {
              fromColor: [255, 255, 191],
              toColor: [253, 174, 97, 127],
            },

            {
              fromColor: [255, 255, 0],
              toColor: [255, 0, 0],
            },
          ],
        },
      });

      const wcsLayer = new WCSLayer({
        url,
        renderer: renderer,
        //  multidimensionalDefinition: multidimensionalDefinition,
        version: '2.0.1',
        // opacity: 0.5,
        customParameters: {
          service: 'WCS',
          version: '2.0.1',
          coverageId: 'duct:UVP.Default_hotspots',
          format: 'geotiff',
        },
      });

      wcsLayer.title = 'wcsLayer title';
      view.map.add(wcsLayer);

      layer.current = wcsLayer;
    }
  }, [url]);

  useEffect(() => {
    return () => {
      cleanUp();
    };
  }, []);

  return null;
}

export default WCSLayers;
