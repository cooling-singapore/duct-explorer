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

import AnalysisConfigRow from './analysis-config-row';
import {
  AnalysisConfigItemByConfig,
  getAnalysisConfigGroupedByConfig,
} from '@duct-core/data';
import { useProject } from '../../context/project.context';
import { useQuery } from 'react-query';

const ConfigTable = () => {
  const projectContext = useProject();
  const projectId = projectContext?.project?.id || '';

  const { data, error, isLoading } = useQuery<
    AnalysisConfigItemByConfig[],
    Error
  >(
    ['getAnalysisConfigGroupedByConfig', projectId],
    () => getAnalysisConfigGroupedByConfig(projectId),
    { retry: false }
  );

  if (error) {
    console.error(error || 'ConfigTable: something went wrong: ');
    return null;
  }

  return (
    <TableContainer component={Paper}>
      <Table aria-label="collapsible table">
        <TableHead>
          <TableRow>
            <TableCell />
            <TableCell align="left">Group ID</TableCell>
            <TableCell>Group Name</TableCell>
            <TableCell align="left">Type</TableCell>
            <TableCell align="right">Scenes</TableCell>
            <TableCell />
          </TableRow>
        </TableHead>
        <TableBody>
          {isLoading ? (
            <TableRow>
              <TableCell colSpan={6}>
                <Skeleton height={35} />
              </TableCell>
            </TableRow>
          ) : (
            <>
              {data &&
                data.map((row) => (
                  <AnalysisConfigRow key={row.group_id} row={row} />
                ))}
            </>
          )}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

export default ConfigTable;
