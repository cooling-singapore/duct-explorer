import { nxE2EPreset } from '@nx/cypress/plugins/cypress-preset';

import { defineConfig } from 'cypress';

export default defineConfig({
  projectId: 'c1qhdn',
  e2e: { ...nxE2EPreset(__filename, { cypressDir: 'cypress' }) },
  env: {
    host: 'http://localhost:4200',
    username: '',
    password: '',
    project_initialised_state: 'initialised',
    project_initialising_state: 'initialising',
    e2e_project_name: 'e2e_project',
  },
});
