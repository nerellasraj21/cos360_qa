// TTC F01-F04 holidays, web (P1). Baseline: qa_manual seeded holidays, today 2026-10-07.
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { createHoliday, findHoliday } = require('./ttc-kit');

const ROUTE = '/masters/holidays';

async function openMonth(page, signIn) {
  await signIn('admin');
  await page.goto(ROUTE);
  await expect(page.getByText('Gandhi Jayanti').first()).toBeVisible({ timeout: 20_000 });
}

test.describe('TTC F01-F04 holidays (web)', () => {
  test.describe.configure({ mode: 'serial' });
  test('TC-TTC-01-E01 month view shows seeded holidays', async ({ page, signIn }) => {
    await openMonth(page, signIn);
    await expect(page.getByRole('button', { name: 'Month' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'All Events' })).toBeVisible();
    await expect(page.getByRole('button', { name: '<', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '>', exact: true })).toBeVisible();
    await expect(page.getByRole('combobox').filter({ has: page.getByRole('option', { name: 'October' }) })).toHaveValue('9');
    await expect(page.getByRole('combobox').filter({ has: page.getByRole('option', { name: '2031' }) })).toHaveValue('2026');
    for (const d of ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']) {
      await expect(page.getByText(d, { exact: true }).first()).toBeVisible();
    }
    await expect(page.getByText('National holiday').first()).toBeVisible();
    await expect(page.getByText('Dasara Vacation').first()).toBeVisible();
    await expect(page.getByText('Dasara festival break').first()).toBeVisible();
  });

  test('TC-TTC-01-E03 all events list', async ({ page, signIn }) => {
    await openMonth(page, signIn);
    await page.getByRole('button', { name: 'All Events' }).click();
    await expect(page.getByText('Filters')).toBeVisible();
    await expect(page.getByPlaceholder('Search events...')).toBeVisible();
    for (const h of ['S.No.', 'Title', 'Description', 'Start Date', 'End Date', 'Color', 'Actions']) {
      await expect(page.getByRole('columnheader', { name: h })).toBeVisible();
    }
    expect(await page.locator('tbody tr').count()).toBeGreaterThanOrEqual(8);
    const gandhi = page.getByRole('row').filter({ hasText: 'Gandhi Jayanti' });
    await expect(gandhi).toContainText('2026-10-02');
    await expect(page.getByRole('row').filter({ hasText: 'Dasara Vacation' })).toContainText('2026-10-24');
    await expect(page.getByRole('button', { name: 'Prev' })).toBeDisabled();
    await expect(page.getByText('Page 1')).toBeVisible();
  });

  test('TC-TTC-02-E02 create from a day cell', async ({ page, signIn, api, cleanup }) => {
    test.fail(true, 'UI-TTC-01: creating from a day cell shows "Failed to create holiday" and sends no request because the mutation is gated on the missing holidays:create alias (doc says it works without it)');
    const name = 'QA Day One';
    const old = await findHoliday(api, name);
    if (old) await api('DELETE', `/masters/holidays/${old.id}`);
    await openMonth(page, signIn);
    await page.getByText('28', { exact: true }).last().click({ force: true });
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText('Add Event').first()).toBeVisible();
    const dates = dialog.locator('input[type=date]');
    await expect(dates.nth(0)).toHaveValue('2026-10-28');
    await expect(dates.nth(1)).toHaveValue('2026-10-28');
    await dialog.getByLabel('Title').fill(name);
    await dialog.getByRole('button', { name: 'Add', exact: true }).click();
    await toast(page, 'Holiday created!');
    const created = await findHoliday(api, name);
    expect(created).toBeTruthy();
    cleanup(() => api('DELETE', `/masters/holidays/${created.id}`));
    expect(created.is_active).toBe(true);
    expect(created.color.toLowerCase()).toBe('#2563eb');
    await expect(page.getByText(name).first()).toBeVisible();
  });

  test('TC-TTC-03-E04 drag a chip to another day', async ({ page, signIn, api, cleanup }) => {
    test.fail(true, 'UI-TTC-02: dragging a chip to another day shows "Failed to update holiday" and sends no request because the mutation is gated on the missing holidays:update alias (doc says it works without it)');
    const name = unique('QA Drag');
    const h = await createHoliday(api, cleanup, name);
    await openMonth(page, signIn);
    const chip = page.getByText(name).first();
    await expect(chip).toBeVisible();
    await chip.dragTo(page.getByText('30', { exact: true }).last());
    await toast(page, 'Holiday updated!');
    await expect.poll(async () => (await findHoliday(api, name)).start_date).toBe('2026-10-30');
    expect((await findHoliday(api, name)).end_date).toBe('2026-10-30');
    await page.getByRole('button', { name: 'All Events' }).click();
    const rowEl = page.getByRole('row').filter({ hasText: name });
    await expect(rowEl).toContainText('2026-10-30');
    expect(h.id).toBeTruthy();
  });
});
