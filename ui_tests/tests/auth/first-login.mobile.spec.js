const { test, expect } = require('../../helpers/fixtures');
const { createFamily, mobileOpenForm, mobileSubmitLogin, mobileReachSetPassword } = require('../../helpers/authkit');

const DEFECT = 'UI-AUTH-01: mobile first-login flashes Set New Password and bounces back to /login (AcademicYearContext fetches /masters/academic_years/ without a token while isAuthenticated is true and the 401 sends the user to login)';
const NEW_PASSWORD = 'Enter new password (min 8 characters)';
const CONFIRM_PASSWORD = 'Re-enter your new password';

async function toSetPassword(page, username, password) {
  await mobileOpenForm(page);
  await mobileSubmitLogin(page, username, password);
  await mobileReachSetPassword(page);
}

test.describe('Auth F04 first-login password change (mobile)', () => {
  test('TC-AUTH-04-E06 temporary password opens the set-password screen', async ({ page, cleanup }) => {
    test.fail(true, DEFECT);
    const family = await createFamily(cleanup);
    await toSetPassword(page, family.admissionNumber, family.studentPassword);
    await expect(page.getByText('Please set a new password for your account')).toBeVisible();
    await expect(page.getByPlaceholder(NEW_PASSWORD)).toBeVisible({ timeout: 3000 });
    await expect(page.getByPlaceholder(CONFIRM_PASSWORD)).toBeVisible({ timeout: 3000 });
  });

  test('TC-AUTH-04-E07 a 7 character password is rejected locally', async ({ page, cleanup }) => {
    test.fail(true, DEFECT);
    const family = await createFamily(cleanup);
    await toSetPassword(page, family.admissionNumber, family.studentPassword);
    await page.getByPlaceholder(NEW_PASSWORD).fill('1234567', { timeout: 3000 });
    await page.getByPlaceholder(CONFIRM_PASSWORD).fill('1234567', { timeout: 3000 });
    await page.getByText('Set Password', { exact: true }).last().click({ timeout: 3000 });
    await expect(page.getByText('New password must be at least 8 characters')).toBeVisible({ timeout: 3000 });
  });

  test('TC-AUTH-04-E08 mismatching confirmation is rejected locally', async ({ page, cleanup }) => {
    test.fail(true, DEFECT);
    const family = await createFamily(cleanup);
    await toSetPassword(page, family.admissionNumber, family.studentPassword);
    await page.getByPlaceholder(NEW_PASSWORD).fill('QA Pass 2026', { timeout: 3000 });
    await page.getByPlaceholder(CONFIRM_PASSWORD).fill('QA Pass 2027', { timeout: 3000 });
    await page.getByText('Set Password', { exact: true }).last().click({ timeout: 3000 });
    await expect(page.getByText('New passwords do not match')).toBeVisible({ timeout: 3000 });
  });

  test('TC-AUTH-04-E09 setting the password signs the student in', async ({ page, cleanup }) => {
    test.fail(true, DEFECT);
    const family = await createFamily(cleanup);
    const fresh = `QA Pass ${Date.now().toString(36)}`;
    await toSetPassword(page, family.admissionNumber, family.studentPassword);
    await page.getByPlaceholder(NEW_PASSWORD).fill(fresh, { timeout: 3000 });
    await page.getByPlaceholder(CONFIRM_PASSWORD).fill(fresh, { timeout: 3000 });
    await page.getByText('Set Password', { exact: true }).last().click({ timeout: 3000 });
    await expect(page.getByText('Modules').locator('visible=true').first()).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText('Exam Management').locator('visible=true').first()).toBeVisible();
    await expect(page.getByText('Fee Management').locator('visible=true').first()).toBeVisible();
  });

  test('TC-AUTH-04-E10 parent sets the password and sees the child selected', async ({ page, cleanup }) => {
    test.fail(true, DEFECT);
    const family = await createFamily(cleanup);
    const fresh = `QA Pass ${Date.now().toString(36)}`;
    await toSetPassword(page, family.fatherEmail, family.parentPassword);
    await page.getByPlaceholder(NEW_PASSWORD).fill(fresh, { timeout: 3000 });
    await page.getByPlaceholder(CONFIRM_PASSWORD).fill(fresh, { timeout: 3000 });
    await page.getByText('Set Password', { exact: true }).last().click({ timeout: 3000 });
    await expect(page.getByText('Modules').locator('visible=true').first()).toBeVisible({ timeout: 60_000 });
    await page.goto('/parents/select-child', { timeout: 60_000 });
    await expect(page.getByText('Select Child').locator('visible=true').first()).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText(/QA Kid/).locator('visible=true').first()).toBeVisible();
  });
});
