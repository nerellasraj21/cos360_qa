// Masters F08 Subjects, web. Baseline: qa_manual seeded 10 subjects in 2026-2027 (English: Languages, ENG).
// Subjects can only be deactivated, so QA subjects created here stay listed as inactive after cleanup.
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

async function categoryId(api, name) {
  const res = await api('GET', `${CATS}/dropdown`);
  return res.data.find((c) => c.name === name).id;
}

async function findSubject(api, name) {
  const res = await api('GET', `${BASE}/?active_only=false`);
  return res.data.find((s) => s.name === name);
}

async function createSubject(api, cleanup, name, shortCode = code()) {
  const res = await api('POST', `${BASE}/`, {
    body: { name, short_code: shortCode, category_id: await categoryId(api, 'Co-Curricular'), academic_year_id: await activeYearId(api) },
  });
  expect(res.status).toBe(200);
  cleanup(() => api('DELETE', `${BASE}/${res.data.id}`));
  return res.data;
}

function row(page, name) {
  return page.getByRole('row').filter({ has: page.getByRole('cell', { name, exact: true }) });
}

function pageSize(page) {
  return page.getByRole('combobox').filter({ has: page.getByRole('option', { name: '100', exact: true }) });
}

async function open(page, api) {
  if (api) {
    const id = await activeYearId(api);
    await page.addInitScript((yearId) => {
      window.localStorage.setItem('academic-year-storage', JSON.stringify({ state: { selectedAcademicYearId: yearId }, version: 0 }));
    }, id);
  }
  await page.goto(ROUTE);
  await expect(page.getByRole('columnheader', { name: 'Category', exact: true })).toBeVisible();
  await expect(page.locator('tbody tr').first()).toContainText(/Active|Inactive/);
}

async function search(page, name) {
  await pageSize(page).selectOption('100');
  await expect(page.getByText(/^1-\d+ of \d+$/)).toBeVisible();
  const box = page.getByPlaceholder('Search...');
  for (let i = 0; i < 20; i++) {
    await box.fill(name);
    const found = await row(page, name).first().waitFor({ timeout: 3000 }).then(() => true, () => false);
    if (found) break;
    await box.fill('');
    await page.getByRole('button', { name: 'Next' }).click();
  }
  await expect(row(page, name)).toBeVisible();
}

async function chooseCategory(scope, page, name) {
  await scope.getByRole('combobox', { name: 'Select Category' }).click();
  await page.getByRole('option', { name, exact: true }).click();
}

