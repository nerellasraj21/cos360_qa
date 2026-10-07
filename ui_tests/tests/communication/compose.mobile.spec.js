// Communication F02 targeting, F06 logs (mobile, Expo web). Mobile cannot list templates (D-COM-01), so no send is automated here.
const { test, expect, unique } = require('../../helpers/fixtures');
const { createStaff } = require('../../helpers/staffkit');
const { createTemplate } = require('../../helpers/comkit');

function vis(page, text, options = {}) {
  return page.getByText(text, options).filter({ visible: true });
}

test.describe('Communication compose and logs (mobile)', () => {
  test('TC-COM-02-E08 class and section show students and estimated recipients', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/communication', { timeout: 180_000 });
    await expect(vis(page, 'SMS', { exact: true }).first()).toBeVisible({ timeout: 60_000 });
    await vis(page, 'SMS', { exact: true }).first().click();
    await vis(page, 'Parents', { exact: true }).first().click();
    await vis(page, 'Select Class').first().click();
    await vis(page, 'Class 1', { exact: true }).last().click();
    await vis(page, 'Select Section').first().click();
    await vis(page, '1-A', { exact: true }).last().click();
    await expect(page.getByPlaceholder('Search name or admission #').filter({ visible: true })).toBeVisible({ timeout: 30_000 });
    await expect(vis(page, /Estimated recipients: ~\d+/).first()).toBeVisible({ timeout: 30_000 });
    await expect(vis(page, 'Kavya Verma').first()).toBeVisible();
  });

  test('TC-COM-06-E08 failed logs filter and detail', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Com');
    const staff = await createStaff(api, cleanup, { first_name: name, last_name: 'Zed', phone: `0000${Math.floor(Math.random() * 900000 + 100000)}` });
    const tpl = await createTemplate(api, cleanup, { name: unique('QA Broken SMS'), body: 'Hi {% if %}' });
    const sent = await api('POST', '/communication/send', { body: { template_id: tpl.id, target_type: 'multiple_staff', target_ref: { staff_ids: [staff.id] }, variables: {} } });
    expect(sent.status).toBe(200);
    await signIn('admin');
    await page.goto('/communication', { timeout: 180_000 });
    await expect(vis(page, 'Logs', { exact: true }).first()).toBeVisible({ timeout: 60_000 });
    await vis(page, 'Logs', { exact: true }).first().click();
    await vis(page, 'All Status').first().click();
    await vis(page, 'Failed', { exact: true }).last().click();
    const card = vis(page, `${name} Zed`).first();
    await expect(card).toBeVisible({ timeout: 30_000 });
    await expect(vis(page, /Phone: 0000\d+/).first()).toBeVisible();
    await page.getByLabel('View log detail').filter({ visible: true }).first().click();
    await expect(vis(page, 'Log Detail').first()).toBeVisible();
    await expect(vis(page, /Expected an expression/).first()).toBeVisible();
  });
});
