const { test, expect, unique } = require('../../helpers/fixtures');
const { credentials } = require('../../helpers/api');
const { createInactiveYear, webSubmitLogin, adminCall } = require('../../helpers/authkit');

async function years() {
  const res = await adminCall('GET', '/masters/academic_years/?active_only=false&limit=1000');
  return Array.isArray(res.data) ? res.data : res.data.items || [];
}

test.describe('Auth F02 academic year selection (web)', () => {
  test('TC-AUTH-02-E01 current year is preselected and the list is tenant years', async ({ page, cleanup }) => {
    const extra = await createInactiveYear(cleanup, unique('QA 2031'));
    await page.goto('/login');
    const select = page.getByRole('button', { name: /^\d{4}-\d{4}/ }).first();
    await expect(select).toContainText('2026-2027 (Current)', { timeout: 20_000 });
    await expect(page.getByRole('button', { name: 'Login' })).toBeEnabled();
    await select.click();
    await expect(page.getByRole('button', { name: extra.title, exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: /\(Current\)/ })).toHaveCount(2);
  });

  test('TC-AUTH-02-E02 @serial admin login activates the chosen year for the tenant', async ({ page, cleanup }) => {
    const extra = await createInactiveYear(cleanup, unique('QA 2031'));
    const { username, password } = credentials('admin');
    await webSubmitLogin(page, username, password, extra.title);
    await expect(page).toHaveURL(/\/dashboard/);
    await expect.poll(async () => (await years()).filter((y) => y.is_active).map((y) => y.title)).toEqual([extra.title]);
  });

  test('TC-AUTH-02-E03 @serial teacher login does not activate the chosen year', async ({ page, cleanup }) => {
    const extra = await createInactiveYear(cleanup, unique('QA 2031'));
    const { username, password } = credentials('teacher');
    await webSubmitLogin(page, username, password, extra.title);
    await expect(page).toHaveURL(/\/dashboard/);
    await page.waitForTimeout(1500);
    expect((await years()).filter((y) => y.is_active).map((y) => y.title)).toEqual(['2026-2027']);
  });

  test('TC-AUTH-02-E04 navbar year choice survives a reload and leaves the tenant year alone', async ({ page, signIn, cleanup }) => {
    test.fail(true, 'UI-AUTH-02: the navbar Year dropdown requests /masters/academic_years/dropdown with active_only=true, so inactive (past) years can never be chosen');
    const extra = await createInactiveYear(cleanup, unique('QA 2031'));
    await signIn('admin');
    await page.goto('/dashboard');
    const navbarYear = page.getByRole('combobox').first();
    await navbarYear.fill(extra.title);
    await page.getByRole('option', { name: extra.title }).click({ timeout: 5000 });
    await expect(page.getByText(extra.title).first()).toBeVisible();
    await page.reload();
    await expect(page.getByText(extra.title).first()).toBeVisible({ timeout: 20_000 });
    expect((await years()).filter((y) => y.is_active).map((y) => y.title)).toEqual(['2026-2027']);
  });
});
