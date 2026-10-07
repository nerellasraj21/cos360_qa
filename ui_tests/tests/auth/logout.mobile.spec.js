// Auth F14 logout, mobile. Throwaway staff user so the shared QA logins are never logged out server-side.
const { test, expect } = require('../../helpers/fixtures');
const { createStaffUser, createFamily, grantProfile, injectMobile } = require('../../helpers/throwaway');
const { TENANT } = require('../../helpers/api');

async function openProfile(page, cleanup) {
  const user = await createStaffUser(cleanup);
  await injectMobile(page, user.username, user.password);
  await page.goto('/profile', { timeout: 180_000 });
  await expect(page.getByText('Logout', { exact: true }).first()).toBeVisible({ timeout: 60_000 });
  return user;
}

test.describe('Auth F14 logout (mobile)', () => {
  test('TC-AUTH-14-E05 logout dialog confirms and returns to organisation step', async ({ page, cleanup }) => {
    await openProfile(page, cleanup);
    await page.getByText('Logout', { exact: true }).first().click();
    await expect(page.getByText('Are you sure you want to logout?')).toBeVisible();
    await page.getByText('Logout', { exact: true }).last().click();
    await expect(page.getByPlaceholder('Enter organization name')).toBeVisible({ timeout: 30_000 });
    await expect(page).toHaveURL(/login/);
  });

  test('TC-AUTH-14-E06 cancel keeps the user signed in', async ({ page, cleanup }) => {
    await openProfile(page, cleanup);
    await page.getByText('Logout', { exact: true }).first().click();
    await expect(page.getByText('Are you sure you want to logout?')).toBeVisible();
    await page.getByText('Cancel', { exact: true }).click();
    await expect(page.getByText('Are you sure you want to logout?')).toHaveCount(0);
    await expect(page.getByText('Logout', { exact: true }).first()).toBeVisible();
    await expect(page).not.toHaveURL(/login/);
  });

  test('TC-AUTH-14-E07 @serial next parent does not see the previous parent children', async ({ page, cleanup }) => {
    test.setTimeout(300_000);
    const first = await createFamily(cleanup);
    const second = await createFamily(cleanup);
    // doc: Select Child needs profile:read_own or students:read, which the Parent role lacks by default; the test grants profile:read_own
    await grantProfile(cleanup, 'Parent', ['read_own']);
    const formSignIn = async (user) => {
      await page.getByPlaceholder('Enter organization name').fill(TENANT);
      await page.getByText('Continue', { exact: true }).click();
      await page.getByPlaceholder('Enter your username').fill(user.fatherEmail);
      await page.getByPlaceholder('Enter your password').fill(user.fatherPassword);
      await page.getByText('Sign In', { exact: true }).click();
      await page.waitForFunction(() => !location.pathname.includes('login'), null, { timeout: 60_000 });
      await page.waitForTimeout(3000);
    };
    await page.goto('/login', { timeout: 180_000 });
    await formSignIn(first);
    await page.goto('/parents/select-child', { timeout: 180_000 });
    await expect(page.getByText(first.studentName.split(' ')[0]).locator('visible=true').first()).toBeVisible({ timeout: 60_000 });
    await page.goto('/profile', { timeout: 180_000 });
    await page.getByText('Logout', { exact: true }).first().click();
    await page.getByText('Logout', { exact: true }).last().click();
    await expect(page.getByPlaceholder('Enter organization name')).toBeVisible({ timeout: 30_000 });
    await formSignIn(second);
    await page.goto('/parents/select-child', { timeout: 180_000 });
    await expect(page.getByText(second.studentName.split(' ')[0]).locator('visible=true').first()).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText(first.studentName.split(' ')[0]).locator('visible=true')).toHaveCount(0);
  });
});
