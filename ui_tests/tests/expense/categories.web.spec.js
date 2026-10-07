// Expense F02 categories, web. Created categories are soft-deleted in cleanup.
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { findByName } = require('./kit');

test.describe('Expense F02 categories (web)', () => {
  test('TC-EXP-02-E01 create a category', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Utilities');
    await signIn('admin');
    await page.goto('/expense/categories');
    await page.getByRole('button', { name: 'New Category' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText('Create Category').first()).toBeVisible();
    await dialog.getByLabel('Name').fill(name);
    await dialog.getByLabel('Description').fill('QA monthly utility bills');
    await dialog.getByRole('button', { name: 'Save' }).click();
    await toast(page, 'Category created successfully');
    await expect(dialog).toBeHidden();
    const created = await findByName(api, '/expense/categories/', name);
    expect(created).toBeTruthy();
    cleanup(() => api('DELETE', `/expense/categories/${created.id}`));
    expect(created.is_active).toBe(true);
    await page.getByPlaceholder('Search categories...').fill(name);
    const row = page.getByRole('row').filter({ hasText: name });
    await expect(row).toBeVisible();
    await expect(row).toContainText('Active');
    await expect(row).toContainText(new Date().toLocaleDateString('en-US'));
  });
});
