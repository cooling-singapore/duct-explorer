import { FieldProps } from '@rjsf/utils';
import DeleteIcon from '@mui/icons-material/Delete';
import {
  List,
  ListItem,
  IconButton,
  ListItemText,
  Typography,
} from '@mui/material';

import { useScene } from '../../../context/scene.context';
import { HeatEmissionItem } from '@duct-core/data';

function HeatEmission(props: FieldProps) {
  const sceneContext = useScene();
  const emissionItems = sceneContext.context.module_settings[
    'industry-planning'
  ] as HeatEmissionItem[];

  const deleteArea = (index: number) => {
    sceneContext.setContext((prevState) => {
      const copy = { ...prevState };
      const areas = copy.module_settings[
        'industry-planning'
      ] as HeatEmissionItem[];
      areas.splice(index, 1);
      copy.module_settings['industry-planning'] = areas;
      return copy;
    });
  };
  if (emissionItems && emissionItems.length) {
    return (
      <List dense>
        {emissionItems.map((item, index) => (
          <ListItem
            key={`item-${index}`}
            secondaryAction={
              <IconButton
                edge="end"
                aria-label="delete"
                onClick={() => deleteArea(index)}
              >
                <DeleteIcon />
              </IconButton>
            }
          >
            <ListItemText
              primary={item.name}
              secondary={`Sensible Heat Emissions: ${item.sh_emissions} MW, Latent Heat Emissions: ${item.lh_emissions} MW`}
            />
          </ListItem>
        ))}
      </List>
    );
  } else {
    return null;
  }
}

export default HeatEmission;
