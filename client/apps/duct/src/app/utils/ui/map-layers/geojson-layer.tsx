import GeoJSONLayer from '@arcgis/core/layers/GeoJSONLayer';
import { useEffect, useRef } from 'react';
import Expand from '@arcgis/core/widgets/Expand';
import SceneView from '@arcgis/core/views/SceneView';
import Editor from '@arcgis/core/widgets/Editor';
import { arcgisToGeoJSON } from '@terraformer/arcgis';

import {
  EditLayerConfig,
  GeojsonVisualization,
  EditImportLayerConfig,
  GeoJSON,
} from '@duct-core/data';
import { errorCallback } from '../../helpers/arcgis-helpers';

interface GeoJsonLayerProps {
  view: SceneView;
  visible: boolean;
  data: GeojsonVisualization;
  editable?: boolean;
  editorConfig?: EditLayerConfig | EditImportLayerConfig;
  onEdit?: (geojson: GeoJSON) => void;
  stopZoomInOnLoad?: boolean;
}

function GeoJsonLayer(props: GeoJsonLayerProps) {
  const {
    visible,
    data,
    view,
    editable,
    onEdit,
    editorConfig,
    stopZoomInOnLoad,
  } = props;

  const layer = useRef<GeoJSONLayer | undefined>(undefined);

  useEffect(() => {
    if (visible && view) {
      const blob = new Blob([JSON.stringify(data.geojson)], {
        type: 'application/json',
      });

      const url = URL.createObjectURL(blob);
      // setup basic geojson layer
      const geoJSONLayer = new GeoJSONLayer({
        title: data.title,
        url: url,
        renderer: data.renderer,
        editingEnabled: editable,
        labelingInfo: data.labelingInfo,
      });

      if (data.popupTemplate) {
        geoJSONLayer.popupTemplate = data.popupTemplate as __esri.PopupTemplate;
      }

      view.map.add(geoJSONLayer);

      geoJSONLayer.on('layerview-create', () => {
        // some layers dont need to fit to view. its annoying
        if (!stopZoomInOnLoad) {
          view
            .goTo(geoJSONLayer.fullExtent, {
              duration: 3000,
            })
            .catch(errorCallback);
        }
      });

      layer.current = geoJSONLayer;
    }
    return () => {
      if (view && view.ui) {
        // clear edit widget
        view.ui.empty('bottom-right');

        if (layer.current) {
          view.map.remove(layer.current);
          layer.current = undefined;
        }
      }
    };
  }, [visible, data]);

  useEffect(() => {
    let editor: Editor | undefined = undefined;
    if (!editable) {
      if (view && view.ui) {
        // clear edit widget
        view.ui.empty('bottom-right');
      }
    } else {
      // config edit capabilites
      if (view && layer.current && editable && editorConfig) {
        layer.current.objectIdField = editorConfig.objectIdField;
        layer.current.fields = editorConfig.fields as __esri.Field[];

        if ((editorConfig as EditLayerConfig).geometryType) {
          layer.current.geometryType = (
            editorConfig as EditLayerConfig
          ).geometryType;
        }

        // add editor to UI
        editor = new Editor({
          view: view,
          visibleElements: {
            // sketchTooltipControls: false, // removed in @arcgis/core 4.28
            snappingControls: false,
            createFeaturesSection: editorConfig.allowedWorkflows.includes(
              'update'
            )
              ? false
              : true,
          },
          // allowedWorkflows depricated with arcgis 4.29: https://developers.arcgis.com/javascript/latest/api-reference/esri-widgets-Editor.html#allowedWorkflows
          // allowedWorkflows: editorConfig.allowedWorkflows as any,
        });

        const editorComponents = view.ui.getComponents('bottom-right');
        if (editorComponents.length === 0) {
          // add the editor widget only if theres no other editors
          view.ui.add(
            new Expand({
              content: editor,
              view: view,
              expanded: true,
            }),
            'bottom-right'
          );
        }

        // bind edit event handler
        layer.current.on('edits', (e) => {
          if (layer.current && onEdit) {
            layer.current
              .queryFeatures()
              .then((featureSet: __esri.FeatureSet) => {
                const { features } = featureSet;

                // rebuild a geojson feature list
                const allFeatures = features.map((feature) => {
                  return {
                    type: 'Feature',
                    // id: null,
                    geometry: arcgisToGeoJSON(feature.geometry),
                    properties: feature.attributes,
                  };
                });

                onEdit({
                  features: allFeatures as any,
                  type: 'FeatureCollection',
                } as GeoJSON);
              });
          }
        });
      }
    }

    return () => {
      if (editor) {
        if (editor.activeWorkflow) {
          // cancel workflow
          editor.cancelWorkflow();
        }
        editor.destroy();
      }
    };
  }, [editable]);

  return null;
}

export default GeoJsonLayer;
