import { render } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';

import AppLayout2 from './app-layout-2';

describe('AppLayout2', () => {
  it('should render successfully', () => {
    const menuItems = [
      {
        icon: <>icon</>,
        text: 'Build',
        key: 'build',
        route: `/build`,
      },
    ];

    const { baseElement } = render(
      <BrowserRouter>
        <AppLayout2 menuItems={menuItems} />
      </BrowserRouter>
    );
    expect(baseElement).toBeTruthy();
  });
});
