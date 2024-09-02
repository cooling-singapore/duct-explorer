import {
  Analysis,
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
import { useQuery } from 'react-query';
import { useProject } from '../../../context/project.context';
import { useEffect, useState } from 'react';

interface AnalysisSelectProps {
  onChange: (analysis: Analysis) => void;
  filteredScale: AnalysisScale;
}

const AnalysisSelect = (props: AnalysisSelectProps) => {
  const { onChange, filteredScale } = props;
  const [selected, setSelected] = useState('');
  const projectContext = useProject();
  const projectId = projectContext?.project?.id || '';

  const { data, isLoading, error } = useQuery(
    ['getAnalyses', projectId],
    () => getAnalyses(projectId),
    {
      refetchOnWindowFocus: false,
      onSuccess(data) {
        setDefaultSelection(data);
      },
    }
  );

  const setDefaultSelection = (list?: GroupedAnalyses) => {
    if (list && list[filteredScale] && list[filteredScale].length) {
      if (list[filteredScale][0].name !== selected) {
        setSelected(list[filteredScale][0].name);
        onChange(list[filteredScale][0]);
      }
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

  const changed = (analysisName: string) => {
    setSelected(analysisName);
    const flatList = [...data.meso, ...data.micro];
    const selectedAnalysis = flatList.find(
      (analysis) => analysis.name === analysisName
    );
    if (selectedAnalysis) {
      onChange(selectedAnalysis);
    }
  };

  return (
    <FormControl sx={{ minWidth: 120 }} fullWidth margin="normal">
      <InputLabel id="analysis-select">Analysis Type</InputLabel>
      <Select
        label="Select Analysis"
        labelId="analysis-select"
        data-testid="analysis-select"
        value={selected}
        onChange={(e) => changed(e.target.value)}
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
};

export default AnalysisSelect;
