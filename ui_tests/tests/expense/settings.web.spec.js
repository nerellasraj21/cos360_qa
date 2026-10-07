// Expense F05 settings, web.
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { list } = require('./kit');

test.describe('Expense F05 settings (web)', () => {
  test('TC-EXP-05-E01 create a numeric setting', async ({ page, signIn, api, cleanup }) => {
    const key = unique('qa_limit').toLowerCase().replace(/\s+/g, '_');
    const label = unique('QA limit');
    await signIn('admin');
    await page.goto('/expense/settings');
    await page.getByRole('button', { name: 'New Setting' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('textbox', { name: 'Setting Key *' }).fill(key);
    await dialog.getByRole('textbox', { name: 'Setting Name *' }).fill(label);
    await expect(dialog.getByRole('button', { name: 'Approval' })).toBeVisible();
    await expect(dialog.getByRole('button', { name: 'Standard' })).toBeVisible();
    await dialog.getByRole('spinbutton', { name: 'Numeric Value' }).fill('1500');
    await dialog.getByRole('button', { name: 'Save' }).click();
    await toast(page, 'Settings updated successfully');
    const all = list(await api('GET', '/expense/settings/?limit=1000'));
    const created = all.find((s) => s.setting_key === key);
    expect(created).toBeTruthy();
    cleanup(() => api('DELETE', `/expense/settings/${created.id}`));
    const row = page.getByRole('row').filter({ hasText: label });
    await expect(row).toBeVisible();
    await expect(row).toContainText(/approval/i);
    await expect(row).toContainText('1500');
  });
});
