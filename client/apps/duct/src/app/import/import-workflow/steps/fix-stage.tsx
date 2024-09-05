import { useEffect, useState } from 'react';
import { Alert } from '@mui/material';

import { AnalysisMessage } from '@duct-core/data';
import { useImport } from '../../../context/import.context';

function FixStage() {
  const importContext = useImport();
  const data = importContext.context.uploadResponse;
  const [verificationErrors, setVerificationErrors] = useState<
    AnalysisMessage[]
  >([]);

  useEffect(() => {
    if (data) {
      setVerificationErrors(data.verification_messages);
    }
  }, [data]);

  return (
    <>
      {verificationErrors.map((message, index) => (
        <Alert
          key={`alert-${index}`}
          sx={{ mt: 1 }}
          severity={message.severity}
        >
          {message.message}
        </Alert>
      ))}
    </>
  );
}

export default FixStage;
