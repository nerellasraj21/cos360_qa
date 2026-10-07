// Fee F01 categories, F02 types, F03 terms (web, P1). Baseline: qa_manual seeded fee data.
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const kit = require('../../helpers/feekit');

async function listFind(api, path, field, value) {
  const res = await api('GET', `${path}?limit=500`);
  const rows = Array.isArray(res.data) ? res.data : res.data.items || [];
  return rows.find((r) => r[field] === value);
}

test.describe('Fee F01 categories (web)', () => {
  test('TC-FEE-01-E01 create an active category', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Sports');
    await signIn('admin');
    await page.goto('/fee/categories');
    await page.getByRole('button', { name: 'Add Category' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByPlaceholder("Enter category name").fill(name);
    await expect(dialog.getByRole('checkbox', { name: 'Active' })).toBeChecked();
    await dialog.getByRole('button', { name: 'Save' }).click();
    await toast(page, 'Fee category created successfully');
    const created = await listFind(api, '/fee/categories/', 'category_name', name);
    expect(created).toBeTruthy();
    cleanup(() => api('DELETE', `/fee/categories/${created.id}`));
    expect(created.category_status).toBe('active');
    const year = await kit.yearId();
    expect(created.academic_year_id).toBe(year);
    await page.getByPlaceholder('Search categories...').fill(name);
    const row = page.getByRole('row').filter({ hasText: name });
    await expect(row).toContainText('Active');
    await expect(row).toContainText('0 fee types');
  });
});

test.describe('Fee F03 terms (web)', () => {
  test('TC-FEE-03-E01 create a four-installment term', async ({ page, signIn, api, cleanup }) => {
    test.skip((await kit.allTerms()).length >= 50, 'blocked: qa_manual already holds 50 or more fee terms (QA leftovers that cannot be deleted); the web Fee Terms list only loads the first 50, so a new term is not shown');
    const name = unique('QA Quarterly');
    await signIn('admin');
    await page.goto('/fee/terms');
    await page.getByRole('button', { name: 'Add New Term' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('textbox', { name: 'Term Name' }).fill(name);
    await dialog.getByRole('spinbutton', { name: 'Number of Terms' }).fill('4');
    for (const d of ['2026-06-10', '2026-09-10', '2026-12-10', '2027-03-10']) {
      await dialog.getByPlaceholder('Select date').fill(d);
      await dialog.getByRole('button', { name: 'Add Date' }).click();
    }
    await dialog.getByRole('button', { name: 'Create Term' }).click();
    await toast(page, 'Fee term created successfully');
    const created = await listFind(api, '/fee/terms/', 'term_name', name);
    expect(created).toBeTruthy();
    cleanup(() => api('DELETE', `/fee/terms/${created.id}`));
    expect(created.number_of_terms).toBe(4);
    await page.getByPlaceholder('Search by term name...').fill(name);
    const row = page.getByRole('row').filter({ hasText: name });
    await expect(row).toContainText('4 terms');
    await expect(row).toContainText('Jun 10 - Mar 10 (4 dates)');
    await expect(row).toContainText('Active');
  });
});

test.describe('Fee F02 types (web)', () => {
  test('TC-FEE-02-E01 create a fee type on a category and term', async ({ page, signIn, api, cleanup }) => {
    const catName = unique('QA Sports');
    const termName = unique('QA Quarterly');
    const typeName = unique('QA Lab');
    const cat = await kit.createCategory(cleanup, catName);
    const term = await kit.createTerm(cleanup, termName);
    await signIn('admin');
    await page.goto('/fee/types');
    await page.getByRole('button', { name: 'Add New Type' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('textbox', { name: 'Type Name' }).fill(typeName);
    await dialog.getByRole('combobox').nth(0).click();
    await page.getByRole('option', { name: catName }).click();
    await dialog.getByRole('combobox').nth(1).click();
    await page.getByRole('option', { name: termName }).click();
    await dialog.getByRole('button', { name: 'Create Type' }).click();
    await toast(page, 'Fee type created successfully');
    const created = await listFind(api, '/fee/types/', 'type_name', typeName);
    expect(created).toBeTruthy();
    cleanup(() => api('DELETE', `/fee/types/${created.id}`));
    await page.getByPlaceholder('Search by name, category or term...').fill(typeName);
    const row = page.getByRole('row').filter({ hasText: typeName });
    await expect(row).toContainText(catName);
    await expect(row).toContainText(termName);
    await expect(row).toContainText('Active');
  });
});
