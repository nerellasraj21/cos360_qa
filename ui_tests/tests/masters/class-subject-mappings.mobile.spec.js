// Masters F09 class-subject mappings and F10 bulk mappings, mobile (Expo web). Baseline: qa_manual seeded classes and mappings (read only).
// Every write runs on QA classes created here through the API; seeded mappings are never changed.
const { test, expect, unique, toast } = require('../../helpers/fixtures');

const ROUTE = '/masters/classsubjectmappings';
const BASE = '/masters/class-subject-mappings';

async function workingYearId(api) {
  const res = await api('GET', '/masters/academic_years/?active_only=false&limit=1000');
  const rows = Array.isArray(res.data) ? res.data : res.data.items || [];
  return rows.find((y) => y.title === '2026-2027').id;
}

async function activeSubjects(api) {
  const res = await api('GET', '/masters/subjects/?limit=1000');
  const rows = Array.isArray(res.data) ? res.data : res.data.items || [];
  return rows.filter((s) => s.is_active);
}

async function classMappings(api, classId) {
  const res = await api('GET', `${BASE}/?class_id=${classId}&active_only=false&limit=1000`);
  return res.data.items;
}

async function createQaClass(api, cleanup, sections = ['A', 'B'], prefix = 'QA C8') {
  const name = unique(prefix);
  const year = await workingYearId(api);
  const res = await api('POST', '/masters/class_sections/', {
    body: {
      name,
      short_code: `Q${Date.now().toString(36).slice(-6)}`,
      academic_year_id: year,
      sections: sections.map((s) => ({ name: s })),
    },
  });
  expect(res.status).toBe(201);
  cleanup(async () => {
    for (const m of await classMappings(api, res.data.id)) await api('DELETE', `${BASE}/${m.id}`);
    await api('DELETE', `/masters/class_sections/${res.data.id}`);
  });
  const sectionIds = Object.fromEntries(res.data.sections.map((s) => [s.name, s.id]));
  return { id: res.data.id, name, year, sectionIds };
}

async function bulkMap(api, cls, subjects, sectionId) {
  const all = await activeSubjects(api);
  const res = await api('POST', `${BASE}/bulk`, {
    body: {
      class_id: cls.id,
      section_id: sectionId,
      academic_year_id: cls.year,
      subjects: subjects.map((name, i) => ({ subject_id: all.find((s) => s.name === name).id, order: i + 1 })),
    },
  });
  expect(res.status).toBe(201);
}

async function open(page) {
  await page.goto(ROUTE, { timeout: 180_000 });
  await expect(page.getByText(/^\d+ mappings?$/)).toBeVisible({ timeout: 60_000 });
}

async function search(page, text) {
  await page.getByPlaceholder('Search by class, section or subject...').fill(text);
  await expect(page.getByText(/^\d+ mappings? found$/)).toBeVisible();
}

async function openAddSheet(page, className) {
  await search(page, 'qa-no-such-mapping');
  await page.getByText('Add Subject Mapping', { exact: true }).click();
  await expect(page.getByText('Add Subject Mappings', { exact: true })).toBeVisible();
  if (!className) return;
  await page.getByText('Select Class', { exact: true }).first().click();
  await page.getByText(className, { exact: true }).last().click({ timeout: 10_000 });
  await expect(page.getByText('All Sections', { exact: true })).toBeVisible();
}

