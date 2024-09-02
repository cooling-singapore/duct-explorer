import GeoJSONLayer from '@arcgis/core/layers/GeoJSONLayer';
import PopupTemplate from '@arcgis/core/PopupTemplate';
import { createRoot } from 'react-dom/client';
import { lazy, useEffect, useRef } from 'react';
import { useQuery } from 'react-query';
import Graphic from '@arcgis/core/Graphic';

import {
  GeoType,
  getGeometries,
  ZoneVersion,
  ZoneConfig,
  getZoneVersions,
} from '@duct-core/data';
import { useProject } from '../../../context/project.context';
import { useView } from '../../../context/view.context';
import { useScene } from '../../../context/scene.context';

const PopupWidget = lazy(
  () => import('../../../build/create-scene/workflow/popup-widget')
);

interface ZoneVersionPickerLayerProps {
  showZoneVersionPicker: boolean;
  onZoneVersionUpdate?: (zones: ZoneVersion[]) => void;
}

function ZoneVersionPickerLayer(props: ZoneVersionPickerLayerProps) {
  const { showZoneVersionPicker, onZoneVersionUpdate } = props;
  const viewContext = useView();
  const view = viewContext?.context.view;
  const sceneContext = useScene();
  const projectContext = useProject();
  const projectId = projectContext?.project?.id || '';
  const layer = useRef<GeoJSONLayer | undefined>(undefined);
  const zoneVersions = sceneContext.context.zoneVersions;

  const pop = new PopupTemplate({
    title: 'Select Configuration',
    content: async (feature: any) => {
      const graphic = feature.graphic as Graphic;
      const zoneId = graphic.attributes['__OBJECTID'];
      const availableConfigs = await getZoneVersions(projectId, zoneId);
      const areaName = graphic.getAttribute('planning_area_name') as string;

      const currentZoneConfig = sceneContext.context.zoneVersions.find(
        (zone) => zone.zoneId === zoneId
      );

      const updateLayer = () => {
        if (layer.current) {
          layer.current?.applyEdits({
            updateFeatures: [graphic],
          });
        }
      };

      const setZoneVersion = (zone: ZoneConfig) => {
        const zoneVersionsTemp = zoneVersions || [];
        if (view) {
          // config_count to renderer mapping
          // 2 to 100 = Alternative zone configurations available
          // -1 = Alternative zone configuration selected
          // default = No alternative zone configurations available
          // we dont use config_count for anything besides the renderer, so setting 2 is harmless
          graphic.setAttribute(
            'config_count',
            zone.name === 'Default' ? 2 : -1
          );
          //duplicate check
          const duplicateIndex = zoneVersionsTemp.findIndex(
            (zone) => zone.zoneId === zoneId
          );

          if (duplicateIndex < 0) {
            //not a duplicate zone. so push
            zoneVersionsTemp.push({
              zoneName: areaName,
              zoneId,
              alternateIndex: zone.config_id,
              alternateName: zone.name,
            });
          } else {
            //found a duplicate zone. so replace with new selection
            zoneVersionsTemp[duplicateIndex] = {
              zoneName: areaName,
              zoneId,
              alternateIndex: zone.config_id,
              alternateName: zone.name,
            };
          }
          // close the damn popup
          view.popup.close();
        }

        updateLayer();

        if (onZoneVersionUpdate) {
          sceneContext.setContext((prevState) => {
            const copy = { ...prevState };
            copy.zoneVersions = zoneVersionsTemp;
            return copy;
          });

          onZoneVersionUpdate(zoneVersionsTemp);
        }
      };

      const popupNode = document.createElement('div');
      const root = createRoot(popupNode);
      root.render(
        <PopupWidget
          availableConfigs={availableConfigs}
          currentConfigId={
            currentZoneConfig
              ? currentZoneConfig.alternateIndex
              : availableConfigs[0].config_id
          }
          setZoneVersion={setZoneVersion}
        />
      );
      return popupNode;
    },
  });

  useQuery(
    ['getshowZoneVersionPickerGeometries', GeoType.ZONE, projectId],
    ({ signal }) => {
      return getGeometries(
        signal,
        projectId,
        GeoType.ZONE,
        undefined,
        false // use cache for every caz except for zoneversion picker
      );
    },
    {
      refetchOnWindowFocus: false,
      enabled: projectId !== '' && showZoneVersionPicker,
      onSuccess(caZoneData) {
        removeLayer();
        if (view) {
          const caZoneBlob = new Blob([JSON.stringify(caZoneData.geojson)], {
            type: 'application/json',
          });

          const caZoneUrl = URL.createObjectURL(caZoneBlob);
          const caZoneLayer = new GeoJSONLayer({
            title: caZoneData.title,
            editingEnabled: true, // allows us to use applyEdits when a non default config is picked
            url: caZoneUrl,
            outFields: ['*'],
            popupEnabled: true,
            popupTemplate: pop,
            renderer: caZoneData.renderer,
            fields: [
              {
                name: '__OBJECTID',
                alias: '__OBJECTID',
                type: 'oid',
              },
              {
                name: 'config_count',
                type: 'small-integer',
              },
              {
                name: 'planning_area_name',
                type: 'string',
              },
            ],
          });

          layer.current = caZoneLayer;
          view.map.add(caZoneLayer);
        }
      },
    }
  );

  const removeLayer = () => {
    // remove layer
    if (view && view.map && layer.current) {
      view.map.remove(layer.current);
      layer.current = undefined;
    }
  };

  // CAZ useEffect. handles layer removal
  useEffect(() => {
    if (!showZoneVersionPicker) {
      // a CAZ layer was removed, so remove it from map
      removeLayer();
    }

    return () => {
      removeLayer();
    };
  }, [showZoneVersionPicker]);

  return null;
}

export default ZoneVersionPickerLayer;
