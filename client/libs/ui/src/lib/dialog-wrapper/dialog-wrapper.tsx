import { Dialog, DialogContent, Box } from '@mui/material';
import { ReactNode } from 'react';

interface DialogWrapperProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}

function DialogWrapper(props: DialogWrapperProps) {
  const { onClose, children, open } = props;

  const handleClose = () => {
    onClose();
  };

  return (
    <Dialog fullWidth onClose={handleClose} open={open} maxWidth="md">
      <DialogContent>
        <Box
          justifyContent="center"
          sx={{ display: 'flex', maxHeight: '50vh' }}
        >
          {children}
        </Box>
      </DialogContent>
    </Dialog>
  );
}

export default DialogWrapper;