test.describe('Masters F09 class-subject mappings (mobile)', () => {
  test('TC-MST-09-E08 list and search by class', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await expect(page.getByText('Map subjects to classes and manage settings')).toBeVisible();
    await search(page, 'Class 3');
    await expect(page.getByText('Class: Class 3').first()).toBeVisible();
    const classes = await page.getByText(/^Class: /).allInnerTexts();
    expect(classes.length).toBeGreaterThan(0);
    for (const c of classes) expect(c).toBe('Class: Class 3');
    const sections = await page.getByText(/^Section: /).allInnerTexts();
    for (const s of sections) expect(['Section: 3-A', 'Section: 3-B']).toContain(s);
    await expect(page.getByText('Active', { exact: true }).first()).toBeVisible();
    await expect(page.getByText(/^Order: \d+$/).first()).toBeVisible();
  });

  test('TC-MST-09-E09 edit order and exclude from marks', async ({ page, signIn, api, cleanup }) => {
    const cls = await createQaClass(api, cleanup, ['A']);
    await bulkMap(api, cls, ['Mathematics']);
    await signIn('admin');
    await open(page);
    await search(page, cls.name);
    await page.getByLabel('Edit', { exact: true }).click();
    await expect(page.getByText('Edit Mapping', { exact: true })).toBeVisible();
    await page.getByPlaceholder('e.g. 1').fill('2');
    await page.getByText('Exclude from Marks', { exact: true }).click();
    await page.getByText('Save Changes', { exact: true }).click();
    await toast(page, 'Mapping updated successfully');
    await expect(page.getByText('Order: 2', { exact: true })).toBeVisible();
    await expect(page.getByText('Excl. Marks', { exact: true })).toBeVisible();
    const [row] = await classMappings(api, cls.id);
    expect(row.order).toBe(2);
    expect(row.exclude_marks).toBe(true);
  });

  test('TC-MST-09-E10 remove a mapping', async ({ page, signIn, api, cleanup }) => {
    const cls = await createQaClass(api, cleanup, ['A']);
    await bulkMap(api, cls, ['Mathematics']);
    await signIn('admin');
    await open(page);
    await search(page, cls.name);
    await page.getByLabel('Delete', { exact: true }).click();
    await expect(page.getByText('Remove Mapping', { exact: true })).toBeVisible();
    await expect(page.getByText('Remove "Mathematics" from the class?')).toBeVisible();
    await page.getByText('Remove', { exact: true }).click();
    await toast(page, 'Subject mapping has been removed.');
    await expect(page.getByText(`Class: ${cls.name}`)).toHaveCount(0);
    expect(await classMappings(api, cls.id)).toEqual([]);
  });

  test('TC-MST-09-E11 Show Fields hides the section line', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await expect(page.getByText(/^Section: /).first()).toBeVisible();
    await page.getByLabel('Filters', { exact: true }).click();
    await expect(page.getByText('Show Fields', { exact: true })).toBeVisible();
    await expect(page.getByText('Select All', { exact: true })).toBeVisible();
    await page.getByText('Section', { exact: true }).click();
    await expect(page.getByText(/^Section: /)).toHaveCount(0);
    await expect(page.getByText(/^Class: /).first()).toBeVisible();
  });

  test('TC-MST-09-E12 student has no Masters card and gets no mappings', async ({ page, signIn }) => {
    test.setTimeout(180_000);
    // doc: preconditions should name the QA student login; seeded student logins force a password change at first sign-in
    await signIn('student');
    const okMappings = [];
    page.on('response', (r) => { if (r.url().includes('/class-subject-mappings') && r.status() === 200) okMappings.push(r.url()); });
    await page.goto('/', { timeout: 180_000 });
    await expect(page.getByText('Modules', { exact: true }).locator('visible=true').first()).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText('Masters', { exact: true }).locator('visible=true')).toHaveCount(0);
    await page.goto(ROUTE, { timeout: 180_000 });
    await page.waitForTimeout(1500);
    await expect(page.getByText(/^\d+ mappings?$/)).toHaveCount(0);
    await expect(page.getByText(/^Class: /)).toHaveCount(0);
    expect(okMappings).toEqual([]);
  });
});

