import Box from '@mui/material/Box';
import ReportProblemIcon from '@mui/icons-material/ReportProblem';

export interface EmptyStateProps {
  message: string;
}

export function EmptyState(props: EmptyStateProps) {
  return (
    <Box m={4} textAlign="center">
      <ReportProblemIcon sx={{ fontSize: '2rem' }} />
      <Box m={1} sx={{ fontSize: (theme) => theme.typography.body2.fontSize }}>
        {props.message}
      </Box>
    </Box>
  );
}

export default EmptyState;
