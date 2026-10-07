// Fee F07 concessions, F08 old fees, F09 search and summary, F10 payment (web, P1).
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const kit = require('../../helpers/feekit');

const RS = '₹';

function today() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function money(text) {
  return Number(text.replace(/[^0-9.]/g, ''));
}

const THREE_TERMS = ['2026-06-15', '2026-10-15', '2027-01-15'];

async function ownFee(cleanup, total, dates, name = 'QA Tuition') {
  const cat = await kit.createCategory(cleanup, unique('QA Cat'));
  const term = await kit.sharedTerm('QA Shared Three Terms', dates);
  const type = await kit.createType(cleanup, unique(name), cat.id, term.id);
  const student = await kit.createStudent(cleanup);
  cleanup(() => kit.dropStudentMappings(student.studentId));
  await kit.createStudentMapping(() => {}, student, type.id, total);
  return { cat, term, type, student };
}

async function openStudent(page, query, name) {
  await page.goto('/fee/collection');
  await page.getByPlaceholder('Search by name, admission no, mobile, city...').fill(query);
  await page.keyboard.press('Enter');
  const row = page.getByRole('row').filter({ hasText: name });
  for (let i = 0; i < 8; i++) {
    await page.getByRole('row').nth(1).waitFor();
    if (await row.count()) break;
    await page.getByRole('button', { name: 'Next' }).click();
  }
  await row.click();
}

async function selectUpTo(page, termName, label) {
  await page.getByRole('button', { name: 'Select installment...' }).click();
  await page.getByRole('button', { name: `${termName} (${label})` }).click();
}

test.describe('Fee F07 concessions (web)', () => {
  test('TC-FEE-07-E01 save a concession and see the payable amount drop', async ({ page, signIn, cleanup }) => {
    test.fail(true, 'UI-FEE-03: after "Save All Concessions" the Fee Summary tab keeps the old Payable Amount 27,000.00 until the page is reloaded (summary query is not refreshed)');
    // doc: uses a QA student with Tuition 27,000 instead of Kavya Verma so no seeded student is changed
    const { type, student } = await ownFee(cleanup, 27000, THREE_TERMS);
    cleanup(async () => {
      const history = await kit.admin('GET', `/fee/concessions/history/${student.studentId}?academic_year_id=${await kit.yearId()}`);
      for (const c of history.data || []) await kit.admin('DELETE', `/fee/concessions/${c.id}`);
    });
    await signIn('admin');
    await page.goto(`/fee/collection/${student.studentId}`);
    await expect(page.getByRole('row').filter({ hasText: type.type_name }).first()).toContainText('27,000.00');
    await page.getByRole('tab', { name: 'Concessions' }).click();
    const row = page.getByRole('row').filter({ hasText: type.type_name });
    await row.getByRole('spinbutton').fill('2000');
    await row.getByPlaceholder('Reason...').fill('QA sibling discount');
    await row.getByRole('button', { name: 'Select' }).click();
    // the menu item is clipped (UI-FEE-02), so it is activated without a pointer click
    await page.getByRole('button', { name: 'Principal' }).dispatchEvent('click');
    await page.getByRole('button', { name: 'Save All Concessions' }).click();
    await toast(page, 'Concessions saved successfully');
    await page.getByRole('tab', { name: 'Fee Summary' }).click();
    const summary = page.getByRole('row').filter({ hasText: type.type_name }).first();
    await expect(summary).toContainText('25,000.00');
  });

  test('TC-FEE-07-E01 approved-by menu of the first row can be used with the mouse', async ({ page, signIn, cleanup }) => {
    test.fail(true, 'UI-FEE-02: Concessions tab: the "Approved By" menu of the first fee row opens upward and is clipped by the table container, so Owner and Principal cannot be clicked');
    const { type, student } = await ownFee(cleanup, 27000, THREE_TERMS);
    await signIn('admin');
    await page.goto(`/fee/collection/${student.studentId}`);
    await page.getByRole('tab', { name: 'Concessions' }).click();
    const row = page.getByRole('row').filter({ hasText: type.type_name });
    await row.getByRole('button', { name: 'Select' }).click();
    await page.getByRole('button', { name: 'Principal' }).click({ timeout: 5000 });
  });
});

test.describe('Fee F08 old fees (web)', () => {
  test('TC-FEE-08-E01 add a manual old fee entry', async () => {
    test.skip(true, 'blocked: K08 (manual entries are filtered out of the web Old Fees tab)');
  });
});

