import GeoJSONLayer from '@arcgis/core/layers/GeoJSONLayer';
import { SnackbarKey, useSnackbar } from 'notistack';
import { useEffect, useState } from 'react';
import { useQuery } from 'react-query';

import { GeoType, getGeometries } from '@duct-core/data';
import { useProject } from '../../../context/project.context';
import { useView } from '../../../context/view.context';

interface BuildingFootprintLayerProps {
  visible: boolean;
  sceneName: string;
  sceneId: string;
  disableOnLayerControl?: boolean;
}

function BuildingFootprintLayer(props: BuildingFootprintLayerProps) {
  const { visible, sceneName, sceneId, disableOnLayerControl } = props;
  const viewContext = useView();
  const { enqueueSnackbar, closeSnackbar } = useSnackbar();
  const projectContext = useProject();
  const projectId = projectContext?.project?.id || '';
  const [footprintNotificationKey, setFootprintNotificationKey] =
    useState<SnackbarKey>('');

  const { data } = useQuery(
    ['getGeometries', GeoType.BUILDING, sceneId],
    ({ signal }) => {
      //close old snackbars if any
      closeSnackbar();
      // show non-blocking loader
      const key = enqueueSnackbar(
        `Fetching building footprint. This can take up to 10 seconds`,
        {
          variant: 'info',
          persist: true,
        }
      );
      setFootprintNotificationKey(key);

      // fetch fresh footprint
      return getGeometries(signal, projectId, GeoType.BUILDING, sceneId, true);
    },
    {
      cacheTime: 2000,
      refetchOnWindowFocus: false,
      enabled: projectId !== '' && visible,
    }
  );

  useEffect(() => {
    let layer: GeoJSONLayer | undefined = undefined;
    if (data && viewContext?.context.view) {
      const buildingBlob = new Blob([JSON.stringify(data.geojson)], {
        type: 'application/json',
      });

      const buildingUrl = URL.createObjectURL(buildingBlob);

      const buildingLayer = new GeoJSONLayer({
        title: sceneName,
        id: 'building-footprint',
        minScale: 10000,
        legendEnabled: false,
        url: buildingUrl,
        renderer: data.renderer,
        geometryType: 'polygon',
        objectIdField: 'id', // This must be defined when creating a layer from `Graphic` objects
        fields: [
          {
            name: 'height',
            type: 'single',
          },
        ],
        visible: disableOnLayerControl ? !disableOnLayerControl : true,
      });

      viewContext.context.view.map.add(buildingLayer);
      layer = buildingLayer;
    }

    closeSnackbar(footprintNotificationKey);
    return () => {
      // remove buildingFootprintLayer layer
      if (layer) {
        viewContext?.context.view?.map?.remove(layer);
        layer = undefined;
      }
      closeSnackbar();
    };
  }, [data, visible]);

  return null;
}

export default BuildingFootprintLayer;
