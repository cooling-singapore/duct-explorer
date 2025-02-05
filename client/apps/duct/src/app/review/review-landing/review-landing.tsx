import { AnalysisScale, ReviewForm } from '@duct-core/data';
import { lazy } from 'react';
import { FormProvider, useForm } from 'react-hook-form';
import { ProvideReviewContext } from '../../context/review.context';
import { ProvideViewContext } from '../../context/view.context';

const ManualResultFetch = lazy(() => import('./manual-result-fetch'));

function ReviewLanding() {
  const params = new URLSearchParams(window.location.search);
  const analysisScale = params.get('scale');
  const analysisType = params.get('type');
  const analysisRun = params.get('run');
  const resultName = params.get('name');

  const defaultValues = {
    selectedAoiId: 'no-masking',
    ...(analysisScale && { scale: analysisScale as AnalysisScale }),
    ...(analysisType && { selectedAnalysisName: analysisType }),
    ...(analysisRun && { selectedAnalysisId: analysisRun }),
    ...(resultName && { selectedResultName: resultName }),
  };

  const methods = useForm<ReviewForm>({ defaultValues });

  return (
    <ProvideReviewContext>
      <ProvideViewContext>
        <FormProvider {...methods}>
          <ManualResultFetch />
        </FormProvider>
      </ProvideViewContext>
    </ProvideReviewContext>
  );
}

export default ReviewLanding;
