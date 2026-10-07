// Auth F06 Role-based menu, mobile (Expo web).
const { test, expect } = require('../../helpers/fixtures');
const { mobileOpenDrawer, visibleText } = require('../../helpers/auth-users');

async function home(page) {
  await page.goto('/', { timeout: 180_000 });
  await expect(visibleText(page, 'Modules').first()).toBeVisible({ timeout: 60_000 });
}

test.describe('Auth F06 role-based menu (mobile)', () => {
  test('TC-AUTH-06-E07 parent modules and drawer', async ({ page, signIn }) => {
    await signIn('parent');
    await home(page);
    for (const name of ['Students', 'Exam Management', 'Fee Management']) await expect(visibleText(page, name).first()).toBeVisible();
    for (const name of ['Communication', 'Reports', 'Masters', 'Transport']) await expect(visibleText(page, name)).toHaveCount(0);
    await mobileOpenDrawer(page);
    await expect(visibleText(page, 'MENU').first()).toBeVisible();
    // doc: the parent drawer also lists "My Transport" next to Dashboard, Students, Fee, Exam
    for (const name of ['Students', 'Fee', 'Exam']) await expect(visibleText(page, name).first()).toBeVisible();
    for (const name of ['Communication', 'Reports', 'Masters', 'Transport']) await expect(visibleText(page, name)).toHaveCount(0);
  });

  test('TC-AUTH-06-E08 teacher has no fee module and no school settings access', async ({ page, signIn }) => {
    await signIn('teacher');
    await home(page);
    await expect(visibleText(page, 'Fee Management')).toHaveCount(0);
    await expect(visibleText(page, 'Students').first()).toBeVisible();
    await visibleText(page, 'Administration').first().click();
    await expect(visibleText(page, 'School Settings').first()).toBeVisible({ timeout: 30_000 });
    const card = page.locator('div').filter({ hasText: 'School Settings' }).filter({ hasText: /No access/ }).last();
    await expect(card).toBeVisible();
  });
});
