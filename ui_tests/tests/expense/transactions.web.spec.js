// Expense F06-F09 transactions (create, view, edit, actions), web. Transactions cannot be deleted through the API,
// so every QA transaction stays behind with a "QA " vendor name; assertions only concern the rows created here.
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { createTransaction, findTransaction } = require('./kit');

const ROUTE = '/expense/transactions';

function row(page, text) {
  return page.getByRole('row').filter({ hasText: text });
}

test.describe('Expense F06-F09 transactions (web)', () => {
  test('TC-EXP-06-E01 create a transaction without approval', async ({ page, signIn, api }) => {
    const vendor = unique('QA Power Co');
    await signIn('admin');
    await page.goto(ROUTE);
    await page.getByRole('button', { name: 'New Transaction' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('button', { name: 'Select expense type' }).click();
    await dialog.getByRole('button', { name: 'Electricity Bill', exact: true }).click();
    await dialog.getByPlaceholder('Enter vendor name').fill(vendor);
    await expect(dialog.getByRole('button', { name: 'Cash' })).toBeVisible();
    await dialog.getByPlaceholder('Enter transaction description').fill('QA Electricity bill');
    await dialog.getByRole('spinbutton').fill('500');
    await dialog.getByRole('button', { name: 'Save Transaction' }).click();
    await toast(page, 'Transaction created successfully');
    await expect(row(page, vendor)).toBeVisible();
    await expect(row(page, vendor)).toContainText('Pending');
    await expect(row(page, vendor)).toContainText('₹500');
    await page.getByRole('tab', { name: /^Pending/ }).click();
    await expect(row(page, vendor)).toBeVisible();
    const stored = await findTransaction(api, vendor);
    expect(stored.status).toBe('pending');
    expect(stored.requires_approval).toBe(false);
    expect(Number(stored.amount)).toBe(500);
  });

  test('TC-EXP-07-E04 view the seeded Balaji Book Depot transaction', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto(ROUTE);
    await row(page, 'Balaji Book Depot').getByRole('button', { name: 'View' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText('Transaction Details').first()).toBeVisible();
    await expect(dialog).toContainText('Pending');
    await expect(dialog).toContainText('Balaji Book Depot');
    await expect(dialog).toContainText('Stationery');
    await expect(dialog).toContainText('Cash');
    await expect(dialog).toContainText('₹850');
    await expect(dialog).toContainText('Chart paper and markers for classrooms');
    await expect(dialog).toContainText('9/11/2026');
  });

  test('TC-EXP-08-E01 edit the description of a pending transaction', async ({ page, signIn, api }) => {
    const vendor = unique('QA Power Co');
    const txn = await createTransaction(api, { vendor_name: vendor, description: 'QA Electricity bill' });
    await signIn('admin');
    await page.goto(ROUTE);
    await row(page, vendor).getByRole('button', { name: 'Edit' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText('Edit Transaction').first()).toBeVisible();
    const description = dialog.getByPlaceholder('Enter transaction description');
    await expect(description).toHaveValue('QA Electricity bill');
    await description.fill('QA Electricity bill September');
    await dialog.getByRole('button', { name: 'Save Transaction' }).click();
    await toast(page, 'Transaction updated successfully');
    await expect(row(page, vendor)).toContainText('Pending');
    await row(page, vendor).getByRole('button', { name: 'View' }).click();
    await expect(page.getByRole('dialog')).toContainText('QA Electricity bill September');
    const stored = await findTransaction(api, vendor);
    expect(stored.id).toBe(txn.id);
    expect(stored.description).toBe('QA Electricity bill September');
    expect(stored.status).toBe('pending');
  });

  test('TC-EXP-09-E03 pending row offers View, Edit and Approve or reject but no Delete', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto(ROUTE);
    const seeded = row(page, 'Balaji Book Depot');
    await expect(seeded.getByRole('button', { name: 'View' })).toBeVisible();
    await expect(seeded.getByRole('button', { name: 'Edit' })).toBeVisible();
    await expect(seeded.getByRole('button', { name: 'Approve or reject' })).toBeVisible();
    await expect(seeded.getByRole('button', { name: 'Delete' })).toHaveCount(0);
  });
});
