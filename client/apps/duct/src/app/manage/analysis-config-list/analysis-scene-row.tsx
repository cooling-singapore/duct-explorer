import { useState } from 'react';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import DeleteIcon from '@mui/icons-material/Delete';
import ReplayIcon from '@mui/icons-material/Replay';
import CancelIcon from '@mui/icons-material/Cancel';
import InfoIcon from '@mui/icons-material/Info';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { DateTime } from 'luxon';
import { Link } from 'react-router-dom';
import { useMutation, useQueryClient } from 'react-query';
import { useSnackbar } from 'notistack';
import {
  Alert,
  Box,
  Chip,
  Collapse,
  IconButton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
} from '@mui/material';

import {
  AnalysisConfigItemByScene,
  AnalysisScale,
  AnalysisState,
  AvailableDataset,
  cancelAnalysis,
  deleteAnalysis,
  deleteScene,
  submitAnalysis,
} from '@duct-core/data';
import { useProject } from '../../context/project.context';
import { Confirmation, HtmlTooltip } from '@duct-core/ui';

interface AnalysisSceneRowProps {
  row: AnalysisConfigItemByScene;
  onViewConfig: (configId: string) => void;
  aoiList: AvailableDataset[];
}

export function AnalysisSceneRow(props: AnalysisSceneRowProps) {
  const { row, onViewConfig, aoiList } = props;
  const projectContext = useProject();
  const projectId = projectContext?.project?.id || '';
  const { enqueueSnackbar } = useSnackbar();
  const queryClient = useQueryClient();
  const [rowExpanded, setRowExpanded] = useState(false);

  const sceneDelteMutation = useMutation(
    (sceneId: string) => deleteScene(projectId, sceneId),
    {
      onSuccess: () => {
        enqueueSnackbar(`Scene deleted successfully`, { variant: 'success' });
        //invalidate getScenes so list gets updated
        queryClient.invalidateQueries('AnalysisConfigItemByScene');
      },
    }
  );

  const analysisDelteMutation = useMutation(
    (analysisId: string) => deleteAnalysis(projectId, analysisId),
    {
      onSuccess: () => {
        enqueueSnackbar(`Analysis deleted successfully`, {
          variant: 'success',
        });
        //invalidate getScenes so list gets updated
        queryClient.invalidateQueries('AnalysisConfigItemByScene');
      },
    }
  );

  const analysisCanceMutation = useMutation(
    (analysisId: string) => cancelAnalysis(projectId, analysisId),
    {
      onSuccess: () => {
        enqueueSnackbar(`Analysis canceled successfully`, {
          variant: 'success',
        });
        //invalidate getScenes so list gets updated
        queryClient.invalidateQueries('AnalysisConfigItemByScene');
      },
    }
  );

  const analysisRetryMutation = useMutation(
    (params: {
      groupId: string;
      name: string;
      sceneId: string;
      AOIId?: string;
    }) =>
      submitAnalysis(
        projectId,
        params.groupId,
        params.name,
        params.sceneId,
        params.AOIId
      ),
    {
      onSuccess: () => {
        enqueueSnackbar(`Analysis has been restarted`, {
          variant: 'success',
        });
        //invalidate getScenes so list gets updated
        queryClient.invalidateQueries('AnalysisConfigItemByScene');
      },
    }
  );

  const getChipColor = (state: AnalysisState) => {
    switch (state) {
      case AnalysisState.TIMEOUT:
        return {
          backgroundColor: 'warning.light',
          color: 'warning.main',
        };
      case AnalysisState.RUNNING:
        return {
          backgroundColor: 'info.light',
          color: 'info.main',
        };
      case AnalysisState.COMPLETED:
        return {
          backgroundColor: 'success.light',
          color: 'success.dark',
        };
      case AnalysisState.FAILED:
        return {
          backgroundColor: 'error.light',
          color: 'error.main',
        };
      default:
        return {
          backgroundColor: 'warning.light',
          color: 'warning.main',
        };
    }
  };

  const capitalizeFirstLetter = (string: string) => {
    return string.charAt(0).toUpperCase() + string.slice(1);
  };

  const onSceneDelete = (sceneId: string) => {
    sceneDelteMutation.mutate(sceneId);
  };

  const onAnalysisDelete = (analysisId: string) => {
    analysisDelteMutation.mutate(analysisId);
  };

  const onAnalysisCancel = (analysisId: string) => {
    analysisCanceMutation.mutate(analysisId);
  };

  const onAnalysisRetry = (
    groupId: string,
    name: string,
    sceneId: string,
    AOIId?: string
  ) => {
    analysisRetryMutation.mutate({ groupId, name, sceneId, AOIId });
  };

  const getAoiNameById = (id: string) => {
    const found = aoiList.find((aoi) => aoi.obj_id === id);
    if (found) {
      return found.name;
    } else {
      return 'Unknown';
    }
  };

  return (
    <>
      <TableRow
        sx={{
          '& > *': {
            borderBottom: 'unset',
          },
        }}
      >
        <TableCell>
          <IconButton
            disabled={row.analyses.length === 0} //no need to expand if there are no analyses for the scene
            aria-label="expand row"
            size="small"
            onClick={() => setRowExpanded(!rowExpanded)}
          >
            {rowExpanded ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
          </IconButton>
        </TableCell>
        <TableCell>{row.scene_id.substring(0, 5)}</TableCell>
        <TableCell>{row.scene_name}</TableCell>
        <TableCell>{row.analyses.length}</TableCell>
        <TableCell>
          <Confirmation
            disabled={row.scene_name === 'Default'}
            text="Are you sure you want to delete this scene?"
            confirmButtonText="Yes"
            cancelButtonText="No"
            onConfirm={() => onSceneDelete(row.scene_id)}
            button={
              <IconButton
                disabled={row.scene_name === 'Default'}
                title="Delete scene"
                size="small"
              >
                <DeleteIcon />
              </IconButton>
            }
          />
        </TableCell>
      </TableRow>
      <TableRow>
        <TableCell style={{ paddingBottom: 0, paddingTop: 0 }} colSpan={6}>
          <Collapse in={rowExpanded} timeout="auto" unmountOnExit>
            <Box margin={1}>
              <Table size="small" aria-label="analysis-detail">
                <TableHead>
                  <TableRow>
                    <TableCell width="100">Analysis ID</TableCell>
                    <TableCell width="250">Analysis Name</TableCell>
                    <TableCell width="250">Area of Interest</TableCell>
                    <TableCell width="250">User</TableCell>
                    <TableCell width="250">Type</TableCell>
                    <TableCell width="250">Date Created</TableCell>
                    <TableCell width="300">Status</TableCell>
                    <TableCell width="100">Progress</TableCell>
                    <TableCell></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {row.analyses.map((analysis) => (
                    <TableRow key={analysis.analysis_id}>
                      <TableCell component="th" scope="row">
                        {analysis.results.length &&
                        analysis.status === AnalysisState.COMPLETED ? (
                          <Link
                            title={analysis.analysis_id}
                            to={`/app/review?scale=${
                              analysis.aoi_obj_id
                                ? AnalysisScale.MICRO
                                : AnalysisScale.MESO
                            }&type=${analysis.analysis_type}&run=${
                              analysis.analysis_id
                            }&name=${analysis.results[0].name}`}
                          >
                            {analysis.analysis_id.substring(0, 5)}
                          </Link>
                        ) : (
                          <span title={analysis.analysis_id}>
                            {analysis.analysis_id.substring(0, 5)}
                          </span>
                        )}
                      </TableCell>
                      <TableCell>{analysis.name}</TableCell>
                      <TableCell title={analysis.aoi_obj_id}>
                        {analysis.aoi_obj_id
                          ? getAoiNameById(analysis.aoi_obj_id)
                          : 'N.A'}
                      </TableCell>
                      <TableCell>{analysis.username}</TableCell>
                      <TableCell>{analysis.analysis_type_label}</TableCell>
                      <TableCell>
                        {DateTime.fromMillis(analysis.t_created).toLocaleString(
                          DateTime.DATETIME_MED_WITH_SECONDS
                        )}
                      </TableCell>
                      <TableCell>
                        <Chip
                          sx={getChipColor(analysis.status)}
                          label={capitalizeFirstLetter(analysis.status)}
                          size="small"
                        />
                        {analysis.message && (
                          <HtmlTooltip
                            title={
                              <Alert severity={analysis.message.severity}>
                                {analysis.message.message}
                              </Alert>
                            }
                          >
                            <IconButton>
                              <InfoIcon />
                            </IconButton>
                          </HtmlTooltip>
                        )}
                      </TableCell>
                      <TableCell>{analysis.progress}%</TableCell>
                      <TableCell>
                        <Stack direction="row">
                          <IconButton
                            title="View Analysis Config"
                            size="small"
                            onClick={() => onViewConfig(analysis.group_id)}
                          >
                            <VisibilityIcon />
                          </IconButton>
                          {analysis.status === AnalysisState.RUNNING ? (
                            <Confirmation
                              text="Are you sure you want to cancel this Analysis?"
                              confirmButtonText="Yes"
                              cancelButtonText="No"
                              onConfirm={() =>
                                onAnalysisCancel(analysis.analysis_id)
                              }
                              button={
                                <IconButton
                                  title="Cancel Analysis"
                                  size="small"
                                >
                                  <CancelIcon />
                                </IconButton>
                              }
                            />
                          ) : (
                            <Confirmation
                              text="Are you sure you want to delete this Analysis?"
                              confirmButtonText="Yes"
                              cancelButtonText="No"
                              onConfirm={() =>
                                onAnalysisDelete(analysis.analysis_id)
                              }
                              button={
                                <IconButton
                                  title="Delete Analysis"
                                  size="small"
                                >
                                  <DeleteIcon />
                                </IconButton>
                              }
                            />
                          )}

                          {(analysis.status === AnalysisState.FAILED ||
                            analysis.status === AnalysisState.CANCELLED) && (
                            <IconButton
                              title="Rerun Analysis"
                              size="small"
                              onClick={() =>
                                onAnalysisRetry(
                                  analysis.group_id,
                                  analysis.name,
                                  analysis.scene_id,
                                  analysis?.aoi_obj_id
                                )
                              }
                            >
                              <ReplayIcon />
                            </IconButton>
                          )}
                        </Stack>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </>
  );
}

export default AnalysisSceneRow;
