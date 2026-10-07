// Auth F10 own profile, mobile (Expo web). Throwaway users only; profile grants are tenant-wide, so tests using them are @serial.
const { test, expect } = require('../../helpers/fixtures');
const { createFamily, grantProfile, injectMobile, createStaffUser, plainLogin } = require('../../helpers/throwaway');

async function openProfile(page) {
  await page.goto('/profile', { timeout: 180_000 });
  await expect(page.getByText('Edit Profile').first().or(page.getByText('Account Information'))).toBeVisible({ timeout: 60_000 });
}

test.describe('Auth F10 profile (mobile)', () => {
  test.describe.configure({ mode: 'serial' });

  test('TC-AUTH-10-E08 @serial staff edits phone', async ({ page, cleanup }) => {
    const user = await createStaffUser(cleanup);
    await grantProfile(cleanup, 'Staff');
    await injectMobile(page, user.username, user.password);
    await openProfile(page);
    await page.getByText('Edit Profile').first().click();
    const phone = page.getByPlaceholder('Enter 10-digit phone number');
    await phone.fill('9876501235');
    await expect(phone).toHaveValue('9876501235');
    await page.getByText('Save Changes').click();
    await expect(page.getByText('9876501235').first()).toBeVisible({ timeout: 30_000 });
    expect((await plainLogin('9876501235', user.password)).status).toBe(200);
  });

  test('TC-AUTH-10-E09 @serial student edits email', async ({ page, cleanup }) => {
    const family = await createFamily(cleanup);
    await grantProfile(cleanup, 'Student');
    await injectMobile(page, family.admissionNumber, family.studentPassword);
    await openProfile(page);
    const email = `qa.auth.m.${family.admissionNumber.split('.').pop()}@example.com`;
    await page.getByText('Edit Profile').first().click();
    const field = page.getByPlaceholder('Enter email address');
    await field.fill(email);
    await expect(field).toHaveValue(email);
    await page.getByText('Save Changes').click();
    await expect(page.getByText(email).first()).toBeVisible({ timeout: 30_000 });
  });

  test('TC-AUTH-10-E10 @serial parent edits occupation', async ({ page, cleanup }) => {
    const family = await createFamily(cleanup);
    await grantProfile(cleanup, 'Parent');
    await injectMobile(page, family.fatherEmail, family.fatherPassword);
    await openProfile(page);
    await page.getByText('Edit Profile').first().click();
    const field = page.getByPlaceholder('Enter occupation');
    await field.fill('QA Engineer');
    await expect(field).toHaveValue('QA Engineer');
    await page.getByText('Save Changes').click();
    await expect(page.getByText('QA Engineer').first()).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(family.fatherEmail).locator('visible=true').first()).toBeVisible();
  });

  test('TC-AUTH-10-E11 teacher sees the fallback profile', async ({ page, signIn }) => {
    await signIn('teacher');
    await openProfile(page);
    await expect(page.getByText('qa_teacher').locator('visible=true').first()).toBeVisible();
    await expect(page.getByText('Teacher', { exact: true }).locator('visible=true').first()).toBeVisible();
    await expect(page.getByText('Active', { exact: true }).locator('visible=true').first()).toBeVisible();
    await expect(page.getByText('Account Information').locator('visible=true').first()).toBeVisible();
    await expect(page.getByText('Username', { exact: true }).locator('visible=true').first()).toBeVisible();
    await expect(page.getByText('Email', { exact: true }).locator('visible=true').first()).toBeVisible();
    await expect(page.getByText('Role', { exact: true }).locator('visible=true').first()).toBeVisible();
    await expect(page.getByText('Logout', { exact: true }).locator('visible=true').first()).toBeVisible();
    await expect(page.getByText('Edit Profile').locator('visible=true')).toHaveCount(0);
  });
});
