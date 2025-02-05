import { useRef, useEffect, RefObject } from 'react';
import Map from '@arcgis/core/Map';
import Home from '@arcgis/core/widgets/Home';
import SceneView from '@arcgis/core/views/SceneView';
import { Box, Grid } from '@mui/material';
import LayerList from '@arcgis/core/widgets/LayerList';
import Expand from '@arcgis/core/widgets/Expand';
import Legend from '@arcgis/core/widgets/Legend';
import SpatialReference from '@arcgis/core/geometry/SpatialReference';

import { useSBSView } from '../../../context/sbs-view.context';
import { useProject } from '../../../context/project.context';
import { setLegendVisibility } from '../../helpers/arcgis-helpers';

export function SBSBaseMap() {
  const rightContainer = useRef<HTMLDivElement>(null);
  const leftContainer = useRef<HTMLDivElement>(null);
  const leftMapRef = useRef<Map | undefined>(undefined);
  const rightMapRef = useRef<Map | undefined>(undefined);
  const leftViewRef = useRef<SceneView | undefined>(undefined);
  const rightViewRef = useRef<SceneView | undefined>(undefined);
  const viewContext = useSBSView();
  const projectContext = useProject();

  let horMid = 0;
  let verMid = 0;
  if (projectContext?.project) {
    const bounding_box = projectContext.project.bounding_box;
    horMid = (bounding_box.west + bounding_box.east) / 2;
    verMid = (bounding_box.north + bounding_box.south) / 2;
  }

  const buildSceneView = (
    map: Map,
    container: RefObject<HTMLDivElement>
  ): SceneView | undefined => {
    if (container.current) {
      const view = new SceneView({
        map: map,
        container: container.current,
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

      // add layer control widget to UI
      const layerList = new Expand({
        content: new LayerList({
          view: view,
        }),
        view: view,
        expanded: true,
      });

      // Add widget to the top right corner of the view
      view.ui.add(layerList, 'top-right');

      return view;
    }
    return undefined;
  };

  const buildMap = (): Map =>
    new Map({
      basemap: 'dark-gray-vector',
      layers: [],
    });

  // for debugging layers
  // set a title for all layers first
  // const view1 = viewContext?.context.view1;
  // const layerList = view1?.map.layers.map((layer) => layer.title);
  // console.log('layers on view1:', JSON.stringify(layerList));

  useEffect(() => {
    leftViewRef.current = viewContext?.context.leftView;
    rightViewRef.current = viewContext?.context.rightView;

    // if not in context already, build map and view
    if (!leftViewRef.current || !rightViewRef.current) {
      const leftMap = buildMap();
      leftMapRef.current = leftMap;
      const rightMap = buildMap();
      rightMapRef.current = rightMap;

      const leftView = buildSceneView(leftMap, leftContainer);
      leftViewRef.current = leftView;
      const rightView = buildSceneView(rightMap, rightContainer);
      rightViewRef.current = rightView;

      if (leftView) {
        // add legend to left view only
        const legend = new Expand({
          content: new Legend({
            view: leftView,
          }),
          view: leftView,
          expanded: true,
          id: 'legendExpand',
          visible: false,
        });

        leftView.ui.add(legend, 'bottom-left');

        leftView.when(() => {
          // handles when to show/hide the legend
          setLegendVisibility(leftView);
        });
      }

      // set view context
      viewContext?.setContext(() => ({ leftView, rightView }));
    }

    const views = [leftViewRef.current, rightViewRef.current];
    let active: SceneView;

    const sync = (source: SceneView) => {
      if (!active || !active.viewpoint || active !== source) {
        return;
      }

      for (const view of views) {
        if (view && view !== active) {
          view.viewpoint = active.viewpoint;
        }
      }
    };

    for (const view of views) {
      view?.watch(['interacting', 'animation'], () => {
        active = view;
        sync(active);
      });

      view?.watch('viewpoint', () => sync(view));
    }

    return () => {
      if (leftViewRef.current) {
        leftViewRef.current.ui.empty('bottom-left');
        leftViewRef.current.destroy();
      }

      if (rightViewRef.current) {
        rightViewRef.current.ui.empty('bottom-left');
        rightViewRef.current.destroy();
      }

      if (leftMapRef.current) {
        leftMapRef.current.destroy();
      }

      if (rightMapRef.current) {
        rightMapRef.current.destroy();
      }
    };
  }, []);

  const heightStyle = { height: '100%' };

  return (
    <Grid sx={heightStyle} container>
      <Grid sx={heightStyle} item md={12} lg={6}>
        <Box sx={heightStyle} ref={leftContainer}></Box>
      </Grid>
      <Grid sx={heightStyle} item md={12} lg={6}>
        <Box sx={heightStyle} ref={rightContainer}></Box>
      </Grid>
    </Grid>
  );
}

export default SBSBaseMap;
