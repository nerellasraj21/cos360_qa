// Masters F02 Active year and working-year selection, mobile (Expo web). Baseline: qa_manual seeded year "2026-2027" (active).
const { test, expect, unique, TENANT } = require('../../helpers/fixtures');
const { credentials } = require('../../helpers/api');

async function createYearViaApi(api, cleanup, title, start = '2034-04-01', end = '2035-03-31') {
  const res = await api('POST', '/masters/academic_years/', { body: { title, start_date: start, end_date: end, is_active: false } });
  expect([200, 201]).toContain(res.status);
  cleanup(() => api('DELETE', `/masters/academic_years/${res.data.id}/permanent`));
  return res.data;
}

async function signInChoosingYear(page, role, yearTitle) {
  const { username, password } = credentials(role);
  await page.goto('/login', { timeout: 180_000 });
  await page.getByPlaceholder('Enter organization name').fill(TENANT);
  await page.getByText('Continue', { exact: true }).click();
  await page.getByPlaceholder('Enter your username').fill(username);
  await page.getByPlaceholder('Enter your password').fill(password);
  await page.getByText('2026-2027', { exact: true }).click();
  await expect(page.getByText('Select Academic Year')).toBeVisible();
  await page.getByText(yearTitle, { exact: true }).click();
  await expect(page.getByText('Select Academic Year')).toBeHidden();
  await expect(page.getByText(yearTitle, { exact: true })).toBeVisible();
  await page.getByText('Sign In', { exact: true }).click();
  await page.waitForFunction(() => !location.pathname.includes('login'), null, { timeout: 45_000 });
}

test.describe('Masters F02 active year and working-year selection (mobile)', () => {
  test('TC-MST-02-E03 mobile working year scopes screens and leaves the active year', async ({ page, api, cleanup }) => {
    test.fail(true, 'UI-MST-02: mobile ignores the year chosen at login; AcademicYearContext keeps the stored or active year, so screens stay on 2026-2027');
    const title = unique('QA 2034-35');
    const year = await createYearViaApi(api, cleanup, title);
    await signInChoosingYear(page, 'admin', title);
    await page.goto('/masters/subjects', { timeout: 180_000 });
    await expect(page.getByText('Subjects').first()).toBeVisible({ timeout: 60_000 });
    const active = await api('GET', '/masters/academic_years/active');
    expect(active.data.map((y) => y.title)).toEqual(['2026-2027']);
    expect((await api('GET', `/masters/academic_years/${year.id}`)).data.is_active).toBe(false);
    await expect(page.getByText(/^\d+ subjects?$/).first()).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText('Mathematics', { exact: true })).toHaveCount(0);
  });
});
