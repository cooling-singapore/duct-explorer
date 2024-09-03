import { Project } from '@duct-core/data';

const {
  host,
  username,
  password,
  project_initialised_state,
  e2e_project_name,
} = Cypress.env();

export const login = () => {
  cy.visit(`${host}`);
  cy.get('#email').click();
  cy.get('#email').type(username);
  cy.get('#password').click();
  cy.get('#password').type(password);
  cy.intercept('POST', '**/token').as('getToken');
  cy.get('[data-testid=signin]').click();
  cy.wait('@getToken');
  cy.location('pathname').should('include', '/projects');
};

export const findE2EProject = (projects: Project[]) => {
  // look for initialised e2e projects to avoid deleting other projects
  return projects.find(
    (project: Project) =>
      project.state === project_initialised_state &&
      project.name === e2e_project_name
  );
};

export const openProject = () => {
  // set up intercept
  cy.intercept('GET', '**/project').as('getProjects');
  cy.visit(`${host}/manage/projects`);

  cy.get('@getProjects')
    .its('response')
    .then((response) => {
      const { body } = response;
      const found = findE2EProject(body);

      if (found) {
        // if found verify that the user is in the correct page
        cy.get(`[data-testid=open-${found.id}]`).click();
        cy.location('pathname').should('include', '/build');
      }
    });
};

export const loginAndOpenProject = () => {
  login();
  openProject();
};
