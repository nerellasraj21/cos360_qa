// Auth F12 forgot password, mobile.
const { test, expect, TENANT } = require('../../helpers/fixtures');

const NOTICE = 'Please contact your school administrator. They can reset your password and give you a temporary one to sign in with.';

async function openForgot(page) {
  await page.goto('/login', { timeout: 180_000 });
  await page.getByPlaceholder('Enter organization name').fill(TENANT);
  await page.getByText('Continue', { exact: true }).click();
  await expect(page.getByPlaceholder('Enter your username')).toBeVisible({ timeout: 60_000 });
  await page.getByText('Forgot Password?', { exact: true }).locator('visible=true').first().click();
}

test.describe('Auth F12 forgot password (mobile)', () => {
  test('TC-AUTH-12-E03 forgot password screen shows the notice', async ({ page }) => {
    await openForgot(page);
    await expect(page.getByText('Forgot Password?').locator('visible=true').first()).toBeVisible();
    await expect(page.getByText('Password reset by email is not available yet.').locator('visible=true')).toBeVisible();
    await expect(page.getByText(NOTICE).locator('visible=true')).toBeVisible();
  });

  test('TC-AUTH-12-E04 both back controls return to the sign-in form', async ({ page }) => {
    await openForgot(page);
    await expect(page.getByText('Back to Login').locator('visible=true').first()).toBeVisible();
    await page.getByText('Back to Login').locator('visible=true').first().click();
    await expect(page.getByPlaceholder(/Enter (your username|organization name)/).locator('visible=true').first()).toBeVisible({ timeout: 30_000 });
    if (await page.getByPlaceholder('Enter organization name').isVisible()) {
      await page.getByPlaceholder('Enter organization name').fill(TENANT);
      await page.getByText('Continue', { exact: true }).click();
    }
    await page.getByText('Forgot Password?', { exact: true }).locator('visible=true').first().click();
    await expect(page.getByText('Password reset by email is not available yet.').locator('visible=true')).toBeVisible();
    await page.getByText('Back to Login').locator('visible=true').last().click();
    await expect(page.getByPlaceholder(/Enter (your username|organization name)/).locator('visible=true').first()).toBeVisible({ timeout: 30_000 });
  });
});
