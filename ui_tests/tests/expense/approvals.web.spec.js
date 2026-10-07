// Expense F11-F12 approval queue and approve action, web. Own transactions only; seeded pending rows are never approved.
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { createTransaction, findTransaction } = require('./kit');

const ROUTE = '/expense/approvals';

test.describe.configure({ mode: 'serial' });

async function stat(page, label) {
  const p = page.getByRole('main').locator('p').filter({ hasText: new RegExp(`^${label}$`) }).first();
  const text = await p.locator('xpath=following-sibling::p[1]').innerText();
  return Number(text.replace(/[^0-9.]/g, ''));
}

function row(page, text) {
  return page.getByRole('row').filter({ hasText: text });
}

test.describe('Expense F11-F12 approvals (web)', () => {
  test('TC-EXP-11-E01 a transaction above 1000 appears in the approval queue', async ({ page, signIn, api, cleanup }) => {
    const vendor = unique('QA Gen Services');
    await signIn('admin');
    await page.goto(ROUTE);
    await expect(page.getByRole('heading', { name: 'Pending Approvals' })).toBeVisible();
    await expect(row(page, 'Broadband plan renewal for office')).toBeVisible();
    const pendingBefore = await stat(page, 'Pending Approvals');
    const attentionBefore = await stat(page, 'Requires Attention');
    await page.goto('/expense/transactions');
    await page.getByRole('button', { name: 'New Transaction' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('button', { name: 'Select expense type' }).click();
    await dialog.getByRole('button', { name: 'Electricity Bill', exact: true }).click();
    await dialog.getByPlaceholder('Enter vendor name').fill(vendor);
    await dialog.getByPlaceholder('Enter transaction description').fill('QA Generator repair');
    await dialog.getByRole('spinbutton').fill('1500');
    await dialog.getByRole('button', { name: 'Save Transaction' }).click();
    await toast(page, 'Transaction created successfully');
    await page.goto(ROUTE);
    await expect(row(page, vendor)).toBeVisible();
    expect(await stat(page, 'Pending Approvals')).toBe(pendingBefore + 1);
    expect(await stat(page, 'Requires Attention')).toBe(attentionBefore + 1);
    const stored = await findTransaction(api, vendor);
    cleanup(() => api('POST', `/expense/transactions/${stored.id}/approval`, { body: { action: 'reject', approval_comment: 'QA cleanup' } }));
    expect(stored.requires_approval).toBe(true);
    expect(stored.status).toBe('pending');
  });

  test('TC-EXP-12-E01 approve a pending transaction with a comment', async ({ page, signIn, api }) => {
    const vendor = unique('QA Approve Co');
    const txn = await createTransaction(api, { vendor_name: vendor, amount: '1499.00', description: 'QA approval target' });
    await signIn('admin');
    await page.goto(ROUTE);
    await expect(row(page, vendor)).toBeVisible();
    const pendingBefore = await stat(page, 'Pending Approvals');
    const amountBefore = await stat(page, 'Total Amount');
    await row(page, vendor).getByRole('button', { name: 'Approve' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText('Approve Transaction').first()).toBeVisible();
    await dialog.getByRole('textbox', { name: 'Comment *' }).fill('QA approved');
    await dialog.getByRole('button', { name: 'Approve Transaction' }).click();
    await toast(page, 'Transaction approved successfully');
    await expect(row(page, vendor)).toHaveCount(0);
    await expect.poll(() => stat(page, 'Pending Approvals')).toBe(pendingBefore - 1);
    expect(await stat(page, 'Total Amount')).toBeCloseTo(amountBefore - 1499, 2);
    const stored = await findTransaction(api, vendor);
    expect(stored.id).toBe(txn.id);
    expect(stored.status).toBe('approved');
    expect(stored.approved_by_role).toBe('Admin');
    expect(stored.approval_comment).toBe('QA approved');
  });
});
