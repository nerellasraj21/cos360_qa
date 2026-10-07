// Fee F11 receipts, F12 transactions, F13 refunds (web, P1).
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const kit = require('../../helpers/feekit');

const THREE_TERMS = ['2026-06-15', '2026-10-15', '2027-01-15'];

function today() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

async function ownFee(cleanup, total = 9000) {
  const cat = await kit.createCategory(cleanup, unique('QA Cat'));
  const term = await kit.sharedTerm('QA Shared Three Terms', THREE_TERMS);
  const type = await kit.createType(cleanup, unique('QA Tuition'), cat.id, term.id);
  const student = await kit.createStudent(cleanup);
  cleanup(() => kit.dropStudentMappings(student.studentId));
  await kit.createStudentMapping(() => {}, student, type.id, total);
  return { type, student };
}

async function pickReact(page, scope, index, text) {
  await scope.getByRole('combobox').nth(index).click();
  await page.keyboard.type(text);
  await page.getByRole('option').first().click();
}

test.describe('Fee F11 receipts (web)', () => {
  test('TC-FEE-11-E01 receipt details after choosing a receipt', async ({ page, signIn, cleanup }) => {
    // doc: "Prints: 0" is not shown; the Prints badge only appears once a receipt has been reprinted
    const { type, student } = await ownFee(cleanup);
    const paid = await kit.pay(student, [{ typeId: type.id, amount: 100 }]);
    expect(paid.status).toBe(200);
    const receiptNumber = paid.data.receipt_number;
    await signIn('admin');
    await page.goto('/fee/receipts');
    await page.getByRole('button', { name: 'Choose a receipt...' }).click();
    await page.getByRole('button', { name: new RegExp(`^${receiptNumber} - `) }).click();
    const heading = page.getByRole('heading', { name: 'Receipt Details' });
    await expect(heading).toBeVisible();
    const details = heading.locator('xpath=..');
    await expect(details.getByText('Original', { exact: true })).toBeVisible();
    await expect(details.getByText(/Prints:/)).toHaveCount(0);
    await expect(details.getByText(receiptNumber, { exact: true })).toBeVisible();
    await expect(details.getByText(student.name, { exact: true })).toBeVisible();
    await expect(details.getByText(`Admission: ${student.admissionNumber}`)).toBeVisible();
    await expect(details.getByText('2026-2027', { exact: true })).toBeVisible();
    await expect(details.getByText(`${student.className} - ${student.sectionName}`, { exact: true })).toBeVisible();
    await expect(details.getByText('Generated At')).toBeVisible();
  });

  test('TC-FEE-11-E07 download the receipt PDF', async ({ page, signIn, cleanup }) => {
    const { type, student } = await ownFee(cleanup);
    const paid = await kit.pay(student, [{ typeId: type.id, amount: 100 }]);
    expect(paid.status).toBe(200);
    const receiptNumber = paid.data.receipt_number;
    await signIn('admin');
    await page.goto('/fee/receipts');
    await page.getByRole('button', { name: 'Choose a receipt...' }).click();
    await page.getByRole('button', { name: new RegExp(`^${receiptNumber} - `) }).click();
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Download PDF' }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe(`${receiptNumber}.pdf`);
    await toast(page, 'Receipt PDF downloaded');
  });
});

