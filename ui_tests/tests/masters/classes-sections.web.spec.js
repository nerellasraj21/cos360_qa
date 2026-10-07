// Masters F03 Classes and sections: list, search, sort, export and create, web. Baseline: qa_manual seeded classes Nursery to Class 5 in 2026-2027.
const fs = require('fs');
const { test, expect, unique, toast } = require('../../helpers/fixtures');

const ROUTE = '/masters/classesandsections';
const SEEDED = [
  ['Nursery', 'NUR'], ['LKG', 'LKG'], ['UKG', 'UKG'], ['Class 1', 'C1'], ['Class 2', 'C2'], ['Class 3', 'C3'], ['Class 4', 'C4'], ['Class 5', 'C5'],
];

function code() {
  return `Q${Math.random().toString(36).slice(2, 8).toUpperCase()}`;
}

async function seededYearId(api) {
  const res = await api('GET', '/masters/academic_years/?active_only=false&limit=1000');
  return res.data.items.find((y) => y.title === '2026-2027').id;
}

async function findClass(api, name) {
  const res = await api('GET', '/masters/class_sections/read_all');
  return (res.data || []).find((c) => c.name === name);
}

async function createClassViaApi(api, cleanup, name, sections = ['A', 'B', 'C']) {
  const body = { name, short_code: code(), academic_year_id: await seededYearId(api), sections: sections.map((s) => ({ name: s })) };
  const res = await api('POST', '/masters/class_sections/', { body });
  expect(res.status).toBe(201);
  cleanup(() => api('DELETE', `/masters/class_sections/${res.data.id}`));
  return res.data;
}

function classRow(page, name) {
  return page.getByRole('row').filter({ has: page.getByRole('cell', { name, exact: true }) });
}

async function open(page) {
  await page.goto(ROUTE);
  await expect(classRow(page, 'Class 1')).toBeVisible({ timeout: 30_000 });
  if (await page.getByRole('button', { name: 'Next', exact: true }).count()) {
    await page.getByRole('button', { name: '10', exact: true }).click();
    await page.getByRole('button', { name: '50', exact: true }).click();
  }
}

