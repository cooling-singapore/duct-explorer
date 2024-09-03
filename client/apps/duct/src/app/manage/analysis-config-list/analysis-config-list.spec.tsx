import { render } from '@testing-library/react';
import { SnackbarProvider } from 'notistack';
import { QueryClient, QueryClientProvider } from 'react-query';
import { BrowserRouter as Router } from 'react-router-dom';

import AnalysisConfigList from './analysis-config-list';

describe('AnalysisConfigList', () => {
  it('should render successfully', () => {
    const queryClient = new QueryClient();
    const { baseElement } = render(
      <QueryClientProvider client={queryClient}>
        <Router>
          <SnackbarProvider
            maxSnack={3}
            anchorOrigin={{ horizontal: 'center', vertical: 'bottom' }}
          >
            <AnalysisConfigList />
          </SnackbarProvider>
        </Router>
      </QueryClientProvider>
    );
    expect(baseElement).toBeTruthy();
  });
});
