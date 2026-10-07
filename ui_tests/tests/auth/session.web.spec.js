// Auth F07 Session persistence and route guards, web.
const { test, expect } = require('../../helpers/fixtures');
const { login } = require('../../helpers/api');
const { injectWebSession } = require('../../helpers/auth-users');

test.describe('Auth F07 session persistence (web)', () => {
  test('TC-AUTH-07-E01 reload keeps the session', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/dashboard');
    await expect(page.getByText('Welcome back, qa_admin (Admin)')).toBeVisible();
    await page.reload();
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByText('Welcome back, qa_admin (Admin)')).toBeVisible();
    await expect(page.locator('aside nav').getByRole('button', { name: 'Students', exact: true })).toBeVisible();
  });

  test('TC-AUTH-07-E02 session restored in a new tab', async ({ page, signIn, context }) => {
    await signIn('admin');
    await page.goto('/dashboard');
    await expect(page.getByText('Welcome back, qa_admin (Admin)')).toBeVisible();
    const storage = await page.evaluate(() => ({ a: localStorage.getItem('auth-storage'), t: localStorage.getItem('authToken') }));
    await page.close();
    const fresh = await context.newPage();
    await fresh.goto('/dashboard');
    await expect(fresh.getByText('Welcome back, qa_admin (Admin)')).toBeVisible();
    expect(await fresh.evaluate(() => localStorage.getItem('auth-storage'))).toBeTruthy();
    expect(storage.a).toBeTruthy();
  });

  test('TC-AUTH-07-E03 signed out user is sent to login', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/login/);
  });

  test('TC-AUTH-07-E04 signed in user cannot open the auth pages', async ({ page, signIn }) => {
    await signIn('staff');
    await page.goto('/login');
    await expect(page).toHaveURL(/\/dashboard/);
    await page.goto('/forgot-password');
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('TC-AUTH-07-E05 deleting auth-storage ends the session', async ({ page }) => {
    await injectWebSession(page, await login('admin'));
    await page.goto('/dashboard');
    await expect(page.getByText('Welcome back, qa_admin (Admin)')).toBeVisible();
    await page.evaluate(() => window.localStorage.removeItem('auth-storage'));
    await page.reload();
    await expect(page).toHaveURL(/\/login/);
  });
});