test.describe('Fee F12 transactions (web)', () => {
  test('TC-FEE-12-E01 transactions list, newest first', async ({ page, signIn, cleanup }) => {
    const { type, student } = await ownFee(cleanup);
    const paid = await kit.pay(student, [{ typeId: type.id, amount: 100 }]);
    expect(paid.status).toBe(200);
    await signIn('admin');
    await page.goto('/fee/transactions');
    await expect(page.getByText('Fee Transactions', { exact: true }).first()).toBeVisible();
    for (const header of ['Transaction #', 'Student', 'Total Amount', 'Payment Method', 'Status', 'Date']) {
      await expect(page.getByRole('columnheader', { name: header, exact: true })).toBeVisible();
    }
    const mine = page.getByRole('row').filter({ hasText: paid.data.transaction_number });
    await expect(mine).toContainText(student.admissionNumber);
    await expect(mine).toContainText('100');
    await expect(mine).toContainText('CASH');
    await expect(mine).toContainText('Completed');
    const dates = await page.locator('tbody tr').evaluateAll((rows) => rows.map((r) => r.children[6] && r.children[6].textContent));
    const stamps = dates.filter(Boolean).map((t) => {
      const [m, d, y] = t.trim().split('/').map(Number);
      return new Date(y, m - 1, d).getTime();
    });
    expect(stamps.length).toBeGreaterThan(1);
    for (let i = 1; i < stamps.length; i++) expect(stamps[i]).toBeLessThanOrEqual(stamps[i - 1]);
  });

  test('TC-FEE-12-E05 mark a pending cheque completed', async ({ page, signIn, cleanup }) => {
    const { type, student } = await ownFee(cleanup);
    const paid = await kit.pay(student, [{ typeId: type.id, amount: 500 }], 'cheque', {
      cheque_number: 'QA480001', cheque_bank: 'QA Bank', cheque_date: today(),
    });
    expect(paid.status).toBe(200);
    await signIn('admin');
    await page.goto('/fee/transactions');
    const row = page.getByRole('row').filter({ hasText: paid.data.transaction_number });
    await expect(row).toContainText('Pending');
    await row.getByRole('button', { name: 'View' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('button', { name: 'Mark Completed' }).click();
    await toast(page, 'Transaction status updated successfully');
    await expect(row).toContainText('Completed');
    await row.getByRole('button', { name: 'View' }).click();
    await expect(page.getByRole('dialog')).toContainText('Completed');
    await expect(page.getByRole('dialog').getByRole('button', { name: 'Generate Receipt' })).toBeVisible();
  });
});

test.describe('Fee F13 refunds (web)', () => {
  test('TC-FEE-13-E01 create a refund request', async ({ page, signIn, cleanup }) => {
    // doc: uses a QA student and a QA completed transaction instead of Aarav Gupta so seeded refunds are untouched
    const { type, student } = await ownFee(cleanup);
    const paid = await kit.pay(student, [{ typeId: type.id, amount: 1000 }]);
    expect(paid.status).toBe(200);
    await signIn('admin');
    await page.goto('/fee/refunds');
    await page.getByRole('button', { name: 'Create Refund Request' }).click();
    const dialog = page.getByRole('dialog');
    await pickReact(page, dialog, 0, student.admissionNumber);
    await dialog.getByRole('combobox').nth(1).click();
    await page.keyboard.type(paid.data.transaction_number);
    await page.getByRole('option').first().click();
    await dialog.getByRole('spinbutton', { name: 'Refund Amount' }).fill('200');
    await dialog.getByRole('button', { name: 'Select refund reason' }).click();
    await page.getByRole('button', { name: 'Excess Payment' }).click();
    await dialog.getByRole('textbox', { name: 'Detailed Reason' }).fill('QA refund');
    await dialog.getByRole('button', { name: 'Create Refund' }).click();
    await toast(page, 'Refund created successfully');
    const row = page.getByRole('row').filter({ hasText: student.admissionNumber });
    await expect(row).toContainText('Pending');
    await expect(row).toContainText('200');
  });

  test('TC-FEE-13-E03 approve a pending refund', async ({ page, signIn, cleanup }) => {
    const { type, student } = await ownFee(cleanup);
    const paid = await kit.pay(student, [{ typeId: type.id, amount: 1000 }]);
    expect(paid.status).toBe(200);
    await kit.createRefund(paid.data.transaction_id, 200);
    await signIn('admin');
    await page.goto('/fee/refunds');
    const row = page.getByRole('row').filter({ hasText: student.admissionNumber });
    await expect(row).toContainText('Pending');
    await row.getByRole('button', { name: 'Approve/Reject' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('button', { name: 'Approve', exact: true })).toBeVisible();
    await dialog.getByRole('button', { name: 'Submit' }).click();
    await expect(row).toContainText('Approved');
    await expect(row.getByRole('button', { name: 'Process' })).toBeVisible();
  });

  test('TC-FEE-13-E06 process approved refunds with and without a reference', async ({ page, signIn, cleanup }) => {
    const { type, student } = await ownFee(cleanup);
    const paid = await kit.pay(student, [{ typeId: type.id, amount: 1000 }]);
    expect(paid.status).toBe(200);
    const first = await kit.createRefund(paid.data.transaction_id, 100, 'approve');
    const second = await kit.createRefund(paid.data.transaction_id, 150, 'approve');
    await signIn('admin');
    await page.goto('/fee/refunds');
    const rowFirst = page.getByRole('row').filter({ hasText: first.refund_number });
    const rowSecond = page.getByRole('row').filter({ hasText: second.refund_number });
    await rowFirst.getByRole('button', { name: 'Process' }).click();
    let dialog = page.getByRole('dialog');
    await dialog.getByRole('textbox', { name: 'Reference Number (Optional)' }).fill('QA-REF-1');
    await dialog.getByRole('button', { name: 'Process Refund' }).click();
    await toast(page, 'Refund processed successfully');
    await expect(rowFirst).toContainText('Processed');
    await rowSecond.getByRole('button', { name: 'Process' }).click();
    dialog = page.getByRole('dialog');
    await dialog.getByRole('button', { name: 'Process Refund' }).click();
    await expect(rowSecond).toContainText('Processed');
    const methods = await kit.admin('GET', `/fee/refunds/?student_id=${student.studentId}`);
    const byId = Object.fromEntries((methods.data || []).map((r) => [r.id, r.refund_method]));
    expect(byId[first.id]).toBe('bank_transfer');
    expect(byId[second.id]).toBe('cash');
  });
});
