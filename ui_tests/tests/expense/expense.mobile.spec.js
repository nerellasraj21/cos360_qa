// Expense P1 cases, mobile (Expo web). Own data only: transactions cannot be deleted through the API, so QA rows stay.
const fs = require('fs');
const os = require('os');
const path = require('path');
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { createTransaction, findTransaction, findByName } = require('./kit');

function vis(page, text, options = { exact: true }) {
  return page.getByText(text, options).locator('visible=true').first();
}

async function open(page, route, readyText) {
  await page.goto(route, { timeout: 180_000 });
  await expect(vis(page, readyText)).toBeVisible({ timeout: 60_000 });
}


test.describe('Expense P1 (mobile)', () => {
  test('TC-EXP-02-E08 create a category', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Mobile Category');
    await signIn('admin');
    await open(page, '/expense/categories', 'New Category');
    await vis(page, 'New Category').click();
    await page.getByPlaceholder('Enter category name').locator('visible=true').fill(name);
    await vis(page, 'Save').click();
    await toast(page, 'Category Created');
    await toast(page, `"${name}" has been saved.`);
    const created = await findByName(api, '/expense/categories/', name);
    expect(created).toBeTruthy();
    cleanup(() => api('DELETE', `/expense/categories/${created.id}`));
    await expect(vis(page, name)).toBeVisible();
    const card = page.locator('div').filter({ hasText: name }).filter({ hasText: 'Active' }).locator('visible=true').last();
    await expect(card).toContainText('Active');
  });

  test('TC-EXP-06-E06 create a transaction with two items', async ({ page, signIn, api }) => {
    const vendor = unique('QA Power Co');
    await signIn('admin');
    await open(page, '/expense/transactions', 'New Transaction');
    await vis(page, 'New Transaction').click();
    await expect(vis(page, 'Create New Transaction')).toBeVisible();
    await vis(page, 'Select expense type').click();
    await vis(page, 'Electricity Bill').click();
    await vis(page, 'Add Item').click();
    const names = page.getByPlaceholder('Item name').locator('visible=true');
    await names.nth(0).fill('QA Cable');
    await page.getByPlaceholder('0.00', { exact: true }).locator('visible=true').nth(0).fill('250');
    await page.getByPlaceholder('1', { exact: true }).locator('visible=true').nth(0).fill('3');
    const small = page.getByPlaceholder('0', { exact: true }).locator('visible=true');
    await small.nth(0).fill('18');
    await small.nth(1).fill('10');
    await vis(page, 'Add Item').click();
    await names.nth(1).fill('QA Switch');
    await page.getByPlaceholder('0.00', { exact: true }).locator('visible=true').nth(1).fill('99.99');
    await page.getByPlaceholder('Enter transaction description').locator('visible=true').fill('QA Mobile bill');
    await page.getByPlaceholder('Enter vendor/supplier name').locator('visible=true').fill(vendor);
    const total = page.getByPlaceholder('Enter amount').locator('visible=true');
    await expect(total).toHaveValue(/909.99$/);
    await expect(total).toHaveAttribute('readonly', '');
    await vis(page, 'Save Transaction').click();
    await toast(page, 'Transaction created successfully.');
    await expect(vis(page, vendor, { exact: false })).toBeVisible({ timeout: 60_000 });
    const stored = await findTransaction(api, vendor);
    expect(Number(stored.amount)).toBeCloseTo(909.99, 2);
    expect(stored.status).toBe('pending');
    await expect(vis(page, '₹909.99', { exact: false })).toBeVisible();
  });

  test('TC-EXP-10-E03 upload an attachment from the transaction details', async ({ page, signIn, api }) => {
    test.skip(true, 'Expo web cannot upload: the screen appends the picked file as a plain {uri,name,type} object to FormData (works only on native), so the API answers 422; verify on a device');
    const txn = await createTransaction(api, { description: 'QA Electricity bill', vendor_name: unique('QA Power Co') });
    const file = path.join(os.tmpdir(), `qa-receipt-${Date.now()}.txt`);
    fs.writeFileSync(file, 'QA receipt');
    await signIn('admin');
    await open(page, `/expense/transactions/${txn.id}`, 'Attachments');
    await vis(page, 'Add').click();
    await page.getByPlaceholder('e.g. invoice, receipt, quote').locator('visible=true').fill('receipt');
    const [chooser] = await Promise.all([
      page.waitForEvent('filechooser'),
      vis(page, 'Tap to select file').click(),
    ]);
    await chooser.setFiles(file);
    await vis(page, 'Upload').click();
    await toast(page, 'Attachment uploaded successfully.');
    await expect(vis(page, path.basename(file), { exact: false })).toBeVisible();
    await expect(vis(page, 'receipt', { exact: false })).toBeVisible();
    fs.unlinkSync(file);
  });

  test('TC-EXP-12-E07 approve a pending transaction with a comment', async ({ page, signIn, api }) => {
    const vendor = unique('QA Mobile Approve');
    const txn = await createTransaction(api, { vendor_name: vendor, amount: '2250.00', description: 'QA mobile approval target' });
    await signIn('admin');
    await open(page, '/expense/approvals', 'Expense Approvals');
    await expect(vis(page, vendor, { exact: false })).toBeVisible({ timeout: 60_000 });
    const pending = async () => Number((await page.getByText(/^\d+$/).locator('visible=true').first().innerText()));
    const before = await pending();
    const card = page.locator('div').filter({ hasText: vendor }).filter({ has: page.getByText('Approve', { exact: true }) }).locator('visible=true').last();
    await card.getByText('Approve', { exact: true }).click();
    await expect(vis(page, 'Approve Transaction')).toBeVisible();
    await page.getByPlaceholder('Enter approve comment').locator('visible=true').fill('QA mobile approve');
    await page.getByText('Approve', { exact: true }).locator('visible=true').last().click();
    await expect(vis(page, 'Approve Transaction')).toBeHidden();
    await expect(vis(page, vendor, { exact: false })).toBeHidden();
    await expect.poll(pending).toBe(before - 1);
    const stored = await findTransaction(api, vendor);
    expect(stored.id).toBe(txn.id);
    expect(stored.status).toBe('approved');
    expect(stored.approval_comment).toBe('QA mobile approve');
  });
});
