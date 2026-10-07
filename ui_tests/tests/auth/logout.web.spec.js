// Auth F14 logout, web. Throwaway staff user so the shared QA logins are never logged out server-side.
const { test, expect, toast } = require('../../helpers/fixtures');
const { call } = require('../../helpers/api');
const { createStaffUser, injectWeb } = require('../../helpers/throwaway');

async function logout(page, user) {
  await page.goto('/');
  await page.getByRole('button', { name: new RegExp(user.username, 'i') }).first().click();
  await page.getByRole('menuitem', { name: 'Logout' }).click();
}

test.describe('Auth F14 logout (web)', () => {
  test('TC-AUTH-14-E01 logout returns to login and clears the store', async ({ page, cleanup }) => {
    const user = await createStaffUser(cleanup);
    await injectWeb(page, user.username, user.password);
    await logout(page, user);
    await expect(page).toHaveURL(/\/login/);
    const stored = await page.evaluate(() => JSON.parse(localStorage.getItem('auth-storage') || '{}').state || {});
    expect(stored.user ?? null).toBeNull();
    expect(stored.accessToken ?? null).toBeNull();
    expect(stored.refreshToken ?? null).toBeNull();
    expect(stored.permissions || []).toHaveLength(0);
    expect(stored.menuItems || []).toHaveLength(0);
  });

  test('TC-AUTH-14-E02 back button after logout stays on login', async ({ page, cleanup }) => {
    const user = await createStaffUser(cleanup);
    await injectWeb(page, user.username, user.password);
    await logout(page, user);
    await expect(page).toHaveURL(/\/login/);
    await page.goBack();
    await page.waitForTimeout(1000);
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByLabel('Username / Admission Number')).toBeVisible();
  });

  test('TC-AUTH-14-E03 access token is rejected after logout', async ({ page, cleanup }) => {
    const user = await createStaffUser(cleanup);
    await injectWeb(page, user.username, user.password);
    await page.goto('/');
    await expect(page.getByRole('button', { name: new RegExp(user.username, 'i') }).first()).toBeVisible();
    const accessToken = await page.evaluate(() => JSON.parse(localStorage.getItem('auth-storage')).state.accessToken);
    await logout(page, user);
    await expect(page).toHaveURL(/\/login/);
    const res = await call('GET', '/auth/available-resources', { token: accessToken });
    expect(res.status).toBe(401);
    expect(JSON.stringify(res.data)).toContain('Token has been invalidated. Please login again.');
  });

  test('TC-AUTH-14-E04 logout works while offline', async ({ page, context, cleanup }) => {
    test.fail(true, 'UI-AUTH-21: when POST /auth/logout fails the store is cleared but navigate to /login runs only in onSuccess, so the user stays on the page');
    const user = await createStaffUser(cleanup);
    await injectWeb(page, user.username, user.password);
    await page.goto('/');
    await page.getByRole('button', { name: new RegExp(user.username, 'i') }).first().click();
    await context.setOffline(true);
    await page.getByRole('menuitem', { name: 'Logout' }).click();
    await expect(page).toHaveURL(/\/login/);
    const stored = await page.evaluate(() => JSON.parse(localStorage.getItem('auth-storage') || '{}').state || {});
    expect(stored.accessToken ?? null).toBeNull();
    expect(stored.user ?? null).toBeNull();
    await context.setOffline(false);
  });
});
