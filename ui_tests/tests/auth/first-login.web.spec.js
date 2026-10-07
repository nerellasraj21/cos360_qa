const { test, expect } = require('../../helpers/fixtures');
const { createStaffUser, webSubmitLogin, call, webLogout, activeYear } = require('../../helpers/authkit');

async function reachSetPassword(page, user) {
  await webSubmitLogin(page, user.username, user.password);
  await expect(page).toHaveURL(/\/set-password/);
}

test.describe('Auth F04 first-login password change (web)', () => {
  test('TC-AUTH-04-E01 temporary password leads to the set-password page', async ({ page, cleanup }) => {
    const user = await createStaffUser(cleanup);
    await reachSetPassword(page, user);
    await expect(page.getByText('Set Your Password')).toBeVisible();
    await expect(page.getByText('Create a new password to access your account.')).toBeVisible();
    await expect(page.getByLabel('New Password')).toBeVisible();
    await expect(page.getByLabel('Confirm Password')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Set Password' })).toBeVisible();
    await expect(page.getByText('Welcome back')).toHaveCount(0);
  });

  test('TC-AUTH-04-E02 setting the password signs the user in', async ({ page, cleanup }) => {
    const user = await createStaffUser(cleanup);
    const fresh = `QA Pass ${Date.now().toString(36)}`;
    await reachSetPassword(page, user);
    await page.getByLabel('New Password').fill(fresh);
    await page.getByLabel('Confirm Password').fill(fresh);
    await page.getByRole('button', { name: 'Set Password' }).click();
    await expect(page).not.toHaveURL(/set-password|login/, { timeout: 20_000 });
    await expect(page.getByRole('button', { name: 'Dashboard', exact: true })).toBeVisible();
    const year = await activeYear();
    const old = await call('POST', '/auth/login', { body: { username: user.username, password: user.password, academic_year_id: year.id } });
    expect(old.status).toBe(401);
  });

  test('TC-AUTH-04-E03 mismatching confirmation shows the banner', async ({ page, cleanup }) => {
    const user = await createStaffUser(cleanup);
    await reachSetPassword(page, user);
    await page.getByLabel('New Password').fill('QA Pass 2026');
    await page.getByLabel('Confirm Password').fill('QA Pass 2027');
    await page.getByRole('button', { name: 'Set Password' }).click();
    await expect(page.getByText('Passwords do not match')).toBeVisible();
    await expect(page).toHaveURL(/\/set-password/);
  });

  test('TC-AUTH-04-E04 opening /set-password without a token shows the expired panel', async ({ page }) => {
    await page.goto('/set-password');
    await expect(page.getByText('Session expired or invalid')).toBeVisible();
    await expect(page.getByText('Please log in again with your temporary password.')).toBeVisible();
    await page.getByRole('button', { name: 'Back to Login' }).click();
    await expect(page).toHaveURL(/\/login/);
  });

  test('TC-AUTH-04-E05 after the change the next login is a normal login', async ({ page, cleanup }) => {
    const user = await createStaffUser(cleanup);
    const fresh = `QA Pass ${Date.now().toString(36)}`;
    await reachSetPassword(page, user);
    await page.getByLabel('New Password').fill(fresh);
    await page.getByLabel('Confirm Password').fill(fresh);
    await page.getByRole('button', { name: 'Set Password' }).click();
    await expect(page).not.toHaveURL(/set-password|login/, { timeout: 20_000 });
    await webLogout(page);
    await expect(page).toHaveURL(/\/login/);
    await webSubmitLogin(page, user.username, fresh);
    await expect(page).toHaveURL(/\/dashboard/);
  });
});
