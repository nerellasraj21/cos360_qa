// Masters F07 Subject categories, web. Baseline: qa_manual seeded Languages, Core Academics, Co-Curricular.
const fs = require('fs');
const { test, expect, unique, toast } = require('../../helpers/fixtures');

const ROUTE = '/masters/subjectcategories';
const BASE = '/masters/subject_categories/categories';

async function findCategory(api, name) {
  const res = await api('GET', `${BASE}/dropdown`);
  return res.data.find((c) => c.name === name);
}

async function createCategory(api, cleanup, name) {
  const res = await api('POST', BASE, { body: { name } });
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

async function open(page) {
  await page.goto(ROUTE);
  await expect(row(page, 'Co-Curricular')).toBeVisible();
}

async function search(page, name) {
  await pageSize(page).selectOption('100');
  await expect(page.getByText(/^1-\d+ of \d+$/)).toBeVisible();
  await page.getByPlaceholder('Search...').fill(name);
  await expect(row(page, name)).toBeVisible();
}

test.describe('Masters F07 subject categories (web)', () => {
  test('TC-MST-07-E01 list shows the seeded categories', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await expect(page.getByText('Subject Categories').first()).toBeVisible();
    await expect(page.getByRole('columnheader', { name: 'Name', exact: true })).toBeVisible();
    for (const name of ['Languages', 'Core Academics', 'Co-Curricular']) await expect(row(page, name)).toBeVisible();
    await expect(pageSize(page)).toHaveValue('5');
    await expect(page.getByText('Filters', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Export' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Add Subject Categories' })).toBeVisible();
  });

  test('TC-MST-07-E02 create a category', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Languages');
    await signIn('admin');
    await open(page);
    await page.getByRole('button', { name: 'Add Subject Categories' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Category Name').fill(name);
    await dialog.getByRole('button', { name: 'Add Subject Categories' }).click();
    await toast(page, 'Subject category created successfully!');
    const created = await findCategory(api, name);
    expect(created).toBeTruthy();
    cleanup(() => api('DELETE', `${BASE}/${created.id}`));
    await expect(dialog).toBeHidden();
    await search(page, name);
  });

  test('TC-MST-07-E03 duplicate name shows the failure toast', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await page.getByRole('button', { name: 'Add Subject Categories' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Category Name').fill('Languages');
    await dialog.getByRole('button', { name: 'Add Subject Categories' }).click();
    await toast(page, 'Failed to create subject category: Category already exists');
  });

  test('TC-MST-07-E04 inline rename', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Languages');
    await createCategory(api, cleanup, name);
    await signIn('admin');
    await open(page);
    await search(page, name);
    await row(page, name).getByRole('button', { name: 'Edit' }).click();
    const first = page.locator('tbody tr').first();
    const input = first.getByRole('textbox');
    await expect(input).toHaveValue(name);
    await input.fill(`${name} 2`);
    await first.getByRole('button').first().click();
    await toast(page, 'Subject category updated successfully!');
    expect(await findCategory(api, `${name} 2`)).toBeTruthy();
  });

  test('TC-MST-07-E05 delete an unused category', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Languages 2');
    const res = await api('POST', BASE, { body: { name } });
    expect(res.status).toBe(200);
    cleanup(() => api('DELETE', `${BASE}/${res.data.id}`));
    await signIn('admin');
    await open(page);
    await search(page, name);
    await row(page, name).getByRole('button', { name: 'Delete' }).click();
    await expect(page.getByText('Delete Row?')).toBeVisible();
    await page.getByRole('button', { name: 'Delete', exact: true }).last().click();
    await toast(page, 'Subject category deleted successfully!');
    await expect(row(page, name)).toHaveCount(0);
    expect(await findCategory(api, name)).toBeFalsy();
  });

  test('TC-MST-07-E06 a category in use cannot be deleted', async ({ page, signIn, api }) => {
    await signIn('admin');
    await open(page);
    await row(page, 'Languages').getByRole('button', { name: 'Delete' }).click();
    await page.getByRole('button', { name: 'Delete', exact: true }).last().click();
    await toast(page, "Failed to delete subject category: Cannot delete category 'Languages' because it is being used by 3 subject(s)");
    await expect(row(page, 'Languages')).toBeVisible();
    expect(await findCategory(api, 'Languages')).toBeTruthy();
  });

  test('TC-MST-07-E07 search, sort and paging', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await page.getByPlaceholder('Search...').fill('Core');
    await expect(row(page, 'Core Academics')).toBeVisible();
    await expect(row(page, 'Languages')).toHaveCount(0);
    await page.getByPlaceholder('Search...').fill('');
    const header = page.getByRole('columnheader', { name: 'Name', exact: true });
    await header.click();
    await header.click();
    const rows = await page.locator('tbody tr').allInnerTexts();
    const at = (name) => rows.findIndex((r) => r.includes(name));
    expect(at('Languages')).toBeLessThan(at('Core Academics'));
    expect(at('Core Academics')).toBeLessThan(at('Co-Curricular'));
    await pageSize(page).selectOption('10');
    await expect(pageSize(page)).toHaveValue('10');
    await expect(page.getByText(/^1-\d+ of \d+$/)).toBeVisible();
    expect(await page.locator('tbody tr').count()).toBeLessThanOrEqual(10);
  });

  test('TC-MST-07-E08 export to CSV', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await page.getByRole('button', { name: 'Export' }).click();
    const download = page.waitForEvent('download');
    await page.getByRole('menuitem', { name: 'Export to CSV' }).click();
    const file = await download;
    expect(file.suggestedFilename()).toBe('subject_categories_data.csv');
    const content = fs.readFileSync(await file.path(), 'utf8');
    expect(content.split('\n')[0].replace(/"/g, '').trim()).toBe('Name');
  });

  test('TC-MST-07-E09 teacher sees a read-only list', async ({ page, signIn }) => {
    await signIn('teacher');
    await open(page);
    await expect(page.getByRole('button', { name: 'Export' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Add Subject Categories' })).toHaveCount(0);
    await expect(row(page, 'Languages').getByRole('button', { name: 'Edit' })).toHaveCount(0);
    await expect(row(page, 'Languages').getByRole('button', { name: 'Delete' })).toHaveCount(0);
  });
});
