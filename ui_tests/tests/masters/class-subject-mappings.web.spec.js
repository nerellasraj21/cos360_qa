// Masters F09 class-subject mappings and F10 bulk mappings, web. Baseline: qa_manual seeded classes and mappings (read only).
// Every write runs on QA classes created here through the API; seeded mappings are never changed.
const { test, expect, unique, toast } = require('../../helpers/fixtures');

const ROUTE = '/masters/classsubjectmappings';
const BASE = '/masters/class-subject-mappings';

async function workingYearId(api) {
  const res = await api('GET', '/masters/academic_years/?active_only=false&limit=1000');
  const rows = Array.isArray(res.data) ? res.data : res.data.items || [];
  return rows.find((y) => y.title === '2026-2027').id;
}

async function subjectIds(api) {
  const res = await api('GET', '/masters/subjects/?limit=1000');
  const rows = Array.isArray(res.data) ? res.data : res.data.items || [];
  const map = {};
  for (const s of rows) if (s.is_active && !map[s.name]) map[s.name] = s.id;
  return map;
}

async function classMappings(api, classId) {
  const res = await api('GET', `${BASE}/?class_id=${classId}&active_only=false&limit=1000`);
  return res.data.items;
}

async function createQaClass(api, cleanup, sections = ['A', 'B', 'C'], prefix = 'QA C9') {
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
  const ids = await subjectIds(api);
  const res = await api('POST', `${BASE}/bulk`, {
    body: {
      class_id: cls.id,
      section_id: sectionId,
      academic_year_id: cls.year,
      subjects: subjects.map((name, i) => ({ subject_id: ids[name], order: i + 1 })),
    },
  });
  expect(res.status).toBe(201);
  return res.data;
}

function mappingRow(page, className, section, subject) {
  return page
    .locator('tbody tr')
    .filter({ has: page.getByRole('cell', { name: className, exact: true }) })
    .filter({ has: page.getByRole('cell', { name: section, exact: true }) })
    .filter({ has: page.getByRole('cell', { name: subject, exact: true }) });
}

async function openList(page) {
  await page.goto(ROUTE);
  await expect(page.getByText('Class-Subject Mappings').first()).toBeVisible();
  await expect(page.getByText(/\d+-\d+ of \d+/)).toBeVisible();
}

async function showClass(page, className, section, subject) {
  await page.locator('select').filter({ hasText: '100' }).selectOption('100');
  await expect(page.getByText(/^1-\d+ of \d+$/)).toBeVisible();
  await page.getByPlaceholder('Search...').fill(className);
  const target = mappingRow(page, className, section, subject);
  for (let i = 0; i < 10; i++) {
    if (await target.count()) break;
    const next = page.getByRole('button', { name: 'Next', exact: true });
    if (await next.isDisabled()) break;
    await next.click();
    await page.waitForTimeout(800);
  }
  await expect(target).toBeVisible();
  return target;
}

