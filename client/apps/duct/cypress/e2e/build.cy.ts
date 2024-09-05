import { SceneModule } from '@duct-core/data';
import { loginAndOpenProject } from '../support/app.po';

const { host } = Cypress.env();

const vistBuild = () => {
  cy.visit(`${host}/app/build`);
  cy.location('pathname').should('include', '/build');
};

describe('Compare', () => {
  beforeEach(loginAndOpenProject);

  it('Should load create scene workflow', () => {
    vistBuild();
    // verify create scene redirect
    cy.get('[data-testid=create-scene]').click();
    cy.location('pathname').should('include', '/build/workflow');
  });

  it('Should load at least one module', () => {
    vistBuild();
    // verify create scene redirect
    cy.get('[data-testid=create-scene]').click();

    //verify modules loaded
    cy.intercept('GET', '**/info/scene/**').as('getModules');
    cy.get('[data-testid=next]').click();

    cy.get('@getModules')
      .its('response')
      .then((response) => {
        const { body } = response;
        expect((body as SceneModule[]).length).to.greaterThan(0);
      });
  });
});
