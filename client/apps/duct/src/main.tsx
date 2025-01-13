import {
  createTheme,
  ThemeProvider,
  StyledEngineProvider,
  CssBaseline,
} from '@mui/material';
import { SnackbarProvider } from 'notistack';
import { StrictMode } from 'react';
import * as ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from 'react-query';
import { BrowserRouter } from 'react-router-dom';

import App from './app/app';
import { ProvideAuth } from './app/context/auth.context';
import { ProvideProject } from './app/context/project.context';
import { environment } from './environments/environment';

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
