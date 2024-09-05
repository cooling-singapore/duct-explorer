import { useQuery } from 'react-query';
import { lazy } from 'react';

import {
  getGeometries,
  GeoJSON,
  UploadVerificationDataset,
  UploadDatasetTarget,
  getLibItem,
  GeojsonVisualization,
  HeatMapVisualization,
} from '@duct-core/data';
import { useProject } from '../../../context/project.context';
import { useView } from '../../../context/view.context';
import { useImport } from '../../../context/import.context';
import { LoadingIndicator } from '@duct-core/ui';

const HeatMapLayer = lazy(() => import('./heatmap-layer'));
const GeoJsonLayer = lazy(() => import('./geojson-layer'));

interface TempImportLayerProps {
  visible: boolean;
  dataSet: UploadVerificationDataset;
  editable: boolean;
}

function TempImportLayer(props: TempImportLayerProps) {
  const { visible: showZoneSelector, editable, dataSet } = props;

  const geoType = dataSet.info.geo_type;
  const objectId = dataSet.obj_id || '';
  const editorConfig = dataSet.info.editor_config;
  const target = dataSet.target;

  const viewContext = useView();
  const view = viewContext?.context.view;
  const importContext = useImport();
  const projectContext = useProject();
  const projectId = projectContext?.project?.id || '';

  // zone selection query
  const { data: geoData } = useQuery(
    ['getGeometries', geoType, objectId],
    ({ signal }) => {
      return getGeometries(
        signal,
        projectId,
        geoType,
        `temp:${objectId}`,
        false
      );
    },
    {
      refetchOnWindowFocus: false,
      enabled: target === UploadDatasetTarget.GEODB && showZoneSelector,
    }
  );

  const { data: libData, isLoading } = useQuery(
    ['getLibItem', objectId],
    ({ signal }) => {
      return getLibItem(projectId, objectId, signal);
    },
    {
      refetchOnWindowFocus: false,
      enabled: target === UploadDatasetTarget.LIBRARY && showZoneSelector,
    }
  );

  if (isLoading) {
    return <LoadingIndicator loading={isLoading} />;
  }

  if (!geoData && !libData) {
    return null;
  }

  if (!view) {
    return null;
  }

  const edit = (geojson: GeoJSON) => {
    importContext.setContext((prevState) => {
      const copy = { ...prevState };

      // set the updates to context. it will be read when user clicks save in the workflow
      copy.layersToSave[geoType] = {
        objId: objectId,
        geoJson: geojson,
      };
      return copy;
    });
  };

  return (
    <>
      {geoData && (
        <GeoJsonLayer
          visible={showZoneSelector}
          data={geoData}
          view={view}
          editable={editable}
          editorConfig={editorConfig}
          onEdit={edit}
        />
      )}

      {libData &&
        libData.map((layer, index) => {
          if (layer.type === 'heatmap') {
            return (
              <HeatMapLayer
                key={`heatmap-${index}`}
                view={view}
                visible={true}
                data={layer as HeatMapVisualization}
              />
            );
          } else
            return (
              <GeoJsonLayer
                key={`geojon-${index}`}
                view={view}
                visible={true}
                data={layer as GeojsonVisualization}
              />
            );
        })}
    </>
  );
}

export default TempImportLayer;
