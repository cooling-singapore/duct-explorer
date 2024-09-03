import { StepContent, Typography, Stack, Button } from '@mui/material';
import React from 'react';

interface ZoneSelectionStageProps {
  handleBack: () => void;
  handleNext: () => void;
}

function ZoneSelectionStage(props: ZoneSelectionStageProps) {
  const { handleBack, handleNext } = props;
  return (
    <StepContent>
      <Typography variant="caption">
        Select a zone on the map for import.
      </Typography>

      <Stack mt={4} spacing={1} direction="row">
        <Button variant="contained" onClick={handleBack}>
          Back
        </Button>
        <Button variant="contained" color="secondary" onClick={handleNext}>
          Next
        </Button>
      </Stack>
    </StepContent>
  );
}

export default ZoneSelectionStage;
