// Masters F01 Academic years, web. Baseline: qa_manual seeded year "2026-2027" (active).
const fs = require('fs');
const { test, expect, unique, toast } = require('../../helpers/fixtures');

const ROUTE = '/masters/academicyears';

async function findYear(api, title) {
  const res = await api('GET', '/masters/academic_years/?active_only=false&limit=1000');
  const rows = Array.isArray(res.data) ? res.data : res.data.items || [];
  return rows.find((y) => y.title === title);
}

async function createYearViaApi(api, cleanup, title, start = '2033-04-01', end = '2034-03-31') {
  const res = await api('POST', '/masters/academic_years/', { body: { title, start_date: start, end_date: end, is_active: false } });
  expect([200, 201]).toContain(res.status);
  cleanup(() => api('DELETE', `/masters/academic_years/${res.data.id}/permanent`));
  return res.data;
}

function rowsPerPage(page) {
  return page.getByRole('combobox').filter({ has: page.getByRole('option', { name: '100' }) });
}

function row(page, title) {
  return page.getByRole('row').filter({ hasText: title });
}

test.describe('Masters F01 academic years (web)', () => {
  test('TC-MST-01-E01 list shows the seeded year with actions', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto(ROUTE);
    await expect(page.getByText('Academic Years').first()).toBeVisible();
    for (const header of ['S.No.', 'Title', 'Start Date', 'End Date', 'Active', 'Actions']) {
      await expect(page.getByRole('columnheader', { name: header, exact: true })).toBeVisible();
    }
    const seeded = row(page, '2026-2027');
    await expect(seeded).toBeVisible();
    await expect(seeded).toContainText('Active');
    await expect(page.getByRole('button', { name: 'Add Academic Year' })).toBeVisible();
    await expect(page.getByRole('button', { name: /Export/ })).toBeVisible();
    await expect(seeded.getByRole('button', { name: 'Edit' })).toBeVisible();
    await expect(seeded.getByRole('button', { name: 'Delete' })).toBeVisible();
  });

  test('TC-MST-01-E05 create an inactive year', async ({ page, signIn, api, cleanup }) => {
    const title = unique('QA 2033-34');
    await signIn('admin');
    await page.goto(ROUTE);
    await page.getByRole('button', { name: 'Add Academic Year' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText('Add New Academic Year')).toBeVisible();
    await dialog.getByLabel('Title').fill(title);
    await dialog.getByLabel('Start Date').fill('2033-04-01');
    await dialog.getByLabel('End Date').fill('2034-03-31');
    const active = dialog.getByLabel('Active');
    if (await active.isChecked()) await active.uncheck();
    await dialog.getByRole('button', { name: 'Add Academic Year' }).click();
    await toast(page, 'Academic year created!');
    const created = await findYear(api, title);
    expect(created).toBeTruthy();
    cleanup(() => api('DELETE', `/masters/academic_years/${created.id}/permanent`));
    expect(created.is_active).toBe(false);
    await expect(dialog).toBeHidden();
    const seeded = await findYear(api, '2026-2027');
    expect(seeded.is_active).toBe(true);
  });

  test('TC-MST-01-E06 title is required', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto(ROUTE);
    await page.getByRole('button', { name: 'Add Academic Year' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Start Date').fill('2033-04-01');
    await dialog.getByLabel('End Date').fill('2034-03-31');
    let posted = false;
    page.on('request', (r) => { if (r.method() === 'POST' && r.url().includes('/academic_years')) posted = true; });
    await dialog.getByRole('button', { name: 'Add Academic Year' }).click();
    await page.waitForTimeout(1000);
    expect(posted).toBe(false);
    await expect(dialog).toBeVisible();
  });

  test('TC-MST-01-E07 duplicate title shows the failure toast', async ({ page, signIn }) => {
    test.fail(true, 'UI-MST-01: the create dialog closes even when the save fails (onCreate does not wait for the mutation)');
    await signIn('admin');
    await page.goto(ROUTE);
    await page.getByRole('button', { name: 'Add Academic Year' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Title').fill('2026-2027');
    await dialog.getByLabel('Start Date').fill('2033-04-01');
    await dialog.getByLabel('End Date').fill('2034-03-31');
    const active = dialog.getByLabel('Active');
    if (await active.isChecked()) await active.uncheck();
    await dialog.getByRole('button', { name: 'Add Academic Year' }).click();
    await toast(page, 'Failed to create academic year');
    await expect(dialog).toBeVisible();
  });

  test('TC-MST-01-E08 inline edit saves a new title', async ({ page, signIn, api, cleanup }) => {
    const title = unique('QA 2033-34');
    await createYearViaApi(api, cleanup, title);
    await signIn('admin');
    await page.goto(ROUTE);
    await page.getByPlaceholder('Search...').fill(title);
    const target = row(page, title);
    await target.getByRole('button', { name: 'Edit' }).click();
    const input = page.locator('tbody tr').first().getByRole('textbox').first();
    await expect(input).toHaveValue(title);
    await input.fill(`${title} B`);
    await input.press('Enter');
    await toast(page, 'Academic year updated!');
    expect(await findYear(api, `${title} B`)).toBeTruthy();
  });

  test('TC-MST-01-E09 inline edit cancel keeps the title', async ({ page, signIn, api, cleanup }) => {
    const title = unique('QA 2033-34');
    await createYearViaApi(api, cleanup, title);
    await signIn('admin');
    await page.goto(ROUTE);
    await page.getByPlaceholder('Search...').fill(title);
    await row(page, title).getByRole('button', { name: 'Edit' }).click();
    const input = page.locator('tbody tr').first().getByRole('textbox').first();
    await expect(input).toHaveValue(title);
    let put = false;
    page.on('request', (r) => { if (r.method() === 'PUT' && r.url().includes('/academic_years')) put = true; });
    await input.fill('QA changed');
    await input.press('Escape');
    await page.waitForTimeout(800);
    expect(put).toBe(false);
    expect(await findYear(api, title)).toBeTruthy();
  });

  test('TC-MST-01-E11 delete deactivates the year', async ({ page, signIn, api, cleanup }) => {
    const title = unique('QA 2033-34');
    await createYearViaApi(api, cleanup, title);
    await api('PUT', `/masters/academic_years/${(await findYear(api, title)).id}`, { body: { is_active: false } });
    await signIn('admin');
    await page.goto(ROUTE);
    await page.getByPlaceholder('Search...').fill(title);
    await row(page, title).getByRole('button', { name: 'Delete' }).click();
    await expect(page.getByText('Delete Row?')).toBeVisible();
    await page.getByRole('button', { name: 'Cancel' }).click();
    await expect(row(page, title)).toBeVisible();
    await row(page, title).getByRole('button', { name: 'Delete' }).click();
    await page.getByRole('button', { name: 'Delete', exact: true }).last().click();
    await toast(page, 'Academic year deleted!');
    const after = await findYear(api, title);
    expect(after).toBeTruthy();
    expect(after.is_active).toBe(false);
  });

  test('TC-MST-01-E13 teacher sees a read-only list', async ({ page, signIn }) => {
    await signIn('teacher');
    await page.goto(ROUTE);
    await expect(row(page, '2026-2027')).toBeVisible();
    await expect(page.getByRole('button', { name: /Export/ })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Add Academic Year' })).toHaveCount(0);
    await expect(row(page, '2026-2027').getByRole('button', { name: 'Edit' })).toHaveCount(0);
    await expect(row(page, '2026-2027').getByRole('button', { name: 'Delete' })).toHaveCount(0);
  });

  test('TC-MST-01-E14 student and parent have no Masters menu', async ({ page, signIn }) => {
    for (const role of ['student', 'parent']) {
      await page.context().clearCookies();
      await signIn(role);
      await page.goto('/');
      await expect(page.getByRole('link', { name: 'Dashboard' }).or(page.getByText('Dashboard')).first()).toBeVisible();
      await expect(page.getByRole('link', { name: 'Masters', exact: true })).toHaveCount(0);
    }
  });

  test('TC-MST-01-E02 search filters the current page and clearing restores it', async ({ page, signIn, api, cleanup }) => {
    const title = unique('QA 2033-34');
    await createYearViaApi(api, cleanup, title);
    await signIn('admin');
    await page.goto(ROUTE);
    await rowsPerPage(page).selectOption('100');
    await expect(row(page, '2026-2027')).toBeVisible();
    await expect(row(page, title)).toBeVisible();
    const before = await page.locator('tbody tr').count();
    const search = page.getByPlaceholder('Search...');
    await search.fill(title);
    await expect(page.locator('tbody tr')).toHaveCount(1);
    await expect(page.locator('tbody tr').first()).toContainText(title);
    await expect(page.getByText(`1 of ${before} results`)).toBeVisible();
    await search.fill('');
    await expect(page.locator('tbody tr')).toHaveCount(before);
    await expect(row(page, '2026-2027')).toBeVisible();
  });

  test('TC-MST-01-E03 title header cycles ascending, descending and original order', async ({ page, signIn, api, cleanup }) => {
    const a = unique('QA 2033-34 A');
    const b = unique('QA 2033-34 B');
    await createYearViaApi(api, cleanup, a);
    await createYearViaApi(api, cleanup, b, '2034-04-01', '2035-03-31');
    await signIn('admin');
    await page.goto(ROUTE);
    await rowsPerPage(page).selectOption('100');
    await expect(row(page, a)).toBeVisible();
    await expect(row(page, b)).toBeVisible();
    const titles = async () => {
      const texts = await page.locator('tbody tr').allInnerTexts();
      return texts.map((t) => t.split('\t').map((c) => c.trim())[2]);
    };
    const header = page.getByRole('columnheader', { name: 'Title', exact: true });
    const original = await titles();
    const icon0 = await header.innerHTML();
    const sorted = [...original].sort((x, y) => x.localeCompare(y, undefined, { numeric: true }));
    await header.click();
    await expect.poll(titles).toEqual(sorted);
    const icon1 = await header.innerHTML();
    await header.click();
    await expect.poll(titles).toEqual([...sorted].reverse());
    const icon2 = await header.innerHTML();
    await header.click();
    await expect.poll(titles).toEqual(original);
    expect(icon1).not.toBe(icon0);
    expect(icon2).not.toBe(icon1);
    expect(await header.innerHTML()).toBe(icon0);
  });

  test('TC-MST-01-E04 @serial pagination with five rows per page', async ({ page, signIn, api, cleanup }) => {
    for (let i = 0; i < 6; i += 1) {
      const y = 2031 + i;
      await createYearViaApi(api, cleanup, unique(`QA ${y}-${String(y + 1).slice(2)}`), `${y}-04-01`, `${y + 1}-03-31`);
    }
    const all = await api('GET', '/masters/academic_years/?active_only=false&limit=1000');
    const total = all.data.total_count;
    expect(total).toBeGreaterThanOrEqual(7);
    await signIn('admin');
    await page.goto(ROUTE);
    await expect(page.locator('tbody tr')).toHaveCount(5);
    await expect(page.getByRole('button', { name: 'Previous' })).toBeDisabled();
    await expect(page.getByText(/^1-5 of \d+$/)).toBeVisible();
    const firstPage = await page.locator('tbody tr').allInnerTexts();
    await page.getByRole('button', { name: 'Next' }).click();
    await expect(page.locator('tbody tr').first().getByRole('cell').first()).toHaveText('6');
    const secondPage = await page.locator('tbody tr').allInnerTexts();
    for (const text of secondPage) expect(firstPage).not.toContain(text);
    await expect(page.getByRole('button', { name: 'Previous' })).toBeEnabled();
    await rowsPerPage(page).selectOption('10');
    await expect(page.locator('tbody tr')).toHaveCount(Math.min(total, 10));
    if (total <= 10) await expect(page.getByText(`1-${total} of ${total}`)).toBeVisible();
  });

  test('TC-MST-01-E10 @serial activating a year deactivates the others', async ({ page, signIn, api, cleanup }) => {
    const title = unique('QA 2033-34');
    const created = await createYearViaApi(api, cleanup, title);
    const seeded = await findYear(api, '2026-2027');
    expect(seeded.is_active).toBe(true);
    cleanup(async () => {
      const now = await findYear(api, '2026-2027');
      if (!now.is_active) await api('PUT', `/masters/academic_years/${seeded.id}`, { body: { is_active: true } });
      await api('PUT', `/masters/academic_years/${created.id}`, { body: { is_active: false } });
    });
    await signIn('admin');
    await page.goto(ROUTE);
    await rowsPerPage(page).selectOption('100');
    const editing = page.getByRole('row').filter({ has: page.getByRole('textbox') });
    await row(page, title).getByRole('button', { name: 'Edit' }).click();
    await editing.getByRole('checkbox').check();
    await editing.getByRole('button').first().click();
    await toast(page, 'Academic year updated!');
    await page.reload();
    await rowsPerPage(page).selectOption('100');
    await expect(row(page, title)).not.toContainText('Inactive');
    await expect(row(page, title)).toContainText('Active');
    await expect(row(page, '2026-2027')).toContainText('Inactive');
    await row(page, '2026-2027').getByRole('button', { name: 'Edit' }).click();
    await editing.getByRole('checkbox').check();
    await editing.getByRole('button').first().click();
    await toast(page, 'Academic year updated!');
    await page.reload();
    await rowsPerPage(page).selectOption('100');
    await expect(row(page, '2026-2027')).not.toContainText('Inactive');
    await expect(row(page, title)).toContainText('Inactive');
    const active = await api('GET', '/masters/academic_years/active');
    expect(active.data.map((y) => y.title)).toEqual(['2026-2027']);
  });

  test('TC-MST-01-E12 export CSV with only Title and Active columns', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto(ROUTE);
    await rowsPerPage(page).selectOption('100');
    await expect(row(page, '2026-2027')).toBeVisible();
    const exportButton = page.getByRole('button', { name: 'Export' });
    await exportButton.locator('xpath=preceding-sibling::button[1]').click();
    for (const name of ['ID', 'Start Date', 'End Date']) {
      await page.getByRole('menuitemcheckbox', { name, exact: true }).click();
    }
    await expect(page.getByRole('menuitemcheckbox', { name: 'Title', exact: true })).toHaveAttribute('aria-checked', 'true');
    await expect(page.getByRole('menuitemcheckbox', { name: 'Active', exact: true })).toHaveAttribute('aria-checked', 'true');
    await page.keyboard.press('Escape');
    const listed = await page.locator('tbody tr').count();
    await exportButton.click();
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.getByRole('menuitem', { name: 'Export to CSV' }).click(),
    ]);
    expect(download.suggestedFilename()).toBe('academic_years_data.csv');
    const lines = fs.readFileSync(await download.path(), 'utf8').trim().split('\n');
    expect(lines[0]).toBe('Title,Active');
    expect(lines.length - 1).toBe(listed);
    expect(lines).toContain('"2026-2027","true"');
  });
});
