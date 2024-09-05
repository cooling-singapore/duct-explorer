import Grid from '@mui/material/Grid';

import { ProvideViewContext } from '../../context/view.context';
import BuildMapLayers from './build-map-layers';
import SceneList from './scene-list/scene-list';
import { ProvideSceneContext } from '../../context/scene.context';
import { ProvideBuildContext } from '../../context/build.context';

export function BuildLanding() {
  return (
    <ProvideBuildContext>
      <ProvideSceneContext>
        <Grid container sx={{ height: '100%' }}>
          <Grid item sm={9}>
            <ProvideViewContext>
              <BuildMapLayers />
            </ProvideViewContext>
          </Grid>
          <Grid
            item
            sm={3}
            sx={{ height: '100%', overflowX: 'hidden', overflowY: 'auto' }}
          >
            <SceneList />
          </Grid>
        </Grid>
      </ProvideSceneContext>
    </ProvideBuildContext>
  );
}

export default BuildLanding;
