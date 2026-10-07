// Masters F06 Class and section lookups, mobile (Expo web timetable pickers). Baseline: qa_manual seeded classes.
const { test, expect } = require('../../helpers/fixtures');

const ROUTE = '/masters/timetable';

test.describe('Masters F06 class and section lookups (mobile)', () => {
  test('TC-MST-06-E04 timetable lists classes then the sections of the chosen class', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto(ROUTE, { timeout: 180_000 });
    await expect(page.getByText('Select Class').first()).toBeVisible({ timeout: 60_000 });
    for (const name of ['Class 1', 'Class 2', 'LKG', 'Nursery', 'UKG']) {
      await expect(page.getByText(name, { exact: true })).toBeVisible();
    }
    await page.getByText('Class 1', { exact: true }).click();
    await expect(page.getByText('Select Section').first()).toBeVisible();
    await expect(page.getByText('1-A', { exact: true })).toBeVisible();
    await expect(page.getByText('1-B', { exact: true })).toBeVisible();
    await expect(page.getByText('2-A', { exact: true })).toHaveCount(0);
  });
});
