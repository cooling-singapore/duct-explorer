import Map from '@arcgis/core/Map';
import SceneView from '@arcgis/core/views/SceneView';
import Point from '@arcgis/core/geometry/Point';
import Color from '@arcgis/core/Color';
import PolygonSymbol3D from '@arcgis/core/symbols/PolygonSymbol3D';
import ExtrudeSymbol3DLayer from '@arcgis/core/symbols/ExtrudeSymbol3DLayer';
import SolidEdges3D from '@arcgis/core/symbols/edges/SolidEdges3D';
import * as promiseUtils from '@arcgis/core/core/promiseUtils';
import * as reactiveUtils from '@arcgis/core/core/reactiveUtils.js';
import Expand from '@arcgis/core/widgets/Expand';

export function createSceneViewBase(
  container: HTMLDivElement,
  basemap: string
) {
  const map = new Map({ basemap: basemap });
  return new SceneView({
    container: container,
    map,
  });
}

export function createDebugInfo(view: SceneView) {
  //*** Add div element to show coordates ***//
  const coordsWidget = document.createElement('div');
  coordsWidget.id = 'coordsWidget';
  coordsWidget.className = 'esri-widget esri-component';
  coordsWidget.style.padding = '7px 15px 5px';
  view.ui.add(coordsWidget, 'bottom-right');

  //*** Update lat, lon, zoom and scale ***//
  const showCoordinates = (pt: Point) => {
    if (pt === null) return;

    // const point = new Float32Array(3);
    // fromRenderCoordinates(view, [view.camera.position.x, view.camera.position.y, view.camera.position.z], 0,
    //     point, 0, SpatialReference.WGS84, 3);

    const coords =
      'Lat/Lon ' +
      pt.latitude.toFixed(3) +
      ' ' +
      pt.longitude.toFixed(3) +
      ' | Scale 1:' +
      Math.round(view.scale * 1) / 1 +
      ' | Zoom ' +
      view.zoom;
    // " | Camera " + view.camera.position.x + " " + view.camera.position.y + " " +view.camera.position.z + " " + view.camera.tilt;
    coordsWidget.innerHTML = coords;
  };

  //*** Add event and show center coordinates after the view is finished moving e.g. zoom, pan ***//
  view.watch(['stationary'], function () {
    showCoordinates(view.center);
  });

  //*** Add event to show mouse coordinates on click and move ***//
  view.on('pointer-down', function (evt) {
    showCoordinates(view.toMap({ x: evt.x, y: evt.y }));
  });
}

interface LightSource {
  color: number[];
  intensity: number;
}

export function getFlatColor(source: LightSource, output: Float32Array) {
  output[0] = source.color[0] * source.intensity;
  output[1] = source.color[1] * source.intensity;
  output[2] = source.color[2] * source.intensity;
  return output;
}

export function getSymbol(color: Color) {
  return new PolygonSymbol3D({
    symbolLayers: [
      new ExtrudeSymbol3DLayer({
        material: {
          color: color,
        },
        edges: new SolidEdges3D({
          color: [1, 1, 1, 1],
          size: 0.5,
        }),
      }),
    ],
  });
}

function componentToHex(c: number) {
  const hex = c.toString(16);
  return hex.length === 1 ? '0' + hex : hex;
}

export function rgbToHex(r: number, g: number, b: number) {
  return '#' + componentToHex(r) + componentToHex(g) + componentToHex(b);
}

export function errorCallback(reason: any) {
  if (!promiseUtils.isAbortError(reason)) {
    console.error('something went wrong:', reason);
  }
}

export function setLegendVisibility(view: SceneView) {
  // watch the count of layers on the map
  reactiveUtils.watch(
    () => view.map?.allLayers.length,
    () => {
      // get a count of all geojson layers only since we dont want to count other types
      // ignore building-footprint since its not on the legend anyway
      // ignore the default CAZ layer as well
      const layers = view.map?.allLayers.filter(
        (layer) =>
          layer.type === 'geojson' &&
          layer.id !== 'building-footprint' &&
          layer.id !== 'caz-layer'
      );
      const expand = view.ui?.find('legendExpand') as Expand;
      // if there is atleast one geojson layer, show the legend
      if (layers && layers.length > 0) {
        if (expand) {
          expand.visible = true;
        }
      } else {
        if (expand) {
          expand.visible = false;
        }
      }
    }
  );
}
