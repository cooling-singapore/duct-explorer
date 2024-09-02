import LoadingButton from '@mui/lab/LoadingButton';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemText from '@mui/material/ListItemText';
import Paper from '@mui/material/Paper';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { styled } from '@mui/material/styles';
import axios from 'axios';
import { SyntheticEvent, useState } from 'react';
import { useQuery } from 'react-query';
import { ValidationError, object, string } from 'yup';

import { LoginUser } from '@duct-core/data';

export interface SignInProps {
  imageUrl: string;
  onSubmit: submitCallback;
  appTitle: string;
  appDescription: string;
  isLoading: boolean;
}

interface submitCallback {
  (credentials: LoginUser): void;
}

export function SignIn(props: SignInProps) {
  const LoginForm = styled('form')(
    ({ theme }) => `
      width: 80%;
      marginTop: ${theme.spacing(1)}`
  );

  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  const { data: serverInfo } = useQuery(
    ['getServerInfo'],
    () => axios.get('/public_info').then((data) => data.data),
    {
      refetchOnWindowFocus: false,
    }
  );

  const schema = object().shape({
    email: string().required('Email is required').email('Invalid email'),
    password: string().required('Password is required'),
  });

  const handleSubmit = (e: SyntheticEvent) => {
    e.preventDefault();
    const target = e.target as typeof e.target & {
      email: { value: string };
      password: { value: string };
    };
    const email = target.email.value;
    const password = target.password.value;

    schema
      .validate({ email, password }, { abortEarly: false })
      .then((user: LoginUser) => {
        props.onSubmit(user);
      })
      .catch((e: ValidationError) => {
        setValidationErrors(e.errors);
      });
  };

  const explorerVersion = process.env.NX_DUCT_VERSION;

  return (
    <Grid sx={{ height: '100vh' }} container component="main">
      <Grid
        item
        xs={false}
        sm={4}
        md={7}
        sx={{
          backgroundImage: `url(${props.imageUrl})`,
          backgroundRepeat: 'no-repeat',
          backgroundColor: (theme) =>
            theme.palette.mode === 'light'
              ? theme.palette.grey[50]
              : theme.palette.grey[900],
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }}
      />
      <Grid item xs={12} sm={8} md={5} component={Paper} elevation={6} square>
        <Box
          sx={{
            height: '80%',
            margin: (theme) => theme.spacing(8, 4),
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Box sx={{ alignItems: 'center', width: '80%' }}>
            <Typography variant="h5">{props.appTitle}</Typography>
            <Typography variant="subtitle1">{props.appDescription}</Typography>
          </Box>
          <LoginForm noValidate onSubmit={handleSubmit}>
            <TextField
              variant="outlined"
              margin="normal"
              required
              fullWidth
              id="email"
              label="Email Address"
              name="email"
              autoComplete="email"
              autoFocus
              data-testid="email"
            />
            <TextField
              variant="outlined"
              margin="normal"
              required
              fullWidth
              name="password"
              label="Password"
              type="password"
              id="password"
              autoComplete="current-password"
              data-testid="password"
            />
            {validationErrors.length > 0 ? (
              <Box>
                <List aria-label="form errors">
                  {validationErrors.map((error) => (
                    <ListItem key={error}>
                      <ListItemText>
                        <Alert severity="error">{error}</Alert>
                      </ListItemText>
                    </ListItem>
                  ))}
                </List>
              </Box>
            ) : null}
            <LoadingButton
              loading={props.isLoading}
              type="submit"
              fullWidth
              variant="contained"
              color="primary"
              sx={{ m: (theme) => theme.spacing(3, 0, 2) }}
              data-testid="signin"
            >
              Sign In
            </LoadingButton>
            {/* <Grid container>
              <Grid item xs>
                <Link href="#" variant="body2">
                  Forgot password?
                </Link>
              </Grid>
              <Grid item>
                <Link href="#" variant="body2">
                  {"Don't have an account? Sign Up"}
                </Link>
              </Grid>
            </Grid> */}
            {/* <Box mt={5}>
              <Copyright />
            </Box> */}
          </LoginForm>
          <Typography sx={{ fontSize: 10, color: 'text.disabled' }}>
            {explorerVersion && `Explorer: ${explorerVersion} | `}
            {serverInfo && `Server: v${serverInfo.server_version}`}
          </Typography>
        </Box>
      </Grid>
    </Grid>
  );
}

export default SignIn;
