// TTC F06-F07 section timetable, mobile (P1). Baseline: qa_manual seeded timetables for 1-A, 1-B, 2-A, 2-B; 4-A empty.
const { test, expect, toast } = require('../../helpers/fixtures');
const { sectionId, subjectIds, putTimetable, subjectRow, getTimetable, clearTimetable } = require('./ttc-kit');

function vis(page, text, exact = true) {
  return page.getByText(text, { exact }).locator('visible=true');
}

async function openTimetable(page, signIn) {
  await signIn('admin');
  await page.goto('/masters/timetable', { timeout: 180_000 });
  await expect(vis(page, 'Select Class').first()).toBeVisible({ timeout: 60_000 });
}

async function openSection(page, signIn, cls, section) {
  await openTimetable(page, signIn);
  await vis(page, cls).first().click({ timeout: 60_000 });
  await vis(page, section).first().click({ timeout: 60_000 });
  await expect(vis(page, `${cls} - ${section}`).first()).toBeVisible({ timeout: 30_000 });
}

test.describe('TTC F06-F07 timetable (mobile)', () => {
  test.describe.configure({ mode: 'serial' });

  test('TC-TTC-06-E09 open the seeded timetable of 1-A from the dashboard', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/', { timeout: 180_000 });
    await vis(page, 'Timetable').first().click({ timeout: 60_000 });
    await vis(page, 'Class 1').first().click({ timeout: 60_000 });
    await vis(page, '1-A').first().click({ timeout: 60_000 });
    await expect(vis(page, 'Class 1 - 1-A').first()).toBeVisible({ timeout: 30_000 });
    await expect(vis(page, 'Timetable').first()).toBeVisible();
    await expect(vis(page, 'Export').first()).toBeVisible();
    await expect(vis(page, 'Edit').first()).toBeVisible();
    for (const d of ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']) await expect(vis(page, d).first()).toBeVisible();
    await expect(vis(page, 'Sat')).toHaveCount(0);
    await expect(vis(page, '9:00 AM - 10:00 AM').first()).toBeVisible();
    await expect(vis(page, 'English').first()).toBeVisible();
  });

  test('TC-TTC-07-E12 create a timetable for 4-A', async ({ page, signIn, api, cleanup }) => {
    const sid = await sectionId(api, 'Class 4 - 4-A');
    await clearTimetable(api, sid);
    cleanup(() => clearTimetable(api, sid));
    const ids = await subjectIds(api);
    await openSection(page, signIn, 'Class 4', '4-A');
    for (let i = 0; i < 5; i++) {
      await vis(page, 'Select Subject').first().click();
      await vis(page, 'English').last().click();
    }
    await vis(page, 'Save Timetable').first().click();
    await toast(page, 'Timetable created successfully');
    await expect(vis(page, '9:00 AM - 9:45 AM').first()).toBeVisible({ timeout: 20_000 });
    for (const d of ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']) await expect(vis(page, d).first()).toBeVisible();
    await expect(vis(page, 'English').first()).toBeVisible();
    const saved = await getTimetable(api, sid);
    expect(saved.timetable_data).toHaveLength(1);
    expect(saved.timetable_data[0].time).toEqual({ from: '09:00', to: '09:45' });
    expect(Object.values(saved.timetable_data[0].subjects)).toEqual(Array(5).fill(ids.English));
  });

  test('TC-TTC-07-E14 change Wednesday and save', async ({ page, signIn, api, cleanup }) => {
    const sid = await sectionId(api, 'Class 4 - 4-A');
    const ids = await subjectIds(api);
    await putTimetable(api, cleanup, sid, [subjectRow('09:00', '09:45', ids.English)]);
    await openSection(page, signIn, 'Class 4', '4-A');
    await vis(page, 'Edit').first().click();
    await expect(vis(page, 'Save Timetable').first()).toBeVisible();
    await vis(page, 'English').nth(2).click();
    await vis(page, 'Mathematics').last().click();
    await vis(page, 'Save', true).first().click();
    await toast(page, 'Timetable updated successfully');
    await expect.poll(async () => (await getTimetable(api, sid)).timetable_data[0].subjects.Wednesday).toBe(ids.Mathematics);
    const saved = await getTimetable(api, sid);
    expect(saved.timetable_data[0].subjects.Tuesday).toBe(ids.English);
    await vis(page, 'Wed').first().click();
    await expect(vis(page, 'Mathematics').first()).toBeVisible();
  });
});
