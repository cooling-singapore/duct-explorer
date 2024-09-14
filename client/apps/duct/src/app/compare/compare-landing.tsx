import FlipIcon from '@mui/icons-material/Flip';
import JoinInnerIcon from '@mui/icons-material/JoinInner';
import {
  Alert,
  Box,
  Button,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  SelectChangeEvent,
  Skeleton,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import { IChangeEvent } from '@rjsf/core';
import Form from '@rjsf/mui';
import validator from '@rjsf/validator-ajv8';
import { useSnackbar } from 'notistack';
import { useEffect, useReducer } from 'react';
import { useMutation, useQuery, useQueryClient } from 'react-query';

import {
  Analysis,
  AnalysisConfigItemByConfig,
  AnalysisScale,
  AnalysisState,
  CompareActionKind,
  SceneListItem,
  exportDeltaCompareVisualizationData,
  getAnalysisCompareVisualizationData,
  getAnalysisConfigGroupedByConfig,
  getDeltaCompareVisualizationData,
} from '@duct-core/data';
import { LoadingIndicator, PageTitle } from '@duct-core/ui';
import { useProject } from '../context/project.context';
import { ProvideReviewContext } from '../context/review.context';
import { ProvideSBSViewContext } from '../context/sbs-view.context';
import { ProvideViewContext } from '../context/view.context';
import ReviewResultPanel from '../review/review-result-panel/review-result-panel';
import ReviewVisualization from '../review/review-visualization/review-visualization';
import AnalysisSelect from '../utils/ui/components/analysis-select';
import ScaleSelect from '../utils/ui/components/scale-select';
import { filterMapResults, filterPanelResults } from '../utils/utils';
import { resultCompareReducer } from './compare.reducer';
import CompareAOISelect from './form-components/compare-aoi-select';
import ReviewVisualizationComparison from './review-visualization-comparison';

const INITIAL_STATE = {
  scale: AnalysisScale.MESO,
  selectedAnalysis: undefined,
  analysisRuns: [],
  rightRunList: [],
  leftRun: undefined,
  rightRun: undefined,
  resultName: undefined,
  leftResult: undefined,
  rightResult: undefined,
  isDeltaCompare: false,
  deltaResult: undefined,
  paramForm: {},
  formComplete: false,
  selectedResult: undefined,
  panelResults: undefined,
  aoi_obj_id: undefined,
};

function CompareLanding() {
  const queryClient = useQueryClient();
  const projectContext = useProject();
  const projectId = projectContext?.project?.id || '';
  const { enqueueSnackbar } = useSnackbar();
  const [state, dispatch] = useReducer(resultCompareReducer, INITIAL_STATE);

  const {
    data: configList,
    error: configListError,
    isLoading: configListLoading,
  } = useQuery<AnalysisConfigItemByConfig[], Error>(
    ['getAnalysisConfigGroupedByConfig', projectId],
    () => getAnalysisConfigGroupedByConfig(projectId),
    {
      retry: false,
    }
  );

  const getResultMutation = useMutation(
    (params: {
      analysisId0: string;
      analysisId1: string;
      resultId: string;
      formParams: object | undefined;
    }) =>
      getAnalysisCompareVisualizationData(
        projectId,
        params.analysisId0,
        params.analysisId1,
        params.resultId,
        params.formParams
      )
        .then((res) => {
          dispatch({
            type: CompareActionKind.SET_RESULT,
            payload: {
              rightResult: res.results1,
              leftResult: res.results0,
              panelResults: res.chart_results,
            },
          });
        })
        .catch((err) => {
          enqueueSnackbar('Result fetch failed', {
            variant: 'error',
          });
          console.error(err);
        })
  );

  const getDeltaResultMutation = useMutation(
    (params: {
      analysisId0: string;
      analysisId1: string;
      resultId: string;
      formParams: object | undefined;
      isLeft: boolean;
    }) =>
      getDeltaCompareVisualizationData(
        projectId,
        params.analysisId0,
        params.analysisId1,
        params.resultId,
        params.formParams
      )
        .then((res) => {
          const mapResult = filterMapResults(res);
          const panelResults = filterPanelResults(res);

          dispatch({
            type: CompareActionKind.SET_DELTA_RESULT,
            payload: {
              deltaResult: mapResult,
              panelResults: panelResults,
            },
          });
        })
        .catch((err) => {
          enqueueSnackbar('Result fetch failed', {
            variant: 'error',
          });
          console.error(err);
        })
  );

  const exportDeltaResultMutation = useMutation(
    (params: {
      analysisId0: string;
      analysisId1: string;
      resultId: string;
      formParams: object | undefined;
      fileName: string;
    }) =>
      exportDeltaCompareVisualizationData(
        projectId,
        params.analysisId0,
        params.analysisId1,
        params.resultId,
        params.formParams
      )
        .then((res) => {
          const url = window.URL.createObjectURL(res);
          const link = document.createElement('a');
          link.href = url;
          link.setAttribute('download', params.fileName);
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

  useEffect(() => {
    // fetch result if view changes && user has completed form
    if (state.formComplete && state.leftRun && state.rightRun) {
      if (!state.isDeltaCompare) {
        // fetch results for both 🥳
        const props = {
          analysisId0: state.leftRun.analysis_id,
          analysisId1: state.rightRun.analysis_id,
          resultId: state.selectedResult?.name || '',
          formParams:
            state.scale === AnalysisScale.MESO
              ? { ...state.paramForm, display_aoi_obj_id: state.aoi_obj_id }
              : state.paramForm, // aoi id is only required for meso scale results
        };

        getResultMutation.mutate(props);
      } else if (state.isDeltaCompare) {
        const props = {
          analysisId0: state.leftRun.analysis_id,
          analysisId1: state.rightRun.analysis_id,
          resultId: state.selectedResult?.name || '',
          formParams:
            state.scale === AnalysisScale.MESO
              ? { ...state.paramForm, display_aoi_obj_id: state.aoi_obj_id }
              : state.paramForm, // aoi id is only required for meso scale results
          isLeft: true,
        };
        getDeltaResultMutation.mutate(props);
      }
    }
  }, [state.paramForm, state.isDeltaCompare, state.formComplete]);

  if (configListError) {
    console.error(configListError || 'CompareLanding: something went wrong');
    return null;
  }

  const leftRunChange = (event: SelectChangeEvent<string>) => {
    const value = event.target.value;
    //find run by id
    const selectedAnalysis = state.analysisRuns?.find(
      (run) => run.analysis_id === value
    );

    if (selectedAnalysis) {
      let rightRunList: SceneListItem[] = [];

      if (state.scale === AnalysisScale.MESO) {
        // remove the analysis selected on the left from the right list
        rightRunList =
          state.analysisRuns?.filter(
            (run) => run.analysis_id !== selectedAnalysis.analysis_id
          ) || [];
      } else {
        // only show analyese that share the same AOI on the right
        rightRunList =
          state.analysisRuns?.filter(
            (run) =>
              run.analysis_id !== selectedAnalysis.analysis_id &&
              run.aoi_obj_id === selectedAnalysis.aoi_obj_id
          ) || [];
      }

      dispatch({
        type: CompareActionKind.SET_LEFT_RUN,
        payload: {
          leftRun: selectedAnalysis,
          rightRunList,
        },
      });
    }
  };

  const rightRunChange = (event: SelectChangeEvent<string>) => {
    const value = event.target.value;
    //find run by id
    const selectedAnalysis = state.analysisRuns?.find(
      (run) => run.analysis_id === value
    );

    dispatch({
      type: CompareActionKind.SET_RIGHT_RUN,
      payload: {
        rightRun: selectedAnalysis,
      },
    });
  };

  const handleAnalysisChange = (selectedAnalysis: Analysis) => {
    if (configList) {
      const analysisRuns: SceneListItem[] = [];
      // list of all asnalyses
      configList.forEach((config) => analysisRuns.push(...config.analyses));
      // filter completed and of same type as selected analysis
      const filteredAnalyses = analysisRuns.filter(
        (analysis) =>
          analysis.status === AnalysisState.COMPLETED &&
          analysis.analysis_type === selectedAnalysis.name
      );

      dispatch({
        type: CompareActionKind.SET_SELECTED_ANALYSIS,
        payload: {
          selectedAnalysis,
          analysisRuns: filteredAnalyses,
        },
      });
    }
  };

  const handleResultNameChange = (event: SelectChangeEvent<string>) => {
    const selectedResult = state.rightRun?.results.find(
      (result) => result.name === event.target.value
    );

    if (selectedResult) {
      const hasParamForm = Object.keys(
        selectedResult.specification.parameters
      ).length;

      dispatch({
        type: CompareActionKind.SET_SELECTED_RESULT,
        payload: {
          selectedResult,
          formComplete: !hasParamForm,
        },
      });
    }
  };

  const handleCompareViewChange = (
    event: React.MouseEvent<HTMLElement>,
    newAlignment: string | null
  ) => {
    dispatch({
      type: CompareActionKind.SET_COMPARE_MODE,
      payload: {
        isDeltaCompare: newAlignment === 'delta' ? true : false,
      },
    });
  };

  const handleAOIChange = (aoiId: string) => {
    dispatch({
      type: CompareActionKind.SET_AOI,
      payload: {
        aoi_obj_id: aoiId,
      },
    });
  };

  const onDownloadClick = () => {
    if (state.leftRun && state.rightRun) {
      const props = {
        analysisId0: state.leftRun.analysis_id,
        analysisId1: state.rightRun.analysis_id,
        resultId: state.selectedResult?.name || '',
        formParams:
          state.scale === AnalysisScale.MESO
            ? { ...state.paramForm, display_aoi_obj_id: state.aoi_obj_id }
            : state.paramForm, // aoi id is only required for meso scale results
        fileName: `${state.leftRun.name}_${state.rightRun.name}_${state.selectedResult?.name}.${state.selectedResult?.export_format}`,
      };
      exportDeltaResultMutation.mutate(props);
    }
  };

  const formUpdated = (form: IChangeEvent) => {
    if (form.edit && form.errors.length === 0 && state.rightRun) {
      dispatch({
        type: CompareActionKind.SET_FORM_COMPLETED,
        payload: {
          formComplete: true,
          paramForm: form.formData,
        },
      });
    } else {
      dispatch({
        type: CompareActionKind.SET_FORM,
        payload: {
          paramForm: form.formData,
          formComplete: false,
        },
      });
    }
  };

  return (
    <Grid container height="100%">
      <Grid item lg={9} sm={8}>
        <ProvideReviewContext>
          <Box sx={{ height: '100%' }}>
            {state.isDeltaCompare && (
              <ProvideViewContext>
                <ReviewVisualization data={state.deltaResult} />
              </ProvideViewContext>
            )}
            {!state.isDeltaCompare && (
              <ProvideSBSViewContext>
                <ReviewVisualizationComparison
                  rightData={state.rightResult}
                  leftData={state.leftResult}
                />
              </ProvideSBSViewContext>
            )}
          </Box>
          <LoadingIndicator loading={queryClient.isMutating() > 0} />
        </ProvideReviewContext>
      </Grid>
      <Grid item lg={3} sm={4}>
        <Box m={4}>
          <>
            <PageTitle title="Compare" />
            <Box my={2}>
              <ToggleButtonGroup
                value={state.isDeltaCompare ? 'delta' : 'sbs'}
                exclusive
                onChange={handleCompareViewChange}
                aria-label="Compare Mode"
                size="small"
                color="secondary"
              >
                <ToggleButton value="sbs" data-testid="sbs">
                  <FlipIcon /> Side by side
                </ToggleButton>
                <ToggleButton value="delta" data-testid="delta">
                  <JoinInnerIcon /> Delta
                </ToggleButton>
              </ToggleButtonGroup>
            </Box>

            {configListLoading ? (
              <Stack spacing={1} direction="column" width="100%" sx={{ my: 2 }}>
                <Skeleton variant="rectangular" height={50} width="100%" />
                <Skeleton variant="rectangular" height={50} width="100%" />
                <Skeleton variant="rectangular" height={50} width="100%" />
              </Stack>
            ) : (
              <>
                <ScaleSelect
                  onChange={(scale) =>
                    dispatch({
                      type: CompareActionKind.SET_SCALE,
                      payload: {
                        scale: scale,
                      },
                    })
                  }
                  selectedScale={state.scale}
                />

                <AnalysisSelect
                  onChange={handleAnalysisChange}
                  filteredScale={state.scale}
                />

                <Grid container columnSpacing={{ md: 0, lg: 1 }}>
                  <Grid item lg={6} md={12} sm={12} xs={12}>
                    <FormControl fullWidth margin="normal">
                      <InputLabel id="analysis-left">
                        Analysis Run A (Left)
                      </InputLabel>
                      <Select
                        label="Analysis Run (Left)"
                        labelId="analysis-left"
                        value={state.leftRun?.analysis_id || ''}
                        onChange={leftRunChange}
                        data-testid="analysis-left"
                      >
                        {state.analysisRuns?.map((run, index) => (
                          <MenuItem
                            key={run.name}
                            value={run.analysis_id}
                            data-testid={`run-a-${index}`}
                          >
                            {run.name}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </Grid>
                  <Grid item lg={6} md={12} sm={12} xs={12}>
                    <FormControl fullWidth margin="normal">
                      <InputLabel id="analysis-right">
                        Analysis Run B (Right)
                      </InputLabel>
                      <Select
                        label="Analysis Run (Right)"
                        labelId="analysis-right"
                        value={state.rightRun?.analysis_id || ''}
                        onChange={rightRunChange}
                        data-testid="analysis-right"
                      >
                        {state.rightRunList?.map((run, index) => (
                          <MenuItem
                            key={run.name}
                            value={run.analysis_id}
                            data-testid={`run-b-${index}`}
                          >
                            {run.name}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </Grid>
                </Grid>

                {state.scale === AnalysisScale.MICRO && (
                  <Box>
                    <Alert severity="info">
                      Analysis run B will exclusively list runs within the same
                      Area of Interest as Analysis run A
                    </Alert>
                  </Box>
                )}

                <FormControl fullWidth margin="normal">
                  <InputLabel id="select-result">Select Result</InputLabel>
                  <Select
                    label="Select Result"
                    labelId="select-result"
                    value={state.selectedResult?.name || ''}
                    onChange={handleResultNameChange}
                    data-testid="select-result"
                  >
                    {state.rightRun?.results?.map((result, index) => (
                      <MenuItem
                        key={result.name}
                        value={result.name}
                        data-testid={`result-${index}`}
                      >
                        {result.label ? result.label : result.name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                {state.scale === AnalysisScale.MESO && (
                  <CompareAOISelect onChange={handleAOIChange} />
                )}
              </>
            )}

            {state.selectedResult?.specification && (
              <Box sx={{ width: '100%' }}>
                <Form
                  schema={state.selectedResult?.specification.parameters}
                  onChange={formUpdated}
                  liveValidate
                  showErrorList={false}
                  formData={state.paramForm}
                  validator={validator}
                >
                  {/* Empty fragment allows us to remove the submit button from the rjsf form */}
                  {/*  eslint-disable-next-line react/jsx-no-useless-fragment */}
                  <></>
                </Form>
              </Box>
            )}
          </>

          {state.panelResults && state.panelResults.length > 0 && (
            <Box my={2}>
              <ReviewResultPanel data={state.panelResults} />
            </Box>
          )}

          {state.isDeltaCompare && state.selectedResult?.name && (
            <Grid container>
              <Grid item xs={12}>
                <Box my={2}>
                  <Button
                    fullWidth
                    variant="contained"
                    color="secondary"
                    onClick={onDownloadClick}
                  >
                    Export
                  </Button>
                </Box>
              </Grid>
            </Grid>
          )}
        </Box>
      </Grid>
    </Grid>
  );
}

export default CompareLanding;
