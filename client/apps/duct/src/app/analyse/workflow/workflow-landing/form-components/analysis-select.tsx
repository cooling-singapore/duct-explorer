import {
  AnalyseForm,
  AnalysisScale,
  GroupedAnalyses,
  getAnalyses,
} from '@duct-core/data';
import {
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Skeleton,
} from '@mui/material';
import { useEffect } from 'react';
import { Controller, useFormContext } from 'react-hook-form';
import { useQuery } from 'react-query';
import { useProject } from '../../../../context/project.context';

const AnalysisSelect = () => {
  const { watch, setValue, control } = useFormContext<AnalyseForm>();
  const projectContext = useProject();
  const projectId = projectContext?.project?.id || '';

  const filteredScale = watch('scale');

  const { data, isLoading, error } = useQuery(
    ['getAnalyses', projectId],
    () => getAnalyses(projectId, watch()),
    {
      refetchOnWindowFocus: false,
      onSuccess(data) {
        setDefaultSelection(data);
      },
    }
  );

  const setDefaultSelection = (list?: GroupedAnalyses) => {
    if (list && list[filteredScale] && list[filteredScale].length) {
      setValue('analysis_name', list[filteredScale][0].name);
      setValue('analysis', list[filteredScale][0]);
    }
  };

  // effect to update the default value when the scale changes
  useEffect(() => {
    setDefaultSelection(data);
  }, [filteredScale]);

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
      name="analysis_name"
      control={control}
      render={({ field }) => {
        const { onChange, ref, name, value, onBlur } = field;

        const changed = (name: string) => {
          onChange(name);

          const flatList = [...data.meso, ...data.micro];
          const selectedAnalysis = flatList.find(
            (analysis) => analysis.name === name
          );
          if (selectedAnalysis) {
            setValue('analysis', selectedAnalysis);
          }
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
              label="Select Analysis"
              labelId="analysis-select"
              data-testid="analysis-select"
            >
              {filteredScale === AnalysisScale.MESO
                ? data?.meso?.map((analysis) => (
                    <MenuItem key={analysis.name} value={analysis.name}>
                      {analysis.label}
                    </MenuItem>
                  ))
                : data?.micro?.map((analysis) => (
                    <MenuItem key={analysis.name} value={analysis.name}>
                      {analysis.label}
                    </MenuItem>
                  ))}
            </Select>
          </FormControl>
        );
      }}
    />
  );
};

export default AnalysisSelect;
