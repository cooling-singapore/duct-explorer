import { useQuery } from 'react-query';
import ModuleCard from './module-card';

import { Box, Skeleton, Stack } from '@mui/material';
import { useEffect, useState } from 'react';
import { useSnackbar } from 'notistack';

import {
  MapVisualization,
  PendingVisualization,
  SceneCreationStage,
  SceneModule,
  VisualizationStatus,
  getModuleVisualization,
  getModules,
} from '@duct-core/data';
import { useScene } from '../../../../context/scene.context';
import { useProject } from '../../../../context/project.context';
import { useBuild } from '../../../../context/build.context';
import { LoadingIndicator } from '@duct-core/ui';

interface ModuleSettingsProps {
  disableQueries: boolean;
}

function ModuleSettings({ disableQueries }: ModuleSettingsProps) {
  const [activeModule, setactiveModule] = useState<SceneModule | undefined>(
    undefined
  );
  const [refetchInterval, setRefetchInterval] = useState(-1);
  const [loading, setLoading] = useState(false);
  const sceneContext = useScene();
  const projectContext = useProject();
  const buildContext = useBuild();
  const { enqueueSnackbar } = useSnackbar();

  useEffect(() => {
    return () => {
      buildContext.setContext((prevState) => {
        const copy = { ...prevState };
        copy.moduleVisLayers = [];
        copy.mapType = SceneCreationStage.Default;
        copy.editorConfig = undefined;
        return copy;
      });
    };
  }, []);

  const { data, isLoading } = useQuery(['getModules'], () =>
    getModules(projectContext?.project?.id || '')
  );

  const shouldRefetch = (status: PendingVisualization) => {
    let refechTime = -1;

    if (status.status === VisualizationStatus.PENDING) {
      // BE passes seconds, reactQuery expects miliseconds
      refechTime = status.retry_recommendation * 1000;
    }
    setRefetchInterval(refechTime); // no need to refetch if vis is ready
  };

  useQuery(
    [
      'getModuleVisualization',
      sceneContext.context.module_settings,
      activeModule?.name,
    ],
    () => {
      setLoading(true);
      return getModuleVisualization(
        projectContext?.project?.id || '',
        activeModule?.name || '',
        sceneContext.context
      );
    },
    {
      enabled:
        (activeModule && activeModule.has_raster_map ? true : false) &&
        !disableQueries,
      retry: false,
      refetchOnMount: false,
      refetchInterval: refetchInterval > 0 ? refetchInterval : false,
      onSuccess(res: (MapVisualization | PendingVisualization)[]) {
        const readyLayers: MapVisualization[] = [];
        let anyPending = 0;
        // loop through layers and sort
        res.forEach((layer) => {
          if (
            (layer as PendingVisualization).status ===
            VisualizationStatus.PENDING
          ) {
            anyPending++;
            shouldRefetch(layer as PendingVisualization);
          } else {
            readyLayers.push(layer as MapVisualization);
          }
        });

        // //disable refetch if none of the layers are pending
        if (anyPending === 0) {
          setRefetchInterval(-1);
        }

        if (activeModule) {
          if (activeModule.has_area_selector) {
            buildContext.setContext((prevState) => {
              const copy = { ...prevState };
              copy.mapType = SceneCreationStage.AreaSelection;
              copy.editorConfig = activeModule.editorConfig;
              return copy;
            });
          } else if (activeModule.editable) {
            buildContext.setContext((prevState) => {
              const copy = { ...prevState };
              copy.moduleVisLayers = readyLayers;
              copy.mapType = SceneCreationStage.Editable;
              copy.editorConfig = activeModule.editorConfig;
              return copy;
            });
          } else if (activeModule.has_raster_map) {
            buildContext.setContext((prevState) => {
              const copy = { ...prevState };
              copy.moduleVisLayers = readyLayers;
              copy.mapType = SceneCreationStage.Default;
              copy.editorConfig = undefined;
              return copy;
            });
          }
        }

        setLoading(false);
      },
      onError: () => {
        enqueueSnackbar('Sorry, something went wrong', { variant: 'error' });
        setLoading(false);
      },
    }
  );

  const onModuleSelected = (activeModule: SceneModule) => {
    setactiveModule(activeModule);
  };

  if (isLoading) {
    return (
      <Stack spacing={1}>
        <Skeleton variant="rectangular" width="100%" height={100} />
        <Skeleton variant="rectangular" width="100%" height={100} />
      </Stack>
    );
  }

  return (
    <div>
      {data?.map((module) => (
        <Box key={module.name} my={2}>
          <ModuleCard
            active={activeModule?.name === module.name}
            data={module}
            onClick={onModuleSelected}
            loading={activeModule?.name === module.name && refetchInterval > 0}
          />
        </Box>
      ))}
      <LoadingIndicator loading={loading} />
    </div>
  );
}

export default ModuleSettings;
