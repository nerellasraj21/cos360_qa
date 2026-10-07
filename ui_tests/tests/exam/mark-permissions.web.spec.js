// Exam F10 Mark entry permissions, web (P1).
const { test, expect, toast } = require('../../helpers/fixtures');
const { login } = require('../../helpers/api');
const kit = require('./_kit');

test.describe('Exam F10 mark entry permissions (web)', () => {
  test('TC-EXM-10-E01 grant mark entry access to the staff user', async ({ page, signIn, api, cleanup }) => {
    const klass = await kit.createQaClass(api, cleanup);
    const exam = await kit.createExam(api, cleanup, klass);
    const staff = await login('staff');
    await signIn('admin');
    await page.goto(`/exam/exams/${exam.id}`);
    await page.getByRole('button', { name: 'Permissions', exact: true }).click();
    await page.getByRole('button', { name: 'Manage Permissions' }).click();
    await page.getByPlaceholder('Enter User ID').fill(staff.user.id);
    await page.getByRole('button', { name: 'Grant Access' }).click();
    await toast(page, 'Access granted successfully');
    const row = page.locator('tbody tr').first();
    await expect(row).toContainText('Active');
    const perms = await api('GET', `/exams/${exam.id}/mark-permissions`);
    expect(kit.rows(perms).some((p) => p.user_id === staff.user.id && p.is_active)).toBe(true);
  });
});
