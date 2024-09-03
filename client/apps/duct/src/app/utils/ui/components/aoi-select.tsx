import { AnalyseForm, getAOIImports } from '@duct-core/data';
import {
  Alert,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Skeleton,
} from '@mui/material';
import { useEffect } from 'react';
import { Controller, useFormContext } from 'react-hook-form';
import { useQuery } from 'react-query';
import { useProject } from '../../../context/project.context';

const AOISelect = () => {
  const { control, unregister, setValue } = useFormContext<AnalyseForm>();
  const projectContext = useProject();
  const projectId = projectContext?.project?.id as string;

  const { data, isLoading } = useQuery(
    ['getAOIImports', projectId],
    () => getAOIImports(projectId),
    {
      refetchOnWindowFocus: false,
      onSuccess(data) {
        setValue('aoi_obj_id', data[0].obj_id);
      },
    }
  );

  if (isLoading) {
    return <Skeleton variant="rectangular" height={50} />;
  }

  if (data && data.length) {
    return (
      <Controller
        name="aoi_obj_id"
        control={control}
        render={({ field }) => (
          <FormControl sx={{ minWidth: 120 }} fullWidth margin="normal">
            <InputLabel id="analysis-select">
              Select Area of Interest
            </InputLabel>
            <Select
              {...field}
              label="Select Analysis"
              defaultValue={data[0].obj_id}
            >
              {data?.map((aoi) => (
                <MenuItem key={aoi.obj_id} value={aoi.obj_id}>
                  {aoi.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}
      />
    );
  } else {
    return (
      <Alert severity="error">
        No Areas of Interest defined. Please create an Area of Interest in
        Import to continue
      </Alert>
    );
  }
};

export default AOISelect;
