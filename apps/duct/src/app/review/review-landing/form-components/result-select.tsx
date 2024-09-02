import { AnalysisResult, ReviewForm } from '@duct-core/data';
import { FormControl, InputLabel, MenuItem, Select } from '@mui/material';
import { useEffect } from 'react';
import { Controller, useFormContext } from 'react-hook-form';

interface ResultSelectProps {
  onChange: (result: AnalysisResult) => void;
}

const ResultSelect = (props: ResultSelectProps) => {
  const { onChange } = props;
  const { control, setValue, watch } = useFormContext<ReviewForm>();
  const results = watch('selectedAnalysisResults');

  const setValues = (result: AnalysisResult) => {
    setValue('selectedResultName', result.name);
    setValue('selectedResultFormat', result.export_format);
    setValue('selectedResultSpecification', result.specification);
    onChange(result);
  };

  useEffect(() => {
    if (results && results.length) {
      setValues(results[0]);
    }
  }, [results]);

  if (!results) {
    return null;
  }

  return (
    <Controller
      name="selectedResultName"
      control={control}
      render={({ field }) => {
        const { onChange: onFieldChange, ref, name, value, onBlur } = field;

        const changed = (name: string) => {
          if (results && results.length) {
            const found = results.find((result) => result.name === name);
            if (found) {
              setValues(found);
              onFieldChange(found.name);
            }
          }
        };

        return (
          <FormControl fullWidth margin="normal">
            <InputLabel id="select-result">Select Result</InputLabel>
            <Select
              ref={ref}
              name={name}
              value={value}
              onBlur={onBlur}
              onChange={(event) => changed(event.target.value)}
            >
              {results.map((result, index) => (
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
        );
      }}
    />
  );
};

export default ResultSelect;
