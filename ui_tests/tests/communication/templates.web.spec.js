// Communication F01 templates (web). Baseline: qa_manual seeded templates Exam Schedule, Fee Reminder, Holiday Notice.
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { findTemplate } = require('../../helpers/comkit');

test.describe('Communication templates (web)', () => {
  test('TC-COM-01-E01 create an SMS template', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Notice SMS');
    await signIn('admin');
    await page.goto('/communication/templates');
    await page.getByRole('button', { name: /New Template/ }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByPlaceholder('e.g. fee_reminder').fill(name);
    await expect(dialog.getByRole('radio', { name: 'Sms' })).toBeChecked();
    await dialog.getByPlaceholder(/Dear \{\{parent_name\}\}/).fill('Dear {{name}}, this is a QA notice.');
    await dialog.getByRole('button', { name: 'Save Template' }).click();
    await toast(page, 'Template created successfully');
    const created = await findTemplate(api, name);
    expect(created).toBeTruthy();
    cleanup(() => api('DELETE', `/communication/templates/${created.id}`));
    await expect(dialog).toBeHidden();
    const row = page.getByRole('row').filter({ hasText: name });
    await expect(row).toBeVisible();
    await expect(row).toContainText('SMS');
    await expect(row).toContainText('name');
    await expect(row).toContainText('Active');
  });
});
