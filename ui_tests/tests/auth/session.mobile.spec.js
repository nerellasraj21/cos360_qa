// Auth F07 Session persistence, mobile (Expo web).
const { test, expect } = require('../../helpers/fixtures');
const { editStorageOnNextLoad, visibleText } = require('../../helpers/auth-users');

async function home(page) {
  await page.goto('/', { timeout: 180_000 });
  await expect(visibleText(page, 'Modules').first()).toBeVisible({ timeout: 60_000 });
}

test.describe('Auth F07 session persistence (mobile)', () => {
  test('TC-AUTH-07-E06 reload keeps the session', async ({ page, signIn }) => {
    await signIn('staff');
    await home(page);
    await page.reload({ timeout: 180_000 });
    await expect(visibleText(page, 'Modules').first()).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText('Select Organization')).toHaveCount(0);
    await expect(page.getByPlaceholder('Enter your username')).toHaveCount(0);
  });

  test('TC-AUTH-07-E07 expired expiry triggers one refresh', async ({ page, signIn }) => {
    await signIn('staff');
    await home(page);
    await editStorageOnNextLoad(page, { '@secure/auth_token_expiry': '1000' });
    const refreshes = [];
    page.on('request', (r) => { if (r.method() === 'POST' && r.url().includes('/auth/refresh')) refreshes.push(r.url()); });
    await page.reload({ timeout: 180_000 });
    await expect(visibleText(page, 'Modules').first()).toBeVisible({ timeout: 60_000 });
    await page.waitForTimeout(1500);
    expect(refreshes.length).toBe(1);
  });

  test('TC-AUTH-07-E08 failed refresh clears the session', async ({ page, signIn }) => {
    await signIn('staff');
    await home(page);
    await editStorageOnNextLoad(page, { '@secure/auth_refresh_token': 'bad', '@secure/auth_token_expiry': '1000' });
    await page.reload({ timeout: 180_000 });
    await expect(page.getByText('Select Organization').first()).toBeVisible({ timeout: 60_000 });
    await expect(page).toHaveURL(/login/);
  });
});
