// Masters F08 Subjects, mobile (Expo web). Baseline: qa_manual seeded 10 subjects in 2026-2027.
// Subjects can only be deactivated, so QA subjects created here stay as inactive rows after cleanup.
const { test, expect, unique, toast } = require('../../helpers/fixtures');

const ROUTE = '/masters/subjects';
const BASE = '/masters/subjects';
const CATS = '/masters/subject_categories/categories';

function code() {
  return `Q${Date.now().toString(36).slice(-4)}${Math.floor(Math.random() * 90 + 10)}`.toUpperCase();
}

async function activeYearId(api) {
  const res = await api('GET', '/masters/academic_years/?active_only=false&limit=1000');
  const rows = Array.isArray(res.data) ? res.data : res.data.items || [];
  return rows.find((y) => y.title === '2026-2027').id;
}

async function findSubject(api, name) {
  const res = await api('GET', `${BASE}/?active_only=false`);
  return res.data.find((s) => s.name === name);
}

async function findCategory(api, name) {
  const res = await api('GET', `${CATS}/dropdown`);
  return res.data.find((c) => c.name === name);
}

async function open(page) {
  await page.goto(ROUTE, { timeout: 180_000 });
  await expect(page.getByText('Mathematics', { exact: true })).toBeVisible({ timeout: 60_000 });
}

async function chooseCategory(page, name) {
  await page.getByText('Select Category', { exact: true }).click();
  await page.getByText(name, { exact: true }).last().click();
}

test.describe('Masters F08 subjects (mobile)', () => {
  test('TC-MST-08-E10 create a subject', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Chem');
    const shortCode = code();
    cleanup(async () => {
      const s = await findSubject(api, name);
      if (s) await api('DELETE', `${BASE}/${s.id}`);
    });
    await signIn('admin');
    await open(page);
    await page.getByText('Add Subject', { exact: true }).first().click();
    await expect(page.getByText('Add New Subject')).toBeVisible();
    await page.getByPlaceholder('Enter subject name').fill(name);
    await chooseCategory(page, 'Core Academics');
    await page.getByPlaceholder('Enter short code (optional)').fill(shortCode);
    await page.getByText('Add Subject', { exact: true }).last().click();
    await toast(page, 'Subject Created');
    await expect(page.getByText('Add New Subject')).toBeHidden();
    await page.getByPlaceholder('Search subjects...').fill(name);
    await expect(page.getByText(name, { exact: true })).toBeVisible();
    await expect(page.getByText(`Code: ${shortCode}`)).toBeVisible();
    await expect(page.getByText('Category: Core Academics')).toBeVisible();
    const created = await findSubject(api, name);
    expect(created.category.name).toBe('Core Academics');
  });

  test('TC-MST-08-E11 subject name is required', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await page.getByText('Add Subject', { exact: true }).first().click();
    await expect(page.getByPlaceholder('Enter subject name')).toBeVisible();
    await page.getByText('Add Subject', { exact: true }).last().click();
    await toast(page, 'Subject name is required');
    await expect(page.getByText('Add New Subject')).toBeVisible();
  });

  test('TC-MST-08-E12 missing category is rejected by the API', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA NoCat M');
    cleanup(async () => {
      const s = await findSubject(api, name);
      if (s) await api('DELETE', `${BASE}/${s.id}`);
    });
    await signIn('admin');
    await open(page);
    await page.getByText('Add Subject', { exact: true }).first().click();
    await page.getByPlaceholder('Enter subject name').fill(name);
    await page.getByText('Add Subject', { exact: true }).last().click();
    await toast(page, 'Create Failed');
    expect(await findSubject(api, name)).toBeFalsy();
  });

  test('TC-MST-08-E13 create a category from the subject form', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Arts');
    cleanup(async () => {
      const c = await findCategory(api, name);
      if (c) await api('DELETE', `${CATS}/${c.id}`);
    });
    await signIn('admin');
    await open(page);
    await page.getByText('Add Subject', { exact: true }).first().click();
    await expect(page.getByText('Add New Subject')).toBeVisible();
    await page.getByLabel('Add', { exact: true }).last().click();
    await expect(page.getByText('Create Subject Category')).toBeVisible();
    await page.getByPlaceholder('Enter category name').fill(name);
    await page.getByText('Create', { exact: true }).click();
    await toast(page, 'Category Created');
    expect(await findCategory(api, name)).toBeTruthy();
    await page.getByText('Select Category', { exact: true }).click();
    await expect(page.getByText(name, { exact: true }).last()).toBeVisible();
  });

  test('TC-MST-08-E14 edit then delete a subject', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Chem');
    const cats = await api('GET', `${CATS}/dropdown`);
    const yearId = await activeYearId(api);
    const res = await api('POST', `${BASE}/`, {
      body: { name, short_code: code(), category_id: cats.data.find((c) => c.name === 'Core Academics').id, academic_year_id: yearId },
    });
    expect(res.status).toBe(200);
    cleanup(() => api('DELETE', `${BASE}/${res.data.id}`));
    const newCode = code();
    await signIn('admin');
    await open(page);
    await page.getByPlaceholder('Search subjects...').fill(name);
    await expect(page.getByText(name, { exact: true })).toBeVisible();
    await page.getByLabel('Edit', { exact: true }).click();
    const codeBox = page.getByPlaceholder('Enter short code (optional)');
    await expect(codeBox).toHaveValue(res.data.short_code);
    await codeBox.fill(newCode);
    await page.getByText('Update', { exact: true }).click();
    await toast(page, 'Subject Updated');
    await expect(page.getByText(`Code: ${newCode}`)).toBeVisible();
    await page.getByLabel('Delete', { exact: true }).click();
    await expect(page.getByText(`Are you sure you want to delete "${name}"?`)).toBeVisible();
    await page.getByText('Delete', { exact: true }).last().click();
    await toast(page, 'Subject Deleted');
    await expect(page.getByText('Inactive', { exact: true })).toBeVisible();
    expect((await api('GET', `${BASE}/${res.data.id}`)).data.is_active).toBe(false);
    await page.getByPlaceholder('Search subjects...').fill('');
    const yearCount = (await api('GET', `${BASE}/?active_only=false&academic_year_id=${yearId}`)).data.length;
    await expect(page.getByText(`${yearCount} subjects`, { exact: true })).toBeVisible();
  });

  test('TC-MST-08-E15 search and hide the category line', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await page.getByPlaceholder('Search subjects...').fill('Science');
    await expect(page.getByText('General Science', { exact: true })).toBeVisible();
    await expect(page.getByText('Computer Science', { exact: true })).toBeVisible();
    await expect(page.getByText('Mathematics', { exact: true })).toHaveCount(0);
    await expect(page.getByText(/^Category: /)).toHaveCount(2);
    await page.getByText('Filters', { exact: true }).first().click();
    await page.getByText('Category', { exact: true }).last().click();
    await expect(page.getByText(/^Category: /)).toHaveCount(0);
  });
});
