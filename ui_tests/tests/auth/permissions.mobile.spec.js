// Auth F05 Permission loading, mobile (Expo web).
const { test, expect } = require('../../helpers/fixtures');
const { createFamily, grantParentRelated, mobileFormSignInAs, visibleText } = require('../../helpers/auth-users');

async function home(page) {
  await page.goto('/', { timeout: 180_000 });
  await expect(visibleText(page, 'Modules').first()).toBeVisible({ timeout: 60_000 });
}

test.describe('Auth F05 permission loading (mobile)', () => {
  test('TC-AUTH-05-E05 staff sees no access on user management', async ({ page, signIn }) => {
    await signIn('staff');
    await home(page);
    await visibleText(page, 'Administration').first().click();
    await expect(visibleText(page, 'User Management').first()).toBeVisible({ timeout: 30_000 });
    const card = page.locator('div').filter({ hasText: 'User Management' }).filter({ hasText: /No access/ }).last();
    await expect(card).toBeVisible();
    await page.goto('/admin/users', { timeout: 180_000 });
    await expect(visibleText(page, 'Access Denied').first()).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText(/have permission to view this screen\. Please contact your administrator\./).first()).toBeVisible();
  });

  test('TC-AUTH-05-E06 @serial parent with read_related opens attendance', async ({ page, api, cleanup }) => {
    await grantParentRelated(api, cleanup);
    const family = await createFamily(api, cleanup);
    await mobileFormSignInAs(page, family.fatherEmail, family.fatherPassword);
    await visibleText(page, 'Students').first().click();
    // doc: the Students hub card for a parent is called "Child Attendance"
    await visibleText(page, 'Child Attendance').first().click({ timeout: 30_000 });
    await expect(page.getByText('Access Denied')).toHaveCount(0);
    await expect(page).toHaveURL(/attendance/);
  });
});
