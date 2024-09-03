import {
  AnalyseForm,
  AnalysisConfigResponse,
  AnalysisFormType,
  AnalysisScale,
  createAnalysisConfiguration,
  submitAnalysis,
} from '@duct-core/data';
import { PageTitle } from '@duct-core/ui';
import { LoadingButton } from '@mui/lab';
import {
  Box,
  Button,
  Step,
  StepContent,
  StepLabel,
  Stepper,
} from '@mui/material';
import { useState } from 'react';
import { useFormContext } from 'react-hook-form';
import { useMutation, useQueryClient } from 'react-query';
import { useNavigate } from 'react-router-dom';
import { useProject } from '../../../context/project.context';
import AnalyseStep1 from './step-1';
import AnalyseStep2 from './step-2';

export function WorkflowLanding() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const projectContext = useProject();
  const { watch } = useFormContext<AnalyseForm>();

  const projectId = projectContext?.project?.id || '';
  const [activeStep, setActiveStep] = useState(0);

  const handleNext = () => {
    setActiveStep((prevActiveStep) => prevActiveStep + 1);
  };

  const handleBack = () => {
    setActiveStep((prevActiveStep) => prevActiveStep - 1);
  };

  const scale = watch('scale');
  const analysisForm = watch('analysisForm');
  const aoi_obj_id = watch('aoi_obj_id');
  const scene = watch('scene');
  const analysis = watch('analysis');

  const addSceneToGroupMutation = useMutation(
    (params: {
      groupId: string;
      sceneId: string;
      groupAnalysisName: string;
      aoiId?: string;
    }) => {
      return submitAnalysis(
        projectId,
        params.groupId,
        params.groupAnalysisName,
        params.sceneId,
        params.aoiId
      );
    },
    {
      onSuccess: () => {
        // invalidate cache so congif list gets updated when user is sent there
        queryClient.invalidateQueries('getAnalysisConfigGroupedByConfig');
        navigate(`/app/manage`);
      },
    }
  );

  const createAnalysisConfigMutation = useMutation(
    (form: AnalysisFormType) => {
      return createAnalysisConfiguration(
        projectId,
        form.name,
        analysis.name,
        form
      );
    },
    {
      onSuccess: (res: AnalysisConfigResponse) => {
        if (scene) {
          const configName = analysisForm ? analysisForm.name : 'default';
          const params = {
            groupId: res.id,
            sceneId: scene.id,
            groupAnalysisName: `${configName}.${scene.name}`,
            aoiId: aoi_obj_id,
          };
          addSceneToGroupMutation.mutateAsync(params);
        }
      },
    }
  );

  const shouldDisableStep1Progress = () => {
    if (scale === AnalysisScale.MICRO) {
      // require aoi id only for micro analyses
      return !scene || !aoi_obj_id;
    }
    return !scene;
  };

  const shouldDisableStep2Submit = () => {
    // TODO: check rjsf form validity as well
    return analysisForm?.name ? false : true;
  };

  const onFormSubmit = () => {
    // create group
    createAnalysisConfigMutation.mutate(analysisForm);
  };

  return (
    <Box m={4}>
      <PageTitle title="Configure Analysis" />
      <Stepper activeStep={activeStep} orientation="vertical">
        <Step>
          <StepLabel>Select Analysis Scale</StepLabel>
          <StepContent>
            <AnalyseStep1 />
            <Box sx={{ mb: 2, float: 'right' }}>
              <div>
                <Button
                  variant="contained"
                  onClick={handleNext}
                  disabled={shouldDisableStep1Progress()}
                >
                  Continue
                </Button>
              </div>
            </Box>
          </StepContent>
        </Step>
        <Step>
          <StepLabel>Select Analysis Attributes</StepLabel>
          <StepContent>
            <AnalyseStep2 />
            <Box sx={{ mb: 2, float: 'right' }}>
              <div>
                <Button onClick={handleBack} sx={{ mt: 1, mr: 1 }}>
                  Back
                </Button>
                <LoadingButton
                  loading={
                    createAnalysisConfigMutation.isLoading ||
                    addSceneToGroupMutation.isLoading
                  }
                  disabled={shouldDisableStep2Submit()}
                  variant="contained"
                  color="secondary"
                  onClick={onFormSubmit}
                >
                  Analyse
                </LoadingButton>
              </div>
            </Box>
          </StepContent>
        </Step>
      </Stepper>
    </Box>
  );
}

export default WorkflowLanding;
