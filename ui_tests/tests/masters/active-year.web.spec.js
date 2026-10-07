// Masters F02 Active year and working-year selection, web. Baseline: qa_manual seeded year "2026-2027" (active).
const { test, expect, unique } = require('../../helpers/fixtures');
const { credentials } = require('../../helpers/api');

async function createYearViaApi(api, cleanup, title, start = '2033-04-01', end = '2034-03-31') {
  const res = await api('POST', '/masters/academic_years/', { body: { title, start_date: start, end_date: end, is_active: false } });
  expect([200, 201]).toContain(res.status);
  cleanup(() => api('DELETE', `/masters/academic_years/${res.data.id}/permanent`));
  return res.data;
}

async function activeTitles(api) {
  const res = await api('GET', '/masters/academic_years/active');
  expect(res.status).toBe(200);
  return res.data.map((y) => y.title);
}

async function loginViaForm(page, role, yearTitle) {
  const { username, password } = credentials(role);
  await page.goto('/login');
  const trigger = page.getByRole('button', { name: /\(Current\)$/ });
  await expect(trigger).toBeVisible({ timeout: 30_000 });
  if (yearTitle) {
    await trigger.click();
    await page.getByRole('button', { name: new RegExp(`^${yearTitle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}( \\(Current\\))?$`) }).last().click();
    await expect(page.getByRole('button', { name: new RegExp(yearTitle) }).first()).toBeVisible();
  }
  await page.getByLabel('Username / Admission Number').fill(username);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Login', exact: true }).click();
  await expect(page).not.toHaveURL(/\/login/, { timeout: 30_000 });
}

test.describe('Masters F02 active year and working-year selection (web)', () => {
  test.use({ baseURL: process.env.QA_WEB_URL || 'http://localhost:5174' });

  test('TC-MST-02-E01 admin login with the seeded year keeps it the only active year', async ({ page, api }) => {
    expect(await activeTitles(api)).toEqual(['2026-2027']);
    await loginViaForm(page, 'admin', '2026-2027');
    await page.goto('/masters/subjects');
    await expect(page.getByText('Mathematics').first()).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText('Year', { exact: true })).toBeVisible();
    await expect(page.getByText('2026-2027', { exact: true }).first()).toBeVisible();
    expect(await activeTitles(api)).toEqual(['2026-2027']);
  });

  test('TC-MST-02-E02 teacher working year scopes pages without activating it', async ({ page, api, cleanup }) => {
    const title = unique('QA 2033-34');
    const year = await createYearViaApi(api, cleanup, title);
    await loginViaForm(page, 'teacher', title);
    const request = page.waitForRequest((r) => r.url().includes('/masters/class_sections/read_all'), { timeout: 30_000 });
    await page.goto('/masters/classesandsections');
    const url = new URL((await request).url());
    expect(url.searchParams.get('academic_year_id')).toBe(year.id);
    expect(await activeTitles(api)).toEqual(['2026-2027']);
    const after = await api('GET', `/masters/academic_years/${year.id}`);
    expect(after.data.is_active).toBe(false);
  });

  test('TC-MST-02-E04 @serial the year store only receives the first 10 years', async ({ page, signIn, api, cleanup }) => {
    const created = [];
    for (let i = 0; i < 11; i += 1) {
      const y = 2040 + i;
      created.push(await createYearViaApi(api, cleanup, unique(`QA ${y}-${String(y + 1).slice(2)}`), `${y}-04-01`, `${y + 1}-03-31`));
    }
    const all = await api('GET', '/masters/academic_years/?active_only=false&limit=1000');
    expect(all.data.total_count).toBeGreaterThanOrEqual(12);
    await signIn('admin');
    const response = page.waitForResponse((r) => /\/masters\/academic_years\/(\?|$)/.test(r.url()) && r.request().method() === 'GET', { timeout: 30_000 });
    await page.goto('/masters/subjects');
    const res = await response;
    const url = new URL(res.url());
    // doc: the web year store sends limit=10 explicitly (fetchAcademicYears default), it does not omit the limit
    expect(url.searchParams.get('limit')).toBe('10');
    const body = await res.json();
    expect(body.items).toHaveLength(10);
    expect(body.total_count).toBeGreaterThanOrEqual(12);
    expect(body.has_next).toBe(true);
    const received = new Set(body.items.map((y) => y.id));
    const unreachable = all.data.items.filter((y) => !received.has(y.id));
    expect(unreachable.length).toBeGreaterThanOrEqual(2);
  });
});
