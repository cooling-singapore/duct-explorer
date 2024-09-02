import { Box, Button, Popover, Stack, Typography } from '@mui/material';
import { ReactNode, useState } from 'react';

interface ConfirmationProps {
  text: string;
  confirmButtonText: string;
  cancelButtonText: string;
  onConfirm: () => void;
  onCancel?: () => void;
  button: ReactNode;
  disabled?: boolean;
  confirmButtonTestId?: string;
}

function Confirmation(props: ConfirmationProps) {
  const {
    button,
    text,
    confirmButtonText,
    cancelButtonText,
    onConfirm,
    onCancel,
    disabled,
    confirmButtonTestId,
  } = props;
  const [anchorEl, setAnchorEl] = useState<HTMLDivElement | null>(null);

  const handleClick = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!disabled) {
      setAnchorEl(event.currentTarget);
    }
  };

  const handleClose = () => {
    setAnchorEl(null);
    if (onCancel) {
      onCancel();
    }
  };

  const open = Boolean(anchorEl);
  const id = open ? 'confirmation-popover' : undefined;

  return (
    <>
      <div onClick={handleClick}>{button}</div>
      <Popover
        id={id}
        open={open}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={{
          vertical: 'center',
          horizontal: 'center',
        }}
      >
        <Box sx={{ p: 2 }}>
          <Typography>{text}</Typography>
          <Stack
            direction="row"
            spacing={1}
            justifyContent="center"
            sx={{ paddingTop: 1 }}
          >
            <Button
              data-testid="close"
              size="small"
              onClick={() => handleClose()}
              variant="contained"
              color="inherit"
            >
              {cancelButtonText}
            </Button>
            <Button
              data-testid={confirmButtonTestId}
              size="small"
              onClick={() => {
                setAnchorEl(null);
                onConfirm();
              }}
              variant="contained"
              color="secondary"
            >
              {confirmButtonText}
            </Button>
          </Stack>
        </Box>
      </Popover>
    </>
  );
}

export default Confirmation;
