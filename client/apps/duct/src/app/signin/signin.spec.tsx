import { render } from '@testing-library/react';
import { SnackbarProvider } from 'notistack';
import { QueryClient, QueryClientProvider } from 'react-query';
import { BrowserRouter as Router } from 'react-router-dom';

import Signin from './signin';

const queryClient = new QueryClient();

describe('Signin', () => {
  it('should render successfully', () => {
    const { baseElement } = render(
      <SnackbarProvider
        maxSnack={3}
        anchorOrigin={{ horizontal: 'center', vertical: 'bottom' }} >
        <Router>
          <QueryClientProvider client={queryClient}><Signin /></QueryClientProvider>
        </Router>
      </SnackbarProvider>);
    expect(baseElement).toBeTruthy();
  });
});
