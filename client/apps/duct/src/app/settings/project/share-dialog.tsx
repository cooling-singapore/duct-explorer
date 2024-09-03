import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  Grid,
  FormControl,
  InputLabel,
  Select,
  OutlinedInput,
  Box,
  Chip,
  MenuItem,
  DialogActions,
  Button,
  SelectChangeEvent,
  Theme,
  useTheme,
  Avatar,
  IconButton,
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  Typography,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import { useState } from 'react';

const ITEM_HEIGHT = 48;
const ITEM_PADDING_TOP = 8;
const MenuProps = {
  PaperProps: {
    style: {
      maxHeight: ITEM_HEIGHT * 4.5 + ITEM_PADDING_TOP,
      width: 250,
    },
  },
};

const names = [
  'Oliver Hansen',
  'Van Henry',
  'April Tucker',
  'Ralph Hubbard',
  'Omar Alexander',
  'Carlos Abbott',
  'Miriam Wagner',
  'Bradley Wilkerson',
  'Virginia Andrews',
  'Kelly Snyder',
];

function getStyles(name: string, personName: readonly string[], theme: Theme) {
  return {
    fontWeight:
      personName.indexOf(name) === -1
        ? theme.typography.fontWeightRegular
        : theme.typography.fontWeightMedium,
  };
}

function randomColor() {
  const hex = Math.floor(Math.random() * 0xffffff);
  return '#' + hex.toString(16);
}

interface ShareDialogProps {
  projectId: string;
  onClose: () => void;
}

function ShareDialog(props: ShareDialogProps) {
  const { projectId, onClose } = props;
  const theme = useTheme();

  const [personName, setPersonName] = useState<string[]>([]);

  const handleChange = (event: SelectChangeEvent<typeof personName>) => {
    const {
      target: { value },
    } = event;
    setPersonName(
      // On autofill we get a stringified value.
      typeof value === 'string' ? value.split(',') : value
    );
  };

  return (
    <Dialog fullWidth maxWidth="md" open={true}>
      <DialogTitle>Share Project</DialogTitle>
      <DialogContent>
        <DialogContentText>
          Allows you to provide other users access to your project. Select the
          users you wish to allow access to, pick the role and click share.
        </DialogContentText>
        <Grid container spacing={2} sx={{ p: 2 }}>
          <Grid item sm={10}>
            <FormControl fullWidth>
              <InputLabel id="demo-multiple-chip-label">Chip</InputLabel>
              <Select
                labelId="demo-multiple-chip-label"
                id="demo-multiple-chip"
                multiple
                value={personName}
                onChange={handleChange}
                input={<OutlinedInput id="select-multiple-chip" label="Chip" />}
                renderValue={(selected) => (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {selected.map((value) => (
                      <Chip key={value} label={value} />
                    ))}
                  </Box>
                )}
                MenuProps={MenuProps}
              >
                {names.map((name) => (
                  <MenuItem
                    key={name}
                    value={name}
                    style={getStyles(name, personName, theme)}
                  >
                    {name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item sm={2}>
            <FormControl fullWidth>
              <InputLabel id="role">Role</InputLabel>
              <Select
                labelId="role"
                id="role-select"
                // value={age}
                label="Role"
              >
                <MenuItem>Editor</MenuItem>
                <MenuItem>Viewer</MenuItem>
              </Select>
            </FormControl>
          </Grid>
        </Grid>

        <Typography gutterBottom variant="body1">
          Shared With
        </Typography>
        <Grid container>
          <Grid item xs={4}>
            <List dense>
              <ListItem
                disableGutters
                secondaryAction={
                  <IconButton edge="end" aria-label="Remove access">
                    <DeleteIcon />
                  </IconButton>
                }
              >
                <ListItemAvatar>
                  <Avatar sx={{ backgroundColor: randomColor() }}>O</Avatar>
                </ListItemAvatar>
                <ListItemText primary="Single-line item" secondary="Editor" />
              </ListItem>
              <ListItem
                disableGutters
                secondaryAction={
                  <IconButton edge="end" aria-label="Remove access">
                    <DeleteIcon />
                  </IconButton>
                }
              >
                <ListItemAvatar>
                  <Avatar sx={{ backgroundColor: randomColor() }}>S</Avatar>
                </ListItemAvatar>
                <ListItemText primary="Single-line item" secondary="Viewer" />
              </ListItem>
            </List>
          </Grid>
        </Grid>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={onClose}>Share</Button>
      </DialogActions>
    </Dialog>
  );
}

export default ShareDialog;
