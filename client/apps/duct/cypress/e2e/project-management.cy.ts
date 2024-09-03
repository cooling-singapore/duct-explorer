import { login, findE2EProject, openProject } from '../support/app.po';

const { host, project_initialising_state, e2e_project_name } = Cypress.env();

describe('Project Management', () => {
  beforeEach(login);

  it('Should be able to create a project', () => {
    cy.location('pathname').should('include', '/projects');
    cy.get('[data-testid=create-project]').click();
    cy.get('#project-name').click();
    cy.get('#project-name').type(e2e_project_name);
    cy.get('#city-select').click();
    cy.get('[data-testid=city-0]').click();
    cy.get('#dataset-select').click();
    cy.get('[data-testid=dataset-0]').click();
    // set up intercept
    cy.intercept('POST', '**/project').as('createProject');
    // click create
    cy.get('[data-testid=create-project]').click();

    cy.get('@createProject')
      .its('response')
      .then((response) => {
        const { body } = response;
        const createdProjectId = body.id;

        // confirm user got sent back to projects list
        cy.location('pathname').should('include', '/projects');

        // confirm project is "initialising"
        cy.get(`[data-testid=state-${createdProjectId}]`).should(
          'have.text',
          project_initialising_state
        );
      });
  });

  it('Should be able to delete a project', () => {
    // set up intercept
    cy.intercept('GET', '**/project').as('getProjects');
    cy.visit(`${host}/manage/projects`);

    cy.get('@getProjects')
      .its('response')
      .then((response) => {
        const { body } = response;
        const found = findE2EProject(body);

        if (found) {
          // if initialised, test deleting it
          cy.intercept('DELETE', '**/project/*').as('deleteProject');
          cy.get(`[data-testid=delete-${found.id}]`).click();
          cy.get(`[data-testid=delete-confirm-${found.id}]`).click();
          cy.get('@deleteProject')
            .its('response')
            .then((response) => {
              expect(response.statusCode).to.eq(200);
            });
        }
      });
  });

  it('Should be able to open a project', () => {
    openProject();
  });
});
