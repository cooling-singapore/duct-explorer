import { lazy } from 'react';

const BaseMap = lazy(() => import('../../utils/ui/map-layers/base-map'));

function BuildMapLayers() {
  return <BaseMap />;
}

export default BuildMapLayers;
