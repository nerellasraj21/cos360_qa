// Masters F05 Add, edit and delete sections, web. Baseline: qa_manual seeded classes (Class 1 with 1-A, 1-B).
const { test, expect, unique, toast } = require('../../helpers/fixtures');

const ROUTE = '/masters/classesandsections';

async function activeYearId(api) {
  const res = await api('GET', '/masters/academic_years/?active_only=false&limit=1000');
  const rows = Array.isArray(res.data) ? res.data : res.data.items || [];
  return rows.find((y) => y.title === '2026-2027').id;
}

async function createClass(api, cleanup, sections) {
  const name = unique('QA C9');
  const res = await api('POST', '/masters/class_sections/', {
    body: {
      name,
      short_code: name.slice(-7).replace(/\s/g, ''),
      academic_year_id: await activeYearId(api),
      sections: sections.map((s) => ({ name: s })),
    },
  });
  expect(res.status).toBe(201);
  cleanup(() => api('DELETE', `/masters/class_sections/${res.data.id}`));
  return res.data;
}

async function sectionsOf(api, classId) {
  const res = await api('GET', '/masters/class_sections/section-list');
  return res.data.filter((s) => s.class_id === classId);
}

async function openClass(page, name) {
  await page.goto(ROUTE);
  await page.getByPlaceholder('Search classes...').fill(name);
  const row = page.getByRole('row').filter({ hasText: name });
  await expect(row).toBeVisible();
  return row;
}

test.describe('Masters F05 sections (web)', () => {
  test('TC-MST-05-E01 generate and add sections D and E', async ({ page, signIn, api, cleanup }) => {
    const cls = await createClass(api, cleanup, ['A', 'B', 'C']);
    await signIn('admin');
    const row = await openClass(page, cls.name);
    await row.getByRole('button', { name: 'Add Section' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText(`Add Sections to ${cls.name}`)).toBeVisible();
    await dialog.getByPlaceholder('A', { exact: true }).fill('D');
    await dialog.getByPlaceholder('D', { exact: true }).fill('E');
    await dialog.getByRole('button', { name: 'Generate' }).click();
    await toast(page, 'Generated 2 sections');
    await dialog.getByRole('button', { name: 'Add 2 Section(s)' }).click();
    await toast(page, '2 sections added successfully!');
    await expect(row).toContainText('5 sections');
    const names = (await sectionsOf(api, cls.id)).map((s) => s.name).sort();
    expect(names).toEqual(['A', 'B', 'C', 'D', 'E']);
  });

  test('TC-MST-05-E02 all duplicates are rejected client-side', async ({ page, signIn, api, cleanup }) => {
    const cls = await createClass(api, cleanup, ['A', 'B']);
    await signIn('admin');
    const row = await openClass(page, cls.name);
    await row.getByRole('button', { name: 'Add Section' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByPlaceholder('Section name (e.g., A)').fill('A');
    await dialog.getByRole('button', { name: 'Add row' }).first().click();
    await dialog.getByPlaceholder('Section name (e.g., B)').fill('b');
    let posted = false;
    page.on('request', (r) => { if (r.method() === 'POST' && r.url().includes('/sections')) posted = true; });
    await dialog.getByRole('button', { name: 'Add 2 Section(s)' }).click();
    await toast(page, 'Sections already exist: A, b');
    await page.waitForTimeout(1000);
    expect(posted).toBe(false);
    expect((await sectionsOf(api, cls.id)).length).toBe(2);
  });

  test('TC-MST-05-E03 partial duplicates are skipped', async ({ page, signIn, api, cleanup }) => {
    const cls = await createClass(api, cleanup, ['A']);
    await signIn('admin');
    const row = await openClass(page, cls.name);
    await row.getByRole('button', { name: 'Add Section' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByPlaceholder('Section name (e.g., A)').fill('A');
    await dialog.getByRole('button', { name: 'Add row' }).first().click();
    await dialog.getByPlaceholder('Section name (e.g., B)').fill('F');
    await dialog.getByRole('button', { name: 'Add 2 Section(s)' }).click();
    await toast(page, 'Skipped duplicate section: A');
    await toast(page, '1 section added successfully!');
    await expect(row).toContainText('2 sections');
    const names = (await sectionsOf(api, cls.id)).map((s) => s.name).sort();
    expect(names).toEqual(['A', 'F']);
  });

  test('TC-MST-05-E04 edit a section', async () => {
    test.skip(true, 'blocked: default Admin lacks sections:update, so the web Edit Section icon is hidden (Known gaps 4)');
  });

  test('TC-MST-05-E05 section name is required on edit', async () => {
    test.skip(true, 'blocked: default Admin lacks sections:update (Known gaps 4)');
  });

  test('TC-MST-05-E06 delete an unreferenced section', async () => {
    test.skip(true, 'blocked: default Admin lacks sections:delete, so the icon is hidden (Known gaps 4)');
  });

  test('TC-MST-05-E07 delete a referenced section fails', async () => {
    test.skip(true, 'blocked: default Admin lacks sections:delete (Known gaps 4)');
  });

  test('TC-MST-05-E08 admin sees no section edit or delete icons', async ({ page, signIn }) => {
    await signIn('admin');
    const row = await openClass(page, 'Class 1');
    await expect(row.getByRole('button', { name: 'Add Section' })).toBeVisible();
    await row.getByRole('button').first().click();
    await expect(page.getByText('Sections:')).toBeVisible();
    await expect(page.getByText('1-A', { exact: true })).toBeVisible();
    await expect(page.getByText('1-B', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Edit Section' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Delete Section' })).toHaveCount(0);
  });

  test('TC-MST-05-E13 teacher sees no section actions', async ({ page, signIn }) => {
    await signIn('teacher');
    const row = await openClass(page, 'Class 1');
    await row.getByRole('button').first().click();
    await expect(page.getByText('1-A', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Add Section' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Edit Section' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Delete Section' })).toHaveCount(0);
  });
});
