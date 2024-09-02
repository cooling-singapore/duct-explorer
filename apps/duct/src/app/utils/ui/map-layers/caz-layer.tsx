import GeoJSONLayer from '@arcgis/core/layers/GeoJSONLayer';
import { useEffect, useRef } from 'react';
import { useQuery } from 'react-query';

import { GeoType, getGeometries } from '@duct-core/data';
import { useProject } from '../../../context/project.context';
import { useView } from '../../../context/view.context';

interface CAZLayerProps {
  showCAZ: boolean;
  setId?: string;
  disableOnLayerControl?: boolean;
}

function CAZLayer(props: CAZLayerProps) {
  const { showCAZ, setId, disableOnLayerControl } = props;
  const viewContext = useView();
  const view = viewContext?.context.view;
  const projectContext = useProject();
  const projectId = projectContext?.project?.id || '';
  const layer = useRef<GeoJSONLayer | undefined>(undefined);

  useQuery(
    ['getGeometries', GeoType.ZONE, projectId, showCAZ],
    ({ signal }) => {
      return getGeometries(
        signal,
        projectId,
        GeoType.ZONE,
        setId ? setId : undefined,
        true // use cache for every caz except for zoneversion picker
      );
    },
    {
      refetchOnWindowFocus: false,
      enabled: projectId !== '' && showCAZ,
      onSuccess(caZoneData) {
        removeCazLayer();
        if (view) {
          const caZoneBlob = new Blob([JSON.stringify(caZoneData.geojson)], {
            type: 'application/json',
          });

          const caZoneUrl = URL.createObjectURL(caZoneBlob);
          const caZoneLayer = new GeoJSONLayer({
            title: caZoneData.title,
            id: 'caz-layer',
            url: caZoneUrl,
            renderer: caZoneData.renderer,
            legendEnabled: false,
            fields: [
              {
                name: '__OBJECTID',
                alias: '__OBJECTID',
                type: 'oid',
              },
              {
                name: 'alt_config_count',
                type: 'small-integer',
              },
            ],
            visible: !disableOnLayerControl,
          });

          layer.current = caZoneLayer;
          view.map.add(caZoneLayer);
        }
      },
    }
  );

  const removeCazLayer = () => {
    // remove layer
    if (view && view.map && layer.current) {
      view.map.remove(layer.current);
      layer.current = undefined;
    }
  };

  // CAZ useEffect. handles layer removal
  useEffect(() => {
    if (!showCAZ) {
      // a CAZ layer was removed, so remove it from map
      removeCazLayer();
    }

    return () => {
      removeCazLayer();
    };
  }, [showCAZ]);

  return null;
}

export default CAZLayer;
