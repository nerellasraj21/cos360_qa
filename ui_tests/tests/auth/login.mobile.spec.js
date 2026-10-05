// Precondition: qa_school tenant with the five QA users; Expo web served at MOBILE_URL.
const { test, expect } = require('@playwright/test');
const { credentials, TENANT } = require('../../helpers/api');

test.describe('mobile login (Expo web at phone size)', () => {
  test('organization step then sign in as admin', async ({ page }) => {
    const { username, password } = credentials('admin');
    await page.goto('/login');
    await page.getByPlaceholder('Enter organization name').fill(TENANT);
    await page.getByText('Continue', { exact: true }).click();
    await page.getByPlaceholder('Enter your username').fill(username);
    await page.getByPlaceholder('Enter your password').fill(password);
    await page.getByText('Sign In', { exact: true }).click();
    await expect(page).not.toHaveURL(/\/login/);
  });

  test('unknown organization shows an error and stays on the first step', async ({ page }) => {
    await page.goto('/login');
    await page.getByPlaceholder('Enter organization name').fill('qa_does_not_exist');
    await page.getByText('Continue', { exact: true }).click();
    await expect(page.getByPlaceholder('Enter your username')).toHaveCount(0);
  });
});
