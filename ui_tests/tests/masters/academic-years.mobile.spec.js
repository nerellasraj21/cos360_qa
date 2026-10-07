// Masters F01 Academic years, mobile (Expo web). Baseline: qa_manual seeded year "2026-2027" (active).
const fs = require('fs');
const { test, expect, unique, toast } = require('../../helpers/fixtures');

const ROUTE = '/masters/academicyears';

async function findYear(api, title) {
  const res = await api('GET', '/masters/academic_years/?active_only=false&limit=1000');
  const rows = Array.isArray(res.data) ? res.data : res.data.items || [];
  return rows.find((y) => y.title === title);
}

async function createYearViaApi(api, cleanup, title, start = '2034-04-01', end = '2035-03-31') {
  const res = await api('POST', '/masters/academic_years/', { body: { title, start_date: start, end_date: end, is_active: false } });
  expect([200, 201]).toContain(res.status);
  cleanup(() => api('DELETE', `/masters/academic_years/${res.data.id}/permanent`));
  return res.data;
}

async function open(page) {
  await page.goto(ROUTE, { timeout: 180_000 });
  await expect(page.getByText('2026-2027').first()).toBeVisible({ timeout: 60_000 });
}

test.describe('Masters F01 academic years (mobile)', () => {
  test('TC-MST-01-E15 list shows the seeded year', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await expect(page.getByText('Academic Years').first()).toBeVisible();
    await expect(page.getByText(/records? found/).first()).toBeVisible();
    await expect(page.getByText('Export').first()).toBeVisible();
    await expect(page.getByText('Add Academic Year').first()).toBeVisible();
    await expect(page.getByText('Active', { exact: true }).first()).toBeVisible();
  });

  test('TC-MST-01-E17 title is required', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await page.getByText('Add Academic Year').first().click();
    await page.getByPlaceholder('YYYY-MM-DD').nth(0).fill('2034-04-01');
    await page.getByPlaceholder('YYYY-MM-DD').nth(1).fill('2035-03-31');
    await page.getByText('Create', { exact: true }).click();
    await toast(page, 'Please fill in all required fields');
    await expect(page.getByPlaceholder('e.g. 2025-26')).toBeVisible();
  });

  test('TC-MST-01-E18 create an inactive year', async ({ page, signIn, api, cleanup }) => {
    const title = unique('QA 2034-35');
    await signIn('admin');
    await open(page);
    await page.getByText('Add Academic Year').first().click();
    await page.getByPlaceholder('e.g. 2025-26').fill(title);
    await page.getByPlaceholder('YYYY-MM-DD').nth(0).fill('2034-04-01');
    await page.getByPlaceholder('YYYY-MM-DD').nth(1).fill('2035-03-31');
    cleanup(async () => {
      const seeded = await findYear(api, '2026-2027');
      if (seeded && !seeded.is_active) await api('PUT', `/masters/academic_years/${seeded.id}`, { body: { is_active: true } });
    });
    await page.getByText('Active', { exact: true }).last().click();
    await page.getByText('Create', { exact: true }).click();
    await toast(page, 'Academic year has been created');
    const created = await findYear(api, title);
    expect(created).toBeTruthy();
    cleanup(() => api('DELETE', `/masters/academic_years/${created.id}/permanent`));
    expect(created.is_active).toBe(false);
    expect((await findYear(api, '2026-2027')).is_active).toBe(true);
    await expect(page.getByText(title).first()).toBeVisible();
  });

  test('TC-MST-01-E22 teacher sees a read-only list', async ({ page, signIn }) => {
    await signIn('teacher');
    await open(page);
    await expect(page.getByText('Export').first()).toBeVisible();
    await expect(page.getByText('Add Academic Year')).toHaveCount(0);
  });

  test('TC-MST-01-E16 search filters by title and clearing shows all', async ({ page, signIn, api, cleanup }) => {
    const title = unique('QA 2034-35');
    await createYearViaApi(api, cleanup, title);
    await signIn('admin');
    await open(page);
    await expect(page.getByText(title, { exact: true })).toBeVisible();
    const search = page.getByPlaceholder('Search...');
    await search.fill(title);
    await expect(page.getByText(title, { exact: true })).toBeVisible();
    await expect(page.getByText('2026-2027', { exact: true })).toHaveCount(0);
    await expect(page.getByText('1 record found')).toBeVisible();
    await search.fill('');
    await expect(page.getByText('2026-2027', { exact: true })).toBeVisible();
    await expect(page.getByText(title, { exact: true })).toBeVisible();
  });

  test('TC-MST-01-E19 edit renames the year', async ({ page, signIn, api, cleanup }) => {
    const title = unique('QA 2034-35');
    const created = await createYearViaApi(api, cleanup, title);
    await signIn('admin');
    await open(page);
    await page.getByPlaceholder('Search...').fill(title);
    await page.getByLabel('Edit', { exact: true }).first().click();
    await expect(page.getByText('Edit Academic Year')).toBeVisible();
    const input = page.getByPlaceholder('e.g. 2025-26');
    await expect(input).toHaveValue(title);
    await input.fill(`${title} B`);
    await page.getByText('Update', { exact: true }).click();
    await toast(page, 'Academic year has been updated.');
    await page.getByPlaceholder('Search...').fill('');
    await expect(page.getByText(`${title} B`)).toBeVisible();
    const after = await api('GET', `/masters/academic_years/${created.id}`);
    expect(after.data.title).toBe(`${title} B`);
    expect(after.data.is_active).toBe(false);
  });

  test('TC-MST-01-E20 delete deactivates the year and keeps it listed', async ({ page, signIn, api, cleanup }) => {
    const title = unique('QA 2034-35');
    const created = await createYearViaApi(api, cleanup, title);
    await signIn('admin');
    await open(page);
    await page.getByPlaceholder('Search...').fill(title);
    await page.getByLabel('Delete', { exact: true }).first().click();
    await expect(page.getByText('Delete Academic Year')).toBeVisible();
    await expect(page.getByText(`Are you sure you want to delete "${title}"?`)).toBeVisible();
    await page.getByText('Delete', { exact: true }).last().click();
    await toast(page, 'Academic year has been deleted.');
    await expect(page.getByText(title, { exact: true })).toBeVisible();
    await expect(page.getByText('Inactive', { exact: true })).toBeVisible();
    const after = await api('GET', `/masters/academic_years/${created.id}`);
    expect(after.status).toBe(200);
    expect(after.data.is_active).toBe(false);
  });

  test('TC-MST-01-E21 export to CSV downloads on the web build', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await page.getByText('Export', { exact: true }).first().click();
    await expect(page.getByText('Export As')).toBeVisible();
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.getByText('Export to CSV').click(),
    ]);
    expect(download.suggestedFilename()).toBe('academic_years_data.csv');
    const lines = fs.readFileSync(await download.path(), 'utf8').trim().split('\n');
    expect(lines[0]).toBe('Title,Start Date,End Date,Active');
    expect(lines.some((l) => l.startsWith('2026-2027,2026-06-01,2027-03-31,Yes'))).toBe(true);
  });
});
