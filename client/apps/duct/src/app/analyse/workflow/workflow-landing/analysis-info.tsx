import { Box, Tab, Typography } from '@mui/material';
import { useState, SyntheticEvent } from 'react';
import TabContext from '@mui/lab/TabContext';
import TabList from '@mui/lab/TabList';
import TabPanel from '@mui/lab/TabPanel';

interface AnalysisInfoProps {
  description?: string;
  contributors?: string;
  image?: string;
}

function AnalysisInfo(props: AnalysisInfoProps) {
  const { description, contributors, image } = props;
  const [value, setValue] = useState(description ? '1' : '2');

  const handleChange = (event: SyntheticEvent, newValue: string) => {
    setValue(newValue);
  };

  return (
    <div>
      {image && (
        <Box>
          <img
            style={{ width: '100%' }}
            src={`./assets/analysisExamples/${image}`}
            alt="Analyis output example"
          />
        </Box>
      )}
      <Box>
        <TabContext value={value}>
          <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
            <TabList onChange={handleChange} aria-label="lab API tabs example">
              {description && <Tab label="Description" value="1" />}
              {contributors && <Tab label="Contributors" value="2" />}
            </TabList>
          </Box>
          {description && (
            <TabPanel value="1">
              <Typography
                variant="body1"
                dangerouslySetInnerHTML={{
                  __html: description,
                }}
              ></Typography>
            </TabPanel>
          )}
          {contributors && (
            <TabPanel value="2">
              <Typography
                variant="body1"
                dangerouslySetInnerHTML={{
                  __html: contributors,
                }}
              ></Typography>
            </TabPanel>
          )}
        </TabContext>
      </Box>
    </div>
  );
}

export default AnalysisInfo;