test.describe('Masters F10 bulk class-subject mappings (mobile)', () => {
  test('TC-MST-10-E09 add subjects to all sections', async ({ page, signIn, api, cleanup }) => {
    test.fail(true, 'UI-MST-21: the "Select Class" picker in Add Subject Mappings opens behind the add sheet, so no class can be chosen');
    const cls = await createQaClass(api, cleanup);
    await signIn('admin');
    await open(page);
    await openAddSheet(page, cls.name);
    await page.getByText('Mathematics', { exact: true }).click();
    await page.getByText('English', { exact: true }).click();
    await page.getByText('Add (2)', { exact: true }).click();
    // doc: with "All Sections" one request is sent, so the toast reads "Subjects Added - 2 subject(s) mapped to class."
    await toast(page, '2 subject(s) mapped to class.');
    await search(page, cls.name);
    for (const section of ['A', 'B']) {
      await expect(page.getByText(`Section: ${section}`, { exact: true })).toHaveCount(2);
    }
    const rows = await classMappings(api, cls.id);
    expect(rows.map((m) => `${m.section_name}/${m.subject_name}`).sort()).toEqual(['A/English', 'A/Mathematics', 'B/English', 'B/Mathematics']);
  });

  test('TC-MST-10-E11 only unmapped subjects are listed', async ({ page, signIn, api, cleanup }) => {
    test.fail(true, 'UI-MST-21: the "Select Class" picker in Add Subject Mappings opens behind the add sheet, so no class can be chosen');
    const full = await createQaClass(api, cleanup, ['A'], 'QA Full');
    await bulkMap(api, full, (await activeSubjects(api)).map((s) => s.name));
    await signIn('admin');
    await open(page);
    await openAddSheet(page, 'Class 1');
    await expect(page.getByText('General Science', { exact: true })).toBeVisible();
    await expect(page.getByText('Social Studies', { exact: true })).toBeVisible();
    for (const mapped of ['English', 'Hindi', 'Telugu', 'Mathematics', 'Environmental Studies', 'Computer Science', 'Art and Craft', 'Physical Education']) {
      await expect(page.getByText(mapped, { exact: true })).toHaveCount(0);
    }
    await page.getByText('Class 1', { exact: true }).first().click();
    await page.getByText(full.name, { exact: true }).last().click();
    await expect(page.getByText('All subjects mapped', { exact: true })).toBeVisible();
    await expect(page.getByText('All available subjects are already mapped to this class.')).toBeVisible();
  });

  test('TC-MST-10-E12 add a subject to selected sections', async ({ page, signIn, api, cleanup }) => {
    test.fail(true, 'UI-MST-21: the "Select Class" picker in Add Subject Mappings opens behind the add sheet, so no class can be chosen');
    const cls = await createQaClass(api, cleanup);
    await signIn('admin');
    await open(page);
    await openAddSheet(page, cls.name);
    await page.getByText('All Sections', { exact: true }).click();
    await expect(page.getByText('Select Sections', { exact: true })).toBeVisible();
    await page.getByText('A', { exact: true }).click();
    await page.getByText('B', { exact: true }).click();
    await page.getByText('Done', { exact: true }).click();
    await expect(page.getByText('2 sections selected', { exact: true })).toBeVisible();
    await page.getByText('Hindi', { exact: true }).click();
    await page.getByText('Add (1)', { exact: true }).click();
    await toast(page, '1 subject(s) mapped to 2 sections.');
    await search(page, cls.name);
    await expect(page.getByText(`Class: ${cls.name}`)).toHaveCount(2);
    const rows = await classMappings(api, cls.id);
    expect(rows.map((m) => `${m.section_name}/${m.subject_name}`).sort()).toEqual(['A/Hindi', 'B/Hindi']);
  });

  test('TC-MST-10-E13 no add button before a class is chosen', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await openAddSheet(page);
    await expect(page.getByText('Select a Class', { exact: true })).toBeVisible();
    await expect(page.getByText('Choose a class above to see its sections and available subjects.')).toBeVisible();
    await expect(page.getByText(/^Add( \(\d+\))?\s*$/)).toHaveCount(0);
  });
});
