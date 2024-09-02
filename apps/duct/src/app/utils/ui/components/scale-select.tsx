import { AnalysisScale } from '@duct-core/data';
import { FormControl, InputLabel, Select, MenuItem } from '@mui/material';

interface ScaleSelectProps {
  onChange: (scale: AnalysisScale) => void;
  selectedScale: AnalysisScale;
}

const ScaleSelect = (props: ScaleSelectProps) => {
  const { onChange, selectedScale } = props;
  return (
    <FormControl sx={{ minWidth: 120 }} fullWidth margin="normal">
      <InputLabel id="scale-select">Select Scale</InputLabel>
      <Select
        label="Select Scale"
        labelId="scale-select"
        data-testid="scale-select"
        value={selectedScale}
        onChange={(e) => onChange(e.target.value as AnalysisScale)}
      >
        <MenuItem value={AnalysisScale.MESO}>Mesoscale</MenuItem>
        <MenuItem value={AnalysisScale.MICRO}>Microscale</MenuItem>
      </Select>
    </FormControl>
  );
};

export default ScaleSelect;
