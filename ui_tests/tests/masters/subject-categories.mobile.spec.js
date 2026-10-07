// Masters F07 Subject categories, mobile (Expo web). Baseline: qa_manual seeded Languages, Core Academics, Co-Curricular.
const { test, expect, unique, toast } = require('../../helpers/fixtures');

const ROUTE = '/masters/subjectcategories';
const BASE = '/masters/subject_categories/categories';

async function findCategory(api, name) {
  const res = await api('GET', `${BASE}/dropdown`);
  return res.data.find((c) => c.name === name);
}

async function open(page) {
  await page.goto(ROUTE, { timeout: 180_000 });
  await expect(page.getByText('Co-Curricular', { exact: true })).toBeVisible({ timeout: 60_000 });
}

async function count(page) {
  const text = await page.getByText(/^\d+ categor(y|ies)$/).innerText();
  return Number(text.split(' ')[0]);
}

test.describe('Masters F07 subject categories (mobile)', () => {
  test('TC-MST-07-E10 create, edit and delete a category', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Humanities');
    await signIn('admin');
    await open(page);
    const before = await count(page);
    cleanup(async () => {
      for (const n of [name, `${name} 2`]) {
        const c = await findCategory(api, n);
        if (c) await api('DELETE', `${BASE}/${c.id}`);
      }
    });

    await page.getByText('Add Subject Categories', { exact: true }).first().click();
    await page.getByPlaceholder('Enter category name').fill(name);
    await page.getByText('Add Subject Categories', { exact: true }).last().click();
    await toast(page, 'Category Created');
    await expect(page.getByText(name, { exact: true })).toBeVisible();
    await expect.poll(() => count(page)).toBe(before + 1);
    expect(await findCategory(api, name)).toBeTruthy();

    await page.getByPlaceholder('Search categories...').fill(name);
    await expect.poll(() => count(page)).toBe(1);
    await page.getByLabel('Edit', { exact: true }).click();
    await expect(page.getByText('Edit Category')).toBeVisible();
    const input = page.getByPlaceholder('Enter category name');
    await expect(input).toHaveValue(name);
    await input.fill(`${name} 2`);
    await page.getByText('Update', { exact: true }).click();
    await toast(page, 'Category Updated');
    await expect(page.getByText(`${name} 2`, { exact: true })).toBeVisible();
    expect(await findCategory(api, `${name} 2`)).toBeTruthy();

    await page.getByLabel('Delete', { exact: true }).click();
    await expect(page.getByText('Delete Subject Category')).toBeVisible();
    await expect(page.getByText(`Are you sure you want to delete "${name} 2"?`)).toBeVisible();
    await page.getByText('Delete', { exact: true }).last().click();
    await toast(page, 'Category Deleted');
    await expect(page.getByText(`${name} 2`, { exact: true })).toHaveCount(0);
    await expect.poll(() => count(page)).toBe(0);
    expect(await findCategory(api, `${name} 2`)).toBeFalsy();
  });

  test('TC-MST-07-E11 category name is required', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await page.getByText('Add Subject Categories', { exact: true }).first().click();
    await expect(page.getByPlaceholder('Enter category name')).toBeVisible();
    await page.getByText('Add Subject Categories', { exact: true }).last().click();
    await toast(page, 'Category name is required');
    await expect(page.getByPlaceholder('Enter category name')).toBeVisible();
  });

  test('TC-MST-07-E12 student gets no Masters card and a load error', async ({ page, signIn }) => {
    test.setTimeout(240_000);
    await signIn('student');
    await page.goto('/', { timeout: 180_000 });
    await expect(page.getByRole('button', { name: 'Open Exam Management' })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole('button', { name: 'Open Students' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Open Fee Management' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Open Masters' })).toHaveCount(0);
    await page.goto(ROUTE, { timeout: 180_000 });
    await expect(page.getByText('Failed to load subject categories data')).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText('Error', { exact: true })).toBeVisible();
    await expect(page.getByText('Retry', { exact: true })).toBeVisible();
  });
});
