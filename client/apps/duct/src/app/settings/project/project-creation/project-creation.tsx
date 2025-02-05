import Box from '@mui/material/Box';
import FormControl from '@mui/material/FormControl';
import Grid from '@mui/material/Grid';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select, { SelectChangeEvent } from '@mui/material/Select';
import TextField from '@mui/material/TextField';
import { useMutation, useQuery, useQueryClient } from 'react-query';
import { lazy, useState } from 'react';
import Button from '@mui/material/Button';
import { useSnackbar } from 'notistack';
import { ValidationError } from 'yup';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemText from '@mui/material/ListItemText';
import { Link, useNavigate } from 'react-router-dom';
import { Alert, IconButton } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import Markdown from 'react-markdown';

import { LoadingIndicator, PageTitle } from '@duct-core/ui';
import { environment } from '../../../../environments/environment';
import {
  City,
  CityPackage,
  createProject,
  getCities,
  InfoResponse,
  Project,
  ProjectForm,
  projectFormSchema,
} from '@duct-core/data';
import { useProject } from '../../../context/project.context';

const PreviewWidget = lazy(() => import('./preview-widget'));

export function ProjectCreation() {
  const { enqueueSnackbar } = useSnackbar();
  const projectContext = useProject();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selectedCity, setSelectedCity] = useState<City | undefined>(undefined);
  const [selectedDataset, setSelectedDataset] = useState<
    CityPackage | undefined
  >(undefined);
  const [projectName, setProjectName] = useState<string>('');
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState<boolean>(false);

  const { data, isLoading } = useQuery<InfoResponse>(
    'getCities',
    () => getCities(),
    {
      retry: false,
    }
  );

  const createProjectMutation = useMutation((project: ProjectForm) => {
    setLoading(true);
    return createProject(project)
      .then((project: Project) => {
        setLoading(false);
        projectContext?.setProject(project);
        // add project in session so app can survive refreshes
        sessionStorage.setItem(
          environment.PROJECT_SESSION_KEY,
          JSON.stringify(project)
        );

        //invalidate getScenes and getProjects so lists gets updated
        queryClient.invalidateQueries(['getScenes', 'getProjects']);
        navigate(`/manage/projects`);
      })
      .catch((err) => {
        setLoading(false);
        console.error(err);
        enqueueSnackbar('Sorry, something went wrong', { variant: 'error' });
      });
  });

  const onCitySelected = (event: SelectChangeEvent<string>) => {
    const cityName = event.target.value as string;
    const cityResult = data?.bdps.find((city) => city.city === cityName);
    if (cityResult) {
      setSelectedCity(cityResult);
    }
  };

  const onDatasetSelected = (event: SelectChangeEvent<string>) => {
    const datasetName = event.target.value as string;

    //extract dataset details for preview
    const result = selectedCity?.packages.find(
      (cityPackage) => cityPackage.name === datasetName
    );
    if (result) {
      setSelectedDataset(result);
    }
  };

  const onCreateClicked = () => {
    setValidationErrors([]);
    const project: ProjectForm = {
      name: projectName,
      city: selectedCity?.city || '',
      bdp_id: selectedDataset?.id || '',
    };

    projectFormSchema
      .validate(project, {
        abortEarly: false,
      })
      .then(() => createProjectMutation.mutate(project))
      .catch((e: ValidationError) => setValidationErrors(e.errors));
  };

  return (
    <Grid container sx={{ height: '100%' }}>
      <Grid item xs={8}>
        <PreviewWidget cityPackage={selectedDataset} />
      </Grid>
      <Grid item xs={4}>
        <Box my={4} mx={2}>
          <Grid container spacing={1} alignItems="top">
            <Grid item md={2} lg={1}>
              <IconButton
                title="Back to scene management"
                edge="start"
                size="small"
                component={Link}
                to={'/manage/projects'}
              >
                <ArrowBackIcon />
              </IconButton>
            </Grid>
            <Grid item md={10} lg={11}>
              <PageTitle title="Create New Project" />
            </Grid>
          </Grid>

          <Box>
            <FormControl fullWidth margin="normal">
              <TextField
                id="project-name"
                data-testid="project-name"
                label="Project name"
                onChange={(event) => setProjectName(event.target.value)}
              />
            </FormControl>
            <FormControl fullWidth margin="normal">
              <InputLabel id="city">City</InputLabel>
              <Select
                label="City"
                labelId="city"
                id="city-select"
                value={selectedCity?.city || ''}
                onChange={onCitySelected}
                data-testid="city-select"
              >
                {data?.bdps.map((city, index) => (
                  <MenuItem
                    value={city.city}
                    key={city.city}
                    data-testid={`city-${index}`}
                  >
                    {city.city}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl fullWidth margin="normal">
              <InputLabel id="dataset">Base Dataset</InputLabel>
              <Select
                label="Base Dataset"
                disabled={selectedCity ? false : true}
                labelId="dataset"
                id="dataset-select"
                value={selectedDataset?.name || ''}
                onChange={onDatasetSelected}
                data-testid="dataset-select"
              >
                {selectedCity?.packages.map((dataset, index) => (
                  <MenuItem
                    value={dataset.name}
                    key={dataset.name}
                    data-testid={`dataset-${index}`}
                  >
                    {dataset.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>
          <Box my={4}>
            <Button
              variant="contained"
              color="secondary"
              fullWidth
              onClick={onCreateClicked}
              data-testid="create-project"
            >
              Create Project
            </Button>
            {validationErrors.length > 0 ? (
              <Box>
                <List aria-label="form errors">
                  {validationErrors.map((error) => (
                    <ListItem key={error}>
                      <ListItemText>
                        <Alert severity="error">{error}</Alert>
                      </ListItemText>
                    </ListItem>
                  ))}
                </List>
              </Box>
            ) : null}
          </Box>
        </Box>

        {selectedDataset && selectedDataset.description && (
          <Box my={4} mx={2}>
            <Markdown>{selectedDataset.description}</Markdown>
          </Box>
        )}
      </Grid>
      <LoadingIndicator
        loading={loading}
        message="Creating project. This can take up to 10 seconds"
      />
      <LoadingIndicator loading={isLoading} />
    </Grid>
  );
}

export default ProjectCreation;
