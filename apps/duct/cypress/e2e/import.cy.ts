import { DataSet } from '@duct-core/data';
import { loginAndOpenProject } from '../support/app.po';

const { host } = Cypress.env();

const vistImport = () => {
  cy.visit(`${host}/app/import`);
  cy.location('pathname').should('include', '/import');
};

describe('Import', () => {
  beforeEach(loginAndOpenProject);

  it('Should load Import workflow', () => {
    vistImport();
    // verify import redirect
    cy.get('[data-testid=new-import]').click();
    cy.location('pathname').should('include', '/import/workflow');
  });

  it('Should support at least one type of import', () => {
    vistImport();

    //verify import support count
    cy.intercept('GET', '**/dataset/**').as('getImports');
    cy.get('[data-testid=new-import]').click();

    cy.get('@getImports')
      .its('response')
      .then((response) => {
        const { body } = response;
        expect((body as DataSet).supported.length).to.greaterThan(0);
      });
  });
});
