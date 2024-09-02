import { lazy, useState } from 'react';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import List from '@mui/material/List';
import { ListItemButton } from '@mui/material';
import ListItemSecondaryAction from '@mui/material/ListItemSecondaryAction';
import ListItemText from '@mui/material/ListItemText';
import Divider from '@mui/material/Divider';
import { useQuery } from 'react-query';
import Button from '@mui/material/Button';
import { Link } from 'react-router-dom';

import { EmptyState, LoadingIndicator, PageTitle } from '@duct-core/ui';
import {
  getScenes,
  Scene,
  SceneCreationStage,
  SceneType,
} from '@duct-core/data';
import { useProject } from '../../../context/project.context';
import { useBuild } from '../../../context/build.context';
import { useScene } from '../../../context/scene.context';

const SceneMenu = lazy(() => import('./scene-menu'));

function SceneList() {
  const projectContext = useProject();
  const projectId = projectContext?.project?.id || '';
  const buildContext = useBuild();
  const sceneContext = useScene();
  const [selectedSceneId, setSelectedSceneId] = useState('');

  const onSceneSelected = (sceneId: string, sceneName: string) => {
    setSelectedSceneId(sceneId);
    buildContext.setContext((prevState) => {
      return {
        ...prevState,
        selectedSceneId: sceneId,
        selectedSceneName: sceneName,
      };
    });
  };

  const onSceneCreationOpen = () => {
    buildContext.setContext((prevState) => {
      const copy = { ...prevState };
      copy.mapType = SceneCreationStage.ZoneVersionSeletion;
      return copy;
    });

    sceneContext.setContext((prevState) => {
      const copy = { ...prevState };
      copy.sceneType = SceneType.Islandwide;
      return copy;
    });
  };

  const {
    data: list,
    error,
    isLoading,
  } = useQuery<Scene[], Error>(
    ['getScenes', projectId],
    () => getScenes(projectId),
    {
      retry: false,
      enabled: projectId !== '',
      onSuccess: (data) => {
        if (data.length) {
          const firstScene = data[0];
          onSceneSelected(firstScene.id, firstScene.name);
        }
      },
    }
  );

  if (!list) {
    return null;
  }

  if (error) {
    console.error(error || 'SceneList: something went wrong');
    return null;
  }

  return (
    <Box m={4}>
      <Grid container sx={{ mb: 1 }}>
        <PageTitle title="Scenes" />
      </Grid>
      <Divider />

      {list.length ? (
        <List dense disablePadding>
          {list.map((scene, index) => (
            <ListItemButton
              key={scene.id}
              dense
              onClick={() => onSceneSelected(scene.id, scene.name)}
              selected={
                selectedSceneId === ''
                  ? index === 0
                  : selectedSceneId === scene.id
              }
            >
              <ListItemText
                primary={scene.name}
                secondary={scene.id.substring(0, 5)}
              />
              <ListItemSecondaryAction>
                <SceneMenu projectId={projectId} scene={scene} />
              </ListItemSecondaryAction>
            </ListItemButton>
          ))}
        </List>
      ) : (
        <Box m={6}>
          <EmptyState message="No scenes have been created. Click on Create Scene to get started" />
        </Box>
      )}
      <Box my={8}>
        <Button
          variant="contained"
          color="secondary"
          fullWidth
          component={Link}
          to="workflow"
          onClick={onSceneCreationOpen}
          data-testid="create-scene"
        >
          Create scene
        </Button>
      </Box>
      <LoadingIndicator loading={isLoading} />
    </Box>
  );
}

export default SceneList;
