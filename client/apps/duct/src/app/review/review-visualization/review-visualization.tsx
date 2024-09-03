import { useEffect, useState } from 'react';

import {
  GeojsonVisualization,
  HeatMapVisualization,
  MapVisualization,
  NetworkVisualization,
  WindDirectionVisualization,
} from '@duct-core/data';
import { useReview } from '../../context/review.context';
import { useView } from '../../context/view.context';
import BaseMap from '../../utils/ui/map-layers/base-map';
import BuildingFootprintLayer from '../../utils/ui/map-layers/building-footprint-layer';
import CAZLayer from '../../utils/ui/map-layers/caz-layer';
import GeoJsonLayer from '../../utils/ui/map-layers/geojson-layer';
import HeatMapLayer from '../../utils/ui/map-layers/heatmap-layer';
import NetworkLayer from '../../utils/ui/map-layers/network-layer';
import WindDirectionLayer from '../../utils/ui/map-layers/wind-direction-layer';
import { randomId } from '../../utils/utils';

export interface ReviewVisualizationProps {
  data: MapVisualization[] | undefined;
}

export function ReviewVisualization(props: ReviewVisualizationProps) {
  const { data } = props;
  const reviewContext = useReview();
  const viewContext = useView();
  const view = viewContext.context.view;
  const [children, setChildren] = useState<JSX.Element[]>([]);

  useEffect(() => {
    if (view && data) {
      const list = data.map((layer, index) => {
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
                stopZoomInOnLoad={index > 0} // auto zoom to first layer. this prevents weird rendering issues
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
      setChildren(list);
    }
  }, [data]);

  return (
    <>
      <BaseMap />
      <BuildingFootprintLayer
        visible={reviewContext.context.showBuildingFootprint}
        sceneId={reviewContext.context.sceneId}
        sceneName="Building Footprint"
        disableOnLayerControl={true}
      />
      <CAZLayer showCAZ={true} disableOnLayerControl={true} />
      {children}
    </>
  );
}

export default ReviewVisualization;
