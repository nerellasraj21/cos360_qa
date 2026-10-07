// Staff F10 mark attendance (mobile, Expo web). Baseline: qa_manual with 9 seeded staff, no attendance rows for today.
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { createStaff } = require('../../helpers/staffkit');

const ROUTE = '/staff/attendance';

function staffRow(page, name) {
  return page
    .getByText(name)
    .filter({ visible: true })
    .first()
    .locator('xpath=ancestor::div[.//div[normalize-space(.)="Present"]][1]');
}

test.describe('Staff attendance (mobile)', () => {
  test('TC-STF-10-E10 mark a staff member absent', async ({ page, signIn, api, cleanup }) => {
    const ravi = unique('QA Ravi');
    const created = await createStaff(api, cleanup, { first_name: ravi, last_name: 'Kumar' });
    await signIn('admin');
    await page.goto(ROUTE, { timeout: 180_000 });
    await page.getByPlaceholder('Search by name, email, or department...').filter({ visible: true }).fill(ravi, { timeout: 60_000 });
    await expect(page.getByText(ravi).filter({ visible: true }).first()).toBeVisible({ timeout: 60_000 });
    await staffRow(page, ravi).getByText('Present', { exact: true }).click();
    await page.getByText('Absent', { exact: true }).filter({ visible: true }).last().click();
    await expect(page.getByText('Modified').filter({ visible: true }).first()).toBeVisible();
    await page.getByText('Save Attendance (1)').filter({ visible: true }).first().click();
    await expect(page.getByText('Save Attendance?').filter({ visible: true }).first()).toBeVisible();
    await expect(page.getByText(/You are about to save attendance changes for 1 staff member on .+\. Continue\?/).filter({ visible: true }).first()).toBeVisible();
    await page.getByText('Save', { exact: true }).filter({ visible: true }).last().click();
    await toast(page, 'Attendance updated successfully');
    await expect(page.locator('body')).toContainText(/1\s*ABSENT/i);
    const day = await api('GET', `/staff/${created.id}/attendance/filter`);
    expect(day.data.some((r) => r.status === 'absent')).toBe(true);
  });
});
