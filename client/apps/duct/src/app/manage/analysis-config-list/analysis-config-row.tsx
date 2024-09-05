import Box from '@mui/material/Box';
import { useState } from 'react';
import Collapse from '@mui/material/Collapse';
import IconButton from '@mui/material/IconButton';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Typography from '@mui/material/Typography';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import AddIcon from '@mui/icons-material/Add';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import FormControl from '@mui/material/FormControl';
import Select, { SelectChangeEvent } from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import TextField from '@mui/material/TextField';
import { useMutation, useQuery, useQueryClient } from 'react-query';
import { useSnackbar } from 'notistack';
import { DateTime } from 'luxon';
import Chip from '@mui/material/Chip';

import {
  AnalysisConfigItemByConfig,
  getScenes,
  Scene,
  submitAnalysis,
} from '@duct-core/data';
import { LoadingIndicator } from '@duct-core/ui';
import { useProject } from '../../context/project.context';

export function AnalysisConfigRow(props: { row: AnalysisConfigItemByConfig }) {
  const { row } = props;
  const projectContext = useProject();
  const queryClient = useQueryClient();
  const projectId = projectContext?.project?.id || '';
  const { enqueueSnackbar } = useSnackbar();
  const [rowExpanded, setRowExpanded] = useState(false);
  const [showSceneModal, setShowSceneModal] = useState(false);
  const [selectedScene, setSelectedScene] = useState<string>('');
  const [analysisName, setAnalysisName] = useState<string>('');

  const {
    data: sceneList,
    error: sceneListError,
    isLoading: sceneListLoading,
  } = useQuery<Scene[], Error>(
    ['getScenes', projectId],
    () => getScenes(projectId),
    { retry: false }
  );

  const addSceneToGroupMutation = useMutation(
    (params: { groupId: string; sceneId: string; analysisName: string }) => {
      return submitAnalysis(
        projectId,
        params.groupId,
        params.analysisName,
        params.sceneId
      );
    },
    {
      onSuccess: () => {
        enqueueSnackbar('Scene added to configuration successfully!', {
          variant: 'success',
        });
        // invalidate cache so congif list gets updated
        queryClient.invalidateQueries('getAnalysisConfigGroupedByConfig');
      },
    }
  );

  const onSceneSelected = (event: SelectChangeEvent<string>) => {
    setSelectedScene(event.target.value as string);
  };

  const onAnalyseClick = () => {
    if (analysisName !== '') {
      const currentScene = sceneList?.find(
        (scene) => scene.id === selectedScene
      );

      const params = {
        groupId: row.group_id,
        sceneId: selectedScene,
        analysisName: `${analysisName}.${currentScene?.name}`,
      };
      addSceneToGroupMutation.mutate(params);
      // close modal
      setShowSceneModal(false);
    } else {
      //show error. analysis name required
      enqueueSnackbar('Analysis Name is required', {
        variant: 'warning',
      });
    }
  };

  if (!sceneList || sceneListError) {
    console.error(
      sceneListError || 'AnalysisConfigurationRow: something went wrong'
    );
    return null;
  }

  const getChipColor = (state: string) => {
    switch (state) {
      case 'timeout ':
        return {
          backgroundColor: 'warning.light',
          color: 'warning.main',
        };
      case 'running':
        return {
          backgroundColor: 'info.light',
          color: 'info.main',
        };
      case 'completed':
        return {
          backgroundColor: 'success.light',
          color: 'success.dark',
        };
      case 'failed':
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
            aria-label="expand row"
            size="small"
            onClick={() => setRowExpanded(!rowExpanded)}
          >
            {rowExpanded ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
          </IconButton>
        </TableCell>
        <TableCell align="left">{row.group_id.substring(0, 5)}</TableCell>
        <TableCell component="th" scope="row">
          {row.group_name}
        </TableCell>
        <TableCell align="left">{row.type_label}</TableCell>
        <TableCell align="right">{row.analyses.length}</TableCell>
        <TableCell align="center">
          <Button
            variant="outlined"
            color="secondary"
            size="small"
            startIcon={<AddIcon />}
            onClick={() => setShowSceneModal(true)}
          >
            Add Scene
          </Button>
        </TableCell>
      </TableRow>
      <TableRow>
        <TableCell style={{ paddingBottom: 0, paddingTop: 0 }} colSpan={6}>
          <Collapse in={rowExpanded} timeout="auto" unmountOnExit>
            <Box margin={1}>
              <Table size="small" aria-label="purchases">
                <TableHead>
                  <TableRow>
                    <TableCell>Scene ID</TableCell>
                    <TableCell>Analysis Name</TableCell>
                    <TableCell>User</TableCell>
                    <TableCell>Date Created</TableCell>
                    <TableCell align="right">Status</TableCell>
                    <TableCell align="right">Progress</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {row.analyses.map((sceneRow) => (
                    <TableRow key={sceneRow.scene_id}>
                      <TableCell component="th" scope="row">
                        {sceneRow.scene_id.substring(0, 5)}
                      </TableCell>
                      <TableCell>{sceneRow.name}</TableCell>
                      <TableCell>{sceneRow.username}</TableCell>
                      <TableCell>
                        {DateTime.fromMillis(sceneRow.t_created).toLocaleString(
                          DateTime.DATETIME_MED_WITH_SECONDS
                        )}
                      </TableCell>
                      <TableCell align="right">
                        <Chip
                          title={sceneRow.message}
                          sx={getChipColor(sceneRow.status)}
                          label={capitalizeFirstLetter(sceneRow.status)}
                          size="small"
                        />
                      </TableCell>
                      <TableCell align="right">{sceneRow.progress}%</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
      <Dialog onClose={() => setShowSceneModal(false)} open={showSceneModal}>
        <DialogTitle>Add Scenes to Analysis</DialogTitle>
        <DialogContent>
          <Typography variant="subtitle2" gutterBottom>
            Choose the scene(s) that you want to analyse. Each scene will be
            simulated individually and the results can be compared
          </Typography>
          <FormControl sx={{ minWidth: 120 }} fullWidth margin="normal">
            <Select
              value={selectedScene}
              labelId="scene-select"
              onChange={onSceneSelected}
            >
              {sceneList.map((scene) => (
                <MenuItem key={scene.id} value={scene.id}>
                  {scene.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl sx={{ minWidth: 120 }} fullWidth margin="normal">
            <TextField
              required
              label="Analysis Name"
              onChange={(event) => setAnalysisName(event.target.value)}
            />
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button variant="contained" onClick={() => setShowSceneModal(false)}>
            Cancel
          </Button>
          <Button
            variant="contained"
            color="secondary"
            onClick={onAnalyseClick}
          >
            Analyse
          </Button>
        </DialogActions>
      </Dialog>
      <LoadingIndicator loading={sceneListLoading} />
    </>
  );
}

export default AnalysisConfigRow;
