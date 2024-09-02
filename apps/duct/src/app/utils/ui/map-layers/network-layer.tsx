import GeoJSONLayer from '@arcgis/core/layers/GeoJSONLayer';
import { useEffect } from 'react';
import SceneView from '@arcgis/core/views/SceneView';
import GroupLayer from '@arcgis/core/layers/GroupLayer.js';

import { GeojsonVisualization, NetworkVisualization } from '@duct-core/data';
import { errorCallback } from '../../helpers/arcgis-helpers';

interface NetworkLayerProps {
  data: NetworkVisualization;
  view: SceneView;
  visible: boolean;
  stopZoomInOnLoad?: boolean;
}

function NetworkLayer(props: NetworkLayerProps) {
  const { visible, data, view, stopZoomInOnLoad } = props;

  useEffect(() => {
    let layerGroup: GroupLayer | undefined = undefined;

    const createLayer = (
      data: GeojsonVisualization,
      geometryType: 'point' | 'polygon' | 'polyline' | 'multipoint'
    ) => {
      const blob = new Blob([JSON.stringify(data.geojson)], {
        type: 'application/json',
      });

      const url = URL.createObjectURL(blob);

      return new GeoJSONLayer({
        title: data.title,
        url: url,
        renderer: data.renderer,
        geometryType,
        labelingInfo: data.labelingInfo,
      });
    };

    if (visible && data && view) {
      const pointLayer = createLayer(data.pointData, 'point');
      const lineLayer = createLayer(data.lineData, 'polyline');

      const group = new GroupLayer({
        layers: [pointLayer, lineLayer],
        title: data.title,
      });

      if (!stopZoomInOnLoad) {
        lineLayer.on('layerview-create', () => {
          view
            .goTo(lineLayer.fullExtent, {
              duration: 3000,
            })
            .catch(errorCallback);
        });
      }

      view.map.add(group);

      layerGroup = group;
    }

    return () => {
      if (view && layerGroup) {
        view.map?.remove(layerGroup);
        layerGroup = undefined;
      }
    };
  }, [visible, data]);

  return null;
}

export default NetworkLayer;
