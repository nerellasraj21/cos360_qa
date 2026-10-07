// Masters F04 Edit and delete a class, web. Baseline: qa_manual seeded classes Nursery to Class 5 in 2026-2027.
const { test, expect, unique, toast } = require('../../helpers/fixtures');

const ROUTE = '/masters/classesandsections';

function code() {
  return `Q${Math.random().toString(36).slice(2, 8).toUpperCase()}`;
}

async function seededYearId(api) {
  const res = await api('GET', '/masters/academic_years/?active_only=false&limit=1000');
  return res.data.items.find((y) => y.title === '2026-2027').id;
}

async function createClassViaApi(api, cleanup, name, sections = ['A', 'B', 'C']) {
  const body = { name, short_code: code(), academic_year_id: await seededYearId(api), sections: sections.map((s) => ({ name: s })) };
  const res = await api('POST', '/masters/class_sections/', { body });
  expect(res.status).toBe(201);
  cleanup(() => api('DELETE', `/masters/class_sections/${res.data.id}`));
  return res.data;
}

async function mapSubject(api, cleanup, cls, subjectName = 'Mathematics') {
  const subjects = await api('GET', '/masters/subjects/?limit=100');
  const subject = subjects.data.find((s) => s.name === subjectName && s.academic_year_id === cls.academic_year_id);
  const res = await api('POST', '/masters/class-subject-mappings/bulk', {
    body: { class_id: cls.id, academic_year_id: cls.academic_year_id, subjects: [{ subject_id: subject.id, order: 1 }] },
  });
  expect(res.status).toBe(201);
  cleanup(async () => {
    const list = await api('GET', `/masters/class-subject-mappings/?class_id=${cls.id}&active_only=false&limit=1000`);
    for (const m of list.data.items || []) await api('DELETE', `/masters/class-subject-mappings/${m.id}`);
  });
  return res.data;
}

function classRow(page, name) {
  return page.getByRole('row').filter({ has: page.getByRole('cell', { name, exact: true }) });
}

async function openFiltered(page, name) {
  await page.goto(ROUTE);
  await expect(page.getByPlaceholder('Search classes...')).toBeVisible({ timeout: 30_000 });
  await page.getByPlaceholder('Search classes...').fill(name);
  await expect(classRow(page, name)).toBeVisible();
  return classRow(page, name);
}

test.describe('Masters F04 edit and delete a class (web)', () => {
  test('TC-MST-04-E01 rename a class', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA C9');
    await createClassViaApi(api, cleanup, name);
    await signIn('admin');
    const row = await openFiltered(page, name);
    await row.getByRole('button', { name: 'Edit Class' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('heading', { name: 'Edit Class' })).toBeVisible();
    await expect(dialog.getByLabel('Class Name')).toHaveValue(name);
    await dialog.getByLabel('Class Name').fill(`${name} R`);
    await dialog.getByRole('button', { name: 'Update Class' }).click();
    await toast(page, 'Class and sections updated successfully!');
    await page.getByPlaceholder('Search classes...').fill(`${name} R`);
    await expect(classRow(page, `${name} R`)).toContainText('3 sections');
  });

  test('TC-MST-04-E02 class code is required on edit', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA C9');
    await createClassViaApi(api, cleanup, name);
    await signIn('admin');
    const row = await openFiltered(page, name);
    await row.getByRole('button', { name: 'Edit Class' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Class Code').fill('');
    let put = false;
    page.on('request', (r) => { if (r.method() === 'PUT' && r.url().includes('/class_sections/')) put = true; });
    await dialog.getByRole('button', { name: 'Update Class' }).click();
    await page.waitForTimeout(1000);
    expect(put).toBe(false);
    await expect(dialog).toBeVisible();
    expect(await dialog.getByLabel('Class Code').evaluate((el) => el.validity.valueMissing)).toBe(true);
  });

  test('TC-MST-04-E03 deactivated class leaves the timetable class list', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA C9');
    const cls = await createClassViaApi(api, cleanup, name);
    cleanup(() => api('PUT', `/masters/class_sections/${cls.id}`, { body: { is_active: true, academic_year_id: cls.academic_year_id } }));
    await signIn('admin');
    const row = await openFiltered(page, name);
    await row.getByRole('button', { name: 'Edit Class' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Class is active').uncheck();
    await dialog.getByRole('button', { name: 'Update Class' }).click();
    await toast(page, 'Class and sections updated successfully!');
    await expect(classRow(page, name)).toContainText('Inactive');
    await page.goto('/TimeTable');
    await page.getByText('Select Class', { exact: true }).click({ force: true });
    await expect(page.getByRole('option', { name: 'Class 1', exact: true })).toBeVisible();
    await expect(page.getByRole('option', { name, exact: true })).toHaveCount(0);
  });

  test('TC-MST-04-E04 delete an unused class', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA C9');
    const cls = await createClassViaApi(api, cleanup, name);
    await signIn('admin');
    const row = await openFiltered(page, name);
    await row.getByRole('button', { name: 'Delete Class' }).click();
    const dialog = page.getByRole('alertdialog');
    await expect(dialog.getByText('Confirm Deletion')).toBeVisible();
    await expect(dialog).toContainText(`Are you sure you want to delete class "${name}"?`);
    await expect(dialog).toContainText('This class has 3 sections. Deletion will fail if');
    await dialog.getByRole('button', { name: 'Delete' }).click();
    await toast(page, 'Class and sections deleted successfully!');
    await expect(classRow(page, name)).toHaveCount(0);
    expect((await api('GET', `/masters/class_sections/by_class_id/${cls.id}`)).status).toBe(404);
  });

  test('TC-MST-04-E05 delete is refused while a subject mapping exists', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA C9');
    const cls = await createClassViaApi(api, cleanup, name);
    await mapSubject(api, cleanup, cls);
    await signIn('admin');
    const row = await openFiltered(page, name);
    await row.getByRole('button', { name: 'Delete Class' }).click();
    await page.getByRole('alertdialog').getByRole('button', { name: 'Delete' }).click();
    await toast(page, `Failed to delete class and sections: Cannot delete class '${name}' because it is being used by`);
    await expect(page.getByText(/subject mapping\(s\)/).first()).toBeVisible();
    await expect(classRow(page, name)).toBeVisible();
    expect((await api('GET', `/masters/class_sections/by_class_id/${cls.id}`)).status).toBe(200);
  });

  test('TC-MST-04-E06 cancel keeps the class', async ({ page, signIn }) => {
    await signIn('admin');
    const row = await openFiltered(page, 'Class 1');
    let deleted = false;
    page.on('request', (r) => { if (r.method() === 'DELETE') deleted = true; });
    await row.getByRole('button', { name: 'Delete Class' }).click();
    const dialog = page.getByRole('alertdialog');
    await expect(dialog).toContainText('Are you sure you want to delete class "Class 1"?');
    await dialog.getByRole('button', { name: 'Cancel' }).click();
    await expect(dialog).toBeHidden();
    await expect(classRow(page, 'Class 1')).toBeVisible();
    expect(deleted).toBe(false);
  });

  test('TC-MST-04-E10 teacher has no class or section actions', async ({ page, signIn }) => {
    await signIn('teacher');
    const row = await openFiltered(page, 'Class 1');
    await row.getByRole('button').first().click();
    await expect(page.getByText('1-A', { exact: true })).toBeVisible();
    for (const name of ['Edit Class', 'Delete Class', 'Edit Section', 'Delete Section', 'Add Section']) {
      await expect(page.getByRole('button', { name })).toHaveCount(0);
    }
  });
});
