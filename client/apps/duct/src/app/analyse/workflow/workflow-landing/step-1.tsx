import { AnalyseForm, AnalysisScale, Scene, getScenes } from '@duct-core/data';
import {
  Box,
  FormControl,
  MenuItem,
  Select,
  Skeleton,
  Typography,
} from '@mui/material';

import { EmptyState } from '@duct-core/ui';
import { useFormContext } from 'react-hook-form';
import { useQuery } from 'react-query';
import { useProject } from '../../../context/project.context';
import AOISelect from '../../../utils/ui/components/aoi-select';
import ScaleSelect from '../../../utils/ui/components/scale-select';

const AnalyseStep1 = () => {
  const { watch, setValue, resetField } = useFormContext<AnalyseForm>();
  const projectContext = useProject();
  const projectId = projectContext?.project?.id || '';

  const { data: sceneList, isLoading: sceneListLoading } = useQuery<
    Scene[],
    Error
  >(['getScenes', projectId], () => getScenes(projectId), {
    retry: false,
    enabled: projectId !== '',
    onSuccess(data) {
      setValue('scene', data[0]);
    },
  });

  if (!sceneList || sceneList.length === 0) {
    return (
      <Box m={6}>
        <EmptyState message="No scenes have been created. Please create a scene first before configuring an analysis" />
      </Box>
    );
  }

  const selectedScale = watch('scale');
  const selectedScene = watch('scene');

  return (
    <>
      {sceneListLoading ? (
        <Skeleton variant="rectangular" height={50} />
      ) : (
        <Box my={2}>
          <ScaleSelect
            onChange={(scale) => {
              setValue('scale', scale);
              // meso scale doesnt have an aoi. so remove it if it has been set previously
              if (scale === AnalysisScale.MESO) {
                resetField('aoi_obj_id');
              }
            }}
            selectedScale={selectedScale}
          />

          {selectedScale === AnalysisScale.MICRO && <AOISelect />}
          <Box my={2}>
            <Typography variant="subtitle1">Select Scene *</Typography>
            <FormControl
              sx={{ minWidth: 120 }}
              fullWidth
              margin="normal"
              required
            >
              <Select
                value={selectedScene?.id || ''}
                labelId="scene-select"
                onChange={(e) => {
                  const found = sceneList.find(
                    (scene) => scene.id === e.target.value
                  );
                  if (found) {
                    setValue('scene', found);
                  }
                }}
              >
                {sceneList.map((scene) => (
                  <MenuItem key={scene.id} value={scene.id}>
                    {scene.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>
        </Box>
      )}
    </>
  );
};

export default AnalyseStep1;
