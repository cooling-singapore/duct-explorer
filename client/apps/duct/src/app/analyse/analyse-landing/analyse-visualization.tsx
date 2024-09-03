import {
  AnalyseForm,
  GeojsonVisualization,
  HeatMapVisualization,
  NetworkVisualization,
  getView,
} from '@duct-core/data';
import { useSnackbar } from 'notistack';
import { lazy, useState } from 'react';
import { useFormContext } from 'react-hook-form';
import { useQuery } from 'react-query';
import { useProject } from '../../context/project.context';
import { useView } from '../../context/view.context';

const NetworkLayer = lazy(
  () => import('../../utils/ui/map-layers/network-layer')
);
const BaseMap = lazy(() => import('../../utils/ui/map-layers/base-map'));
const HeatMapLayer = lazy(
  () => import('../../utils/ui/map-layers/heatmap-layer')
);
const GeoJsonLayer = lazy(
  () => import('../../utils/ui/map-layers/geojson-layer')
);

export function AnalyseVisualization() {
  const { enqueueSnackbar } = useSnackbar();
  const { watch } = useFormContext<AnalyseForm>();

  const viewContext = useView();
  const view = viewContext.context.view;
  const projectContext = useProject();
  const projectId = projectContext?.project?.id || '';

  const [layers, setLayers] = useState<JSX.Element[]>([]);
  const scene = watch('scene');
  const aoi = watch('aoi_obj_id');

  useQuery(
    ['getView', projectId, scene, aoi],
    ({ signal }) => {
      const params = new URLSearchParams();
      if (scene) {
        params.append('set_id', `scene:${scene.id}`);
      }

      if (aoi) {
        params.append('area', `aoi_obj_id:${aoi}`);
      }

      return getView(projectId, 'analyse', params, signal);
    },
    {
      retry: false,
      enabled: projectId !== '',
      onSuccess(data) {
        if (view) {
          const tempLayers = data.map((layer, index) => {
            const commonProps = {
              key: `${layer.type}-${index}`,
              visible: true,
              view,
            };

            if (layer.type === 'heatmap') {
              return (
                <HeatMapLayer
                  {...commonProps}
                  data={layer as HeatMapVisualization}
                />
              );
            } else if (layer.type === 'network') {
              return (
                <NetworkLayer
                  {...commonProps}
                  data={layer as NetworkVisualization}
                  stopZoomInOnLoad
                />
              );
            } else if (layer.type === 'geojson') {
              return (
                <GeoJsonLayer
                  {...commonProps}
                  data={layer as unknown as GeojsonVisualization}
                />
              );
            } else {
              return <span {...commonProps}>Unknown layer</span>;
            }
          });

          setLayers(tempLayers);
        }
      },
      onError(err) {
        enqueueSnackbar('Sorry, something went wrong', { variant: 'error' });
      },
    }
  );

  return (
    <>
      <BaseMap />
      {layers}
    </>
  );
}

export default AnalyseVisualization;
