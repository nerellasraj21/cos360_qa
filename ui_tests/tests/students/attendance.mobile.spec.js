const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { apiClass, apiStudent } = require('./_kit');

const vis = (page, text) => page.getByText(text, { exact: true }).locator('visible=true');

test.describe('Students F11 attendance (mobile)', () => {
  test('TC-STU-11-E07 teacher marks one student absent and every student gets a row', async ({ page, signIn, api, cleanup }) => {
    test.setTimeout(240_000);
    const klass = await apiClass(api, cleanup);
    const a = await apiStudent(api, cleanup, klass, { first: unique('QAAsa'), last: 'Tmp' });
    const b = await apiStudent(api, cleanup, klass, { first: unique('QAKav'), last: 'Tmp' });
    await signIn('teacher');
    await page.goto('/students/attendance', { timeout: 180_000 });
    await page.locator('[tabindex="0"]').filter({ hasText: /^Class$/ }).first().click({ timeout: 90_000 });
    await page.getByText(klass.className, { exact: true }).last().click({ force: true });
    await page.locator('[tabindex="0"]').filter({ hasText: /^Section$/ }).first().click();
    await page.getByText(klass.sectionName, { exact: true }).last().click({ force: true });
    await expect(vis(page, '2 students total')).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText(a.name, { exact: true }).locator('visible=true')).toBeVisible();
    await vis(page, 'Present').nth(1).click();
    await vis(page, 'Absent').last().click();
    await vis(page, 'Save Attendance').first().click();
    await toast(page, 'Attendance saved successfully');
    await expect.poll(async () => (await api('GET', `/student/attendance/student/${a.studentId}/filter?start_date=2026-01-01&end_date=2026-12-31`)).data.map((r) => r.status), { timeout: 30_000 }).toEqual(['absent']);
    await expect.poll(async () => (await api('GET', `/student/attendance/student/${b.studentId}/filter?start_date=2026-01-01&end_date=2026-12-31`)).data.map((r) => r.status), { timeout: 30_000 }).toEqual(['present']);
  });
});
