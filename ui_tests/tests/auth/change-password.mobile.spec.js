// Auth F11 change password, mobile. Throwaway Admin only; the profile grant is tenant-wide, so tests are @serial.
const { test, expect } = require('../../helpers/fixtures');
const { createStaffUser, grantProfile, injectMobile, plainLogin, newPassword } = require('../../helpers/throwaway');

async function openScreen(page, cleanup) {
  const admin = await createStaffUser(cleanup, { role: 'Admin' });
  await grantProfile(cleanup, 'Admin', ['update_own']);
  await injectMobile(page, admin.username, admin.password);
  await page.goto('/admin/profile', { timeout: 180_000 });
  const row = page.getByText('Change Password', { exact: true }).first();
  await expect(row).toBeVisible({ timeout: 60_000 });
  await expect(async () => {
    await row.click();
    await expect(page.getByPlaceholder('Enter current password')).toBeVisible({ timeout: 4000 });
  }).toPass({ timeout: 45_000 });
  return admin;
}

async function fill(page, current, next, confirm) {
  await page.getByPlaceholder('Enter current password').fill(current);
  await page.getByPlaceholder('Min 8 characters').fill(next);
  await page.getByPlaceholder('Re-enter new password').fill(confirm);
}

function watchPost(page) {
  const state = { posted: false };
  page.on('request', (r) => { if (r.method() === 'POST' && r.url().includes('/profile/change-password')) state.posted = true; });
  return state;
}

function submit(page) {
  return page.getByText('Change Password', { exact: true }).last();
}

test.describe('Auth F11 change password (mobile)', () => {
  test.describe.configure({ mode: 'serial' });

  test('TC-AUTH-11-E06 @serial change password succeeds', async ({ page, cleanup }) => {
    const admin = await openScreen(page, cleanup);
    const fresh = newPassword('QA Pass');
    await fill(page, admin.password, fresh, fresh);
    await submit(page).click();
    await expect(page.getByText('Password changed successfully').first()).toBeVisible({ timeout: 30_000 });
    expect((await plainLogin(admin.username, fresh)).status).toBe(200);
    expect((await plainLogin(admin.username, admin.password)).status).toBe(401);
  });

  test('TC-AUTH-11-E07 @serial mismatching confirmation is rejected locally', async ({ page, cleanup }) => {
    const admin = await openScreen(page, cleanup);
    const watch = watchPost(page);
    await fill(page, admin.password, 'QA Pass 2030', 'QA Pass 2031');
    await expect(page.getByText('Passwords do not match').first()).toBeVisible();
    await submit(page).click();
    await expect(page.getByText('Passwords do not match').first()).toBeVisible();
    await page.waitForTimeout(800);
    expect(watch.posted).toBe(false);
  });

  test('TC-AUTH-11-E08 @serial wrong current password shows an error', async ({ page, cleanup }) => {
    const admin = await openScreen(page, cleanup);
    await fill(page, 'QA Wrong 999', 'QA Pass 2030', 'QA Pass 2030');
    await submit(page).click();
    await expect(page.getByText('Current password is incorrect', { exact: false }).first()).toBeVisible({ timeout: 30_000 });
    expect((await plainLogin(admin.username, admin.password)).status).toBe(200);
  });
});
