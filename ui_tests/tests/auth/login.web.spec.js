// Precondition: qa_school tenant with the five QA users (backend/scripts/qa/setup_qa_tenant.py).
const { test, expect } = require('@playwright/test');
const { credentials } = require('../../helpers/api');

test.describe('web login form', () => {
  test('admin signs in with username and password', async ({ page }) => {
    const { username, password } = credentials('admin');
    await page.goto('/login');
    await page.getByLabel('Username / Admission Number').fill(username);
    await page.getByLabel('Password', { exact: true }).fill(password);
    await page.locator('button[type="submit"]').click();
    await expect(page).not.toHaveURL(/\/login/);
  });

  test('wrong password stays on the login page', async ({ page }) => {
    const { username } = credentials('admin');
    await page.goto('/login');
    await page.getByLabel('Username / Admission Number').fill(username);
    await page.getByLabel('Password', { exact: true }).fill('definitely-wrong-password');
    await page.locator('button[type="submit"]').click();
    await expect(page).toHaveURL(/\/login/);
  });
});
