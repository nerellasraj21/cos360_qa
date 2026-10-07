const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { trackAdmission, phone } = require('./_kit');

const vis = (page, text) => page.getByText(text, { exact: true }).locator('visible=true');

async function choose(page, trigger, option) {
  await vis(page, trigger).first().click();
  await page.getByText(option, { exact: true }).last().click({ force: true });
}

test.describe('Students F03 admission (mobile)', () => {
  test('TC-STU-03-E13 create an admission on mobile', async ({ page, signIn, api, cleanup }) => {
    test.setTimeout(240_000);
    const first = unique('QA Mobile');
    await signIn('admin');
    trackAdmission(api, cleanup, first);
    await page.goto('/students/admission', { timeout: 180_000 });
    await vis(page, 'New Admission').first().click({ timeout: 60_000 });
    await expect(vis(page, 'Step 1 of 5')).toBeVisible({ timeout: 30_000 });
    await page.getByPlaceholder('Enter first name').fill(first);
    await page.getByPlaceholder('Enter last name').fill('Kid');
    await vis(page, 'Academic Details').first().click();
    await choose(page, 'Select year', '2026-2027');
    await choose(page, 'Select class', 'Class 2');
    await expect(page.getByPlaceholder('e.g. 2026001').locator('visible=true')).not.toHaveValue('', { timeout: 20_000 });
    await vis(page, 'Next').first().click();
    await expect(vis(page, 'Step 2 of 5')).toBeVisible();
    await page.getByPlaceholder('Father name').locator('visible=true').first().fill('QA Mobile Father');
    await page.getByPlaceholder('10-digit phone number').locator('visible=true').first().fill(phone());
    await vis(page, 'Next').first().click();
    await expect(vis(page, 'Step 3 of 5')).toBeVisible();
    await page.getByPlaceholder(/address/i).locator('visible=true').first().fill('QA Mobile Road');
    await vis(page, 'Next').first().click();
    await vis(page, 'Next').first().click();
    await expect(vis(page, 'Step 5 of 5')).toBeVisible();
    await vis(page, 'Create Admission').first().click();
    await toast(page, 'Student admission created successfully!');
    await expect(page.getByText(`${first} Kid`).locator('visible=true').first()).toBeVisible({ timeout: 30_000 });
  });
});
