import {
  createTheme,
  ThemeProvider,
  StyledEngineProvider,
  CssBaseline,
} from '@mui/material';
import { SnackbarProvider } from 'notistack';
import { StrictMode, useEffect } from 'react';
import * as ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from 'react-query';
import {
  BrowserRouter,
  createRoutesFromChildren,
  matchRoutes,
  useLocation,
  useNavigationType,
} from 'react-router-dom';
import * as Sentry from '@sentry/react';

import App from './app/app';
import { ProvideAuth } from './app/context/auth.context';
import { ProvideProject } from './app/context/project.context';
import { environment } from './environments/environment';

if (environment.production) {
  console.log(process.env.NX_DUCT_VERSION);

  const getEnvName = (ductVersion: string) => {
    if (ductVersion.includes('staging')) {
      return 'staging';
    } else if (ductVersion.includes('uat')) {
      return 'uat';
    } else {
      return 'development';
    }
  };

  Sentry.init({
    dsn: environment.dsn,
    environment: getEnvName(process.env.NX_DUCT_VERSION || ''),
    release: 'explorer@' + process.env.NX_DUCT_VERSION,
    integrations: [
      new Sentry.BrowserTracing({
        // See docs for support of different versions of variation of react router
        // https://docs.sentry.io/platforms/javascript/guides/react/configuration/integrations/react-router/
        routingInstrumentation: Sentry.reactRouterV6Instrumentation(
          useEffect,
          useLocation,
          useNavigationType,
          createRoutesFromChildren,
          matchRoutes
        ),
      }),
      new Sentry.Replay(),
    ],

    // Set tracesSampleRate to 1.0 to capture 100%
    // of transactions for performance monitoring.
    tracesSampleRate: 1.0,

    // Set `tracePropagationTargets` to control for which URLs distributed tracing should be enabled
    tracePropagationTargets: [environment.apiHost],

    // Capture Replay for 10% of all sessions,
    // plus for 100% of sessions with an error
    replaysSessionSampleRate: 0.1,
    replaysOnErrorSampleRate: 1.0,
  });
}

// set document title
document.title = environment.APP_TITLE;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
    },
  },
});

const theme = createTheme({
  palette: {
    primary: {
      main: '#283244',
      dark: '#000a1d',
      light: '#515b6f',
    },
    secondary: {
      main: '#4d79ff',
      dark: '#004ecb',
      light: '#8aa7ff',
    },
    success: {
      light: '#E8FAEA',
      main: '#4caf50',
      dark: '#388e3c',
    },
    error: {
      light: '#FCE9E9',
      main: '#f44336',
      dark: '#d32f2f',
    },
    warning: {
      light: '#FFEFE5',
      main: '#ff9800',
      dark: '#f57c00',
    },
    info: {
      light: '#EAF4FC',
      main: '#2196f3',
      dark: '#1976d2',
    },
  },
  typography: {
    fontSize: 12,
  },
});

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);

root.render(
  <StrictMode>
    <StyledEngineProvider injectFirst>
      <ThemeProvider theme={theme}>
        <BrowserRouter>
          <QueryClientProvider client={queryClient}>
            <SnackbarProvider
              maxSnack={3}
              anchorOrigin={{ horizontal: 'center', vertical: 'bottom' }}
            >
              <ProvideAuth>
                <ProvideProject>
                  <CssBaseline />
                  <App />
                </ProvideProject>
              </ProvideAuth>
            </SnackbarProvider>
          </QueryClientProvider>
        </BrowserRouter>
      </ThemeProvider>
    </StyledEngineProvider>
  </StrictMode>
);
