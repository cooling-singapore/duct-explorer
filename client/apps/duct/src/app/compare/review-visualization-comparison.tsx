import { useEffect, useState } from 'react';

import {
  GeojsonVisualization,
  HeatMapVisualization,
  MapVisualization,
  NetworkVisualization,
  WindDirectionVisualization,
} from '@duct-core/data';
import { useSBSView } from '../context/sbs-view.context';
import GeoJsonLayer from '../utils/ui/map-layers/geojson-layer';
import HeatMapLayer from '../utils/ui/map-layers/heatmap-layer';
import NetworkLayer from '../utils/ui/map-layers/network-layer';
import SBSBaseMap from '../utils/ui/map-layers/sbs-base-map';
import WindDirectionLayer from '../utils/ui/map-layers/wind-direction-layer';
import { randomId } from '../utils/utils';

export interface ReviewVisualizationProps {
  leftData: MapVisualization[] | undefined;
  rightData: MapVisualization[] | undefined;
}

export function ReviewVisualizationComparison(props: ReviewVisualizationProps) {
  const { leftData, rightData } = props;
  const viewContext = useSBSView();
  const leftView = viewContext?.context.leftView;
  const rightView = viewContext?.context.rightView;

  const [rightChild, setRightChild] = useState<JSX.Element[] | undefined>(
    undefined
  );
  const [leftChild, setLeftChild] = useState<JSX.Element[] | undefined>(
    undefined
  );

  const getLayers = (
    data: MapVisualization[],
    view: __esri.SceneView,
    hideLegend: boolean,
    disableZoom: boolean
  ) => {
    return data.map((layer, index) => {
      const id = randomId();
      const commonProps = {
        key: `${id}-${layer.type}`,
        visible: true,
        view,
      };

      switch (layer.type) {
        case 'heatmap':
          return (
            <HeatMapLayer
              {...commonProps}
              data={layer as HeatMapVisualization}
              stopZoomInOnLoad={disableZoom} // auto zoom to first layer. this prevents weird rendering issues
              hideLegend={hideLegend}
            />
          );
        case 'geojson':
          return (
            <GeoJsonLayer
              {...commonProps}
              data={layer as GeojsonVisualization}
              stopZoomInOnLoad={index > 0}
            />
          );
        case 'network':
          return (
            <NetworkLayer
              {...commonProps}
              data={layer as NetworkVisualization}
              stopZoomInOnLoad={index > 0}
            />
          );
        case 'wind-direction':
          return (
            <WindDirectionLayer
              {...commonProps}
              data={layer as WindDirectionVisualization}
              stopZoomInOnLoad={index > 0}
            />
          );
        default:
          return <span {...commonProps}>unknown layer</span>;
      }
    });
  };

  useEffect(() => {
    if (leftData && leftView) {
      setTimeout(
        () => setLeftChild(getLayers(leftData, leftView, false, true)),
        500
      );
    }
  }, [leftData, leftView]);

  useEffect(() => {
    if (rightData && rightView) {
      setTimeout(
        () => setRightChild(getLayers(rightData, rightView, true, false)),
        1000
      );
    }
  }, [rightData, rightView]);

  return (
    <>
      <SBSBaseMap />
      {leftChild}
      {rightChild}
    </>
  );
}

export default ReviewVisualizationComparison;
