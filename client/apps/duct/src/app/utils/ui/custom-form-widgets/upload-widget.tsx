import { Box, Button, Typography } from '@mui/material';
import { WidgetProps } from '@rjsf/utils';
import axios, { AxiosResponse } from 'axios';
import { ChangeEvent, useState } from 'react';
import { useSnackbar } from 'notistack';

import { useProject } from '../../../context/project.context';
import { LoadingIndicator } from '@duct-core/ui';

interface UploadWidgetState {
  file: File | undefined;
  fileId: string | undefined;
}

function UploadWidget(props: WidgetProps) {
  const { onChange } = props;
  const projectContext = useProject();
  const { enqueueSnackbar } = useSnackbar();
  const projectId = projectContext?.project?.id || '';
  const schema = props.schema;
  const [state, setState] = useState<UploadWidgetState>({
    file: undefined,
    fileId: undefined,
  });
  const [loading, setLoading] = useState(false);

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
    const formData = new FormData();
    formData.append('attachment', state.file as File);

    axios
      .put(
        `/module/${projectId}/${props.options.moduleId as string}/upload`,
        formData,
        {
          headers: {
            'content-type': 'multipart/form-data',
          },
        }
      )
      .then(
        (res: AxiosResponse) => {
          enqueueSnackbar('File upload complete', {
            variant: 'success',
          });
          onChange(res.data.obj_id);
          setState({
            fileId: res.data.obj_id,
            file: undefined,
          });
          setLoading(false);
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
    <Box>
      {schema.title && (
        <Typography variant="body1" gutterBottom>
          {schema.title}
        </Typography>
      )}
      <Box sx={{ textAlign: 'center' }} marginY={3}>
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
                accept={props.options.accept as string}
                onChange={(event) => onFileReadyForUpload(event)}
              />
            </Button>
          </Box>
        )}
      </Box>
      <Box sx={{ margin: (theme) => theme.spacing(2, 0) }}>
        <Button
          disabled={!state.file}
          variant="contained"
          color="secondary"
          onClick={upload}
        >
          Upload
        </Button>
      </Box>
      <LoadingIndicator loading={loading} />
    </Box>
  );
}

export default UploadWidget;
