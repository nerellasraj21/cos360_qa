// Precondition: qa_school tenant with the five QA users; sessions come from the API, not the form.
const { test, expect } = require('@playwright/test');
const { ROLES } = require('../../helpers/api');
const { signInMobile } = require('../../helpers/session');

for (const role of ROLES) {
  test(`${role} reaches the mobile home without the login screen`, async ({ page }) => {
    await signInMobile(page, role);
    await page.goto('/');
    await expect(page.getByPlaceholder('Enter organization name')).toHaveCount(0, { timeout: 30_000 });
    await expect(page.getByPlaceholder('Enter your username')).toHaveCount(0);
  });
}
