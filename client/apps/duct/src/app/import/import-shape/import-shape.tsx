import {
  validateDataset,
  UploadVerificationResponse,
  AnalysisMessage,
} from '@duct-core/data';
import { Box, Button, Typography } from '@mui/material';
import { useSnackbar } from 'notistack';
import { useState } from 'react';
import { useProject } from '../../context/project.context';
import { LoadingIndicator } from '@duct-core/ui';
import AlertList from '../../utils/ui/components/alert-list';

interface ImportShapeProps {
  shape: string;
  onChange: (res: UploadVerificationResponse) => void;
}

const ImportShape = (props: ImportShapeProps) => {
  const { shape, onChange } = props;
  const projectContext = useProject();
  const { enqueueSnackbar } = useSnackbar();
  const projectId = projectContext?.project?.id || '';

  const [loading, setLoading] = useState(false);
  const [validationErrors, setValidationErrors] = useState<AnalysisMessage[]>(
    []
  );

  const upload = () => {
    setLoading(true);
    const file = new File([shape], 'area_of_interest');
    validateDataset(projectId, file as File, 'area_of_interest').then(
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
    <div>
      <Typography variant="caption">
        Click Continue to import the selected Area of Interest
      </Typography>
      <Box my={2}>
        <Button variant="contained" color="secondary" onClick={upload}>
          Continue
        </Button>
        <AlertList alerts={validationErrors} />
      </Box>
      <LoadingIndicator loading={loading} />
    </div>
  );
};

export default ImportShape;
