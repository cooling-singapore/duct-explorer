import GeoJSONLayer from '@arcgis/core/layers/GeoJSONLayer';
import { useEffect, useRef } from 'react';
import { useQuery } from 'react-query';

import { GeoType, getGeometriesInArea } from '@duct-core/data';
import { useProject } from '../../../context/project.context';
import { useView } from '../../../context/view.context';

interface MicroSelectionLayerProps {
  visible: boolean;
  selectedScene: string;
  selectedArea?: {
    dataType: GeoType;
    area: string;
  };
}

function MicroSelectionLayer(props: MicroSelectionLayerProps) {
  const { visible, selectedScene, selectedArea } = props;
  const viewContext = useView();
  const view = viewContext?.context.view;
  const projectContext = useProject();
  const projectId = projectContext?.project?.id || '';
  const dataLayer = useRef<GeoJSONLayer | undefined>(undefined);

  const cleanUp = () => {
    if (view && view.ui) {
      if (dataLayer.current) {
        view.map.remove(dataLayer.current);
        dataLayer.current = undefined;
      }
    }
  };

  useQuery(
    [
      'getGeometriesInArea',
      projectId,
      selectedArea?.dataType,
      selectedScene,
      selectedArea?.area,
    ],
    () => {
      return getGeometriesInArea(
        projectId,
        selectedArea?.dataType || 'buildings',
        selectedScene,
        selectedArea?.area || ''
      );
    },
    {
      refetchOnWindowFocus: false,
      enabled: projectId !== '' && visible && selectedArea ? true : false,
      onSuccess(data) {
        if (view) {
          const blob = new Blob([JSON.stringify(data.geojson)], {
            type: 'application/json',
          });

          const url = URL.createObjectURL(blob);

          const buildingLayer = new GeoJSONLayer({
            title: data.title,
            url: url,
            renderer: data.renderer,
            objectIdField: 'id', // This must be defined when creating a layer from `Graphic` objects
            fields: [
              {
                name: 'id',
                type: 'oid',
              },
              {
                name: 'height',
                type: 'single',
              },
              {
                name: 'building_type',
                type: 'string',
              },
            ],
          });

          view.map.add(buildingLayer);
          dataLayer.current = buildingLayer;
        }
      },
    }
  );

  useEffect(() => {
    return () => {
      cleanUp();
    };
  }, [visible, selectedScene, selectedArea]);

  return null;
}

export default MicroSelectionLayer;
