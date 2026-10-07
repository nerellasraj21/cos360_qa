// Expense F04 departments, web.
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { findByName } = require('./kit');

test.describe('Expense F04 departments (web)', () => {
  test('TC-EXP-04-E01 create a department', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Hostel');
    await signIn('admin');
    await page.goto('/expense/departments');
    for (const seeded of ['Administration', 'Academics', 'Transport', 'Maintenance', 'Sports']) {
      await expect(page.getByRole('row').filter({ hasText: seeded }).first()).toBeVisible();
    }
    await page.getByRole('button', { name: 'New Department' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText('Create Department').first()).toBeVisible();
    await dialog.getByLabel('Name').fill(name);
    await dialog.getByLabel('Description').fill('QA hostel running costs');
    await dialog.getByRole('button', { name: 'Save' }).click();
    await toast(page, 'Department created successfully');
    await expect(dialog).toBeHidden();
    const created = await findByName(api, '/expense/departments/', name);
    expect(created).toBeTruthy();
    cleanup(() => api('DELETE', `/expense/departments/${created.id}`));
    const row = page.getByRole('row').filter({ hasText: name });
    await expect(row).toBeVisible();
    await expect(row).toContainText('Active');
  });
});
