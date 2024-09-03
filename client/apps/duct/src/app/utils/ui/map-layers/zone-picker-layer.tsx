import Graphic from '@arcgis/core/Graphic';
import GeoJSONLayer from '@arcgis/core/layers/GeoJSONLayer';
import GeoJSONLayerView from '@arcgis/core/views/layers/GeoJSONLayerView';
import { useEffect, useRef, useState } from 'react';
import { useQuery } from 'react-query';

import { GeoType, getGeometries } from '@duct-core/data';
import { useProject } from '../../../context/project.context';
import { useView } from '../../../context/view.context';
import { errorCallback } from '../../helpers/arcgis-helpers';

interface ZonePickerLayerProps {
  showZonePicker: boolean;
  onZoneAdded?: (feature: Graphic) => void;
  onZoneRemoved?: (feature: Graphic) => void;
}

interface GraphicHandleObject {
  graphic: Graphic;
  handle: IHandle;
}

function ZonePickerLayer(props: ZonePickerLayerProps) {
  const { showZonePicker, onZoneAdded, onZoneRemoved } = props;
  const viewContext = useView();
  const view = viewContext?.context.view;

  const projectContext = useProject();
  const projectId = projectContext?.project?.id || '';
  const layer = useRef<GeoJSONLayer | undefined>(undefined);
  const [cAZClickHandler, setCAZClickHandler] = useState<IHandle | undefined>(
    undefined
  );
  const highlightList: GraphicHandleObject[] = [];

  useQuery(
    ['getshowZonePickerGeometries', GeoType.ZONE, projectId],
    ({ signal }) => {
      return getGeometries(
        signal,
        projectId,
        GeoType.ZONE,
        undefined,
        true // use cache for every caz except for zoneversion picker
      );
    },
    {
      refetchOnWindowFocus: false,
      enabled: projectId !== '' && showZonePicker,
      onSuccess(caZoneData) {
        removeCazLayer();
        if (view) {
          const caZoneBlob = new Blob([JSON.stringify(caZoneData.geojson)], {
            type: 'application/json',
          });

          const caZoneUrl = URL.createObjectURL(caZoneBlob);
          const caZoneLayer = new GeoJSONLayer({
            title: caZoneData.title,
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
          });

          if (showZonePicker) {
            let caZoneLayerView: GeoJSONLayerView;
            caZoneLayer
              .when(() => {
                view.whenLayerView(caZoneLayer).then(function (layerView) {
                  caZoneLayerView = layerView;
                });
              })
              .catch(errorCallback);

            const handler = view.on('click', function (evt) {
              const point = view.toMap({ x: evt.x, y: evt.y });
              if (evt.button === 0) {
                caZoneLayerView
                  .queryFeatures({
                    //query object
                    geometry: point,
                    spatialRelationship: 'intersects',
                    returnGeometry: false,
                    outFields: ['*'],
                  })
                  .then((featureSet) => {
                    const feature = featureSet.features[0] as Graphic;
                    if (feature === undefined) {
                      return;
                    }

                    for (let i = 0; i < highlightList.length; i++) {
                      if (
                        highlightList[i].graphic.attributes['__OBJECTID'] ===
                        feature.attributes['__OBJECTID']
                      ) {
                        highlightList[i].handle.remove();
                        highlightList.splice(i, 1);
                        if (onZoneAdded) {
                          onZoneAdded(feature);
                        }
                        return;
                      }
                    }

                    const highlight = caZoneLayerView.highlight(feature);
                    highlightList.push({ graphic: feature, handle: highlight });

                    if (onZoneRemoved) {
                      onZoneRemoved(feature);
                    }
                  });
                return;
              }
            });

            setCAZClickHandler(handler);
          } else {
            highlightList.length = 0; // clear highlighs if CA zone selector no needed
          }

          layer.current = caZoneLayer;
          view.map.add(caZoneLayer);
        }
      },
    }
  );

  const removeCazLayer = () => {
    // remove click handler from zone selector if present
    if (cAZClickHandler) {
      cAZClickHandler.remove();
      setCAZClickHandler(undefined);
    }

    // remove layer
    if (view && view.map && layer.current) {
      view.map.remove(layer.current);
      layer.current = undefined;
    }
  };

  // CAZ useEffect. handles layer removal
  useEffect(() => {
    if (!showZonePicker) {
      // a CAZ layer was removed, so remove it from map
      removeCazLayer();
    }

    return () => {
      removeCazLayer();
    };
  }, [showZonePicker]);

  return null;
}

export default ZonePickerLayer;
