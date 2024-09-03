import {
  AnalysisScale,
  MapVisualization,
  PanelVisualization,
  ReviewForm,
  exportAnalysisVisualizationData,
  getAnalysisVisualizationData,
} from '@duct-core/data';
import { LoadingIndicator, PageTitle } from '@duct-core/ui';
import { Box, Button, Grid, Typography } from '@mui/material';
import { IChangeEvent } from '@rjsf/core';
import { useSnackbar } from 'notistack';
import { useEffect, useState } from 'react';
import { SubmitHandler, useFormContext } from 'react-hook-form';
import { useMutation } from 'react-query';
import { useProject } from '../../context/project.context';
import ScaleSelect from '../../utils/ui/components/scale-select';
import { filterMapResults, filterPanelResults } from '../../utils/utils';
import ReviewResultPanel from '../review-result-panel/review-result-panel';
import ReviewVisualization from '../review-visualization/review-visualization';
import AnalysisRunSelect from './form-components/analysis-run-select';
import FormWrapper from './form-components/form-wrapper';
import ResultSelect from './form-components/result-select';
import ReviewAnalysisSelect from './form-components/review-analysis-select';
import ReviewAOISelect from './form-components/review-aoi-select';

function ManualResultFetch() {
  const onSubmit: SubmitHandler<ReviewForm> = (data) => console.log(data);
  const { watch, setValue, handleSubmit, formState } =
    useFormContext<ReviewForm>();

  const { enqueueSnackbar } = useSnackbar();
  const projectContext = useProject();
  const projectId = projectContext?.project?.id || '';

  const [results, setResults] = useState<{
    mapResult: MapVisualization[];
    panelResults: PanelVisualization[];
  }>({
    mapResult: [],
    panelResults: [],
  });

  const selectedScale = watch('scale');
  const selectedAnalysisName = watch('selectedAnalysisName');
  const selectedAnalysisId = watch('selectedAnalysisId');
  const selectedResultName = watch('selectedResultName');
  const selectedResultFormat = watch('selectedResultFormat');
  const selectedResultSpecification = watch('selectedResultSpecification');
  const paramForm = watch('paramForm');
  const selectedAoiId = watch('selectedAoiId'); // use only for MESO

  useEffect(() => {
    // useeffect is triggerd when leaving page. so use project ID to stop that
    if (projectId) {
      resetResults();
      // when a form spec is present, we fetch results when the form is updated. see formUpdated
      // if the result has no form spec, fetch result right away
      if (
        selectedAnalysisId &&
        selectedResultSpecification &&
        Object.keys(selectedResultSpecification.parameters).length === 0
      ) {
        getResultMutation.mutate({});
      } else if (selectedAnalysisId && paramForm) {
        getResultMutation.mutate(paramForm);
      }
    }
  }, [formState]);

  const getResultMutation = useMutation((formParams: object) =>
    getAnalysisVisualizationData(
      projectId,
      selectedAnalysisId || '',
      selectedResultName || '',
      selectedScale === AnalysisScale.MICRO
        ? formParams
        : { ...formParams, display_aoi_obj_id: selectedAoiId } // pass selectedAoiId only if selected scale is micro
    )
      .then((res) => {
        const mapResult = filterMapResults(res);
        const panelResults = filterPanelResults(res);
        setResults({ mapResult, panelResults });
      })
      .catch((err) => {
        enqueueSnackbar('Result fetch failed', {
          variant: 'error',
        });
        console.error(err);
      })
  );

  const exportResultMutation = useMutation(
    (props: { formParams: object; fileName: string }) =>
      exportAnalysisVisualizationData(
        projectId,
        selectedAnalysisId || '',
        selectedResultName || '',
        props.formParams
      )
        .then((res) => {
          const url = window.URL.createObjectURL(res);
          const link = document.createElement('a');
          link.href = url;
          link.setAttribute('download', props.fileName);
          document.body.appendChild(link);
          link.click();
          link.remove();
        })
        .catch((err) => {
          enqueueSnackbar('Result export failed', {
            variant: 'error',
          });
          console.error(err);
        })
  );

  const resetResults = () => {
    setResults({
      mapResult: [],
      panelResults: [],
    });
  };

  const formUpdated = (form: IChangeEvent) => {
    setValue('paramForm', form.formData);
  };

  const onDownloadClick = () => {
    const props = {
      formParams: paramForm as object,
      fileName: `${selectedAnalysisName}_${selectedResultName}.${selectedResultFormat}`,
    };
    exportResultMutation.mutate(props);
  };

  return (
    <Grid container sx={{ height: '100%' }}>
      <Grid item sm={9}>
        <ReviewVisualization data={results.mapResult} />
      </Grid>
      <Grid
        item
        sm={3}
        sx={{ height: '100%', overflowX: 'hidden', overflowY: 'auto' }}
      >
        <Box m={4}>
          <PageTitle title="Review" />
          <Box my={2}>
            <form onSubmit={handleSubmit(onSubmit)}>
              <ScaleSelect
                onChange={(scale) => {
                  setValue('scale', scale);
                }}
                selectedScale={selectedScale}
              />

              <ReviewAnalysisSelect />

              {selectedAnalysisName && selectedScale === AnalysisScale.MESO ? (
                <ReviewAOISelect />
              ) : null}

              {selectedAnalysisName && <AnalysisRunSelect />}

              {selectedAnalysisId && (
                <ResultSelect
                  onChange={(result) => {
                    resetResults();
                  }}
                />
              )}

              {selectedResultSpecification && (
                <Box my={2}>
                  <Typography
                    variant="caption"
                    dangerouslySetInnerHTML={{
                      __html: selectedResultSpecification.description,
                    }}
                  />
                </Box>
              )}

              {selectedResultSpecification &&
                selectedResultSpecification.parameters && (
                  <FormWrapper
                    onChange={formUpdated}
                    parameters={selectedResultSpecification.parameters}
                  />
                )}

              {results.panelResults.length > 0 && (
                <Box my={2}>
                  <ReviewResultPanel data={results.panelResults} />
                </Box>
              )}

              {results.mapResult.length > 0 && (
                <Box my={4}>
                  <Button
                    fullWidth
                    variant="contained"
                    color="secondary"
                    onClick={onDownloadClick}
                  >
                    Export
                  </Button>
                </Box>
              )}
            </form>
          </Box>
        </Box>
      </Grid>
      <LoadingIndicator
        loading={getResultMutation.isLoading || exportResultMutation.isLoading}
      />
    </Grid>
  );
}

export default ManualResultFetch;
