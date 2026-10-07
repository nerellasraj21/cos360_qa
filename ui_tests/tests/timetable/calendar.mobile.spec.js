// TTC F11-F12 read-only views, mobile (P1). Counts are for a test date of 2026-10-07 with the 8 seeded holidays.
const { test, expect } = require('../../helpers/fixtures');

function vis(page, text, exact = true) {
  return page.getByText(text, { exact }).locator('visible=true');
}

test.describe('TTC F11-F12 read-only views (mobile)', () => {
  test('TC-TTC-11-E01 student timetable viewer', async () => {
    test.skip(true, 'blocked: Student has no timetable_management:read in the default seed, so the call returns 403 (Known gaps 5)');
  });

  test('TC-TTC-12-E01 school calendar for Teacher', async ({ page, signIn }) => {
    await signIn('teacher');
    await page.goto('/calendar', { timeout: 180_000 });
    await expect(vis(page, 'School Calendar').first()).toBeVisible({ timeout: 60_000 });
    await expect(vis(page, 'Next holiday: Dasara Vacation on', false).first()).toBeVisible();
    await expect(vis(page, '17 Oct 2026', false).first()).toBeVisible();
    await expect(vis(page, 'Total').first()).toBeVisible();
    await expect(vis(page, 'Upcoming').first()).toBeVisible();
    await expect(vis(page, 'Past').first()).toBeVisible();
    const body = await page.locator('body').innerText();
    expect(body.replace(/\s+/g, ' ')).toMatch(/8\s*Total/i);
    expect(body.replace(/\s+/g, ' ')).toMatch(/5\s*Upcoming/i);
    expect(body.replace(/\s+/g, ' ')).toMatch(/3\s*Past/i);
    await expect(vis(page, 'OCTOBER 2026').first()).toBeVisible();
    await expect(vis(page, 'NOVEMBER 2026').first()).toBeVisible();
    for (const name of ['Dasara Vacation', 'Diwali', 'Christmas', 'Sankranti Break', 'Republic Day']) {
      await expect(vis(page, name).first()).toBeVisible();
    }
    await expect(vis(page, 'Gandhi Jayanti')).toHaveCount(0);
  });
});
