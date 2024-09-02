import {
  TableContainer,
  Paper,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  Skeleton,
} from '@mui/material';
import { useState } from 'react';
import { useMutation, useQuery } from 'react-query';

import {
  AnalysisConfigItemByScene,
  getAOIImports,
  getAnalysisConfig,
  getAnalysisConfigGroupedByScene,
} from '@duct-core/data';
import { JsonDialog } from '@duct-core/ui';
import { useProject } from '../../context/project.context';
import AnalysisSceneRow from './analysis-scene-row';

const SceneTable = () => {
  const projectContext = useProject();
  const projectId = projectContext?.project?.id || '';
  const [openDetail, setopenDetail] = useState(false);
  const [selectedAnalysisConfig, setSelectedAnalysisConfig] = useState<
    undefined | object
  >();
  const [refetchInterval, setRefetchInterval] = useState(0);

  const shouldRefetch = (scenes: AnalysisConfigItemByScene[]) => {
    let refechTime = 0;
    const newList = scenes.map((scene) => scene.analyses);
    const flatList = newList.flat();
    // see if at least one analsis is running
    const somethingRunning = flatList.some(
      (analysis) => analysis.status === 'running'
    );

    if (somethingRunning) {
      refechTime = 5000; // check again in 5 seconds
    }

    setRefetchInterval(refechTime);
  };

  const {
    data: sceneList,
    error: sceneListError,
    isLoading: sceneListLoading,
  } = useQuery<AnalysisConfigItemByScene[], Error>(
    ['AnalysisConfigItemByScene', projectId],
    () => getAnalysisConfigGroupedByScene(projectId),
    {
      retry: false,
      refetchInterval: refetchInterval > 0 ? refetchInterval : false,
      onSuccess: shouldRefetch,
    }
  );

  const { data: aoiData, isLoading: aoiLoading } = useQuery(
    ['getAOIImports', projectId],
    () => getAOIImports(projectId),
    {
      retry: false,
      refetchOnWindowFocus: false,
    }
  );

  const analysisConfigMutation = useMutation(
    (groupId: string) => getAnalysisConfig(projectId, groupId),
    {
      onSuccess: (data) => {
        setSelectedAnalysisConfig(data);
        setopenDetail(true);
      },
    }
  );

  const onViewAnalysisConfig = (groupId: string) => {
    analysisConfigMutation.mutate(groupId);
  };

  if (sceneListError) {
    console.error(sceneListError || 'SceneTable: something went wrong: ');
    return null;
  }

  return (
    <>
      <JsonDialog
        open={openDetail}
        data={selectedAnalysisConfig}
        title="Analysis Config"
        onClose={() => setopenDetail(false)}
      />
      <TableContainer component={Paper}>
        <Table aria-label="collapsible table">
          <TableHead>
            <TableRow>
              <TableCell />
              <TableCell align="left">Scene ID</TableCell>
              <TableCell>Scene Name</TableCell>
              <TableCell>Analyses</TableCell>
              <TableCell />
            </TableRow>
          </TableHead>
          <TableBody>
            {sceneListLoading || aoiLoading ? (
              <TableRow>
                <TableCell colSpan={6}>
                  <Skeleton height={35} />
                </TableCell>
              </TableRow>
            ) : (
              <>
                {aoiData &&
                  sceneList &&
                  sceneList.map((row) => (
                    <AnalysisSceneRow
                      key={row.scene_id}
                      row={row}
                      onViewConfig={onViewAnalysisConfig}
                      aoiList={aoiData}
                    />
                  ))}
              </>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </>
  );
};

export default SceneTable;
