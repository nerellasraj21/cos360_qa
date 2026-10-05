// Precondition: qa_school tenant with the five QA users; sessions come from the API, not the form.
const { test, expect } = require('@playwright/test');
const { ROLES } = require('../../helpers/api');
const { signInWeb } = require('../../helpers/session');

for (const role of ROLES) {
  test(`${role} lands on the app with a menu`, async ({ page }) => {
    await signInWeb(page, role);
    await page.goto('/');
    await expect(page).not.toHaveURL(/\/login/);
    await expect(page.getByRole('navigation').first()).toBeVisible();
  });
}
