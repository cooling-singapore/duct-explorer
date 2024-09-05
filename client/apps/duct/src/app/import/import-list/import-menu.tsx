import { useState } from 'react';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import { useSnackbar } from 'notistack';
import { useMutation, useQueryClient } from 'react-query';
import { IconButton, Menu, MenuItem } from '@mui/material';

import { AvailableDataset, deleteLibImport } from '@duct-core/data';
import { Confirmation } from '@duct-core/ui';

interface ImportMenuProps {
  libItem: AvailableDataset;
  projectId: string;
}

function ImportMenu(props: ImportMenuProps) {
  const { libItem, projectId } = props;
  const { enqueueSnackbar } = useSnackbar();
  const queryClient = useQueryClient();

  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const importDelteMutation = useMutation(
    () => deleteLibImport(projectId, libItem.obj_id),
    {
      onSuccess: () => {
        enqueueSnackbar(`Import deleted successfully`, { variant: 'success' });
        //invalidate getImports so list gets updated
        queryClient.invalidateQueries('getImports');
      },
    }
  );

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleDelete = () => {
    handleClose();
    importDelteMutation.mutate();
  };

  return (
    <>
      <IconButton size="small" aria-label="More" onClick={handleClick}>
        <MoreVertIcon />
      </IconButton>
      <Menu
        id="simple-menu"
        anchorEl={anchorEl}
        keepMounted
        open={Boolean(anchorEl)}
        onClose={handleClose}
      >
        <MenuItem>
          <Confirmation
            text="Are you sure you want to delete this import?"
            confirmButtonText="Yes"
            cancelButtonText="No"
            onConfirm={() => handleDelete()}
            onCancel={handleClose}
            button={<>Delete Import</>}
          />
        </MenuItem>
      </Menu>
    </>
  );
}

export default ImportMenu;
