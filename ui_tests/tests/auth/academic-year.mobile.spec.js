const { test, expect } = require('../../helpers/fixtures');
const { mobileOpenForm } = require('../../helpers/authkit');

const shown = (page, text, exact = true) => page.getByText(text, { exact }).locator('visible=true').first();

test.describe('Auth F02 academic year selection (mobile)', () => {
  test('TC-AUTH-02-E05 the picker lists years with the Current badge and closes on pick', async ({ page }) => {
    await mobileOpenForm(page);
    await expect(shown(page, '2026-2027')).toBeVisible({ timeout: 30_000 });
    await shown(page, '2026-2027').click();
    await expect(shown(page, 'Select Academic Year')).toBeVisible();
    await expect(shown(page, 'Current')).toBeVisible();
    await page.getByText('2026-2027', { exact: true }).locator('visible=true').last().click();
    await expect(page.getByText('Select Academic Year')).toHaveCount(0);
    await expect(shown(page, '2026-2027')).toBeVisible();
  });

  test('TC-AUTH-02-E06 tenant without academic years', async () => {
    test.skip(true, 'blocked: no tenant without academic years can be produced; provisioning always creates one');
  });
});
