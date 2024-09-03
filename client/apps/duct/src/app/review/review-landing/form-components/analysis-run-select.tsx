import {
  AnalysisConfigItemByConfig,
  AnalysisState,
  ReviewForm,
  SceneListItem,
  getAnalysisConfigGroupedByConfig,
} from '@duct-core/data';
import {
  Alert,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Skeleton,
} from '@mui/material';
import { useEffect, useState } from 'react';
import { Controller, useFormContext } from 'react-hook-form';
import { useQuery } from 'react-query';
import { useProject } from '../../../context/project.context';
import { useReview } from '../../../context/review.context';

const AnalysisRunSelect = () => {
  const { control, setValue, watch } = useFormContext<ReviewForm>();
  const projectContext = useProject();
  const reviewContext = useReview();
  const projectId = projectContext?.project?.id || '';
  const [analysisRuns, setAnalysisRuns] = useState<SceneListItem[]>([]);
  const filteredAnalysisName = watch('selectedAnalysisName');

  const { data, error, isLoading } = useQuery<
    AnalysisConfigItemByConfig[],
    Error
  >(
    ['getAnalysisConfigGroupedByConfig', projectId],
    () => getAnalysisConfigGroupedByConfig(projectId),
    {
      retry: false,
      onSuccess(data) {
        setRuns(data);
      },
      enabled: projectId !== '',
    }
  );

  // when the user changes analysis type, filter out the run again
  useEffect(() => {
    if (data) {
      setRuns(data);
    }
  }, [filteredAnalysisName]);

  const setRuns = (list: AnalysisConfigItemByConfig[]) => {
    const runs: SceneListItem[] = [];
    // list of all analyses
    list.forEach((config) => runs.push(...config.analyses));
    // filter completed and of same type as selected analysis
    const filteredAnalyses = runs.filter(
      (analysis) =>
        analysis.status === AnalysisState.COMPLETED &&
        analysis.analysis_type === filteredAnalysisName
    );

    const fieldValue = watch('selectedAnalysisId');
    let defaultValue: SceneListItem | undefined = undefined;
    // fieldValue will be available when navigating from Manage to Review
    if (fieldValue) {
      defaultValue = filteredAnalyses.find(
        (analysis) => analysis.analysis_id === fieldValue
      );
    } else {
      // if user just clicked Review. Select the first one
      defaultValue = filteredAnalyses[0];
    }

    if (defaultValue) {
      reviewContext.setContext((prevState) => {
        const copy = { ...prevState };
        copy.sceneId = defaultValue.scene_id;
        copy.showBuildingFootprint = true;
        return copy;
      });
      setValue('selectedAnalysisId', defaultValue.analysis_id);
      setValue('selectedAnalysisResults', defaultValue.results);
    }

    setAnalysisRuns(filteredAnalyses);

    // if there are no analyses, clear the form
    if (filteredAnalyses.length === 0) {
      setValue('paramForm', undefined);
      setValue('selectedResultSpecification', undefined);
    }
  };

  if (error) {
    return null;
  }

  if (isLoading) {
    return <Skeleton variant="rectangular" height={50} />;
  }

  if (analysisRuns.length === 0) {
    return (
      <Alert sx={{ my: 1 }} severity="info">
        No successful runs available
      </Alert>
    );
  }

  return (
    <Controller
      name="selectedAnalysisId"
      control={control}
      render={({ field }) => {
        return (
          <FormControl sx={{ minWidth: 120 }} fullWidth margin="normal">
            <InputLabel id="analysis-group">Analysis Run</InputLabel>
            <Select {...field}>
              {analysisRuns.map((run) => (
                <MenuItem key={run.analysis_id} value={run.analysis_id}>
                  {run.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        );
      }}
    />
  );
};

export default AnalysisRunSelect;
