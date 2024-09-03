import { lazy } from 'react';
import { useQuery } from 'react-query';
import SceneView from '@arcgis/core/views/SceneView';

import { GeoType, getGeometries } from '@duct-core/data';
const GeoJsonLayer = lazy(() => import('./geojson-layer'));

function GeoJsonData(props: {
  setId: string;
  geoType: GeoType;
  projectId: string;
  stopZoomInOnLoad?: boolean;
  view: SceneView;
}) {
  const { setId, geoType, projectId, stopZoomInOnLoad, view } = props;

  const { data } = useQuery(
    ['getGeometries', geoType, setId, projectId],
    ({ signal }) => {
      return getGeometries(
        signal,
        projectId,
        geoType,
        setId ? setId : undefined,
        true
      );
    },
    {
      refetchOnWindowFocus: false,
      enabled: projectId !== '',
    }
  );

  if (data) {
    return (
      <GeoJsonLayer
        visible={true}
        data={data}
        stopZoomInOnLoad={stopZoomInOnLoad}
        view={view}
      />
    );
  } else {
    return null;
  }
}

export default GeoJsonData;
