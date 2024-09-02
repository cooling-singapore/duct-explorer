import { AnalysisMessage } from '@duct-core/data';
import { Alert } from '@mui/material';

interface AlertListProps {
  alerts: AnalysisMessage[];
}
const AlertList = (props: AlertListProps) => {
  return (
    <>
      {props.alerts.map((message, index) => (
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
};

export default AlertList;
