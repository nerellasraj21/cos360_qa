// Masters F03 Classes and sections, mobile (Expo web). Baseline: qa_manual seeded classes Nursery to Class 5 in 2026-2027.
const fs = require('fs');
const { test, expect, unique, toast } = require('../../helpers/fixtures');

const ROUTE = '/masters/classesandsections';

async function findClass(api, name) {
  const res = await api('GET', '/masters/class_sections/read_all');
  return (res.data || []).find((c) => c.name === name);
}

async function open(page) {
  await page.goto(ROUTE, { timeout: 180_000 });
  await expect(page.getByText('Class 1', { exact: true })).toBeVisible({ timeout: 60_000 });
}

test.describe('Masters F03 classes and sections (mobile)', () => {
  test('TC-MST-03-E12 search by section name and expand the card', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await expect(page.getByText('Classes & Sections').first()).toBeVisible();
    const count = page.getByText(/^\d+ classes$/);
    await expect(count).toBeVisible();
    expect(Number((await count.innerText()).match(/\d+/)[0])).toBeGreaterThanOrEqual(8);
    await page.getByPlaceholder('Search classes or sections...').fill('2-A');
    await expect(page.getByText('1 class', { exact: true })).toBeVisible();
    await expect(page.getByText('Class 2', { exact: true })).toBeVisible();
    await expect(page.getByText('Class 1', { exact: true })).toHaveCount(0);
    await page.getByLabel('Delete', { exact: true }).first().locator('xpath=following-sibling::*[1]').click();
    await expect(page.getByText('2-A', { exact: true })).toBeVisible();
    await expect(page.getByText('2-B', { exact: true })).toBeVisible();
    await expect(page.getByText('Active', { exact: true })).toHaveCount(3);
  });

  test('TC-MST-03-E13 create a class with generated sections', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA C8');
    cleanup(async () => {
      const created = await findClass(api, name);
      if (created) await api('DELETE', `/masters/class_sections/${created.id}`);
    });
    await signIn('admin');
    await open(page);
    await page.getByLabel('Add', { exact: true }).first().click();
    await expect(page.getByText('Enter Class Details')).toBeVisible();
    await page.getByPlaceholder('e.g., Class 1').fill(name);
    await page.getByPlaceholder('e.g., C1').fill(`Q${Math.random().toString(36).slice(2, 8).toUpperCase()}`);
    await page.getByText('Next', { exact: true }).click();
    await expect(page.getByText('Quick Add Sections Alphabetically')).toBeVisible();
    await page.getByPlaceholder('A', { exact: true }).fill('A');
    await page.getByPlaceholder('D', { exact: true }).fill('B');
    await page.getByText('Generate Sections', { exact: true }).click();
    await toast(page, 'Sections Generated');
    await page.getByText('View', { exact: true }).click();
    await expect(page.getByText('Summary', { exact: true })).toBeVisible();
    await page.getByText('Submit', { exact: true }).click();
    await toast(page, 'Class and sections created successfully');
    await page.getByPlaceholder('Search classes or sections...').fill(name);
    await expect(page.getByText(name, { exact: true })).toBeVisible();
    await expect(page.getByText('2 sections', { exact: true })).toBeVisible();
    const created = await findClass(api, name);
    expect(created.sections.map((s) => s.name).sort()).toEqual(['A', 'B']);
  });

  test('TC-MST-03-E14 class name is required in the wizard', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await page.getByLabel('Add', { exact: true }).first().click();
    await expect(page.getByText('Enter Class Details')).toBeVisible();
    await page.getByPlaceholder('e.g., C1').fill('QC14');
    await page.getByText('Next', { exact: true }).click();
    await page.waitForTimeout(1000);
    await expect(page.getByText('Enter Class Details')).toBeVisible();
    await expect(page.getByText('Quick Add Sections Alphabetically')).toHaveCount(0);
  });

  test('TC-MST-03-E15 hide status and export to Excel', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await expect(page.getByText('Active', { exact: true }).first()).toBeVisible();
    await page.getByLabel('Columns', { exact: true }).click();
    await page.getByText('Status', { exact: true }).click();
    await page.getByLabel('Close', { exact: true }).last().click();
    await expect(page.getByText('Select All')).toHaveCount(0);
    await expect(page.getByText('Active', { exact: true })).toHaveCount(0);
    await page.getByLabel('Export', { exact: true }).click();
    await expect(page.getByText('Export As')).toBeVisible();
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.getByText('Export to Excel').click(),
    ]);
    expect(download.suggestedFilename()).toBe('classes_sections_data.xls');
    const html = fs.readFileSync(await download.path(), 'utf8');
    expect(html).toContain('<tr><td>Class Name</td><td>Class Code</td><td>Sections</td></tr>');
    expect(html).toContain('<tr><td>Class 1</td><td>C1</td><td>1-A; 1-B</td></tr>');
  });

  for (const role of ['student', 'parent']) {
    test(`TC-MST-03-E16 ${role} has no Masters card`, async ({ page, signIn }) => {
      test.setTimeout(180_000);
      await signIn(role);
      await page.goto('/', { timeout: 180_000 });
      await expect(page.getByText('Fee Management').filter({ visible: true }).first()).toBeVisible({ timeout: 60_000 });
      await expect(page.getByText('Students', { exact: true }).filter({ visible: true }).first()).toBeVisible();
      await expect(page.getByText('Masters', { exact: true })).toHaveCount(0);
    });
  }
});
