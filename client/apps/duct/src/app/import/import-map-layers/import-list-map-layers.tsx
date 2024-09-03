import { useImportLanding } from '../../context/import-landing.context';
import { useQuery } from 'react-query';
import { useSnackbar } from 'notistack';

import {
  GeojsonVisualization,
  HeatMapVisualization,
  getLibItem,
} from '@duct-core/data';
import { useProject } from '../../context/project.context';
import { LoadingIndicator } from '@duct-core/ui';
import { useView } from '../../context/view.context';
import BaseMap from '../../utils/ui/map-layers/base-map';
import GeoJsonLayer from '../../utils/ui/map-layers/geojson-layer';
import HeatMapLayer from '../../utils/ui/map-layers/heatmap-layer';

function ImportListMapLayers() {
  const { enqueueSnackbar } = useSnackbar();
  const projectContext = useProject();
  const projectId = projectContext?.project?.id || '';
  const importLandingContext = useImportLanding();
  const selectedObjId = importLandingContext.context.selectedImportId;
  const viewContext = useView();
  const view = viewContext.context.view;

  const { data, isLoading } = useQuery(
    ['getLibItem', selectedObjId],
    ({ signal }) => {
      return getLibItem(projectId, selectedObjId || '', signal);
    },
    {
      refetchOnWindowFocus: false,
      enabled: !selectedObjId || selectedObjId === '' ? false : true,
      onError() {
        enqueueSnackbar('Sorry, something went wrong', { variant: 'error' });
      },
    }
  );

  return (
    <>
      <BaseMap />
      {view &&
        data &&
        data.map((layer, index) => {
          if (layer.type === 'heatmap') {
            return (
              <HeatMapLayer
                key={`heatmap-${index}`}
                view={view}
                visible={true}
                data={layer as HeatMapVisualization}
              />
            );
          } else {
            return (
              <GeoJsonLayer
                key={`geojson-${index}`}
                view={view}
                visible={true}
                data={layer as unknown as GeojsonVisualization}
              />
            );
          }
        })}
      <LoadingIndicator loading={isLoading} />
    </>
  );
}

export default ImportListMapLayers;
