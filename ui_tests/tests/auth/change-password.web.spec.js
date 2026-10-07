// Auth F11 change password, web. Throwaway Admin only; the profile grant is tenant-wide, so tests are @serial.
const { test, expect, toast } = require('../../helpers/fixtures');
const { createStaffUser, grantProfile, injectWeb, plainLogin, newPassword } = require('../../helpers/throwaway');

async function setup(page, cleanup) {
  const admin = await createStaffUser(cleanup, { role: 'Admin' });
  await grantProfile(cleanup, 'Admin', ['update_own']);
  await injectWeb(page, admin.username, admin.password);
  await page.goto('/admin/profile');
  await expect(page.getByText('Admin Profile').first()).toBeVisible();
  return admin;
}

async function openDialog(page) {
  await page.getByRole('button', { name: 'Change Password' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  return dialog;
}

test.describe('Auth F11 change password (web)', () => {
  test.describe.configure({ mode: 'serial' });

  test('TC-AUTH-11-E01 @serial change password succeeds', async ({ page, cleanup }) => {
    const admin = await setup(page, cleanup);
    const fresh = newPassword('QA Pass');
    const dialog = await openDialog(page);
    await dialog.getByLabel('Current Password', { exact: true }).fill(admin.password);
    await dialog.getByLabel('New Password', { exact: true }).fill(fresh);
    await dialog.getByLabel('Confirm New Password', { exact: true }).fill(fresh);
    await dialog.getByRole('button', { name: 'Change Password' }).click();
    await toast(page, 'Password changed successfully!');
    await expect(dialog).toBeHidden();
    expect((await plainLogin(admin.username, fresh)).status).toBe(200);
    expect((await plainLogin(admin.username, admin.password)).status).toBe(401);
  });

  async function fill(dialog, current, next, confirm) {
    await dialog.getByLabel('Current Password', { exact: true }).fill(current);
    await dialog.getByLabel('New Password', { exact: true }).fill(next);
    await dialog.getByLabel('Confirm New Password', { exact: true }).fill(confirm);
  }

  function watchPost(page) {
    const state = { posted: false };
    page.on('request', (r) => { if (r.method() === 'POST' && r.url().includes('/profile/change-password')) state.posted = true; });
    return state;
  }

  test('TC-AUTH-11-E02 @serial mismatching confirmation is rejected locally', async ({ page, cleanup }) => {
    const admin = await setup(page, cleanup);
    const watch = watchPost(page);
    const dialog = await openDialog(page);
    await fill(dialog, admin.password, 'QA Pass 2027', 'QA Pass 2028');
    await dialog.getByRole('button', { name: 'Change Password' }).click();
    await expect(dialog.getByText('Passwords do not match')).toBeVisible();
    await page.waitForTimeout(800);
    expect(watch.posted).toBe(false);
  });

  test('TC-AUTH-11-E03 @serial short password is rejected locally', async ({ page, cleanup }) => {
    const admin = await setup(page, cleanup);
    const watch = watchPost(page);
    const dialog = await openDialog(page);
    await fill(dialog, admin.password, 'QA12345', 'QA12345');
    await dialog.getByRole('button', { name: 'Change Password' }).click();
    await expect(dialog.getByText('Password must be at least 8 characters')).toBeVisible();
    await page.waitForTimeout(800);
    expect(watch.posted).toBe(false);
  });

  test('TC-AUTH-11-E04 @serial wrong current password shows the failure toast', async ({ page, cleanup }) => {
    const admin = await setup(page, cleanup);
    const dialog = await openDialog(page);
    await fill(dialog, 'QA Wrong 999', 'QA Pass 2028', 'QA Pass 2028');
    await dialog.getByRole('button', { name: 'Change Password' }).click();
    await toast(page, 'Failed to change password: Current password is incorrect');
    expect((await plainLogin(admin.username, admin.password)).status).toBe(200);
  });

  test('TC-AUTH-11-E05 @serial new password works after logout and the old one does not', async ({ page, cleanup }) => {
    test.fail(true, 'UI-AUTH-20: Logout from /admin/profile crashes the page ("Rendered fewer hooks than expected") and never reaches /login');
    const admin = await setup(page, cleanup);
    const fresh = newPassword('QA Pass');
    const dialog = await openDialog(page);
    await fill(dialog, admin.password, fresh, fresh);
    await dialog.getByRole('button', { name: 'Change Password' }).click();
    await toast(page, 'Password changed successfully!');
    expect((await plainLogin(admin.username, fresh)).status).toBe(200);
    expect((await plainLogin(admin.username, admin.password)).status).toBe(401);
    await page.getByRole('button', { name: new RegExp(admin.username, 'i') }).first().click();
    await page.getByRole('menuitem', { name: 'Logout' }).click();
    await expect(page).toHaveURL(/\/login/);
    await page.getByLabel('Username / Admission Number').fill(admin.username);
    await page.getByLabel('Password', { exact: true }).fill(admin.password);
    await page.locator('button[type="submit"]').click();
    await expect(page.getByText('Invalid Credentials').first()).toBeVisible();
    await page.getByLabel('Password', { exact: true }).fill(fresh);
    await page.locator('button[type="submit"]').click();
    await expect(page).not.toHaveURL(/\/login/);
  });
});
