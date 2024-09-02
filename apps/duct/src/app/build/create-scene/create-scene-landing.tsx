import { Grid } from '@mui/material';

import CreateSceneWorkflow from './workflow/create-scene-workflow';
import { ProvideSceneContext } from '../../context/scene.context';
import { ProvideViewContext } from '../../context/view.context';
import { ProvideBuildContext } from '../../context/build.context';
import CreateSceneMapLayers from './create-scene-map-layers';

function CreateSceneLanding() {
  return (
    <ProvideSceneContext>
      <ProvideBuildContext>
        <ProvideViewContext>
          <Grid container sx={{ height: '100%' }}>
            <Grid item sm={9}>
              <CreateSceneMapLayers />
            </Grid>
            <Grid
              item
              sm={3}
              sx={{ height: '100%', overflowX: 'hidden', overflowY: 'auto' }}
            >
              <CreateSceneWorkflow />
            </Grid>
          </Grid>
        </ProvideViewContext>
      </ProvideBuildContext>
    </ProvideSceneContext>
  );
}

export default CreateSceneLanding;
