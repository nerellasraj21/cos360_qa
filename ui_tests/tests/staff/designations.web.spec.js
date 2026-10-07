// Staff F01 Designations, web. Baseline: qa_manual seeded designations Accountant, Clerk, Driver, Principal, Teacher.
const { test, expect, unique, toast } = require('../../helpers/fixtures');

const ROUTE = '/staff/designations';

async function findDesignation(api, title) {
  const res = await api('GET', '/staff/designations/?limit=100');
  const rows = Array.isArray(res.data) ? res.data : res.data.items || [];
  return rows.find((d) => d.title === title);
}

test.describe('Staff F01 designations (web)', () => {
  test('TC-STF-01-E01 create a designation', async ({ page, signIn, api, cleanup }) => {
    const title = unique('QA Store Keeper');
    await signIn('admin');
    await page.goto(ROUTE);
    await page.getByRole('button', { name: 'Add Designation' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText('Create Designation')).toBeVisible();
    await dialog.getByPlaceholder(/designation title/i).fill(title);
    await dialog.getByRole('button', { name: 'Save' }).click();
    await toast(page, 'Designation created successfully');
    const created = await findDesignation(api, title);
    expect(created).toBeTruthy();
    cleanup(() => api('DELETE', `/staff/designations/${created.id}`));
    await expect(dialog).toBeHidden();
    const row = page.getByRole('row').filter({ hasText: title });
    await expect(row).toBeVisible();
    await expect(row).toContainText('0 staff members');
    await expect(row).toContainText(new Date().toLocaleDateString('en-US'));
  });
});
