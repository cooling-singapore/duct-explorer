import { login } from '../support/app.po';

const { host } = Cypress.env();

describe('DUCT Explorer Auth', () => {
  it('Should Sign in and out', () => {
    login();
    cy.get('[data-testid=signout]').click();
    cy.location('pathname').should('include', '/login');
  });

  it('Should not authenticate in incorrect credentials', () => {
    cy.visit(`${host}`);
    cy.get('#email').click();
    cy.get('#email').type('user@mail.com');
    cy.get('#password').click();
    cy.get('#password').type('letmeinplease!iamyoure2etest');
    cy.intercept('POST', '**/token').as('getToken');
    cy.get('[data-testid=signin]').click();
    cy.get('@getToken')
      .its('response')
      .then((response) => {
        // expect a 401 from the api
        expect(response.statusCode).to.eq(401);
        // make sure app didnt redirect
        cy.location('pathname').should('include', '/login');
      });
  });
});
