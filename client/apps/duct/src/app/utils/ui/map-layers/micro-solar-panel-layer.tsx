import GeoJSONLayer from '@arcgis/core/layers/GeoJSONLayer';
import UniqueValueRenderer from '@arcgis/core/renderers/UniqueValueRenderer';
import SizeVariable from '@arcgis/core/renderers/visualVariables/SizeVariable';
import { useEffect, useRef } from 'react';
import { useQuery } from 'react-query';
import PolygonSymbol3D from '@arcgis/core/symbols/PolygonSymbol3D';
import StylePattern3D from '@arcgis/core/symbols/patterns/StylePattern3D.js';

import { GeoType, getGeometriesInArea } from '@duct-core/data';
import { useProject } from '../../../context/project.context';
import { useView } from '../../../context/view.context';

interface MicroSolarPanelLayerProps {
  visible: boolean;
  selectedScene: string;
  selectedArea?: {
    dataType: GeoType;
    area: string;
  };
}

function MicroSolarPanelLayer(props: MicroSolarPanelLayerProps) {
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
      'solar',
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

          const buildingRenderer = new UniqueValueRenderer({
            defaultSymbol: new PolygonSymbol3D({
              symbolLayers: [
                {
                  type: 'fill',
                  material: { color: '#3f488f' },
                  outline: { color: '#283244' },

                  pattern: new StylePattern3D({
                    style: 'cross',
                  }),
                },
              ],
            }),
            defaultLabel: 'Solar Panels',
            visualVariables: [
              new SizeVariable({
                field: 'height',
                valueUnit: 'meters',
              }),
            ],
          });

          const elevationInfo = {
            mode: 'absolute-height' as const,
            // offset: 1,
            featureExpressionInfo: {
              expression: '$feature.height',
            },
            unit: 'meters' as const,
          };

          const solarPanelLayer = new GeoJSONLayer({
            title: 'Solar Panels',
            url,
            renderer: buildingRenderer,
            objectIdField: 'id', // This must be defined when creating a layer from `Graphic` objects
            fields: [
              {
                name: 'id',
                type: 'oid',
              },
              {
                name: 'name',
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
            elevationInfo,
          });

          view.map.add(solarPanelLayer);
          dataLayer.current = solarPanelLayer;
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

export default MicroSolarPanelLayer;
