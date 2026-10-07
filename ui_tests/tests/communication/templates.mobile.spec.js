// Communication F01 templates (mobile, Expo web). Baseline: qa_manual seeded templates.
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { findTemplate } = require('../../helpers/comkit');

test.describe('Communication templates (mobile)', () => {
  test('TC-COM-01-E12 create an SMS template', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Mobile SMS');
    await signIn('admin');
    await page.goto('/communication', { timeout: 180_000 });
    await expect(page.getByText('Templates', { exact: true }).filter({ visible: true }).first()).toBeVisible({ timeout: 60_000 });
    await page.getByText('Templates', { exact: true }).filter({ visible: true }).first().click();
    await page.getByText('New Template').filter({ visible: true }).first().click();
    await page.getByPlaceholder('Template name...').fill(name);
    await page.getByPlaceholder(/Template content/).fill('Dear {{name}}, mobile QA notice.');
    await page.getByText('Save', { exact: true }).filter({ visible: true }).last().click();
    await toast(page, 'New template has been saved');
    const created = await findTemplate(api, name);
    expect(created).toBeTruthy();
    cleanup(() => api('DELETE', `/communication/templates/${created.id}`));
    expect(created.channel).toBe('sms');
    expect(created.is_active).toBe(true);
    expect(created.body).toBe('Dear {{name}}, mobile QA notice.');
  });
});
