import { lazy, useEffect, useState } from 'react';
import { useMutation, useQuery } from 'react-query';
import {
  GeojsonVisualization,
  HeatMapVisualization,
  NetworkVisualization,
  GeoJSON,
  SceneContext,
  updateModuleData,
  SceneCreationStage,
  ZoneVersion,
  getView,
} from '@duct-core/data';
import { useScene } from '../../context/scene.context';
import { useBuild } from '../../context/build.context';
import { useView } from '../../context/view.context';
import { useProject } from '../../context/project.context';
import { randomId } from '../../utils/utils';
import { environment } from '../../../environments/environment';

const ZoneVersionPickerLayer = lazy(
  () => import('../../utils/ui/map-layers/zone-version-picker-layer')
);

const BaseMap = lazy(() => import('../../utils/ui/map-layers/base-map'));

const NetworkLayer = lazy(
  () => import('../../utils/ui/map-layers/network-layer')
);
const GeoJsonLayer = lazy(
  () => import('../../utils/ui/map-layers/geojson-layer')
);
const HeatMapLayer = lazy(
  () => import('../../utils/ui/map-layers/heatmap-layer')
);
const AreaSelectionLayer = lazy(
  () => import('../../utils/ui/map-layers/area-selection-layer')
);

function CreateSceneMapLayers() {
  const sceneContext = useScene();
  const buildContext = useBuild();
  const viewContext = useView();
  const view = viewContext.context.view;
  const projectContext = useProject();
  const projectId = projectContext?.project?.id || '';
  const [children, setChildren] = useState<JSX.Element[]>([]);
  const layers = buildContext.context.moduleVisLayers;
  const mapType = buildContext.context.mapType;
  const showAreaSelector = mapType === SceneCreationStage.AreaSelection;
  const [setId, setSetId] = useState<URLSearchParams | undefined>(undefined);

  const showZoneVersionPicker =
    mapType === SceneCreationStage.ZoneVersionSeletion;

  const { data, isLoading } = useQuery(
    ['getView', projectId, setId?.toString()],
    ({ signal }) => getView(projectId, 'build', setId, signal),
    {
      retry: false,
      // enabled: showZoneVersionPicker,
    }
  );

  const onZoneVersionUpdate = (zones: ZoneVersion[]) => {
    const zoneString = zones.map(
      (zone) => `${zone.zoneId}=${zone.alternateIndex}`
    );

    const params = new URLSearchParams();
    params.append('set_id', `zone_config:${zoneString.join(',')}`);
    setSetId(params);
  };

  const updateModuleDataMutation = useMutation(
    (params: { moduleName: string; sceneCtx: SceneContext }) =>
      updateModuleData(projectId, params.moduleName, params.sceneCtx).then(
        (res) => {
          sceneContext.setContext((prevState) => {
            const copy = { ...prevState };
            copy.module_settings[params.moduleName].asset_id = res.asset_id;
            return copy;
          });
        }
      )
  );

  useEffect(() => {
    if (view) {
      const onEdit = (geojson: GeoJSON) => {
        const moduleName = buildContext.context.editorConfig?.moduleName;
        if (moduleName) {
          sceneContext.setContext((prevState) => {
            const copy = { ...prevState };
            copy.module_settings[moduleName].geojson = geojson;
            // copy.module_settings[moduleName].layers = layers; //whut??
            return copy;
          });

          const copy = { ...sceneContext.context };
          copy.module_settings[moduleName].geojson = geojson;
          updateModuleDataMutation.mutate({
            moduleName,
            sceneCtx: copy,
          });
        }
      };

      const list = layers.map((layer, index) => {
        const id = randomId();
        const commonProps = {
          key: `${id}-${layer.type}-${index}`,
          visible: true,
          view,
        };

        // TODO: Find better way
        // Sets editorConfig only for modules which should have editing capabilites
        const editorConfig = ['Hazards', 'Recovery Crews'].includes(
          (layer as GeojsonVisualization).title
        )
          ? buildContext.context.editorConfig
          : undefined;

        switch (layer.type) {
          case 'heatmap':
            return (
              <HeatMapLayer
                {...commonProps}
                data={layer as HeatMapVisualization}
              />
            );
          case 'geojson':
            return (
              <GeoJsonLayer
                {...commonProps}
                data={layer as GeojsonVisualization}
                editable={!!editorConfig}
                editorConfig={editorConfig}
                onEdit={onEdit}
                stopZoomInOnLoad
              />
            );
          case 'network':
            return (
              <NetworkLayer
                {...commonProps}
                data={layer as NetworkVisualization}
                stopZoomInOnLoad
              />
            );
          default:
            return <span {...commonProps}>unknown layer</span>;
        }
      });
      setChildren(list);
    }
  }, [layers, view, buildContext.context.editorConfig]);

  const onAreaSelected = (area: string) => {
    const moduleName = buildContext.context.editorConfig?.moduleName;
    if (moduleName) {
      sceneContext.setContext((prevState) => {
        const copy = { ...prevState };
        copy.module_settings[moduleName] = {
          area,
        };
        return copy;
      });
    }
  };

  return (
    <>
      <BaseMap />
      <AreaSelectionLayer
        visible={showAreaSelector}
        onAreaSelected={onAreaSelected}
      />
      <ZoneVersionPickerLayer
        showZoneVersionPicker={showZoneVersionPicker}
        onZoneVersionUpdate={onZoneVersionUpdate}
      />
      {children}
      {!isLoading &&
        view &&
        data &&
        data.map((layer, index) => {
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
            if (!layer.title.includes('Zones')) {
              return (
                <GeoJsonLayer
                  {...commonProps}
                  data={layer as unknown as GeojsonVisualization}
                  stopZoomInOnLoad // https://app.zenhub.com/workspaces/sec-digital-twin-lab-5f7e9787331a05002470dc62/issues/gh/cooling-singapore/digital-urban-climate-twin/724
                />
              );
            } else {
              return null;
            }
          } else {
            return <span {...commonProps}>Unknown layer</span>;
          }
        })}
    </>
  );
}

export default CreateSceneMapLayers;
