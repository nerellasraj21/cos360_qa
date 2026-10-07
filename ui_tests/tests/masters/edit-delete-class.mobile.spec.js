// Masters F04 Edit and delete a class, mobile (Expo web). Baseline: qa_manual seeded classes Nursery to Class 5 in 2026-2027.
const { test, expect, unique, toast } = require('../../helpers/fixtures');

const ROUTE = '/masters/classesandsections';

async function seededYearId(api) {
  const res = await api('GET', '/masters/academic_years/?active_only=false&limit=1000');
  return res.data.items.find((y) => y.title === '2026-2027').id;
}

async function createClassViaApi(api, cleanup, name, sections = ['A', 'B']) {
  const body = {
    name,
    short_code: `Q${Math.random().toString(36).slice(2, 8).toUpperCase()}`,
    academic_year_id: await seededYearId(api),
    sections: sections.map((s) => ({ name: s })),
  };
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
}

async function openFiltered(page, name) {
  await page.goto(ROUTE, { timeout: 180_000 });
  await expect(page.getByText('Class 1', { exact: true })).toBeVisible({ timeout: 60_000 });
  await page.getByPlaceholder('Search classes or sections...').fill(name);
  await expect(page.getByText(name, { exact: true })).toBeVisible();
  await expect(page.getByText('1 class', { exact: true })).toBeVisible();
}

test.describe('Masters F04 edit and delete a class (mobile)', () => {
  test('TC-MST-04-E07 rename a class', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA C8');
    const cls = await createClassViaApi(api, cleanup, name);
    await signIn('admin');
    await openFiltered(page, name);
    await page.getByLabel('Edit', { exact: true }).first().click();
    await expect(page.getByText('Edit Class', { exact: true })).toBeVisible();
    const input = page.getByPlaceholder('e.g., Class 1');
    await expect(input).toHaveValue(name);
    await input.fill(`${name} R`);
    await page.getByText('Update Class', { exact: true }).click();
    await toast(page, 'Class updated successfully');
    await page.getByPlaceholder('Search classes or sections...').fill(`${name} R`);
    await expect(page.getByText(`${name} R`, { exact: true })).toBeVisible();
    const after = await api('GET', `/masters/class_sections/by_class_id/${cls.id}`);
    expect(after.data.name).toBe(`${name} R`);
    expect(after.data.sections).toHaveLength(2);
  });

  test('TC-MST-04-E08 delete an unused class', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA C8');
    const cls = await createClassViaApi(api, cleanup, name);
    await signIn('admin');
    await openFiltered(page, name);
    await page.getByLabel('Delete', { exact: true }).first().click();
    await expect(page.getByText('Delete Class', { exact: true })).toBeVisible();
    await expect(page.getByText(`Delete "${name}"? This will also delete all associated sections. This action cannot be undone.`)).toBeVisible();
    await page.getByText('Delete', { exact: true }).last().click();
    await toast(page, 'Class deleted successfully');
    await expect(page.getByText(name, { exact: true })).toHaveCount(0);
    expect((await api('GET', `/masters/class_sections/by_class_id/${cls.id}`)).status).toBe(404);
  });

  test('TC-MST-04-E09 delete is refused while a subject mapping exists', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA C8');
    const cls = await createClassViaApi(api, cleanup, name);
    await mapSubject(api, cleanup, cls);
    await signIn('admin');
    await openFiltered(page, name);
    await page.getByLabel('Delete', { exact: true }).first().click();
    await page.getByText('Delete', { exact: true }).last().click();
    await toast(page, 'Delete Failed');
    await expect(page.getByText(/being used by/).first()).toBeVisible();
    await expect(page.getByText(name, { exact: true })).toBeVisible();
    expect((await api('GET', `/masters/class_sections/by_class_id/${cls.id}`)).status).toBe(200);
  });

  test('TC-MST-04-E11 teacher has no class or section actions', async ({ page, signIn }) => {
    await signIn('teacher');
    await page.goto(ROUTE, { timeout: 180_000 });
    await expect(page.getByText('Class 1', { exact: true })).toBeVisible({ timeout: 60_000 });
    await page.getByPlaceholder('Search classes or sections...').fill('1-A');
    await expect(page.getByText('1 class', { exact: true })).toBeVisible();
    await expect(page.getByLabel('Delete', { exact: true })).toHaveCount(0);
    await expect(page.getByLabel('Edit', { exact: true })).toHaveCount(0);
    await expect(page.getByLabel('Add', { exact: true })).toHaveCount(0);
    await page.getByText('Active', { exact: true }).first().locator('xpath=../following-sibling::*[1]').click();
    await expect(page.getByText('1-A', { exact: true })).toBeVisible();
    await expect(page.getByLabel('Delete', { exact: true })).toHaveCount(0);
    await expect(page.getByLabel('Edit', { exact: true })).toHaveCount(0);
  });
});
