import { Analysis } from '@duct-core/data';
import { loginAndOpenProject } from '../support/app.po';

const { host } = Cypress.env();

const vistCompare = () => {
  cy.visit(`${host}/app/compare`);
  cy.location('pathname').should('include', '/compare');
};

describe('Compare', () => {
  beforeEach(loginAndOpenProject);

  it('Should load compare successfully', () => {
    vistCompare();
  });

  it('Should have at least one Analysis deployed', () => {
    vistCompare();
    cy.intercept('GET', '**/info').as('getInfo');
    cy.get('@getInfo')
      .its('response')
      .then((response) => {
        const { body } = response;
        expect((body as Analysis[]).length).to.greaterThan(0);
      });
  });
});
