import { AnalysisScale, ReviewForm, getAnalyses } from '@duct-core/data';
import {
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Skeleton,
} from '@mui/material';
import { Controller, useFormContext } from 'react-hook-form';
import { useQuery } from 'react-query';
import { useProject } from '../../../context/project.context';

const ReviewAnalysisSelect = () => {
  const { control, watch, resetField, setValue } = useFormContext<ReviewForm>();
  const projectContext = useProject();
  const projectId = projectContext?.project?.id || '';
  const selectedScale = watch('scale');

  const { data, isLoading, error } = useQuery(
    ['getAnalyses', projectId],
    () => getAnalyses(projectId),
    {
      refetchOnWindowFocus: false,
      enabled: projectId !== '',
    }
  );

  if (error) {
    return null;
  }

  if (isLoading) {
    return <Skeleton variant="rectangular" height={50} />;
  }

  if (!data) {
    return null;
  }

  return (
    <Controller
      name="selectedAnalysisName"
      control={control}
      render={({ field }) => {
        const { onChange, ref, name, value, onBlur } = field;

        const changed = (analysisName: string) => {
          resetField('selectedAnalysisId');
          setValue('paramForm', undefined);
          onChange(analysisName);
        };

        return (
          <FormControl sx={{ minWidth: 120 }} fullWidth margin="normal">
            <InputLabel id="analysis-select">Analysis Type</InputLabel>
            <Select
              ref={ref}
              name={name}
              value={value}
              onBlur={onBlur}
              onChange={(event) => changed(event.target.value)}
            >
              {selectedScale === AnalysisScale.MESO
                ? data.meso?.map((analysis) => (
                    <MenuItem key={analysis.name} value={analysis.name}>
                      {analysis.label}
                    </MenuItem>
                  ))
                : data.micro?.map((analysis) => (
                    <MenuItem key={analysis.name} value={analysis.name}>
                      {analysis.label}
                    </MenuItem>
                  ))}
            </Select>
          </FormControl>
        );
      }}
    ></Controller>
  );
};

export default ReviewAnalysisSelect;
