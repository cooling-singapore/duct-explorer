import { Box, Button, Typography } from '@mui/material';
import { ChangeEvent, useState } from 'react';
import { useSnackbar } from 'notistack';

import { LoadingIndicator } from '@duct-core/ui';
import { useProject } from '../../context/project.context';
import {
  AnalysisMessage,
  UploadVerificationResponse,
  validateDataset,
} from '@duct-core/data';
import AlertList from '../../utils/ui/components/alert-list';

interface UploadWidgetState {
  file: File | undefined;
  fileId: string | undefined;
}

interface ImportValidatorWidgetProps {
  data_type: string;
  onChange: (res: UploadVerificationResponse) => void;
}

function ImportValidatorWidget(props: ImportValidatorWidgetProps) {
  const { onChange } = props;
  const projectContext = useProject();
  const { enqueueSnackbar } = useSnackbar();
  const projectId = projectContext?.project?.id || '';
  const [state, setState] = useState<UploadWidgetState>({
    file: undefined,
    fileId: undefined,
  });
  const [loading, setLoading] = useState(false);
  const [validationErrors, setValidationErrors] = useState<AnalysisMessage[]>(
    []
  );

  const onFileReadyForUpload = (event: ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target?.files
      ? event.target?.files[0]
      : undefined;
    if (selectedFile) {
      setState((prevState) => ({ ...prevState, file: selectedFile }));
    }
  };

  const upload = () => {
    setLoading(true);
    validateDataset(projectId, state.file as File, props.data_type).then(
      (res: UploadVerificationResponse) => {
        setLoading(false);

        if (res.datasets.length) {
          // file upload was successful
          // let the parent know
          onChange(res);
        } else {
          // file was invalid
          // display the errors from the server
          setValidationErrors(res.verification_messages);
          // reset component
          setState({
            file: undefined,
            fileId: undefined,
          });
        }
      },
      (e) => {
        console.error(e);
        enqueueSnackbar('File upload failed', {
          variant: 'error',
        });
        setLoading(false);
      }
    );
  };

  return (
    <>
      <Box>
        <Box sx={{ textAlign: 'center' }} marginY={2}>
          {state.file ? (
            <Typography variant="caption" m={4}>
              selected file: {state.file.name}
            </Typography>
          ) : (
            <Box>
              <Button
                color="primary"
                component="label"
                sx={{
                  p: 8,
                  backgroundColor: 'grey.100',
                  border: (theme) => `1px dashed ${theme.palette.grey[600]}`,
                }}
              >
                Click to select a file to upload.
                <input
                  type="file"
                  hidden
                  // accept={props.options.accept as string}
                  onChange={(event) => onFileReadyForUpload(event)}
                />
              </Button>
            </Box>
          )}
        </Box>
        <Box my={2}>
          <Button
            disabled={!state.file}
            variant="contained"
            color="secondary"
            onClick={upload}
          >
            Upload and Verify
          </Button>
        </Box>
        <AlertList alerts={validationErrors} />
      </Box>
      <LoadingIndicator loading={loading} />
    </>
  );
}

export default ImportValidatorWidget;
