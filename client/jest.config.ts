const { getJestProjects } = require('@nx/jest');

export default {
  projects: [
    ...getJestProjects(),
    '<rootDir>/apps/duct',
    '<rootDir>/libs/ui',
    '<rootDir>/libs/data',
  ],
};
