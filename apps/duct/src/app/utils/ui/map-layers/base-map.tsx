import { useRef, useEffect } from 'react';
import Map from '@arcgis/core/Map';
import Home from '@arcgis/core/widgets/Home';
import SceneView from '@arcgis/core/views/SceneView';
import LayerList from '@arcgis/core/widgets/LayerList';
import { Box } from '@mui/material';
import Expand from '@arcgis/core/widgets/Expand';
import Extent from '@arcgis/core/geometry/Extent';
import SpatialReference from '@arcgis/core/geometry/SpatialReference';
import Legend from '@arcgis/core/widgets/Legend';
import BasemapGallery from '@arcgis/core/widgets/BasemapGallery.js';

import { useView } from '../../../context/view.context';
import { useProject } from '../../../context/project.context';
import { setLegendVisibility } from '../../helpers/arcgis-helpers';
import { environment } from '../../../../environments/environment';

export function BaseMap() {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewContext = useView();
  const projectContext = useProject();

  useEffect(() => {
    let mapRef: Map | undefined = undefined;
    let viewRef: SceneView | undefined = undefined;
    let layerList: Expand | undefined = undefined;
    let legend: Expand | undefined = undefined;
    let basemapGallery: Expand | undefined = undefined;

    mapRef = new Map({
      basemap: 'dark-gray-vector',
      layers: [],
    });

    if (containerRef.current) {
      let horMid = 0;
      let verMid = 0;
      if (projectContext?.project) {
        const bounding_box = projectContext.project.bounding_box;
        horMid = (bounding_box.west + bounding_box.east) / 2;
        verMid = (bounding_box.north + bounding_box.south) / 2;
      }

      const view = new SceneView({
        map: mapRef,
        container: containerRef.current,
        zoom: 11,
        center: [horMid, verMid],
        qualityProfile: 'medium',
        environment: {
          lighting: {
            type: 'virtual',
            directShadowsEnabled: true,
          },
        },
      });

      // add home button to UI
      const home = new Home({
        view: view,
      });
      view.ui.add(home, 'top-left');

      basemapGallery = new Expand({
        content: new BasemapGallery({
          view: view,
        }),
      });
      // Add widget to the top right corner of the view
      view.ui.add(basemapGallery, {
        position: 'top-right',
      });

      // add layer control widget to UI
      layerList = new Expand({
        content: new LayerList({
          view: view,
        }),
        view: view,
        expanded: true,
      });
      // Add widget to the top right corner of the view
      view.ui.add(layerList, 'top-right');

      // add legend to UI
      legend = new Expand({
        content: new Legend({
          view: view,
        }),
        view: view,
        expanded: true,
        visible: false,
        id: 'legendExpand',
      });

      view.ui.add(legend, 'bottom-left');

      view.when(() => {
        // handles when to show/hide the legend
        setLegendVisibility(view);

        // zoom to bounding box
        if (projectContext?.project) {
          const bounding_box = projectContext.project.bounding_box;
          view.goTo(
            new Extent({
              xmin: bounding_box.west,
              ymin: bounding_box.north,
              xmax: bounding_box.east,
              ymax: bounding_box.south,
              spatialReference: new SpatialReference({ wkid: 4326 }),
            }),
            {
              duration: 3000,
            }
          );
        }
      });

      viewRef = view;
      // set view context
      viewContext.setContext(() => ({ view }));
    }

    return () => {
      if (basemapGallery) {
        basemapGallery.destroy();
      }
      if (layerList) {
        layerList.destroy();
      }
      if (legend) {
        legend.destroy();
      }
      if (mapRef) {
        mapRef.destroy();
      }
      if (viewRef) {
        viewRef.destroy();
      }
    };
  }, []);

  return <Box sx={{ height: '100%', width: '100%' }} ref={containerRef} />;
}

export default BaseMap;
