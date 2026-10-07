// TTC F01-F04 holidays, mobile (P1). Baseline: qa_manual seeded holidays, today 2026-10-07 (the Expo web build runs in the local clock).
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { createHoliday, findHoliday } = require('./ttc-kit');

const ROUTE = '/masters/holidays';

async function open(page, signIn) {
  await signIn('admin');
  await page.goto(ROUTE, { timeout: 180_000 });
  await expect(page.getByText('Gandhi Jayanti').first()).toBeVisible({ timeout: 60_000 });
}

function vis(page, text, exact = true) {
  return page.getByText(text, { exact }).locator('visible=true');
}

async function tapSwatch(page, rgb) {
  const box = await page.evaluate((color) => {
    const els = [...document.querySelectorAll('div')].filter((e) => {
      const r = e.getBoundingClientRect();
      return e.offsetWidth > 20 && e.offsetWidth < 50 && Math.abs(r.width - r.height) < 2 && getComputedStyle(e).backgroundColor === color;
    });
    const el = els[els.length - 1];
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
  }, rgb);
  expect(box).toBeTruthy();
  await page.mouse.click(box.x, box.y);
}

test.describe('TTC F01-F04 holidays (mobile)', () => {
  test.describe.configure({ mode: 'serial' });
  test('TC-TTC-01-E12 holidays screen', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/masters', { timeout: 180_000 });
    await vis(page, 'Holidays').first().click({ timeout: 60_000 });
    await expect(vis(page, 'Gandhi Jayanti').first()).toBeVisible({ timeout: 60_000 });
    await expect(vis(page, 'Month').first()).toBeVisible();
    await expect(vis(page, 'All Events').first()).toBeVisible();
    await expect(vis(page, 'Add Event').first()).toBeVisible();
    await expect(vis(page, 'October 2026', false).first()).toBeVisible();
    for (const d of ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']) {
      await expect(vis(page, d).first()).toBeVisible();
    }
    await expect(vis(page, 'Dasara Vacation').first()).toBeVisible();
    await expect(page.getByLabel('Go back').locator('visible=true').first()).toBeVisible();
    await expect(page.getByLabel('Previous month').locator('visible=true').first()).toBeVisible();
    await expect(page.getByLabel('Next month').locator('visible=true').first()).toBeVisible();
  });

  test('TC-TTC-02-E07 create a multi-day green event', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Picnic');
    await open(page, signIn);
    await vis(page, 'Add Event').first().click();
    await page.getByPlaceholder('Event title').locator('visible=true').first().fill(name);
    await page.getByLabel('Select end date').locator('visible=true').first().click();
    await expect(vis(page, 'Select End Date')).toBeVisible();
    await vis(page, 'Day').last().click();
    await vis(page, 'Day').last().click();
    await vis(page, 'Select').last().click();
    await tapSwatch(page, 'rgb(22, 163, 74)');
    await page.getByPlaceholder('Event description').locator('visible=true').first().fill('QA outing');
    await vis(page, 'Add').last().click();
    await toast(page, 'Holiday created successfully');
    const created = await findHoliday(api, name);
    expect(created).toBeTruthy();
    cleanup(() => api('DELETE', `/masters/holidays/${created.id}`));
    expect(created.is_active).toBe(true);
    expect(created.color.toLowerCase()).toBe('#16a34a');
    expect(created.description).toBe('QA outing');
    expect(created.end_date > created.start_date).toBe(true);
    await expect(vis(page, name).first()).toBeVisible();
    await vis(page, 'All Events').first().click();
    await expect(vis(page, name).first()).toBeVisible();
  });

  test('TC-TTC-03-E07 edit the description', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Edit');
    await createHoliday(api, cleanup, name, { start_date: '2026-10-12', end_date: '2026-10-13' });
    await open(page, signIn);
    await vis(page, name).first().click();
    const desc = page.getByPlaceholder('Event description').locator('visible=true').first();
    await expect(desc).toHaveValue('QA outing');
    await desc.fill('QA outing updated');
    await vis(page, 'Save').last().click();
    await toast(page, 'Holiday updated successfully');
    await expect.poll(async () => (await findHoliday(api, name)).description).toBe('QA outing updated');
    await vis(page, 'All Events').first().click();
    await expect(vis(page, 'QA outing updated', false).first()).toBeVisible();
  });

  test('TC-TTC-04-E04 delete from the edit dialog', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Del');
    await createHoliday(api, cleanup, name, { start_date: '2026-10-12', end_date: '2026-10-13' });
    await open(page, signIn);
    await vis(page, name).first().click();
    await vis(page, 'Delete').last().click();
    await expect(vis(page, 'Delete Event').first()).toBeVisible();
    await expect(vis(page, `Are you sure you want to delete "${name}"?`, false).first()).toBeVisible();
    await vis(page, 'Delete').last().click();
    await toast(page, 'Holiday deleted successfully');
    await expect.poll(async () => (await findHoliday(api, name)).is_active).toBe(false);
    await expect(vis(page, name)).toHaveCount(0);
    await vis(page, 'All Events').first().click();
    await expect(vis(page, name)).toHaveCount(0);
  });
});