async function openAddDialog(page) {
  await page.getByRole('button', { name: 'Add Class-Subject Mappings' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('heading', { name: 'Add Class-Subject Mappings' })).toBeVisible();
  return dialog;
}

async function pick(page, dialog, placeholder, value) {
  await dialog.getByText(placeholder, { exact: true }).click({ force: true });
  await page.keyboard.type(value);
  await page.getByRole('option', { name: value, exact: true }).click();
}

async function closeMenu(dialog) {
  await dialog.getByRole('heading', { name: 'Add Class-Subject Mappings' }).click();
}

async function pickMore(page, value) {
  await page.keyboard.type(value);
  await page.getByRole('option', { name: value, exact: true }).click();
}

test.describe('Masters F09 class-subject mappings (web)', () => {
  test('TC-MST-09-E01 list shows the seeded mappings', async ({ page, signIn }) => {
    await signIn('admin');
    await openList(page);
    for (const header of ['S.No.', 'Class', 'Section', 'Subject', 'Exclude from Marks', 'Order', 'Active', 'Actions']) {
      await expect(page.getByRole('columnheader', { name: header, exact: true })).toBeVisible();
    }
    const seeded = await showClass(page, 'Class 1', '1-A', 'English');
    await expect(seeded.getByRole('cell', { name: 'No', exact: true })).toBeVisible();
    await expect(seeded.getByRole('cell', { name: '1', exact: true }).last()).toBeVisible();
    await expect(seeded).toContainText('Active');
    await expect(page.getByRole('button', { name: /Export/ })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Add Class-Subject Mappings' })).toBeVisible();
  });

  test('TC-MST-09-E02 search filters the page, sort and server paging', async ({ page, signIn }) => {
    await signIn('admin');
    await openList(page);
    await expect(page.locator('tbody tr')).toHaveCount(5);
    await page.getByPlaceholder('Search...').fill('English');
    await expect(page.getByText(/^\d+ of 5 results$/)).toBeVisible();
    const filtered = page.locator('tbody tr');
    const n = await filtered.count();
    for (let i = 0; i < n; i++) {
      const text = await filtered.nth(i).innerText();
      if (!/No results found/.test(text)) expect(text).toContain('English');
    }
    await page.getByPlaceholder('Search...').fill('');
    await page.getByRole('columnheader', { name: 'Class', exact: true }).click();
    const classes = await page.locator('tbody tr td:nth-child(2)').allInnerTexts();
    const sorted = [...classes].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
    expect(classes).toEqual(sorted);
    const request = page.waitForRequest((r) => r.url().includes('/class-subject-mappings/') && r.url().includes('limit=20'));
    await page.locator('select').filter({ hasText: '100' }).selectOption('20');
    await request;
    await expect(page.getByText(/^1-20 of \d+$/)).toBeVisible();
    await expect(page.locator('tbody tr')).toHaveCount(20);
  });

  test('TC-MST-09-E03 inline edit sets exclude from marks and order', async ({ page, signIn, api, cleanup }) => {
    const cls = await createQaClass(api, cleanup);
    await bulkMap(api, cls, ['Mathematics', 'English']);
    await signIn('admin');
    await openList(page);
    const target = await showClass(page, cls.name, 'A', 'Mathematics');
    await target.getByRole('button', { name: 'Edit' }).click();
    const editing = page.locator('tbody tr').filter({ has: page.getByRole('textbox') });
    await editing.getByRole('checkbox').first().check();
    await editing.getByRole('textbox').fill('3');
    await editing.getByRole('button').first().click();
    await toast(page, 'Class-subject mapping updated successfully!');
    await expect(target.getByRole('cell', { name: 'Yes', exact: true })).toBeVisible();
    await expect(target.getByRole('cell', { name: '3', exact: true }).last()).toBeVisible();
    const row = (await classMappings(api, cls.id)).find((m) => m.section_id === cls.sectionIds.A && m.subject_name === 'Mathematics');
    expect(row.exclude_marks).toBe(true);
    expect(row.order).toBe(3);
  });

  test('TC-MST-09-E04 empty order is rejected', async ({ page, signIn, api, cleanup }) => {
    const cls = await createQaClass(api, cleanup);
    await bulkMap(api, cls, ['Mathematics', 'English']);
    await signIn('admin');
    await openList(page);
    const target = await showClass(page, cls.name, 'A', 'Mathematics');
    await target.getByRole('button', { name: 'Edit' }).click();
    const editing = page.locator('tbody tr').filter({ has: page.getByRole('textbox') });
    await editing.getByRole('textbox').fill('');
    await editing.getByRole('button').first().click();
    await toast(page, 'Failed to update mapping');
    await expect(target.getByRole('cell', { name: '1', exact: true }).last()).toBeVisible();
    const row = (await classMappings(api, cls.id)).find((m) => m.section_id === cls.sectionIds.A && m.subject_name === 'Mathematics');
    expect(row.order).toBe(1);
  });

  test('TC-MST-09-E05 inactive mapping is not offered in the timetable', async ({ page, signIn, api, cleanup }) => {
    const cls = await createQaClass(api, cleanup);
    await bulkMap(api, cls, ['Mathematics', 'English']);
    await signIn('admin');
    await openList(page);
    const target = await showClass(page, cls.name, 'A', 'Mathematics');
    await target.getByRole('button', { name: 'Edit' }).click();
    const editing = page.locator('tbody tr').filter({ has: page.getByRole('textbox') });
    await editing.getByRole('checkbox').nth(1).uncheck();
    await editing.getByRole('button').first().click();
    await toast(page, 'Class-subject mapping updated successfully!');
    await expect(target).toContainText('Inactive');
    await page.goto('/TimeTable');
    await page.getByText('Select Class', { exact: true }).click({ force: true });
    await page.keyboard.type(cls.name);
    await page.getByRole('option', { name: cls.name, exact: true }).click();
    await page.getByText('Select Section', { exact: true }).click({ force: true });
    await page.getByRole('option', { name: 'A', exact: true }).click();
    await expect(async () => {
      if (!(await page.getByText('Select...', { exact: true }).count())) {
        await page.getByRole('button', { name: '+ Add Subject Row' }).click();
      }
      await expect(page.getByText('Select...', { exact: true }).first()).toBeVisible({ timeout: 1500 });
    }).toPass({ timeout: 20_000 });
    await page.getByText('Select...', { exact: true }).first().click({ force: true });
    await expect(page.getByRole('option', { name: 'English', exact: true })).toBeVisible();
    await expect(page.getByRole('option', { name: 'Mathematics', exact: true })).toHaveCount(0);
  });

  test('TC-MST-09-E06 delete removes the mapping rows', async ({ page, signIn, api, cleanup }) => {
    const cls = await createQaClass(api, cleanup, ['A']);
    await bulkMap(api, cls, ['Mathematics', 'English']);
    await signIn('admin');
    await openList(page);
    for (const subject of ['Mathematics', 'English']) {
      const target = await showClass(page, cls.name, 'A', subject);
      await target.getByRole('button', { name: 'Delete' }).click();
      await expect(page.getByText('Delete Row?')).toBeVisible();
      await page.getByRole('button', { name: 'Delete', exact: true }).last().click();
      await toast(page, 'Class-subject mapping deleted successfully!');
      await expect(target).toHaveCount(0);
    }
    expect(await classMappings(api, cls.id)).toEqual([]);
  });

  test('TC-MST-09-E07 teacher sees a read-only list', async ({ page, signIn }) => {
    await signIn('teacher');
    await openList(page);
    await expect(page.locator('tbody tr').first()).toContainText(/\S/);
    await expect(page.getByRole('button', { name: /Export/ })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Add Class-Subject Mappings' })).toHaveCount(0);
    await expect(page.locator('tbody').getByRole('button', { name: 'Edit' })).toHaveCount(0);
    await expect(page.locator('tbody').getByRole('button', { name: 'Delete' })).toHaveCount(0);
  });
});

test.describe('Masters F10 bulk class-subject mappings (web)', () => {
  test('TC-MST-10-E01 all sections creates rows for every section', async ({ page, signIn, api, cleanup }) => {
    test.fail(true, 'UI-MST-20: subject auto-order skips numbers (2nd selected subject gets order 3, 3rd gets 5) in the web bulk add dialog');
    const cls = await createQaClass(api, cleanup);
    await signIn('admin');
    await openList(page);
    const dialog = await openAddDialog(page);
    await pick(page, dialog, 'Select Class', cls.name);
    await pick(page, dialog, 'Select one or more sections', 'All Sections');
    await closeMenu(dialog);
    await expect(dialog.getByText(`This will apply mappings to all 3 sections in ${cls.name}`)).toBeVisible();
    await pick(page, dialog, 'Select multiple subjects...', 'Mathematics');
    await pickMore(page, 'English');
    await closeMenu(dialog);
    await dialog.getByRole('button', { name: 'Add 2 Mappings' }).click();
    await toast(page, 'Successfully processed class-subject mappings for 3 sections');
    await expect(dialog).toBeHidden();
    const rows = await classMappings(api, cls.id);
    expect(rows).toHaveLength(6);
    await showClass(page, cls.name, 'C', 'English');
    for (const section of ['A', 'B', 'C']) {
      await expect(mappingRow(page, cls.name, section, 'Mathematics')).toBeVisible();
      await expect(mappingRow(page, cls.name, section, 'English')).toBeVisible();
    }
    for (const section of ['A', 'B', 'C']) {
      const math = rows.find((m) => m.section_name === section && m.subject_name === 'Mathematics');
      const eng = rows.find((m) => m.section_name === section && m.subject_name === 'English');
      expect(math.order).toBe(1);
      expect(eng.order).toBe(2);
    }
  });

  test('TC-MST-10-E02 selected sections send one request each', async ({ page, signIn, api, cleanup }) => {
    const cls = await createQaClass(api, cleanup);
    await signIn('admin');
    await openList(page);
    const dialog = await openAddDialog(page);
    await pick(page, dialog, 'Select Class', cls.name);
    await pick(page, dialog, 'Select one or more sections', 'A');
    await pickMore(page, 'B');
    await closeMenu(dialog);
    await expect(dialog.getByText('Mappings will be created for 2 selected sections')).toBeVisible();
    await pick(page, dialog, 'Select multiple subjects...', 'Hindi');
    await closeMenu(dialog);
    const posts = [];
    page.on('request', (r) => { if (r.method() === 'POST' && r.url().includes('/class-subject-mappings/bulk')) posts.push(r.postDataJSON()); });
    await dialog.getByRole('button', { name: 'Add 1 Mapping', exact: true }).click();
    await expect(dialog).toBeHidden();
    expect(posts).toHaveLength(2);
    expect(posts.map((p) => p.section_id).sort()).toEqual([cls.sectionIds.A, cls.sectionIds.B].sort());
    const rows = await classMappings(api, cls.id);
    expect(rows.map((m) => `${m.section_name}/${m.subject_name}`).sort()).toEqual(['A/Hindi', 'B/Hindi']);
  });

  test('TC-MST-10-E03 All Sections replaces other section choices', async ({ page, signIn, api, cleanup }) => {
    const cls = await createQaClass(api, cleanup);
    await signIn('admin');
    await openList(page);
    const dialog = await openAddDialog(page);
    await pick(page, dialog, 'Select Class', cls.name);
    await pick(page, dialog, 'Select one or more sections', 'A');
    await pickMore(page, 'B');
    await expect(dialog.getByRole('button', { name: 'Remove A', exact: true })).toBeVisible();
    await pickMore(page, 'All Sections');
    await closeMenu(dialog);
    await expect(dialog.getByRole('button', { name: 'Remove All Sections', exact: true })).toBeVisible();
    await expect(dialog.getByRole('button', { name: 'Remove A', exact: true })).toHaveCount(0);
    await expect(dialog.getByRole('button', { name: 'Remove B', exact: true })).toHaveCount(0);
  });

  test('TC-MST-10-E04 submit stays disabled until class, section and subject are chosen', async ({ page, signIn, api, cleanup }) => {
    const cls = await createQaClass(api, cleanup);
    await signIn('admin');
    await openList(page);
    const dialog = await openAddDialog(page);
    await expect(dialog.getByRole('button', { name: 'Add 0 Mappings' })).toBeDisabled();
    await pick(page, dialog, 'Select Class', cls.name);
    await expect(dialog.getByRole('button', { name: 'Add 0 Mappings' })).toBeDisabled();
    await pick(page, dialog, 'Select one or more sections', 'A');
    await closeMenu(dialog);
    await expect(dialog.getByRole('button', { name: 'Add 0 Mappings' })).toBeDisabled();
    await pick(page, dialog, 'Select multiple subjects...', 'English');
    await closeMenu(dialog);
    await expect(dialog.getByRole('button', { name: 'Add 1 Mapping', exact: true })).toBeEnabled();
  });

  test('TC-MST-10-E05 removing a subject renumbers orders and inactive flag is saved', async ({ page, signIn, api, cleanup }) => {
    const cls = await createQaClass(api, cleanup);
    await signIn('admin');
    await openList(page);
    const dialog = await openAddDialog(page);
    await pick(page, dialog, 'Select Class', cls.name);
    await pick(page, dialog, 'Select one or more sections', 'All Sections');
    await closeMenu(dialog);
    await pick(page, dialog, 'Select multiple subjects...', 'English');
    await pickMore(page, 'Hindi');
    await pickMore(page, 'Telugu');
    await closeMenu(dialog);
    const settings = dialog.locator('table');
    const settingRow = (name) => settings.locator('tbody tr').filter({ has: page.getByRole('cell', { name, exact: true }) });
    await expect(settingRow('Telugu')).toBeVisible();
    await settingRow('Hindi').getByRole('button').click();
    await expect(settingRow('Hindi')).toHaveCount(0);
    await expect(settingRow('English').getByRole('spinbutton')).toHaveValue('1');
    await expect(settingRow('Telugu').getByRole('spinbutton')).toHaveValue('2');
    await settingRow('Telugu').getByRole('checkbox').nth(1).click();
    await dialog.getByRole('button', { name: 'Add 2 Mappings' }).click();
    await toast(page, 'Successfully processed class-subject mappings');
    await expect(dialog).toBeHidden();
    const rows = await classMappings(api, cls.id);
    const telugu = rows.filter((m) => m.subject_name === 'Telugu');
    expect(telugu).toHaveLength(3);
    for (const m of telugu) {
      expect(m.is_active).toBe(false);
      expect(m.order).toBe(2);
    }
    const shown = await showClass(page, cls.name, 'A', 'Telugu');
    await expect(shown).toContainText('Inactive');
  });

  test('TC-MST-10-E06 bulk add keeps the other mappings of the section active', async ({ page, signIn, api, cleanup }) => {
    const cls = await createQaClass(api, cleanup);
    await bulkMap(api, cls, ['Mathematics', 'English']);
    await signIn('admin');
    await openList(page);
    const dialog = await openAddDialog(page);
    await pick(page, dialog, 'Select Class', cls.name);
    await pick(page, dialog, 'Select one or more sections', 'A');
    await closeMenu(dialog);
    await pick(page, dialog, 'Select multiple subjects...', 'Social Studies');
    await closeMenu(dialog);
    await dialog.getByRole('button', { name: 'Add 1 Mapping', exact: true }).click();
    await toast(page, 'Successfully processed class-subject mappings');
    await expect(dialog).toBeHidden();
    const sectionA = (await classMappings(api, cls.id)).filter((m) => m.section_name === 'A');
    expect(sectionA.map((m) => m.subject_name).sort()).toEqual(['English', 'Mathematics', 'Social Studies']);
    for (const m of sectionA) expect(m.is_active).toBe(true);
  });

  test('TC-MST-10-E07 cancel with a chosen class asks to discard', async ({ page, signIn, api, cleanup }) => {
    const cls = await createQaClass(api, cleanup);
    await signIn('admin');
    await openList(page);
    const dialog = await openAddDialog(page);
    await pick(page, dialog, 'Select Class', cls.name);
    let posted = false;
    page.on('request', (r) => { if (r.method() === 'POST' && r.url().includes('/class-subject-mappings')) posted = true; });
    await dialog.getByRole('button', { name: 'Cancel' }).click();
    await expect(page.getByText('Discard changes?')).toBeVisible();
    await page.getByRole('button', { name: /Discard/ }).last().click();
    await expect(page.getByRole('heading', { name: 'Add Class-Subject Mappings' })).toBeHidden();
    expect(posted).toBe(false);
    expect(await classMappings(api, cls.id)).toEqual([]);
  });

  test('TC-MST-10-E08 teacher has no add button', async ({ page, signIn }) => {
    await signIn('teacher');
    await openList(page);
    await expect(page.getByRole('button', { name: /Export/ })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Add Class-Subject Mappings' })).toHaveCount(0);
  });
});
