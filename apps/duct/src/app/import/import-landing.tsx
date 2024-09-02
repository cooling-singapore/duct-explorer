import Grid from '@mui/material/Grid';

import { ProvideImportLandingContextContext } from '../context/import-landing.context';
import { ProvideViewContext } from '../context/view.context';
import ImportList from './import-list/import-list';
import ImportListMapLayers from './import-map-layers/import-list-map-layers';

export function ImportLanding() {
  return (
    <ProvideImportLandingContextContext>
      <Grid container sx={{ height: '100%' }}>
        <Grid item sm={9}>
          <ProvideViewContext>
            <ImportListMapLayers />
          </ProvideViewContext>
        </Grid>
        <Grid
          item
          sm={3}
          sx={{ height: '100%', overflowX: 'hidden', overflowY: 'auto' }}
        >
          <ImportList />
        </Grid>
      </Grid>
    </ProvideImportLandingContextContext>
  );
}

export default ImportLanding;
