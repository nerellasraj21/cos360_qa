// Fee F04 class mappings, F05 term amounts, F06 student mappings (web, P1).
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const kit = require('../../helpers/feekit');

async function pickCombo(page, scope, index, text) {
  await scope.getByRole('combobox').nth(index).click();
  await page.keyboard.type(text);
  await page.getByRole('option', { name: text, exact: false }).first().click();
}

async function structure(cleanup, opts = {}) {
  const cat = await kit.createCategory(cleanup, unique('QA Cat'));
  const term = await kit.createTerm(cleanup, unique('QA Term'), opts.dates);
  const type = await kit.createType(cleanup, unique(opts.typeName || 'QA Lab'), cat.id, term.id);
  return { cat, term, type };
}

test.describe('Fee F04 class mappings (web)', () => {
  test('TC-FEE-04-E01 add an optional class mapping', async ({ page, signIn, cleanup }) => {
    const { type } = await structure(cleanup);
    const classId = await kit.classIdByName('Class 5');
    cleanup(() => kit.dropClassMappings(type.id));
    await signIn('admin');
    await page.goto('/fee/mappings');
    await page.getByRole('tab', { name: 'Class Mappings' }).click();
    await page.getByRole('button', { name: 'Add Mapping' }).click();
    const dialog = page.getByRole('dialog');
    await pickCombo(page, dialog, 0, type.type_name);
    await pickCombo(page, dialog, 1, 'Class 5');
    await dialog.getByRole('spinbutton').fill('12000');
    const mandatory = dialog.getByRole('checkbox', { name: /Mandatory fee/ });
    await expect(mandatory).not.toBeChecked();
    await dialog.getByRole('button', { name: 'Save' }).click();
    await toast(page, 'Fee class mapping created successfully');
    await page.getByPlaceholder('Search by class, fee type, or amount...').fill(type.type_name);
    const row = page.getByRole('row').filter({ hasText: type.type_name });
    await expect(row).toContainText('Class 5');
    await expect(row).toContainText('12,000');
    await expect(row).toContainText('Not Set');
    await expect(row).toContainText('Optional');
    expect(classId).toBeTruthy();
  });

  test('TC-FEE-04-E02 mandatory class mapping applies to students of the class', async ({ page, signIn, cleanup }) => {
    test.fail(true, 'UI-FEE-01: mandatory class mapping toast says "Fee applied to 0 of 1 students" although the fee was applied (the client bulk call duplicates the backend auto-apply and every student is rejected as DUPLICATE_MAPPING)');
    // doc: uses a QA class and student instead of Class 4 / Tanvi Raju so no seeded student is changed
    const { type } = await structure(cleanup, { typeName: 'QA Kit' });
    const student = await kit.createStudent(cleanup);
    cleanup(() => kit.dropStudentMappings(student.studentId));
    cleanup(() => kit.dropClassMappings(type.id));
    await signIn('admin');
    await page.goto('/fee/mappings');
    await page.getByRole('tab', { name: 'Class Mappings' }).click();
    await page.getByRole('button', { name: 'Add Mapping' }).click();
    const dialog = page.getByRole('dialog');
    await pickCombo(page, dialog, 0, type.type_name);
    await pickCombo(page, dialog, 1, student.className);
    await dialog.getByRole('spinbutton').fill('500');
    await dialog.getByRole('checkbox', { name: /Mandatory fee/ }).check();
    await dialog.getByRole('button', { name: 'Save' }).click();
    const applied = page.getByText(/Fee applied to \d+ of \d+ students in this class\./).first();
    await expect(applied).toBeVisible({ timeout: 20_000 });
    const message = await applied.innerText();
    await page.goto(`/fee/collection/${student.studentId}`);
    const row = page.getByRole('row').filter({ hasText: type.type_name }).first();
    await expect(row).toContainText('500.00');
    expect(message).toBe('Fee applied to 1 of 1 students in this class.');
  });
});

test.describe('Fee F05 term amounts (web)', () => {
  test('TC-FEE-05-E01 equal distribution of a class mapping over four dates', async ({ page, signIn, cleanup }) => {
    const { type } = await structure(cleanup);
    const classId = await kit.classIdByName('Class 5');
    cleanup(() => kit.dropClassMappings(type.id));
    await kit.createClassMapping(() => {}, classId, type.id, 12000, false);
    await signIn('admin');
    await page.goto('/fee/mappings');
    await page.getByRole('tab', { name: 'Class Mappings' }).click();
    await page.getByPlaceholder('Search by class, fee type, or amount...').fill(type.type_name);
    const row = page.getByRole('row').filter({ hasText: type.type_name });
    await row.getByRole('button', { name: 'Manage Term Amounts' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('button', { name: 'Equal Distribution' }).click();
    await dialog.getByRole('button', { name: 'Save Term Amounts' }).click();
    await toast(page, 'Term amounts created successfully');
    await expect(row).toContainText('Complete (4 terms)');
    await page.getByRole('row').filter({ hasText: type.type_name });
  });
});

test.describe('Fee F06 student mappings (web)', () => {
  test('TC-FEE-06-E01 create a student mapping', async ({ page, signIn, cleanup }) => {
    // doc: uses a QA student in a QA class instead of Kavya Verma so no seeded student is changed
    const { type } = await structure(cleanup);
    const student = await kit.createStudent(cleanup);
    cleanup(() => kit.dropStudentMappings(student.studentId));
    await signIn('admin');
    await page.goto('/fee/mappings');
    await page.getByRole('button', { name: 'Create Mapping' }).click();
    const dialog = page.getByRole('dialog');
    await pickCombo(page, dialog, 0, student.firstName);
    await pickCombo(page, dialog, 1, student.className);
    await pickCombo(page, dialog, 2, student.sectionName);
    await pickCombo(page, dialog, 3, type.type_name);
    await dialog.getByRole('spinbutton').fill('1200');
    await dialog.getByRole('button', { name: 'Create Mapping' }).click();
    await toast(page, 'Fee student mapping created successfully');
    await page.goto(`/fee/collection/${student.studentId}`);
    const row = page.getByRole('row').filter({ hasText: type.type_name }).first();
    await expect(row).toContainText('1,200.00');
  });
});
