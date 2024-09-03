import { useEffect, useState } from 'react';
import { useMutation, useQueryClient } from 'react-query';
import { useSnackbar } from 'notistack';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useNavigate } from 'react-router-dom';
import {
  Stepper,
  Step,
  StepLabel,
  StepContent,
  Alert,
  AlertTitle,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  IconButton,
  List,
  ListItem,
  ListItemText,
  TextField,
  Typography,
  useTheme,
} from '@mui/material';
import { AxiosError } from 'axios';

import { LoadingIndicator, PageTitle } from '@duct-core/ui';
import {
  saveScene,
  SaveSceneResponse,
  SceneType,
  SceneCreationStage,
  AppServerError,
} from '@duct-core/data';
import { useProject } from '../../../context/project.context';
import { useBuild } from '../../../context/build.context';
import ModuleSettings from './module-settings/module-settings';
import { useScene } from '../../../context/scene.context';
import { environment } from '../../../../environments/environment';

const multipleDesigns = {
  backgroundColor: '#4b9ef44d',
  borderColor: '#4b9ef4',
};

const alternateDesign = {
  backgroundColor: '#e97c4c4d',
  borderColor: '#e97c4c',
};

const colorBox = {
  height: '20px',
  width: '20px',
  border: 'solid 1px',
};

