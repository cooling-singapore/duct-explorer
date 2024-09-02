import { Backdrop, Grid } from '@mui/material';
import CircularProgress from '@mui/material/CircularProgress';

interface LoadingIndicatorProps {
  loading: boolean;
  message?: string;
}

export function LoadingIndicator(props: LoadingIndicatorProps) {
  return (
    <Backdrop
      sx={{
        zIndex: (theme) => theme.zIndex.drawer + 1,
        color: '#fff',
      }}
      open={props.loading}
    >
      <Grid
        container
        direction="column"
        alignItems="center"
        justifyContent="center"
        spacing={1}
      >
        <Grid item xs={12}>
          <CircularProgress color="inherit" />
        </Grid>
        <Grid item xs={12}>
          {props.message}
        </Grid>
      </Grid>
    </Backdrop>
  );
}

export default LoadingIndicator;