async function openWizard(page, name, classCode) {
  await page.getByRole('button', { name: 'Add Class & Sections' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('heading', { name: 'Enter Class Details' })).toBeVisible();
  if (name !== undefined) await dialog.getByLabel('Class Name').fill(name);
  if (classCode !== undefined) await dialog.getByLabel('Class Code').fill(classCode);
  return dialog;
}

async function sectionCounts(page) {
  const texts = await page.locator('tbody tr').allInnerTexts();
  return texts.map((t) => t.match(/(\d+) sections?/)).filter(Boolean).map((m) => Number(m[1]));
}

test.describe('Masters F03 classes and sections (web)', () => {
  test('TC-MST-03-E01 list shows the seeded classes with actions', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await expect(page.getByText('Classes & Sections').first()).toBeVisible();
    for (const [name, short] of SEEDED) {
      const row = classRow(page, name);
      await expect(row).toBeVisible();
      await expect(row.getByRole('cell', { name: short, exact: true }).last()).toBeVisible();
      await expect(row).toContainText('2 sections');
      await expect(row).toContainText('Active');
    }
    for (const name of ['Columns', 'Export', 'Add Class & Sections']) {
      await expect(page.getByRole('button', { name })).toBeVisible();
    }
    const row = classRow(page, 'Class 1');
    for (const name of ['Add Section', 'Edit Class', 'Delete Class']) {
      await expect(row.getByRole('button', { name })).toBeVisible();
    }
  });

  test('TC-MST-03-E02 search by class name', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await page.getByPlaceholder('Search classes...').fill('Class 1');
    await expect(page.locator('tbody tr')).toHaveCount(1);
    await expect(classRow(page, 'Class 1')).toBeVisible();
    const summary = page.getByText(/^1 of \d+ results$/);
    await expect(summary).toBeVisible();
    const total = Number((await summary.innerText()).match(/of (\d+)/)[1]);
    expect(total).toBeGreaterThanOrEqual(8);
  });

  test('TC-MST-03-E03 sort by section count', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA C9');
    await createClassViaApi(api, cleanup, name);
    await signIn('admin');
    await open(page);
    const header = page.getByRole('columnheader', { name: 'Sections', exact: true });
    await header.click();
    await expect.poll(async () => {
      const counts = await sectionCounts(page);
      return counts.every((c, i) => i === 0 || counts[i - 1] <= c);
    }).toBe(true);
    await header.click();
    await expect.poll(async () => {
      const counts = await sectionCounts(page);
      return counts.every((c, i) => i === 0 || counts[i - 1] >= c);
    }).toBe(true);
    const names = (await page.locator('tbody tr').allInnerTexts()).map((t) => t.split('\t').map((c) => c.trim()));
    const qaIndex = names.findIndex((cells) => cells.includes(name));
    const twoIndex = names.findIndex((cells) => cells.includes('2 sections'));
    if (qaIndex >= 0 && twoIndex >= 0) expect(qaIndex).toBeLessThan(twoIndex);
  });

  test('TC-MST-03-E04 expand shows section tiles or the empty message', async ({ page, signIn, api, cleanup }) => {
    const empty = unique('QA C10');
    await createClassViaApi(api, cleanup, empty, []);
    await signIn('admin');
    await open(page);
    await classRow(page, 'Class 1').getByRole('button').first().click();
    const details = page.getByRole('row').filter({ hasText: 'Sections:' }).first();
    await expect(details).toBeVisible();
    for (const s of ['1-A', '1-B']) await expect(details.getByText(s, { exact: true })).toBeVisible();
    await expect(details.getByText('Active', { exact: true })).toHaveCount(2);
    await page.getByPlaceholder('Search classes...').fill(empty);
    await classRow(page, empty).getByRole('button').first().click();
    await expect(page.getByText('No sections found')).toBeVisible();
  });

  test('TC-MST-03-E05 column selector keeps at least one column', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await page.getByRole('button', { name: 'Columns' }).click();
    await page.getByRole('menuitemcheckbox', { name: 'Status', exact: true }).click();
    await expect(page.getByRole('columnheader', { name: 'Status', exact: true })).toHaveCount(0);
    for (const name of ['Class Name', 'Class Code', 'Sections']) {
      await page.getByRole('menuitemcheckbox', { name, exact: true }).click();
    }
    let visible = 0;
    for (const name of ['Class Name', 'Class Code', 'Sections', 'Status']) {
      visible += await page.getByRole('columnheader', { name, exact: true }).count();
    }
    expect(visible).toBe(1);
  });

  test('TC-MST-03-E06 create a class with generated sections', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA C9');
    cleanup(async () => {
      const created = await findClass(api, name);
      if (created) await api('DELETE', `/masters/class_sections/${created.id}`);
    });
    await signIn('admin');
    await open(page);
    const dialog = await openWizard(page, name, code());
    await dialog.getByRole('button', { name: 'Next' }).click();
    await expect(dialog.getByRole('heading', { name: 'Add Sections' })).toBeVisible();
    await dialog.getByLabel('From:').fill('A');
    await dialog.getByLabel('To:').fill('C');
    await dialog.getByRole('button', { name: 'Generate Sections' }).click();
    await toast(page, 'Generated 3 sections from A to C');
    await dialog.getByRole('button', { name: 'View' }).click();
    await expect(dialog.getByRole('heading', { name: 'Summary' })).toBeVisible();
    await expect(dialog.getByRole('listitem')).toHaveText(['A', 'B', 'C']);
    await dialog.getByRole('button', { name: 'Submit' }).click();
    await toast(page, 'Class and sections created successfully!');
    await expect(classRow(page, name)).toContainText('3 sections');
  });

  test('TC-MST-03-E07 next stays disabled until name and code are filled', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    const dialog = await openWizard(page, 'QA C10');
    const next = dialog.getByRole('button', { name: 'Next' });
    await expect(next).toBeDisabled();
    await dialog.getByLabel('Class Name').fill('');
    await dialog.getByLabel('Class Code').fill('QC10');
    await expect(next).toBeDisabled();
    await dialog.getByLabel('Class Name').fill('QA C10');
    await expect(next).toBeEnabled();
  });

  test('TC-MST-03-E08 generator rejects a reversed range', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    const dialog = await openWizard(page, 'QA C10', 'QC10');
    await dialog.getByRole('button', { name: 'Next' }).click();
    await dialog.getByLabel('From:').fill('D');
    await dialog.getByLabel('To:').fill('A');
    await dialog.getByRole('button', { name: 'Generate Sections' }).click();
    await toast(page, 'Start letter must come before end letter');
    await expect(dialog.getByText('Total sections: 1')).toBeVisible();
    await expect(dialog.getByPlaceholder('Section 1')).toHaveValue('');
  });

  test('TC-MST-03-E09 duplicate class name shows the failure toast', async ({ page, signIn, api, cleanup }) => {
    cleanup(async () => {
      const res = await api('GET', '/masters/class_sections/read_all');
      for (const c of (res.data || []).filter((x) => x.name === 'Class 1' && x.short_code === 'QX1')) {
        await api('DELETE', `/masters/class_sections/${c.id}`);
      }
    });
    await signIn('admin');
    await open(page);
    const dialog = await openWizard(page, 'Class 1', 'QX1');
    await dialog.getByRole('button', { name: 'Next' }).click();
    await dialog.getByLabel('From:').fill('A');
    await dialog.getByLabel('To:').fill('B');
    await dialog.getByRole('button', { name: 'Generate Sections' }).click();
    await dialog.getByRole('button', { name: 'View' }).click();
    await dialog.getByRole('button', { name: 'Submit' }).click();
    await toast(page, 'Failed to create class and sections:');
    await expect(page.getByText(/Failed to create class and sections: .*already exists/)).toBeVisible();
    await expect(classRow(page, 'Class 1')).toHaveCount(1);
  });

  test('TC-MST-03-E10 export CSV joins sections with semicolons', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await page.getByRole('button', { name: 'Export' }).click();
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.getByRole('menuitem', { name: 'Export to CSV' }).click(),
    ]);
    expect(download.suggestedFilename()).toBe('classes_sections_data.csv');
    const lines = fs.readFileSync(await download.path(), 'utf8').trim().split('\n');
    expect(lines[0]).toBe('Class Name,Class Code,Sections,Status');
    expect(lines).toContain('"Class 1","C1","1-A; 1-B","Active"');
  });

  test('TC-MST-03-E11 teacher sees a read-only list', async ({ page, signIn }) => {
    await signIn('teacher');
    await open(page);
    await expect(page.getByRole('button', { name: 'Columns' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Export' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Add Class & Sections' })).toHaveCount(0);
    for (const name of ['Add Section', 'Edit Class', 'Delete Class']) {
      await expect(page.getByRole('button', { name })).toHaveCount(0);
    }
  });
});