test.describe('Masters F08 subjects (web)', () => {
  test('TC-MST-08-E01 list shows the seeded subjects grouped by category', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    for (const header of ['S.No.', 'Name', 'Category', 'Short Code', 'Active', 'Actions']) {
      await expect(page.getByRole('columnheader', { name: header, exact: true })).toBeVisible();
    }
    const cats = [];
    for (const r of await page.locator('tbody tr').all()) {
      const t = await r.innerText();
      cats.push(['Co-Curricular', 'Core Academics', 'Languages'].find((c) => t.includes(c)) || '');
    }
    expect(cats).toEqual([...cats].sort((a, b) => a.localeCompare(b)));
    await search(page, 'English');
    await expect(row(page, 'English')).toContainText('Languages');
    await expect(row(page, 'English')).toContainText('ENG');
  });

  test('TC-MST-08-E02 create a subject', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Physics');
    const shortCode = code();
    await signIn('admin');
    await open(page, api);
    await page.getByRole('button', { name: 'Add Subject' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText('Add New Subject')).toBeVisible();
    await dialog.getByLabel('Subject Name').fill(name);
    await chooseCategory(dialog, page, 'Co-Curricular');
    await dialog.getByLabel('Short Code').fill(shortCode);
    await dialog.getByRole('button', { name: 'Add Subject' }).click();
    await toast(page, 'Subject created successfully!');
    const created = await findSubject(api, name);
    expect(created).toBeTruthy();
    cleanup(() => api('DELETE', `${BASE}/${created.id}`));
    expect(created.is_active).toBe(true);
    expect(created.short_code).toBe(shortCode);
    expect(created.category.name).toBe('Co-Curricular');
    await search(page, name);
    await expect(row(page, name)).toContainText('Active');
  });

  test('TC-MST-08-E03 create a category inline from the subject form', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Electives');
    cleanup(async () => {
      const res = await api('GET', `${CATS}/dropdown`);
      const c = res.data.find((x) => x.name === name);
      if (c) await api('DELETE', `${CATS}/${c.id}`);
    });
    await signIn('admin');
    await open(page, api);
    await page.getByRole('button', { name: 'Add Subject' }).click();
    const dialog = page.getByRole('dialog').first();
    await dialog.getByRole('button', { name: 'Create new category' }).click();
    await expect(page.getByText('Create New Category')).toBeVisible();
    await page.getByLabel('Category Name').fill(name);
    await page.getByRole('button', { name: 'Create', exact: true }).click();
    await toast(page, 'Subject category created successfully!');
    await expect(page.getByText('Create New Category')).toBeHidden();
    await expect(dialog.getByRole('combobox', { name: 'Select Category' })).toContainText(name);
  });

  test('TC-MST-08-E04 category is required', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA NoCat');
    cleanup(async () => {
      const s = await findSubject(api, name);
      if (s) await api('DELETE', `${BASE}/${s.id}`);
    });
    await signIn('admin');
    await open(page, api);
    await page.getByRole('button', { name: 'Add Subject' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Subject Name').fill(name);
    const response = page.waitForResponse((r) => r.request().method() === 'POST' && r.url().includes('/masters/subjects'));
    await dialog.getByRole('button', { name: 'Add Subject' }).click();
    expect((await response).status()).toBe(422);
    await toast(page, 'Failed to create subject:');
    expect(await findSubject(api, name)).toBeFalsy();
  });

  test('TC-MST-08-E05 duplicate name is rejected', async ({ page, signIn, api }) => {
    await signIn('admin');
    await open(page, api);
    const before = (await api('GET', `${BASE}/?active_only=false`)).data.filter((s) => s.name === 'Mathematics').length;
    await page.getByRole('button', { name: 'Add Subject' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Subject Name').fill('Mathematics');
    await chooseCategory(dialog, page, 'Core Academics');
    await dialog.getByLabel('Short Code').fill('QMX');
    await dialog.getByRole('button', { name: 'Add Subject' }).click();
    await toast(page, 'Failed to create subject:');
    const after = (await api('GET', `${BASE}/?active_only=false`)).data.filter((s) => s.name === 'Mathematics').length;
    expect(after).toBe(before);
  });

  test('TC-MST-08-E06 inline edit name and code', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Physics');
    const subject = await createSubject(api, cleanup, name);
    const newCode = code();
    await signIn('admin');
    await open(page, api);
    await search(page, name);
    await row(page, name).getByRole('button', { name: 'Edit' }).click();
    const first = page.locator('tbody tr').first();
    const inputs = first.getByRole('textbox');
    await expect(inputs.first()).toHaveValue(name);
    await inputs.first().fill(`${name} 2`);
    await inputs.last().fill(newCode);
    await first.getByRole('button').nth(-2).click();
    await toast(page, 'Subject updated successfully!');
    const after = (await api('GET', `${BASE}/${subject.id}`)).data;
    expect(after.name).toBe(`${name} 2`);
    expect(after.short_code).toBe(newCode);
  });

  test('TC-MST-08-E07 delete deactivates the subject', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Physics');
    const subject = await createSubject(api, cleanup, name);
    await signIn('admin');
    await open(page, api);
    await search(page, name);
    await row(page, name).getByRole('button', { name: 'Delete' }).click();
    await expect(page.getByText('Delete Row?')).toBeVisible();
    await page.getByRole('button', { name: 'Delete', exact: true }).last().click();
    await toast(page, 'Subject deleted successfully!');
    await expect(row(page, name)).toContainText('Inactive');
    expect((await api('GET', `${BASE}/${subject.id}`)).data.is_active).toBe(false);
  });

  test('TC-MST-08-E08 search, sort and paging', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await pageSize(page).selectOption('100');
    await page.getByPlaceholder('Search...').fill('Math');
    await expect(row(page, 'Mathematics')).toBeVisible();
    await expect(row(page, 'English')).toHaveCount(0);
    await page.getByPlaceholder('Search...').fill('');
    await page.getByRole('columnheader', { name: 'Name', exact: true }).click();
    const rows = await page.locator('tbody tr').allInnerTexts();
    const at = (name) => rows.findIndex((r) => r.includes(name));
    expect(at('Art and Craft')).toBeLessThan(at('English'));
    expect(at('English')).toBeLessThan(at('Mathematics'));
    expect(at('Mathematics')).toBeLessThan(at('Telugu'));
    await pageSize(page).selectOption('10');
    await expect(page.getByText(/^1-10 of \d+$/)).toBeVisible();
    await expect(page.locator('tbody tr')).toHaveCount(10);
  });

  test('TC-MST-08-E09 teacher is read-only and student has no Masters menu', async ({ page, signIn }) => {
    await signIn('teacher');
    await open(page);
    await expect(page.getByRole('button', { name: 'Export' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Add Subject' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Edit' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Delete' })).toHaveCount(0);
    await page.context().clearCookies();
    await signIn('student');
    await page.goto('/');
    await expect(page.getByRole('link', { name: 'Dashboard' }).or(page.getByText('Dashboard')).first()).toBeVisible();
    await expect(page.getByRole('link', { name: 'Masters', exact: true })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Masters', exact: true })).toHaveCount(0);
  });
});
