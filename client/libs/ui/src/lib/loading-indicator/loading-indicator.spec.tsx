import { render } from '@testing-library/react';

import LoadingIndicator from './loading-indicator';

describe('LoadingIndicator', () => {
  it('should render successfully', () => {
    const { baseElement } = render(<LoadingIndicator />);
    expect(baseElement).toBeTruthy();
  });
});
