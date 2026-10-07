// Masters F05 Add, edit and delete sections, mobile (Expo web). Baseline: qa_manual seeded classes.
const { test, expect, unique, toast } = require('../../helpers/fixtures');

const ROUTE = '/masters/classesandsections';

async function activeYearId(api) {
  const res = await api('GET', '/masters/academic_years/?active_only=false&limit=1000');
  const rows = Array.isArray(res.data) ? res.data : res.data.items || [];
  return rows.find((y) => y.title === '2026-2027').id;
}

async function createClass(api, cleanup, sections) {
  const name = unique('QA C8');
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

async function open(page, name) {
  await page.goto(ROUTE, { timeout: 180_000 });
  await expect(page.getByText('Classes & Sections').first()).toBeVisible({ timeout: 60_000 });
  await page.getByPlaceholder('Search classes or sections...').fill(name);
  await expect(page.getByText(name, { exact: true })).toBeVisible({ timeout: 60_000 });
}

async function expand(page) {
  await page.getByLabel('Delete', { exact: true }).first().locator('xpath=following-sibling::*[1]').click();
}

function sectionRow(page, name) {
  return page.getByText(name, { exact: true }).locator('xpath=../..');
}

test.describe('Masters F05 sections (mobile)', () => {
  test('TC-MST-05-E09 edit a section name', async ({ page, signIn, api, cleanup }) => {
    const cls = await createClass(api, cleanup, ['A', 'B']);
    await signIn('admin');
    await open(page, cls.name);
    await expand(page);
    await sectionRow(page, 'A').getByLabel('Edit', { exact: true }).click();
    await expect(page.getByText('Edit Section')).toBeVisible();
    const input = page.getByPlaceholder('e.g., A, B, C');
    await expect(input).toHaveValue('A');
    await input.fill('A2');
    await page.getByText('Update Section', { exact: true }).click();
    await toast(page, 'Section updated successfully');
    await expect(page.getByText('A2', { exact: true })).toBeVisible();
    const names = (await sectionsOf(api, cls.id)).map((s) => s.name).sort();
    expect(names).toEqual(['A2', 'B']);
  });

  test('TC-MST-05-E10 delete an unreferenced section', async ({ page, signIn, api, cleanup }) => {
    const cls = await createClass(api, cleanup, ['A', 'B']);
    await signIn('admin');
    await open(page, cls.name);
    await expand(page);
    await sectionRow(page, 'B').getByLabel('Delete', { exact: true }).click();
    await expect(page.getByText('Delete section "B"? This action cannot be undone.')).toBeVisible();
    await page.getByText('Delete', { exact: true }).last().click();
    await toast(page, 'Section deleted successfully');
    await expect(page.getByText('B', { exact: true })).toHaveCount(0);
    const names = (await sectionsOf(api, cls.id)).map((s) => s.name);
    expect(names).toEqual(['A']);
  });

  test('TC-MST-05-E11 add a section from the class card', async () => {
    test.skip(true, 'blocked: mobile add-section sends a single object and the API returns 422 "Create Failed" (Known gaps 6)');
  });

  test('TC-MST-05-E12 section name is required on add', async ({ page, signIn, api, cleanup }) => {
    const cls = await createClass(api, cleanup, ['A']);
    await signIn('admin');
    await open(page, cls.name);
    await page.getByLabel('Add', { exact: true }).nth(1).click();
    await expect(page.getByText('Add New Section')).toBeVisible();
    await page.getByText('Add Section', { exact: true }).click();
    await toast(page, 'Section name is required');
    await expect(page.getByText('Add New Section')).toBeVisible();
    expect((await sectionsOf(api, cls.id)).length).toBe(1);
  });
});
