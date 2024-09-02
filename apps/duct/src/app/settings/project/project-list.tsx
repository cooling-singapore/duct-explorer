import { lazy, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from 'react-query';
import { Link, useNavigate } from 'react-router-dom';
import DataGrid, { Column, RenderCellProps } from 'react-data-grid';
import {
  Box,
  Button,
  CircularProgress,
  IconButton,
  useTheme,
} from '@mui/material';
import Grid2 from '@mui/material/Unstable_Grid2/Grid2';
import 'react-data-grid/lib/styles.css';
import { useSnackbar } from 'notistack';
import DeleteIcon from '@mui/icons-material/Delete';

import { environment } from '../../../environments/environment';
import { useProject } from '../../context/project.context';
import {
  ProjectState,
  getProjects,
  Project,
  deleteProject,
} from '@duct-core/data';
import { Confirmation, LoadingIndicator, PageTitle } from '@duct-core/ui';

const ShareDialog = lazy(() => import('./share-dialog'));

function ProjectList() {
  const theme = useTheme();
  const projectContext = useProject();
  const navigate = useNavigate();
  const { enqueueSnackbar } = useSnackbar();
  const queryClient = useQueryClient();

  const [refetchInterval, setRefetchInterval] = useState(0);
  const [openShareDialog, setOpenShareDialog] = useState(false);

  const shouldRefetch = (projects: Project[]) => {
    const projectInitializing = projects.some(
      (project) => project.state === ProjectState.INITIALISING
    );
    if (projectInitializing) {
      setRefetchInterval(5000);
    } else {
      setRefetchInterval(0);
    }
  };

  const { data: projectList, isLoading } = useQuery(
    'getProjects',
    () => getProjects(),
    {
      refetchOnWindowFocus: false,
      refetchInterval: refetchInterval > 0 ? refetchInterval : false,
      onSuccess: shouldRefetch,
    }
  );

  const delteMutation = useMutation(
    (projectId: string) => deleteProject(projectId),
    {
      onSuccess: () => {
        enqueueSnackbar(`Project deleted`, { variant: 'success' });
        // invalidate cahce to update list
        queryClient.invalidateQueries('getProjects');
      },
    }
  );

  function rowKeyGetter(row: Project) {
    return row.id;
  }

  const onDeleteProject = (projectId: string) => {
    delteMutation.mutate(projectId);
  };

  const columns: readonly Column<Project>[] = [
    {
      key: 'name',
      name: 'Name',
    },
    {
      key: 'id',
      name: 'Project ID',
    },
    {
      key: 'state',
      name: 'State',
      renderCell: (rowProps: RenderCellProps<Project>) => {
        if (rowProps.row.state === ProjectState.INITIALISING) {
          return (
            <span data-testid={`state-${rowProps.row.id}`}>
              {rowProps.row.state}
              <CircularProgress sx={{ marginLeft: 1 }} size={15} />
            </span>
          );
        } else {
          return (
            <span data-testid={`state-${rowProps.row.id}`}>
              {rowProps.row.state}
            </span>
          );
        }
      },
    },
    {
      key: 'select',
      name: '',
      // maxWidth: 50,
      renderCell: (rowProps: RenderCellProps<Project>) => (
        <Button
          size="small"
          color="primary"
          variant="contained"
          onClick={() => openProject(rowProps.row)}
          data-testid={`open-${rowProps.row.id}`}
          disabled={rowProps.row.state !== ProjectState.INITIALIZED}
        >
          Open
        </Button>
      ),
    },
    {
      key: 'actions',
      name: 'Actions',
      renderCell: (rowProps: RenderCellProps<Project>) => (
        <Confirmation
          key={`confirm-${rowProps.row.id}`}
          text={`Are you sure you want to delete this project?`}
          confirmButtonText="Yes"
          confirmButtonTestId={`delete-confirm-${rowProps.row.id}`}
          cancelButtonText="No"
          onConfirm={() => onDeleteProject(rowProps.row.id)}
          button={
            <IconButton
              title="Delete Project"
              size="small"
              data-testid={`delete-${rowProps.row.id}`}
              disabled={rowProps.row.state === ProjectState.INITIALISING}
            >
              <DeleteIcon />
            </IconButton>
          }
        />
      ),
    },
  ];

  const openProject = (project: Project) => {
    if (projectContext) {
      // save project in session so app can survive refreshes
      sessionStorage.setItem(
        environment.PROJECT_SESSION_KEY,
        JSON.stringify(project)
      );
      projectContext.setProject(project);
      navigate('/app/build');
    }
  };

  const onOpenShareDialog = (projectId: string) => {
    setOpenShareDialog(true);
  };

  const onCloseShareDialog = () => {
    setOpenShareDialog(false);
  };

  return (
    <Box m={2} sx={{ overflow: 'hidden' }}>
      <Grid2 container marginBottom={2}>
        <Grid2 xs={10}>
          <PageTitle title="Projects" />
        </Grid2>
        <Grid2 xs={2} sx={{ textAlign: 'right' }}>
          <Button
            component={Link}
            to={'/manage/create-project'}
            variant="contained"
            color="secondary"
            data-testid="create-project"
          >
            Create Project
          </Button>
        </Grid2>
      </Grid2>

      {projectList && (
        <DataGrid
          style={{
            fontFamily: theme.typography.fontFamily,
            height: '68vh',
            overflow: 'hidden',
          }}
          className="rdg-light"
          rowKeyGetter={rowKeyGetter}
          columns={columns}
          rows={projectList}
        />
      )}
      {openShareDialog && (
        <ShareDialog projectId="" onClose={onCloseShareDialog} />
      )}
      <LoadingIndicator loading={isLoading} />
    </Box>
  );
}

export default ProjectList;
