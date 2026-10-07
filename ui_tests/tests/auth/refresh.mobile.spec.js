// Auth F08 Token refresh and expiry, mobile (Expo web).
const { test, expect } = require('../../helpers/fixtures');
const { editStorageOnNextLoad } = require('../../helpers/auth-users');

async function home(page) {
  await page.goto('/', { timeout: 180_000 });
  await expect(page.getByText('Modules', { exact: true }).locator('visible=true').first()).toBeVisible({ timeout: 60_000 });
}

test.describe('Auth F08 token refresh (mobile)', () => {
  test('TC-AUTH-08-E04 expired access token is refreshed on reload', async ({ page, signIn }) => {
    await signIn('staff');
    await home(page);
    await editStorageOnNextLoad(page, { '@secure/auth_token_expiry': '1000' });
    const refreshes = [];
    page.on('request', (r) => { if (r.method() === 'POST' && r.url().includes('/auth/refresh')) refreshes.push(r.url()); });
    await page.reload({ timeout: 180_000 });
    await expect(page.getByText('Modules', { exact: true }).locator('visible=true').first()).toBeVisible({ timeout: 60_000 });
    await expect.poll(() => refreshes.length).toBeGreaterThan(0);
    await expect.poll(async () => Number(await page.evaluate(() => window.localStorage.getItem('@secure/auth_token_expiry')))).toBeGreaterThan(Date.now() + 23 * 3600 * 1000);
    const expiry = Number(await page.evaluate(() => window.localStorage.getItem('@secure/auth_token_expiry')));
    expect(expiry).toBeLessThan(Date.now() + 25 * 3600 * 1000);
  });

  test('TC-AUTH-08-E05 failed refresh returns to organisation selection', async ({ page, signIn }) => {
    await signIn('staff');
    await home(page);
    await editStorageOnNextLoad(page, { '@secure/auth_refresh_token': 'bad', '@secure/auth_token_expiry': '1000' });
    await page.reload({ timeout: 180_000 });
    await expect(page.getByText('Select Organization').first()).toBeVisible({ timeout: 60_000 });
    const keys = await page.evaluate(() => ({
      org: window.localStorage.getItem('@auth/client_schema'),
      access: window.localStorage.getItem('@secure/auth_access_token'),
      refresh: window.localStorage.getItem('@secure/auth_refresh_token'),
    }));
    expect(keys.org).toBeNull();
    expect(keys.access).toBeNull();
    expect(keys.refresh).toBeNull();
  });
});
