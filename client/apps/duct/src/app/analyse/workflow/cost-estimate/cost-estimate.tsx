import {
  Box,
  Card,
  CardContent,
  Chip,
  Skeleton,
  Stack,
  Typography,
} from '@mui/material';
import { useQuery } from 'react-query';

import { AnalysisFormType, getAnalysisCost } from '@duct-core/data';
import { PageTitle } from '@duct-core/ui';
import AlertList from '../../../utils/ui/components/alert-list';

interface CostEstimateProps {
  projectId: string;
  sceneId?: string;
  parameters?: AnalysisFormType;
  sceneName?: string;
  aoiId?: string;
  analysisType: string;
  onError: (isvalid: boolean) => void;
}

function CostEstimate(props: CostEstimateProps) {
  const {
    projectId,
    sceneId,
    sceneName,
    parameters,
    onError,
    aoiId,
    analysisType,
  } = props;

  const { data, isLoading } = useQuery(
    ['getAnalysisCost', sceneId, parameters, aoiId, analysisType],
    () => {
      const obj = {
        scene_id: sceneId,
        analysis_type: analysisType,
        aoi_obj_id: aoiId,
        parameters,
      };
      return getAnalysisCost(projectId, obj);
    },
    {
      retry: false,
      enabled: sceneId && analysisType && parameters ? true : false,
      onSuccess(data) {
        if (data.messages.length) {
          onError(true);
        }
      },
    }
  );

  return (
    <Box my={6}>
      <PageTitle title="Analysis Estimates" />

      {isLoading ? (
        <Skeleton variant="rectangular" height={165} />
      ) : data ? (
        <Card
          sx={{ minWidth: 275, m: 2 }}
          key={data.analysis_id}
          variant="outlined"
        >
          <CardContent>
            <Typography variant="body1" color="text.primary" gutterBottom>
              Scene Name: {sceneName}
            </Typography>
            <Typography my={2} color="text.secondary" variant="body2">
              <b>Estimated cost:</b> {data.estimated_cost}
              <br />
              <b>Estimated time:</b> {data.estimated_time}
            </Typography>
            <Stack direction="row" spacing={1}>
              <Chip
                size="small"
                label={
                  data.approval_required
                    ? 'Requires approval'
                    : 'Does not require approval'
                }
              />
              <Chip
                size="small"
                label={
                  data.cached_results_available
                    ? 'Cached result available'
                    : 'No cached result available'
                }
              />
            </Stack>
            {data.messages && <AlertList alerts={data.messages} />}
          </CardContent>
        </Card>
      ) : null}
    </Box>
  );
}

export default CostEstimate;
