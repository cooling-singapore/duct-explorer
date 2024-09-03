import Grid from '@mui/material/Grid';

import { ProvideImportContext } from '../../context/import.context';
import { ProvideViewContext } from '../../context/view.context';
import ImportMapLayers from '../import-map-layers/import-map-layers';
import ImportWorkflow from './import-workflow';

export function ImportWorkflowLanding() {
  return (
    <ProvideImportContext>
      <Grid container sx={{ height: '100%' }}>
        <Grid item sm={9}>
          <ProvideViewContext>
            <ImportMapLayers />
          </ProvideViewContext>
        </Grid>
        <Grid
          item
          sm={3}
          sx={{ height: '100%', overflowX: 'hidden', overflowY: 'auto' }}
        >
          <ImportWorkflow />
        </Grid>
      </Grid>
    </ProvideImportContext>
  );
}

export default ImportWorkflowLanding;
