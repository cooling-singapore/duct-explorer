import { getAOIImports } from '@duct-core/data';
import {
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Skeleton,
} from '@mui/material';
import { useState } from 'react';
import { useQuery } from 'react-query';
import { useProject } from '../../context/project.context';

interface ReviewAOISelectProps {
  onChange: (name: string) => void;
}

const CompareAOISelect = (props: ReviewAOISelectProps) => {
  const { onChange } = props;
  const projectContext = useProject();
  const projectId = projectContext?.project?.id as string;
  const [selectedID, setSelectedID] = useState('');

  const { data, isLoading } = useQuery(
    ['getAOIImports', projectId],
    () => getAOIImports(projectId),
    {
      refetchOnWindowFocus: false,
      onSuccess: (data) => {
        if (data.length) {
          setSelectedID(data[0].obj_id);
          onChange(data[0].obj_id);
        }
      },
    }
  );

  if (isLoading) {
    return <Skeleton variant="rectangular" height={50} />;
  }

  return (
    <FormControl sx={{ minWidth: 120 }} fullWidth margin="normal">
      <InputLabel id="aoi-select">
        Select Area of Interest for Masking
      </InputLabel>
      <Select
        label="Select Area of Interest for Masking"
        labelId="aoi-select"
        data-testid="aoi-select"
        value={selectedID}
        onChange={(e) => {
          setSelectedID(e.target.value);
          onChange(e.target.value);
        }}
      >
        <MenuItem selected value="no-masking">
          No Masking
        </MenuItem>
        <MenuItem value="city-admin-zones">City Admin Zones</MenuItem>
        {data?.map((aoi) => (
          <MenuItem key={aoi.obj_id} value={aoi.obj_id}>
            {aoi.name}
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );
};

export default CompareAOISelect;
