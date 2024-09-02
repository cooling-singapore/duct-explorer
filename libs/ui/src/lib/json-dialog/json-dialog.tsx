import { Dialog, DialogTitle, Box } from '@mui/material';
import JsonTable from '../json-table-view/json-table-view';

interface JsonDialogProps {
  open: boolean;
  data: object | undefined;
  title: string;
  onClose: () => void;
}

function JsonDialog(props: JsonDialogProps) {
  const { open, title, data, onClose } = props;
  return (
    <Dialog onClose={onClose} open={open}>
      <DialogTitle>{title}</DialogTitle>
      <Box
        sx={{
          maxWidth: 600,
          maxHeight: 600,
          overflow: 'auto',
          m: 2,
        }}
      >
        <JsonTable data={data as object} />
      </Box>
    </Dialog>
  );
}

export default JsonDialog;
