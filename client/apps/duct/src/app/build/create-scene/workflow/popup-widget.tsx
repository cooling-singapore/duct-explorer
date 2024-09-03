import { useState } from 'react';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormControl from '@mui/material/FormControl';
import FormLabel from '@mui/material/FormLabel';
import Grid from '@mui/material/Grid';
import {
  createTheme,
  ThemeProvider,
  StyledEngineProvider,
} from '@mui/material/styles';

import { ZoneConfig } from '@duct-core/data';

export interface PopupWidgetProps {
  availableConfigs: ZoneConfig[];
  currentConfigId: number;
  setZoneVersion: (zone: ZoneConfig) => void;
}

export function PopupWidget(props: PopupWidgetProps) {
  const { availableConfigs, currentConfigId, setZoneVersion } = props;
  const [selectedConfigId, setSelectedConfigId] =
    useState<number>(currentConfigId);

  const findZone = (configId: number) =>
    availableConfigs.find((zone) => zone.config_id === configId);

  const onSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const configId = Number(event.target.value);
    setSelectedConfigId(configId);
    const selectedZone = findZone(configId);
    if (selectedZone) {
      setZoneVersion(selectedZone);
    }
  };

  // TODO: Figure out why global theme is getting overridden by this popup
  const theme = createTheme({
    palette: {
      primary: {
        main: '#283244',
        dark: '#000a1d',
        light: '#515b6f',
      },
      secondary: {
        main: '#4d79ff',
        dark: '#004ecb',
        light: '#8aa7ff',
      },
    },
    typography: {
      fontSize: 12,
    },
  });

  return (
    <StyledEngineProvider injectFirst>
      <ThemeProvider theme={theme}>
        <Grid container>
          <FormControl component="fieldset">
            <FormLabel component="legend">
              Select alternate configuration for this area
            </FormLabel>
            <RadioGroup
              aria-label="alternate zones"
              name="alternate-zones"
              value={selectedConfigId}
              onChange={onSelect}
            >
              {availableConfigs.map((version) => {
                return (
                  <FormControlLabel
                    key={`radio-${version.config_id}`}
                    value={version.config_id}
                    control={<Radio />}
                    label={version.name}
                  />
                );
              })}
            </RadioGroup>
          </FormControl>
        </Grid>
      </ThemeProvider>
    </StyledEngineProvider>
  );
}
export default PopupWidget;