export function CreateSceneWorkflow() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();
  const theme = useTheme();
  const projectContext = useProject();
  const sceneContext = useScene();
  const buildContext = useBuild();
  const projectId = projectContext?.project?.id || '';
  const [showSceneNameModal, setShowSceneNameModal] = useState<boolean>(false);
  const [sceneName, setSceneName] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [disableModuleQueries, setDisableModuleQueries] = useState(false);
  const [activeStep, setActiveStep] = useState(0);

  useEffect(() => {
    setActiveStep(0);
    sceneContext.setContext((prevState) => {
      const copy = { ...prevState };
      copy.sceneType = SceneType.Islandwide;
      return copy;
    });

    // switch to ZoneVersionSeletion because we dont need area selection in build for now
    setMapToZoneSelection();

    return () => {
      // reset map state when leaving page
      buildContext.setContext((prevState) => {
        const copy = { ...prevState };
        copy.moduleVisLayers = [];
        copy.editorConfig = undefined;
        copy.mapType = SceneCreationStage.Default;
        return copy;
      });
    };
  }, []);

  const handleNext = () => {
    setActiveStep((prevActiveStep) => {
      return prevActiveStep + 1;
    });
  };

  const handleBack = () => {
    setActiveStep((prevActiveStep) => prevActiveStep - 1);
  };

  const setMapToZoneSelection = () => {
    buildContext.setContext((prevState) => {
      const copy = { ...prevState };
      copy.mapType = SceneCreationStage.ZoneVersionSeletion;
      return copy;
    });
  };

  const backToZoneSelection = () => {
    setMapToZoneSelection();
    handleBack();
  };

  const saveSceneMutation = useMutation(
    (name: string) => {
      setLoading(true);
      return saveScene(projectId, name, sceneContext.context);
    },
    {
      onSuccess: (response: SaveSceneResponse) => {
        setLoading(false);
        enqueueSnackbar(`${response.name} created successfully!`, {
          variant: 'success',
        });

        //invalidate getScenes so list gets updated
        queryClient.invalidateQueries('getScenes');
        //take user back to scene list
        navigateToBuild();
      },
      onError: (e: AxiosError<AppServerError>) => {
        setLoading(false);
        enqueueSnackbar(e.response?.data.reason || `Scene creation failed`, {
          variant: 'error',
        });
        console.error(e);
      },
    }
  );

  const saveSettings = () => {
    //open modal to get scene name
    setShowSceneNameModal(true);
    setDisableModuleQueries(true);
  };

  const onSaveScene = () => {
    setShowSceneNameModal(false);
    saveSceneMutation.mutate(sceneName);
  };

  const onSceneNameDialogClose = () => {
    setDisableModuleQueries(false);
    setShowSceneNameModal(false);
  };

  const navigateToBuild = () => {
    navigate('/app/build');
  };

  const exitGeometrySelection = () => {
    handleNext();
  };

  return (
    <Box m={2}>
      <Grid container spacing={1} alignItems="flex-start">
        <Grid item md={2} lg={1}>
          <IconButton
            title="Back to scene management"
            edge="start"
            size="small"
            onClick={() => navigateToBuild()}
          >
            <ArrowBackIcon />
          </IconButton>
        </Grid>
        <Grid item md={10} lg={11}>
          <PageTitle
            title="Scene Creation"
            description="Customize and save a new scene"
          />
        </Grid>
      </Grid>
      <Box my={2}>
        <Stepper activeStep={activeStep} orientation="vertical">
          <Step>
            <StepLabel>Select Urban Geometry Configuration</StepLabel>
            <StepContent>
              {sceneContext.context.sceneType === SceneType.Islandwide ? (
                <>
                  <Typography variant="caption" gutterBottom display="block">
                    This feature allows users to reconfigure the city with new
                    development plans in selected districts or zones. The
                    information used are the building footprints and building
                    height.
                  </Typography>
                  <Typography variant="caption">
                    The highlighted land plots contain multiple design options
                    that you have uploaded. Click on each of the plots to select
                    an alternate plan for this area.
                  </Typography>
                  <Grid
                    container
                    spacing={1}
                    sx={{ my: 1 }}
                    alignItems="center"
                  >
                    <Grid item>
                      <Box sx={{ ...colorBox, ...multipleDesigns }}></Box>
                    </Grid>
                    <Grid item>
                      <Typography variant="caption">
                        Multiple design options available
                      </Typography>
                    </Grid>
                  </Grid>
                  <Grid container spacing={1} alignItems="center">
                    <Grid item>
                      <Box sx={{ ...colorBox, ...alternateDesign }}></Box>
                    </Grid>
                    <Grid item>
                      <Typography variant="caption">
                        Alternate design selected
                      </Typography>
                    </Grid>
                  </Grid>
                </>
              ) : (
                <Typography variant="caption">
                  Use the selection tool to select the area you wish to
                  configure and click next.
                </Typography>
              )}

              {sceneContext.context.zoneVersions.length > 0 && (
                <Box my={4}>
                  <Typography
                    sx={{
                      fontSize: theme.typography.pxToRem(15),
                      fontWeight: theme.typography.fontWeightRegular,
                    }}
                  >
                    Zone Configurations
                  </Typography>
                  <List dense disablePadding>
                    {sceneContext.context.zoneVersions.map((zone) => (
                      <ListItem key={zone.zoneId}>
                        <ListItemText
                          primary={zone.zoneName}
                          secondary={zone.alternateName}
                        />
                      </ListItem>
                    ))}
                  </List>
                </Box>
              )}

              <Box my={4}>
                <Button
                  data-testid="next"
                  variant="contained"
                  color="secondary"
                  onClick={exitGeometrySelection}
                >
                  Next
                </Button>
              </Box>
            </StepContent>
          </Step>
          <Step>
            <StepLabel
              optional={
                <Typography variant="caption">
                  Each module allows you to change the relavant parameters to
                  create your own scenario. Some modules must be run
                  independently while others may be combined to run a holistic
                  analysis. Enable the modules you would like to explore to get
                  started.
                </Typography>
              }
            >
              Configure Scene Parameters
            </StepLabel>
            <StepContent>
              <ModuleSettings disableQueries={disableModuleQueries} />

              {sceneContext.context.errors.size > 0 && (
                <Box>
                  <Alert severity="error">
                    <AlertTitle>
                      The following modules require your attention.
                    </AlertTitle>
                    {Array.from(sceneContext.context.errors).map((module) => (
                      <li key={module}>{module}</li>
                    ))}
                  </Alert>
                </Box>
              )}

              <Box my={4}>
                <Button onClick={backToZoneSelection} sx={{ mr: 1 }}>
                  Back
                </Button>
                <Button
                  variant="contained"
                  color="secondary"
                  onClick={saveSettings}
                  disabled={sceneContext.context.errors.size > 0}
                >
                  Create scene
                </Button>
              </Box>
            </StepContent>
          </Step>
        </Stepper>
      </Box>

      <Dialog onClose={onSceneNameDialogClose} open={showSceneNameModal}>
        <DialogTitle>Name your scene</DialogTitle>
        <DialogContent sx={{ minWidth: '400px' }}>
          <TextField
            label="Scene Name"
            value={sceneName}
            onChange={(event) => setSceneName(event.target.value)}
            fullWidth
          />
        </DialogContent>
        <DialogActions>
          <Button variant="contained" onClick={onSceneNameDialogClose}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={onSaveScene}
            color="secondary"
            autoFocus
          >
            Create Scene
          </Button>
        </DialogActions>
      </Dialog>
      <LoadingIndicator loading={loading} />
    </Box>
  );
}

export default CreateSceneWorkflow;
