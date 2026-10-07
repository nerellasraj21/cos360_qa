// Auth F09 Parent child selection, mobile (Expo web). Own throwaway family; the father signs in through the form.
const { test, expect } = require('../../helpers/fixtures');
const { createFamily, grantParentRelated, mobileFormSignInAs, visibleText } = require('../../helpers/auth-users');

const HINT = 'Select which child you want to view information for.';

test.describe('Auth F09 parent child selection (mobile)', () => {
  test('TC-AUTH-09-E06 @serial select child screen lists both children', async ({ page, api, cleanup }) => {
    // doc: needs a Parent role grant such as students:read_related, otherwise the screen shows Access Denied (UI-AUTH-10)
    await grantParentRelated(api, cleanup, 'students', 'read_related');
    const family = await createFamily(api, cleanup);
    await mobileFormSignInAs(page, family.fatherEmail, family.fatherPassword);
    await page.goto('/parents/select-child', { timeout: 180_000 });
    await expect(visibleText(page, HINT).first()).toBeVisible({ timeout: 60_000 });
    for (const child of family.children) await expect(visibleText(page, child.name).first()).toBeVisible();
    await expect(visibleText(page, family.children[0].admissionNumber).first()).toBeVisible();
  });

  test('TC-AUTH-09-E07 @serial choosing the second child updates the header', async ({ page, api, cleanup }) => {
    await grantParentRelated(api, cleanup, 'students', 'read_related');
    const family = await createFamily(api, cleanup);
    await mobileFormSignInAs(page, family.fatherEmail, family.fatherPassword);
    await page.goto('/parents/select-child', { timeout: 180_000 });
    await expect(visibleText(page, HINT).first()).toBeVisible({ timeout: 60_000 });
    await visibleText(page, family.children[1].name).first().click();
    await expect(visibleText(page, HINT)).toHaveCount(0, { timeout: 30_000 });
    await expect(visibleText(page, family.children[1].name).first()).toBeVisible();
  });

  test('TC-AUTH-09-E08 @serial parent without children', async ({ page, signIn }) => {
    test.setTimeout(240_000);
    test.fail(true, 'UI-AUTH-10: /parents/select-child shows Access Denied to a Parent holding the seeded permissions (gate needs profile:read_own or students:read)');
    await signIn('parent');
    await page.goto('/parents/select-child', { timeout: 180_000 });
    await expect(visibleText(page, HINT).first()).toBeVisible({ timeout: 60_000 });
    await expect(visibleText(page, 'No children linked to your account.').first()).toBeVisible();
  });
});
