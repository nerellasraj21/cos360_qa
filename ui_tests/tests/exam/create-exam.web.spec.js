// Exam F06 Create exam, list and view exams, web (P1). Own QA class; seeded exams are read only.
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const kit = require('./_kit');

async function pick(page, label, option) {
  await page.getByText(label, { exact: true }).locator('xpath=..').getByRole('combobox').click();
  await page.getByRole('option', { name: option, exact: true }).click();
}

async function dropExamNamed(api, name) {
  const res = await api('GET', '/exams');
  for (const e of kit.rows(res).filter((x) => x.exam_name === name)) {
    if (e.status === 'published') await api('POST', `/exams/${e.id}/unlock`, { body: { reason: 'QA cleanup' } });
    await api('DELETE', `/exams/${e.id}`);
  }
}

async function addSubject(page, subject, components) {
  await page.getByText(subject, { exact: true }).click();
  for (let i = 0; i < components.length; i += 1) {
    await page.getByRole('button', { name: 'Add Component' }).click();
    const row = page.locator('tbody tr').filter({ has: page.getByPlaceholder('Written') }).nth(i);
    await row.getByPlaceholder('Written').fill(components[i][0]);
    await row.getByRole('spinbutton').first().fill(String(components[i][1]));
  }
  await page.getByText(subject, { exact: true }).click();
}

test.describe('Exam F06 create, list and view exams (web)', () => {
  test('TC-EXM-06-E01 create an exam through the wizard', async ({ page, signIn, api, cleanup }) => {
    test.fail(true, 'UI-EXM-02: after Create Exam the redirect to /exam/exams shows the cached list without the new exam until the page is reloaded (no GET /exams after the POST)');
    test.setTimeout(120_000);
    const klass = await kit.createQaClass(api, cleanup);
    const name = unique('QA FA1');
    cleanup(() => dropExamNamed(api, name));
    await signIn('admin');
    await page.goto('/exam/exams');
    await page.getByRole('button', { name: /Create Exam/ }).first().click();
    await page.getByPlaceholder('FA1 2024-25').fill(name);
    await pick(page, 'Board *', 'State');
    await pick(page, 'Nature *', 'Formative');
    await pick(page, 'Exam Grade Scheme', 'Standard Percentage Grading');
    await page.getByRole('button', { name: 'Next: Class & Sections' }).click();
    await page.getByRole('combobox').last().click();
    await page.keyboard.type(klass.name);
    await page.getByRole('option', { name: klass.dash }).click();
    await page.keyboard.press('Escape');
    await page.getByRole('button', { name: 'Next: Subject Config' }).click();
    await addSubject(page, 'Mathematics', [['Written', 80], ['Oral', 20]]);
    await addSubject(page, 'English', [['Written', 100]]);
    await addSubject(page, 'Environmental Studies', [['Written', 100]]);
    await page.getByRole('button', { name: 'Next: Exam Dates (Optional)' }).click();
    await page.getByRole('button', { name: 'Review & Submit', exact: true }).click();
    await page.getByRole('button', { name: 'Create Exam', exact: true }).click();
    await toast(page, 'Exam created successfully');
    await expect(page).toHaveURL(/\/exam\/exams$/);
    const row = page.getByRole('row').filter({ hasText: name });
    await expect(row).toContainText(/active/i);
    await expect(row).toContainText('3 subjects');
  });
  test('TC-EXM-06-E16 exam dashboard counts and status tables', async ({ page, signIn, api }) => {
    await signIn('admin');
    await page.goto('/exam');
    await expect(page.getByText('Exam Management').first()).toBeVisible();
    await expect(page.getByText('Academic Year: 2026-2027')).toBeVisible();
    for (const link of ['All Exams', 'Mark Entry', 'Results', 'Hall Tickets', 'Settings']) {
      await expect(page.getByRole('button', { name: link }).or(page.getByRole('link', { name: link })).first()).toBeVisible();
    }
    await expect(page.getByRole('button', { name: /New Exam/ })).toBeVisible();
    await expect(page.getByText('ACTIVE EXAMS')).toBeVisible();
    await expect(page.getByText('PUBLISHED EXAMS')).toBeVisible();
    await expect(page.getByRole('row').filter({ hasText: 'Half Yearly Examination 2026' })).toBeVisible();
    await expect(page.getByRole('row').filter({ hasText: 'Unit Test 1 - Class 1B' })).toBeVisible();
    await expect
      .poll(async () => {
        const text = (await page.locator('main').innerText()).replace(/\s+/g, ' ');
        const m = text.match(/(\d+) Draft (\d+) Active (\d+) Locked (\d+) Published/);
        const year = await kit.workingYear(api);
        const list = kit.rows(await api('GET', `/exams?academic_year_id=${year.id}`));
        const count = (s) => list.filter((e) => e.status === s).length;
        return m ? [Number(m[1]), Number(m[2]), Number(m[3]), Number(m[4])].join() === [count('draft'), count('active'), count('locked'), count('published')].join() : false;
      }, { timeout: 15_000 })
      .toBe(true);
    const text = (await page.locator('main').innerText()).replace(/\s+/g, ' ');
    const m = text.match(/(\d+) Draft (\d+) Active (\d+) Locked (\d+) Published/);
    expect(Number(m[2])).toBeGreaterThanOrEqual(1);
    expect(Number(m[4])).toBeGreaterThanOrEqual(2);
  });

  test('TC-EXM-06-E17 seeded published exam detail overview', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/exam/exams');
    await page.getByRole('row').filter({ hasText: 'Unit Test 1 - Class 1B' }).click();
    await expect(page.getByRole('heading', { name: 'Unit Test 1 - Class 1B' })).toBeVisible();
    await expect(page.getByText(/^published$/i).first()).toBeVisible();
    await expect(page.getByText(/State\s*\S\s*primary\s*\S\s*Unit Test\s*\S\s*formative/)).toBeVisible();
    for (const tab of ['Overview', 'Dates', 'Marks', 'Permissions', 'Audit Log']) {
      await expect(page.getByRole('tab', { name: tab }).or(page.getByRole('button', { name: tab })).first()).toBeVisible();
    }
    for (const card of ['Academic Year', 'Mark Entry Deadline', 'Hall Ticket Attendance', 'Attendance Period', 'Hall Ticket Status']) {
      await expect(page.getByText(card, { exact: true })).toBeVisible();
    }
    await expect(page.getByText('Not Published', { exact: true })).toBeVisible();
    await expect(page.getByText('Configured Subjects')).toBeVisible();
    await expect(page.getByText(/Class 1\s*\S\s*1-B/)).toBeVisible();
    for (const subject of ['English', 'Hindi', 'Telugu', 'Mathematics', 'Environmental Studies']) {
      await expect(page.getByText(subject, { exact: true }).first()).toBeVisible();
    }
  });
});
