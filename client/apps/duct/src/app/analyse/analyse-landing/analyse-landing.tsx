import { AnalyseForm, AnalysisScale } from '@duct-core/data';
import Grid from '@mui/material/Grid';
import { lazy } from 'react';
import { FormProvider, useForm } from 'react-hook-form';
import { ProvideViewContext } from '../../context/view.context';

const WorkflowLanding = lazy(
  () => import('../workflow/workflow-landing/workflow-landing')
);

const AnalyseVisualization = lazy(() => import('./analyse-visualization'));

const defaultValues = {
  scale: AnalysisScale.MESO,
};

export function AnalyseLanding() {
  const methods = useForm<AnalyseForm>({ defaultValues });
  return (
    <Grid container sx={{ height: '100%' }}>
      <FormProvider {...methods}>
        <Grid item md={8} lg={9}>
          <ProvideViewContext>
            <AnalyseVisualization />
          </ProvideViewContext>
        </Grid>
        <Grid
          item
          md={4}
          lg={3}
          sx={{ height: '100%', overflowX: 'hidden', overflowY: 'auto' }}
        >
          <WorkflowLanding />
        </Grid>
      </FormProvider>
    </Grid>
  );
}

export default AnalyseLanding;
