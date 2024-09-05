import { useRef, useEffect, useState } from 'react';
import Map from '@arcgis/core/Map';
import SceneView from '@arcgis/core/views/SceneView';
import Home from '@arcgis/core/widgets/Home';
import { Box } from '@mui/material';

import { CityPackage } from '@duct-core/data';

export interface PreviewWidgetProps {
  cityPackage?: CityPackage;
}

export default function PreviewWidget(props: PreviewWidgetProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const [view, setView] = useState<SceneView | null>(null);
  const [home, setHome] = useState<Home | null>(null);

  const createSceneView = (container: HTMLDivElement, basemap: string) => {
    const map = new Map({ basemap: basemap });
    return new SceneView({
      container: container,
      map,
    });
  };

  useEffect(() => {
    if (mapRef.current) {
      const view = createSceneView(mapRef.current, 'gray-vector');
      if (view) {
        setView(view);
        const home = new Home({
          view: view,
        });

        setHome(home);

        view.ui.add(home, 'top-left');
      }
    }
  }, []);

  useEffect(() => {
    if (mapRef.current && view && props.cityPackage) {
      const bounding_box = props.cityPackage.bounding_box;
      const horMid = (bounding_box.west + bounding_box.east) / 2;
      const verMid = (bounding_box.north + bounding_box.south) / 2;
      view.goTo({
        center: [horMid, verMid],
        zoom: props.cityPackage.default_zoom,
      });

      if (home) {
        home.viewpoint.camera = view.camera;
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.cityPackage]);

  return (
    <Box
      sx={{ padding: 0, margin: 0, height: '100%', width: '100%' }}
      ref={mapRef}
    />
  );
}