test.describe('Fee F09 search and summary (web)', () => {
  test('TC-FEE-09-E01 search a student and open the fee page', async ({ page, signIn }) => {
    await signIn('admin');
    await openStudent(page, '001', 'Karthik Reddy');
    await expect(page.getByText('Manage fee for Karthik Reddy')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Karthik Reddy' })).toBeVisible();
    await expect(page.getByText('001', { exact: true }).first()).toBeVisible();
    for (const tab of ['Fee Summary', 'Fee Payment', 'Concessions', 'Old Fees', 'Fee History']) {
      await expect(page.getByRole('tab', { name: tab })).toBeVisible();
    }
  });

  test('TC-FEE-09-E04 fee summary figures of a seeded student', async ({ page, signIn }) => {
    await signIn('admin');
    await openStudent(page, '20260002', 'Ananya Reddy');
    await expect(page.getByText(`As of ${today()}`)).toBeVisible();
    await expect(page.getByText('AY: 2026-2027')).toBeVisible();
    const tuition = page.getByRole('row').filter({ hasText: 'Tuition Fee' }).first();
    const cells = tuition.getByRole('cell');
    await expect(cells.nth(2)).toHaveText(`${RS}18,000.00`);
    await expect(cells.nth(3)).toHaveText(`${RS}16,000.00`);
    await expect(cells.nth(4)).toHaveText(`${RS}6,000.00`);
    await expect(cells.nth(5)).toHaveText(`${RS}10,000.00`);
    const rows = page.getByRole('table').first().locator('tbody tr');
    const count = await rows.count();
    const sums = [0, 0, 0, 0];
    for (let i = 0; i < count - 1; i++) {
      const cs = rows.nth(i).getByRole('cell');
      for (let c = 0; c < 4; c++) sums[c] += money(await cs.nth(c + 2).innerText());
    }
    const grand = rows.nth(count - 1).getByRole('cell');
    for (let c = 0; c < 4; c++) expect(money(await grand.nth(c + 1).innerText())).toBe(sums[c]);
  });
});

test.describe('Fee F10 payment (web)', () => {
  test('TC-FEE-10-E02 collect a cash payment up to an installment', async ({ page, signIn, cleanup }) => {
    const { term, type, student } = await ownFee(cleanup, 9000, THREE_TERMS);
    await signIn('admin');
    await page.goto(`/fee/collection/${student.studentId}`);
    await page.getByRole('tab', { name: 'Fee Payment' }).click();
    await selectUpTo(page, term.term_name, '15 Oct 2026');
    await expect(page.getByText('Fees Due Up To 15 Oct 2026')).toBeVisible();
    const row = page.getByRole('row').filter({ hasText: type.type_name });
    await expect(row).toContainText('6,000.00');
    await row.getByRole('spinbutton').fill('3000');
    await page.getByRole('switch', { name: 'Send SMS' }).click();
    await expect(page.getByRole('button', { name: 'Cash' })).toBeVisible();
    await page.getByRole('button', { name: 'Collect Payment' }).click();
    await page.getByRole('button', { name: 'Confirm' }).click();
    const dialog = page.getByRole('dialog', { name: 'Payment Recorded' });
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText(/Transaction #:\s*TXN\w+/);
    await expect(dialog).toContainText(/Receipt #:\s*REC-\d{4}-\d{4}/);
    await expect(dialog.getByRole('row').filter({ hasText: type.type_name })).toContainText('3,000.00');
    await dialog.getByRole('button', { name: 'Close' }).last().click();
    await page.getByRole('tab', { name: 'Fee Summary' }).click();
    const summary = page.getByRole('row').filter({ hasText: type.type_name }).first();
    await expect(summary.getByRole('cell').nth(4)).toHaveText(`${RS}3,000.00`);
  });

  test('TC-FEE-10-E05 cheque payment stays pending', async ({ page, signIn, cleanup }) => {
    const { term, type, student } = await ownFee(cleanup, 9000, THREE_TERMS, 'QA Activity');
    await signIn('admin');
    await page.goto(`/fee/collection/${student.studentId}`);
    await page.getByRole('tab', { name: 'Fee Payment' }).click();
    await selectUpTo(page, term.term_name, '15 Oct 2026');
    const row = page.getByRole('row').filter({ hasText: type.type_name });
    await row.getByRole('spinbutton').fill('500');
    await page.getByRole('switch', { name: 'Send SMS' }).click();
    await page.getByRole('button', { name: 'Cash' }).click();
    await page.getByRole('button', { name: 'Cheque' }).click();
    await page.getByRole('textbox', { name: 'Cheque Number' }).fill('QA480001');
    await page.getByRole('textbox', { name: 'Bank Name' }).fill('QA Bank');
    await page.getByLabel('Cheque Date').fill(today());
    await page.getByRole('button', { name: 'Collect Payment' }).click();
    await page.getByRole('button', { name: 'Confirm' }).click();
    const dialog = page.getByRole('dialog', { name: 'Payment Recorded' });
    await expect(dialog).toContainText(/Cheque\/DD pending clearance\s+\S\s+receipt will be generated once the instrument clears\./);
    await expect(dialog.getByRole('button', { name: 'Download Receipt' })).toHaveCount(0);
    await expect(dialog.getByRole('button', { name: 'Send Receipt SMS' })).toHaveCount(0);
    await dialog.getByRole('button', { name: 'Close' }).last().click();
    await page.getByRole('tab', { name: 'Fee Summary' }).click();
    const summary = page.getByRole('row').filter({ hasText: type.type_name }).first();
    await expect(summary.getByRole('cell').nth(4)).toHaveText(`${RS}0.00`);
  });
});
