// Fee F15 reports, F16 student and parent self-service, F17 hub (web, P1).
const { test, expect, unique } = require('../../helpers/fixtures');
const kit = require('../../helpers/feekit');
const { createFamily, injectWebSession, tempPassword, activate } = require('../../helpers/auth-users');
const { webSubmitLogin } = require('../../helpers/authkit');

const THREE_TERMS = ['2026-06-15', '2026-10-15', '2027-01-15'];

async function mapChild(cleanup, family, child, typeId, total) {
  const student = { studentId: child.studentId, admissionNumber: child.admissionNumber, classId: family.klass.classId, sectionId: family.klass.sectionId };
  cleanup(() => kit.dropStudentMappings(child.studentId));
  await kit.createStudentMapping(() => {}, student, typeId, total);
}

test.describe('Fee F15 reports (web)', () => {
  test('TC-FEE-15-E01 collection summary report opens with no filter', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/fee/reports');
    await expect(page.getByRole('heading', { name: 'Fee Reports & Export' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Collection Summary' })).toHaveAttribute('aria-selected', 'true');
    for (const metric of ['Total Collected', 'Total Due', 'Collection %', 'Payment Methods']) {
      await expect(page.getByRole('cell', { name: metric, exact: true })).toBeVisible();
    }
    await expect(page.getByRole('columnheader', { name: 'Metric', exact: true })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: 'Value', exact: true })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: 'Transaction #', exact: true })).toBeVisible();
    await expect(page.getByText('Select at least one filter to generate a report')).toBeVisible();
  });

  test('TC-FEE-15-E05 export the report as Excel for a class', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/fee/reports');
    await expect(page.getByRole('button', { name: 'Export' })).toBeDisabled();
    await page.getByRole('combobox', { name: 'All Classes' }).click();
    await page.getByRole('option', { name: 'Class 1', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Excel' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Export' })).toBeEnabled();
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Export' }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/\.xlsx$/);
    await expect(page.getByText('Report exported successfully').first()).toBeVisible({ timeout: 15_000 });
  });
});

test.describe('Fee F16 self-service (web)', () => {
  test('TC-FEE-16-E02 student sees My Fee Summary', async ({ page, api, cleanup }) => {
    // doc: uses a throwaway student (login = admission number) instead of Karthik Reddy
    test.skip(!(await kit.roleHasGrant('Student', 'fee_transactions', 'read_own')), 'blocked: qa_manual Student role has no fee_transactions:read_own grant (page shows "Permission denied: Student cannot read_own fee_transactions"); the doc assumes the default seed grants');
    const cat = await kit.createCategory(cleanup, unique('QA Cat'));
    const term = await kit.sharedTerm('QA Shared Three Terms', THREE_TERMS);
    const type = await kit.createType(cleanup, unique('QA Tuition'), cat.id, term.id);
    const family = await createFamily(api, cleanup, ['Alpha']);
    const child = family.children[0];
    await mapChild(cleanup, family, child, type.id, 9000);
    const password = `QA Pass ${kit.tag().slice(-6)}`;
    await activate(child.admissionNumber, tempPassword('TEMP_STUDENT_PASSWORD'), password);
    await webSubmitLogin(page, child.admissionNumber, password);
    await page.waitForURL((u) => !u.pathname.includes('login'), { timeout: 30_000 });
    await page.goto('/fee/my-fees');
    await expect(page.getByText('My Fee Summary')).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(`Admission #: ${child.admissionNumber}`)).toBeVisible();
    for (const header of ['S.No.', 'Fee Type', 'Fee Term', 'Due', 'Paid', 'Outstanding']) {
      await expect(page.getByRole('columnheader', { name: header, exact: true })).toBeVisible();
    }
    await expect(page.getByRole('row').filter({ hasText: type.type_name })).toContainText('9,000');
    await expect(page.getByText('Total Outstanding')).toBeVisible();
  });

  test('TC-FEE-16-E06 parent switches child on the fee summary', async ({ page, api, cleanup }) => {
    // doc: uses a throwaway parent with two children (4500 and 9000) instead of the seeded Raju family
    test.skip(!(await kit.roleHasGrant('Parent', 'fee_collection', 'read_related')), 'blocked: qa_manual Parent role has no fee_collection:read_related grant (page shows "Permission denied: Parent cannot read fee_collection"); the doc assumes the default seed grants');
    const cat = await kit.createCategory(cleanup, unique('QA Cat'));
    const term = await kit.sharedTerm('QA Shared Three Terms', THREE_TERMS);
    const type = await kit.createType(cleanup, unique('QA Tuition'), cat.id, term.id);
    const family = await createFamily(api, cleanup, ['Alpha', 'Bravo']);
    await mapChild(cleanup, family, family.children[0], type.id, 4500);
    await mapChild(cleanup, family, family.children[1], type.id, 9000);
    await injectWebSession(page, family.login);
    await page.goto('/fee/collection');
    await expect(page.getByText("My Child's Fee Summary")).toBeVisible({ timeout: 20_000 });
    const selector = page.getByText('Select Child').locator('xpath=..').getByRole('button');
    const amounts = { [family.children[0].name]: '4,500.00', [family.children[1].name]: '9,000.00' };
    const current = (await selector.innerText()).trim();
    const other = family.children.map((c) => c.name).find((n) => n !== current);
    await expect(page.getByRole('row').filter({ hasText: type.type_name }).first()).toContainText(amounts[current]);
    await selector.click();
    await page.getByRole('button', { name: other, exact: true }).click();
    await expect(page.getByRole('row').filter({ hasText: type.type_name }).first()).toContainText(amounts[other]);
  });
});

test.describe('Fee F17 hub (web)', () => {
  test('TC-FEE-17-E01 fee dashboard cards', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/fee');
    await expect(page.getByRole('heading', { name: 'Fee Management Dashboard' })).toBeVisible();
    const cards = ['Fee Categories', 'Fee Types', 'Fee Terms', 'Fee Mappings', 'Fee Term Amounts', 'Fee Collection', 'Fee Receipts', 'Fee Refunds'];
    for (const card of cards) {
      await expect(page.getByRole('main').getByText(card, { exact: true }).first()).toBeVisible();
    }
    await expect(page.getByRole('main').getByRole('button', { name: 'Manage' })).toHaveCount(8);
  });
});
