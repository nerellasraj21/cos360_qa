// Expense F03 types, web.
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { findByName } = require('./kit');

test.describe('Expense F03 types (web)', () => {
  test('TC-EXP-03-E01 create a type in Utilities', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Solar Panels');
    await signIn('admin');
    await page.goto('/expense/types');
    await page.getByRole('button', { name: 'New Type' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Name').fill(name);
    await dialog.getByRole('combobox', { name: 'Select category' }).click();
    await page.getByRole('option', { name: 'Utilities', exact: true }).click();
    await dialog.getByRole('button', { name: 'Save' }).click();
    await toast(page, 'Expense type created successfully');
    const created = await findByName(api, '/expense/types/', name);
    expect(created).toBeTruthy();
    cleanup(() => api('DELETE', `/expense/types/${created.id}`));
    await page.getByPlaceholder('Search types...').fill(name);
    const row = page.getByRole('row').filter({ hasText: name });
    await expect(row).toBeVisible();
    await expect(row).toContainText('Utilities');
    await expect(row).toContainText('Active');
  });
});
