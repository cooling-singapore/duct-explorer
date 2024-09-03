import { useReducer } from 'react';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useNavigate } from 'react-router-dom';
import {
  Stepper,
  Step,
  StepLabel,
  StepContent,
  Box,
  Button,
  Grid,
  IconButton,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Typography,
  TextField,
  Skeleton,
} from '@mui/material';
import { useMutation, useQuery } from 'react-query';
import { useSnackbar } from 'notistack';

import { LoadingIndicator, PageTitle } from '@duct-core/ui';
import { useProject } from '../../context/project.context';
import {
  DataSet,
  getImports,
  importGeoDataset,
  ImportWorkflowAction,
  ImportStage,
  UploadVerificationResponse,
  updateDataset,
  PendingSaveLayer,
  LayerDataSet,
  FixMode,
  importLibDataset,
  UploadDatasetTarget,
  AvailableDataset,
} from '@duct-core/data';
import { importWorkflowReducer } from './import-workflow.reducer';
import { useImport } from '../../context/import.context';
import FixStage from './steps/fix-stage';
import ZoneSelectionStage from './steps/zone-selection-stage';
import ImportValidatorWidget from '../import-validation/import-validator';
import ImportShape from '../import-shape/import-shape';

export function ImportWorkflow() {
  const { enqueueSnackbar } = useSnackbar();
  const importContext = useImport();
  const navigate = useNavigate();
  const projectContext = useProject();
  const projectId = projectContext?.project?.id || '';
  const INITIAL_STATE = {
    activeStep: 0,
    loading: false,
    selectedDataType: undefined,
    tempObjId: undefined,
    importName: undefined,
    fixMode: FixMode.PICK,
  };

  const [state, dispatch] = useReducer(importWorkflowReducer, INITIAL_STATE);

  const showZonePicker =
    state.fixMode === FixMode.PICK || state.fixMode === FixMode.FIX_AND_PICK;

  const showFixStep =
    state.fixMode === FixMode.FIX_AND_PICK ||
    state.fixMode === FixMode.FIX_AND_SKIP;

  const isAreaGeoJsonDefined = !!importContext.context.areaGeoJson;

  const { data, error, isLoading } = useQuery<DataSet, Error>(
    ['getImports', projectId],
    () => getImports(projectId),
    {
      retry: false,
      enabled: projectId !== '',
    }
  );

  const onImportSuccess = (data: AvailableDataset) => {
    enqueueSnackbar('Import successful', {
      variant: 'success',
    });
    dispatch({
      type: ImportWorkflowAction.SET_LOADING,
      payload: {
        loading: false,
      },
    });

    // take user on to import landing
    navigateToImport(data.obj_id);
  };

  const onImportError = () => {
    dispatch({
      type: ImportWorkflowAction.SET_LOADING,
      payload: {
        loading: false,
      },
    });
    enqueueSnackbar('Sorry, something went wrong', {
      variant: 'error',
    });
  };

  const importGeoMutation = useMutation(
    (props: { zoneIds: number[]; datasets: LayerDataSet }) =>
      importGeoDataset(
        projectId,
        state.importName || '',
        props.zoneIds,
        props.datasets
      ),
    {
      onSuccess: onImportSuccess,
      onError: onImportError,
    }
  );

  const importLibMutation = useMutation(
    (props: { objId: string }) =>
      importLibDataset(projectId, state.importName || '', props.objId),
    {
      onSuccess: onImportSuccess,
      onError: onImportError,
    }
  );

  const saveEditsMutation = useMutation(
    (props: { layer: PendingSaveLayer; geo_type: string }) => {
      return updateDataset(projectId, props.layer, props.geo_type);
    }
  );

  if (error) {
    console.error(error || 'ImportWorkflow: something went wrong');
    return null;
  }

  const handleNext = () => {
    dispatch({
      type: ImportWorkflowAction.SET_ACTIVE_STEP,
      payload: {
        activeStep: state.activeStep + 1,
      },
    });
  };

  const handleBack = () => {
    dispatch({
      type: ImportWorkflowAction.SET_ACTIVE_STEP,
      payload: {
        activeStep: state.activeStep - 1,
      },
    });
  };

  const navigateToImport = (obj_id?: string) => {
    importContext.setContext((prevState) => {
      const copy = { ...prevState };
      copy.uploadResponse = undefined;
      copy.importStage = ImportStage.Default;
      copy.selectedZones = new Set<number>();
      return copy;
    });

    if (obj_id) {
      navigate(`/app/import?selected_id=${obj_id}`);
    } else {
      navigate('/app/import');
    }
  };

  const onDataTypeSelected = (dataType: string) => {
    const found = data?.supported.find((type) => type.data_type === dataType);
    if (found) {
      dispatch({
        type: ImportWorkflowAction.SET_SELECTED_DATATYPE,
        payload: {
          selectedDataType: found,
        },
      });
    }
  };

  const afterDataTypeSelected = () => {
    // show area selection layer for AOI data type
    if (
      state.selectedDataType &&
      state.selectedDataType.data_type === 'area_of_interest'
    ) {
      importContext.setContext((prevState) => {
        const copy = { ...prevState };
        copy.showAreaSelection = true;
        return copy;
      });
    }

    handleNext();
  };

  const onImportClick = () => {
    dispatch({
      type: ImportWorkflowAction.SET_LOADING,
      payload: {
        loading: true,
      },
    });
    // set map back to default mode
    importContext.setContext((prevState) => {
      const copy = { ...prevState };
      copy.importStage = ImportStage.Default;
      return copy;
    });
    if (importContext.context.currentTarget === UploadDatasetTarget.GEODB) {
      // create list: geotype: objectIds
      const datasets: LayerDataSet = {};

      importContext.context.uploadResponse?.datasets.forEach((dataSet) => {
        datasets[dataSet.info.geo_type] = dataSet.obj_id || '';
      });

      // get selected zone IDs
      const zoneIds = Array.from(
        importContext.context.selectedZones || new Set()
      ) as number[];

      importGeoMutation.mutate({ zoneIds, datasets });
    } else {
      importLibMutation.mutate({ objId: importContext.context.objId || '' });
    }
  };

  const onAfterImport = (res: UploadVerificationResponse) => {
    if (res.datasets.length) {
      // show Update Attributes stage if FixMode is 'fix-attr-and-pick'
      const currentFixMode = res.mode;
      const currentTarget = res.datasets[0].target;

      dispatch({
        type: ImportWorkflowAction.SET_FIX_MODE,
        payload: {
          fixMode: currentFixMode,
        },
      });

      // upload done, take user to next step
      handleNext();

      //set the upload response  context
      importContext.setContext((prevState) => {
        const copy = { ...prevState };
        copy.currentTarget = currentTarget;

        if (currentTarget === UploadDatasetTarget.LIBRARY) {
          // set obj id to context if its lib item
          copy.objId = res.datasets[0].obj_id || '';
        }

        // response will get picked up by import vis component and load map layers
        copy.uploadResponse = res;
        // if its pick mode, gotta set the map to zone selection mode
        if (currentFixMode === FixMode.PICK) {
          copy.importStage = ImportStage.ZoneSelection;
        }
        return copy;
      });
    }
  };

  const confirmFixes = () => {
    // move the user to zone pick step
    handleNext();

    // save fixes? updateDataset
    for (const geo_type in importContext.context.layersToSave) {
      saveEditsMutation.mutate({
        layer: importContext.context.layersToSave[geo_type],
        geo_type,
      });
    }

    //set the map to zone pick mode
    importContext.setContext((prevState) => {
      const copy = { ...prevState };
      copy.importStage = ImportStage.ZoneSelection;
      return copy;
    });
  };

  const exitZoneSelection = () => {
    // clear old selection
    importContext.setContext((prevState) => {
      const copy = { ...prevState };
      copy.selectedZones = new Set<number>();
      copy.importStage = ImportStage.Default;
      return copy;
    });

    handleBack();
  };

  const afterZoneSelection = () => {
    // check zones selected, if not dont proceed to next step
    const zoneCount = importContext.context.selectedZones?.size;
    if (!zoneCount) {
      enqueueSnackbar('Please pick at least one zone on the map to proceed', {
        variant: 'error',
      });
    } else {
      handleNext();
    }
  };

  const exitUpdateAttributes = () => {
    // clear uploadResponse
    importContext.setContext((prevState) => {
      const copy = { ...prevState };
      copy.uploadResponse = undefined;
      return copy;
    });

    handleBack();
  };

  const exitImport = () => {
    // hide area selection layer if its visible
    if (importContext.context.showAreaSelection) {
      importContext.setContext((prevState) => {
        const copy = { ...prevState };
        copy.showAreaSelection = false;
        return copy;
      });
    }

    handleBack();
  };

  return (
    <Box m={2}>
      <Grid container spacing={1} alignItems="flex-start">
        <Grid item md={2} lg={1}>
          <IconButton
            title="Back to Import management"
            edge="start"
            size="small"
            onClick={() => navigateToImport()}
          >
            <ArrowBackIcon />
          </IconButton>
        </Grid>
        <Grid item md={10} lg={11}>
          <PageTitle title="Import Data" />
        </Grid>
      </Grid>
      <Box my={2}>
        {isLoading ? (
          <Stack direction="column" spacing={1}>
            <Skeleton variant="circular" width={20} height={20} />
            <Skeleton variant="rectangular" width="80%" />
            <Skeleton variant="rectangular" width="100%" height={30} />
            <Skeleton variant="rectangular" width="20%" height={30} />
          </Stack>
        ) : (
          <Stepper activeStep={state.activeStep} orientation="vertical">
            <Step>
              <StepLabel>Select Data Type</StepLabel>
              <StepContent>
                <FormControl fullWidth margin="normal" size="small">
                  <InputLabel>Data Type</InputLabel>
                  <Select
                    label="Data Type"
                    fullWidth
                    value={state.selectedDataType?.data_type || ''}
                    onChange={(event) =>
                      onDataTypeSelected(event.target.value as string)
                    }
                  >
                    {data &&
                      data.supported.map((option) => (
                        <MenuItem
                          key={option.data_type}
                          value={option.data_type}
                        >
                          {option.data_type_label}
                        </MenuItem>
                      ))}
                  </Select>
                </FormControl>

                {state.selectedDataType && (
                  <>
                    <Box my={2}>
                      <img
                        style={{ width: '100%' }}
                        src={`./assets/importExamples/${state.selectedDataType.preview_image_url}`}
                        alt="Import example"
                      />
                    </Box>
                    <Box my={2}>
                      <Typography
                        variant="body2"
                        dangerouslySetInnerHTML={{
                          __html: state.selectedDataType.description,
                        }}
                      />
                    </Box>
                  </>
                )}

                <Box mt={2}>
                  <Button
                    variant="contained"
                    color="secondary"
                    onClick={afterDataTypeSelected}
                    disabled={!state.selectedDataType}
                  >
                    Next
                  </Button>
                </Box>
              </StepContent>
            </Step>
            <Step>
              <StepLabel>
                {importContext.context.showAreaSelection
                  ? 'Upload or Draw Area of Interest'
                  : 'Import'}
              </StepLabel>
              <StepContent>
                {state.selectedDataType && !isAreaGeoJsonDefined && (
                  <ImportValidatorWidget
                    data_type={state.selectedDataType.data_type}
                    onChange={onAfterImport}
                  />
                )}

                {isAreaGeoJsonDefined && (
                  <ImportShape
                    onChange={onAfterImport}
                    shape={importContext.context.areaGeoJson as string}
                  />
                )}

                <Stack mt={4} spacing={1} direction="row">
                  <Button variant="contained" onClick={exitImport}>
                    Back
                  </Button>
                </Stack>
              </StepContent>
            </Step>

            {/* show the update attributes section only for fix modes with "fix" in em */}
            {showFixStep && (
              <Step>
                <StepLabel>Update Attributes</StepLabel>
                <StepContent>
                  <Typography variant="caption" gutterBottom>
                    This step ensures that the data layers contain the necessary
                    attributes and can be used appropriately. Use the edit
                    feature on the map to assign attributes to a layer or update
                    an existing one. You may also delete layers that are not
                    required.
                  </Typography>
                  <FixStage />

                  <Stack mt={4} spacing={1} direction="row">
                    <Button variant="contained" onClick={exitUpdateAttributes}>
                      Back
                    </Button>
                    <Button
                      variant="contained"
                      color="secondary"
                      onClick={confirmFixes}
                    >
                      Save changes
                    </Button>
                  </Stack>
                </StepContent>
              </Step>
            )}

            {/* show the zone selection only if mode is pick or fix and pick */}
            {showZonePicker && (
              <Step>
                <StepLabel
                  optional={
                    <Typography variant="caption">
                      Select on the zones on the map you would like to import
                    </Typography>
                  }
                >
                  Select Zone
                </StepLabel>
                <ZoneSelectionStage
                  handleBack={exitZoneSelection}
                  handleNext={afterZoneSelection}
                />
              </Step>
            )}

            <Step>
              <StepLabel>Confirmation</StepLabel>
              <StepContent>
                <Typography variant="caption">
                  This will create a new layer incorporating the selected
                  geometries which will later be presented as an alternative
                  zone geometry for you scene
                </Typography>
                <Box m={1}>
                  <TextField
                    fullWidth
                    required
                    variant="standard"
                    label="Dataset Name"
                    value={state.importName || ''}
                    onChange={(event) =>
                      dispatch({
                        type: ImportWorkflowAction.SET_IMPORT_NAME,
                        payload: {
                          importName: event.target.value,
                        },
                      })
                    }
                    helperText="Name the dataset"
                  />
                </Box>
                <Stack mt={4} spacing={1} direction="row">
                  <Button variant="contained" onClick={handleBack}>
                    Back
                  </Button>
                  <Button
                    variant="contained"
                    color="secondary"
                    onClick={onImportClick}
                    disabled={!state.importName}
                  >
                    Import
                  </Button>
                </Stack>
              </StepContent>
            </Step>
          </Stepper>
        )}
      </Box>
      <LoadingIndicator loading={state.loading} />
    </Box>
  );
}

export default ImportWorkflow;
