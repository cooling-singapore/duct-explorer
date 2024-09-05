import { render } from '@testing-library/react';
import { SnackbarProvider } from 'notistack';
import { QueryClient, QueryClientProvider } from 'react-query';
import { MemoryRouter } from 'react-router-dom';

import App from './app';
import { ProvideAuth } from './context/auth.context';

describe('App', () => {
  it('should render successfully', () => {
    const queryClient = new QueryClient();
    const { baseElement } = render(
      <QueryClientProvider client={queryClient}>
        <SnackbarProvider
          maxSnack={3}
          anchorOrigin={{ horizontal: 'center', vertical: 'bottom' }}
        >
          <MemoryRouter initialEntries={['/']}>
            <ProvideAuth>
              <App />
            </ProvideAuth>
          </MemoryRouter>
        </SnackbarProvider>
      </QueryClientProvider>
    );

    expect(baseElement).toBeTruthy();
  });
});
