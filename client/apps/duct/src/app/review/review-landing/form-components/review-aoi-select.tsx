import {
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Skeleton,
} from '@mui/material';
import { useQuery } from 'react-query';

import { ReviewForm, getAOIImports } from '@duct-core/data';
import { Controller, useFormContext } from 'react-hook-form';
import { useProject } from '../../../context/project.context';

const ReviewAOISelect = () => {
  const { control } = useFormContext<ReviewForm>();
  const projectContext = useProject();
  const projectId = projectContext?.project?.id || '';

  const { data, isLoading } = useQuery(
    ['getAOIImports', projectId],
    () => getAOIImports(projectId),
    {
      refetchOnWindowFocus: false,
      enabled: projectId !== '',
    }
  );

  if (isLoading) {
    return <Skeleton variant="rectangular" height={50} />;
  }

  return (
    <Controller
      name="selectedAoiId"
      control={control}
      render={({ field }) => (
        <FormControl sx={{ minWidth: 120 }} fullWidth margin="normal">
          <InputLabel id="analysis-select">
            Select Area of Interest for Masking
          </InputLabel>
          <Select {...field}>
            <MenuItem value="no-masking">No Masking</MenuItem>
            <MenuItem value="city-admin-zones">City Admin Zones</MenuItem>
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
};

export default ReviewAOISelect;
