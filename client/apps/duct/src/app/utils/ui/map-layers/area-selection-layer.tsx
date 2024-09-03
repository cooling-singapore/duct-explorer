import Polygon from '@arcgis/core/geometry/Polygon';
import GraphicsLayer from '@arcgis/core/layers/GraphicsLayer';
import Sketch from '@arcgis/core/widgets/Sketch';
import { useEffect, useState } from 'react';
import { arcgisToGeoJSON } from '@terraformer/arcgis';

import { useView } from '../../../context/view.context';
import { meter2degree } from '../../helpers/math-helpers';

interface AreaSelectionLayerProps {
  visible: boolean;
  onAreaSelected: (area: string) => void;
  returnGeoJson?: boolean;
}

const createAreaString = (geom: Polygon): string => {
  let areaString = `free:${geom.rings[0].length}`;
  let temp = null;
  for (let i = 0; i < geom.rings[0].length; i++) {
    temp = meter2degree(geom.rings[0][i][0], geom.rings[0][i][1]);
    areaString += `:${temp[0].toString()}:${temp[1].toString()}`;
  }
  return areaString;
};

const createGeoJson = (geom: Polygon) => {
  return JSON.stringify({
    features: [
      {
        type: 'Feature',
        geometry: arcgisToGeoJSON(geom),
      },
    ],
    crs: {
      type: 'name',
      properties: { name: 'ESRI:102100' },
    },
    type: 'FeatureCollection',
  });
};

function AreaSelectionLayer(props: AreaSelectionLayerProps) {
  const { visible: showAreaSelector, onAreaSelected, returnGeoJson } = props;
  const viewContext = useView();
  const view = viewContext?.context.view;
  const [areaSelectorLayerId, setAreaSelectorLayerId] = useState<
    string | undefined
  >(undefined);

  const cleanup = () => {
    if (areaSelectorLayerId) {
      const layer = view?.map.findLayerById(areaSelectorLayerId);
      const tool = view?.ui.find('SketchToolBar');
      if (layer && tool) {
        view?.map.remove(layer);
        view?.ui.remove(tool);
      }
      setAreaSelectorLayerId(undefined);
    }
  };
  // AreaSelction useEffect
  useEffect(() => {
    // add area selector to map if its needed
    if (showAreaSelector) {
      const sketchLayer = new GraphicsLayer();
      sketchLayer.title = 'Sketch';

      setAreaSelectorLayerId(sketchLayer.id);
      view?.map.add(sketchLayer);

      view?.when(() => {
        const sketch = new Sketch({
          id: 'SketchToolBar',
          view: view,
          layer: sketchLayer,
          visibleElements: {
            createTools: {
              point: false,
              polyline: false,
              circle: false,
            },
            selectionTools: {
              'rectangle-selection': false,
              'lasso-selection': false,
            },
            settingsMenu: false,
          },
          creationMode: 'single',
          defaultCreateOptions: { hasZ: false },
        });

        view.ui.add(sketch, 'bottom-right');
        let sketchGeometry = null;

        sketch.on('create', function (event) {
          if (sketchLayer.graphics.length > 1) {
            sketchLayer.remove(sketchLayer.graphics.getItemAt(0));
          }

          if (event.state === 'complete') {
            sketchGeometry = event.graphic.geometry as Polygon;
            const area = returnGeoJson
              ? createGeoJson(sketchGeometry)
              : createAreaString(sketchGeometry);
            onAreaSelected(area);
          }
        });

        sketch.on('update', function (event) {
          const eventInfo = event.toolEventInfo;
          if (
            eventInfo &&
            (eventInfo.type.includes('move') ||
              eventInfo.type.includes('rotate') ||
              eventInfo.type.includes('reshape') ||
              eventInfo.type.includes('scale'))
          ) {
            if (
              eventInfo.type === 'move-stop' ||
              eventInfo.type === 'rotate-stop' ||
              eventInfo.type === 'reshape-stop' ||
              eventInfo.type === 'scale-stop'
            ) {
              sketchGeometry = event.graphics[0].geometry as Polygon;
              const area = returnGeoJson
                ? createGeoJson(sketchGeometry)
                : createAreaString(sketchGeometry);
              onAreaSelected(area);
            }
          }
        });
      });
    } else {
      // remove area selector from map if its already added
      cleanup();
    }
  }, [showAreaSelector]);

  useEffect(() => {
    return () => {
      cleanup();
    };
  }, []);

  return null;
}

export default AreaSelectionLayer;
