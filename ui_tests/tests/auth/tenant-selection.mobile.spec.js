const { test, expect } = require('../../helpers/fixtures');
const { TENANT, call } = require('../../helpers/authkit');

const shown = (page, text, exact = true) => page.getByText(text, { exact }).locator('visible=true').first();

async function storedOrg(page) {
  return page.evaluate(() => window.localStorage.getItem('@auth/client_schema'));
}

test.describe('Auth F01 organisation selection (mobile)', () => {
  test('TC-AUTH-01-E02 unknown organisation shows the not found text', async ({ page }) => {
    await page.goto('/login', { timeout: 180_000 });
    await page.getByPlaceholder('Enter organization name').fill('NoSuchSchool');
    await page.getByText('Continue', { exact: true }).click();
    await expect(page.getByText('Organisation not found. Check the name and try again.')).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText('Select Organization')).toBeVisible();
    await expect(page.getByPlaceholder('Enter your username')).toHaveCount(0);
    expect(await storedOrg(page)).toBeNull();
  });

  test('TC-AUTH-01-E03 organisation code is trimmed and lowercased', async ({ page }) => {
    await page.goto('/login', { timeout: 180_000 });
    await page.getByPlaceholder('Enter organization name').fill(' QA_Manual ');
    await page.getByText('Continue', { exact: true }).click();
    await expect(page.getByText('Welcome Back!')).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText('Sign in to your account to continue')).toBeVisible();
    await expect(page.getByPlaceholder('Organization name')).toHaveValue(TENANT);
    await expect(page.getByPlaceholder('Organization name')).not.toBeEditable();
    await expect(page.getByText('2026-2027').first()).toBeVisible({ timeout: 30_000 });
  });

  test('TC-AUTH-01-E04 changing the organisation reloads that tenant years', async ({ page }) => {
    const other = await call('GET', '/auth/academic-years', { headers: { cschema: 'qa_school' } });
    expect(other.status).toBe(200);
    const title = other.data.find((y) => !y.is_active).title;
    await page.goto('/login', { timeout: 180_000 });
    await page.getByPlaceholder('Enter organization name').fill(TENANT);
    await page.getByText('Continue', { exact: true }).click();
    await expect(page.getByPlaceholder('Enter your username')).toBeVisible({ timeout: 60_000 });
    await page.getByText('Change Organization', { exact: true }).click();
    await expect(page.getByText('Select Organization')).toBeVisible();
    await page.getByPlaceholder('Enter organization name').fill('qa_school');
    await page.getByText('Continue', { exact: true }).click();
    await expect(page.getByPlaceholder('Organization name')).toHaveValue('qa_school', { timeout: 60_000 });
    await expect(shown(page, '2026-2027')).toBeVisible({ timeout: 30_000 });
    await shown(page, '2026-2027').click();
    await expect(shown(page, 'Select Academic Year')).toBeVisible();
    await expect(shown(page, title)).toBeVisible();
  });

  test('TC-AUTH-01-E05 offline shows the connection error and stores nothing', async ({ page, context }) => {
    await page.goto('/login', { timeout: 180_000 });
    await expect(page.getByPlaceholder('Enter organization name')).toBeVisible({ timeout: 60_000 });
    await context.setOffline(true);
    await page.getByPlaceholder('Enter organization name').fill(TENANT);
    await page.getByText('Continue', { exact: true }).click();
    await expect(page.getByText('Could not reach the server. Check your connection and try again.')).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText('Select Organization')).toBeVisible();
    expect(await storedOrg(page)).toBeNull();
    await context.setOffline(false);
  });
});
