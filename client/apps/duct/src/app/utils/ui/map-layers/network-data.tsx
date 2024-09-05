import SceneView from '@arcgis/core/views/SceneView';
import { getNetwork } from '@duct-core/data';
import { lazy } from 'react';
import { useQuery } from 'react-query';

const NetworkLayer = lazy(() => import('./network-layer'));

function NetworkData(props: {
  projectId: string;
  network_id: string;
  view: SceneView;
}) {
  const { data } = useQuery(
    ['getNetwork', props.projectId, props.network_id],
    ({ signal }) => getNetwork(signal, props.projectId, props.network_id),
    {
      retry: false,
      refetchOnMount: false,
      refetchOnWindowFocus: false,
    }
  );
  if (data) {
    return <NetworkLayer data={data} visible view={props.view} />;
  } else {
    return null;
  }
}

export default NetworkData;
