// Staff F02 enroll, F06 list, F08 bulk upload (mobile, Expo web). Baseline: qa_manual with 9 seeded staff.
const fs = require('fs');
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { phone, findStaffByPhone, removeStaff, makeBulkFile } = require('../../helpers/staffkit');

const ROUTE = '/staff/enrollment';

async function open(page) {
  await page.goto(ROUTE, { timeout: 180_000 });
  await expect(page.getByText('Lakshmi Narayana Rao').first()).toBeVisible({ timeout: 60_000 });
}

test.describe('Staff enrollment (mobile)', () => {
  test('TC-STF-02-E10 enroll a staff member', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Mobile');
    const mobile = phone();
    await signIn('admin');
    await open(page);
    const before = await page.getByText(/^\d+ staff members?$/).first().innerText();
    await page.getByText('Add Staff', { exact: true }).first().click();
    await page.getByPlaceholder('Enter first name').fill(name);
    await page.getByPlaceholder('Enter phone number').fill(mobile);
    await page.getByPlaceholder('Enter residential address').fill('5 QA Street');
    await page.getByText('Save', { exact: true }).last().click();
    await toast(page, 'New staff member enrolled successfully');
    const created = await findStaffByPhone(api, mobile);
    expect(created).toBeTruthy();
    cleanup(() => removeStaff(api, created));
    await expect(page.getByText(name).first()).toBeVisible();
    await expect(page.getByText('No Designation').first()).toBeVisible();
    const after = await page.getByText(/^\d+ staff members?$/).first().innerText();
    expect(parseInt(after)).toBeGreaterThan(parseInt(before));
  });

  test('TC-STF-06-E09 search and view a staff member', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await page.getByPlaceholder('Search staff...').fill('ramesh');
    await expect(page.getByText('Ramesh Yadav').first()).toBeVisible();
    await expect(page.getByText('Mohan Singh')).toHaveCount(0);
    await page.getByText('View', { exact: true }).first().click();
    await expect(page.getByText('Driver').filter({ visible: true }).first()).toBeVisible();
    await expect(page.getByText('Transport').filter({ visible: true }).first()).toBeVisible();
    await expect(page.getByText('9000010008').filter({ visible: true }).first()).toBeVisible();
    await expect(page.getByText('Close', { exact: true }).filter({ visible: true }).first()).toBeVisible();
    await expect(page.getByText('Edit Staff').filter({ visible: true }).first()).toBeVisible();
  });

  test('TC-STF-08-E06 bulk upload two staff', async ({ page, signIn, api, cleanup }) => {
    const tag = unique('QA Bulk').replace(/\s+/g, '');
    const p1 = phone();
    const p2 = phone();
    const file = makeBulkFile([
      { 'First Name': `${tag}Five`, Phone: p1, Address: '8 QA Street', Email: `${tag.toLowerCase()}.5@qa.example` },
      { 'First Name': `${tag}Six`, Phone: p2, Address: '9 QA Street', Email: `${tag.toLowerCase()}.6@qa.example` },
    ]);
    cleanup(() => fs.unlinkSync(file));
    cleanup(async () => {
      for (const p of [p1, p2]) await removeStaff(api, await findStaffByPhone(api, p));
    });
    await signIn('admin');
    await open(page);
    await page.getByText('Bulk Upload', { exact: true }).first().click();
    const chooser = page.waitForEvent('filechooser');
    await page.getByText('Tap to select the filled Excel file').first().click();
    await (await chooser).setFiles(file);
    await page.getByText('Upload', { exact: true }).last().click();
    await toast(page, '2 of 2 staff created successfully');
    await expect(page.getByText('2 created').first()).toBeVisible();
    await expect(page.getByText('0 failed').first()).toBeVisible();
    await expect(page.getByText('2 total rows').first()).toBeVisible();
  });
});
