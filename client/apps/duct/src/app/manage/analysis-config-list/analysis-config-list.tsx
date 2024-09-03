import { Box, Paper, Tab, Tabs } from '@mui/material';
import { useState } from 'react';

import { PageTitle } from '@duct-core/ui';
import SceneTable from './scene-table';
import ConfigTable from './config-table';

export function AnalysisConfigList() {
  const [tabIndex, setTabIndex] = useState(0);

  const onTabChange = (event: React.ChangeEvent<unknown>, newValue: number) => {
    setTabIndex(newValue);
  };

  return (
    <Box sx={{ padding: (theme) => theme.spacing(3) }}>
      <Box my={3}>
        <PageTitle title="Analysis Configurations"></PageTitle>
      </Box>
      <Paper sx={{ marginBottom: (theme) => theme.spacing(2) }}>
        <Tabs value={tabIndex} onChange={onTabChange}>
          <Tab label="Group by Scene" />
          <Tab label="Group by Configuration" />
        </Tabs>
      </Paper>
      {tabIndex === 0 ? <SceneTable /> : <ConfigTable />}
    </Box>
  );
}

export default AnalysisConfigList;
