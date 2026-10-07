// Masters F06 Class and section lookups and dropdowns, web (Timetable pickers). Baseline: qa_manual seeded classes.
const { test, expect, unique } = require('../../helpers/fixtures');

const ROUTE = '/TimeTable';
const SEEDED = ['Class 1', 'Class 2', 'Class 3', 'Class 4', 'Class 5', 'LKG', 'Nursery', 'UKG'];

async function activeYearId(api) {
  const res = await api('GET', '/masters/academic_years/?active_only=false&limit=1000');
  const rows = Array.isArray(res.data) ? res.data : res.data.items || [];
  return rows.find((y) => y.title === '2026-2027').id;
}

async function open(page) {
  await page.goto(ROUTE);
  await expect(page.getByText('Please select a class and section to view or create a timetable')).toBeVisible();
}

function classPicker(page) {
  return page.getByRole('main').getByRole('combobox', { includeHidden: true }).nth(0);
}

function sectionPicker(page) {
  return page.getByRole('main').getByRole('combobox', { includeHidden: true }).nth(1);
}

async function optionTexts(page) {
  const options = page.getByRole('option');
  await expect(options.first()).toBeVisible();
  return options.allInnerTexts();
}

test.describe('Masters F06 class and section lookups (web)', () => {
  test('TC-MST-06-E01 class picker lists only active classes by name', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Inactive');
    const res = await api('POST', '/masters/class_sections/', {
      body: { name, short_code: name.slice(-7), academic_year_id: await activeYearId(api), is_active: false, sections: [{ name: 'A' }] },
    });
    expect(res.status).toBe(201);
    cleanup(() => api('DELETE', `/masters/class_sections/${res.data.id}`));
    await signIn('admin');
    await open(page);
    await classPicker(page).click();
    const texts = await optionTexts(page);
    expect(texts).not.toContain(name);
    const seededOrder = texts.filter((t) => SEEDED.includes(t));
    expect(seededOrder).toEqual(SEEDED);
    const dropdown = await api('GET', '/masters/class_sections/dropdown');
    const active = dropdown.data.map((c) => c.name);
    for (const t of texts) expect(active).toContain(t);
  });

  test('TC-MST-06-E02 section picker waits for a class then lists its sections', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await expect(sectionPicker(page)).toBeDisabled();
    await classPicker(page).click();
    await page.getByRole('option', { name: 'Class 1', exact: true }).click();
    await expect(sectionPicker(page)).toBeEnabled();
    await sectionPicker(page).click();
    expect(await optionTexts(page)).toEqual(['1-A', '1-B']);
  });

  test('TC-MST-06-E03 changing the class clears the section', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await classPicker(page).click();
    await page.getByRole('option', { name: 'Class 1', exact: true }).click();
    await sectionPicker(page).click();
    await page.getByRole('option', { name: '1-A', exact: true }).click();
    await expect(page.getByText('1-A', { exact: true })).toBeVisible();
    await classPicker(page).click();
    await page.getByRole('option', { name: 'Class 2', exact: true }).click();
    await expect(page.getByText('1-A', { exact: true })).toHaveCount(0);
    await expect(page.getByText('Select Section')).toBeVisible();
  });
});
