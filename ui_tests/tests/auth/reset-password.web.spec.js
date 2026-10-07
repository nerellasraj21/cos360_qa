// Auth F12 forgot and reset password, web.
const { test, expect, toast } = require('../../helpers/fixtures');
const { createStaffUser, injectWeb } = require('../../helpers/throwaway');

const NOTICE = 'Please contact your school administrator. They can reset your password and give you a temporary one to sign in with.';

test.describe('Auth F12 forgot password (web)', () => {
  test('TC-AUTH-12-E01 forgot password page and back link', async ({ page }) => {
    await page.goto('/login');
    await page.getByText('Forgot your password?').click();
    await expect(page).toHaveURL(/\/forgot-password/);
    await expect(page.getByText('Forgot your password?').first()).toBeVisible();
    await expect(page.getByText('Password reset by email is not available yet.')).toBeVisible();
    await expect(page.getByText(NOTICE)).toBeVisible();
    await page.getByText('Back to login').click();
    await expect(page).toHaveURL(/\/login/);
  });

  test('TC-AUTH-12-E02 admin resets a staff password and the user signs in with it', async ({ page, browser, signIn, cleanup }) => {
    const user = await createStaffUser(cleanup);
    const fresh = 'QA Reset 2026';
    await signIn('admin');
    await page.goto('/admin/users');
    await page.getByPlaceholder('Search username or email...').fill(user.username);
    const row = page.getByRole('row').filter({ hasText: user.username });
    await expect(row).toBeVisible();
    await row.getByRole('button', { name: 'Reset Password' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('New Password').fill(fresh);
    await dialog.getByLabel('Confirm Password').fill(fresh);
    await dialog.getByRole('button', { name: 'Reset Password' }).click();
    await toast(page, 'Password reset successfully');
    const other = await browser.newContext();
    cleanup(() => other.close());
    const page2 = await other.newPage();
    await page2.goto('/login');
    await page2.getByLabel('Username / Admission Number').fill(user.username);
    await page2.getByLabel('Password', { exact: true }).fill(fresh);
    await page2.locator('button[type="submit"]').click();
    await expect(page2).toHaveURL(/\/dashboard/);
    await expect(page2).not.toHaveURL(/set-password/);
  });
});
