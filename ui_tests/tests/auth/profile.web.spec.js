// Auth F10 own profile, web. Throwaway users only; profile grants are tenant-wide, so every test using them is @serial.
const { test, expect, toast } = require('../../helpers/fixtures');
const { createFamily, grantProfile, injectWeb, createStaffUser, plainLogin } = require('../../helpers/throwaway');

async function openProfile(page, username) {
  await page.goto('/');
  await page.getByRole('button', { name: new RegExp(username, 'i') }).first().click();
  await page.getByRole('menuitem', { name: 'Profile' }).click();
}

test.describe('Auth F10 profile (web)', () => {
  test.describe.configure({ mode: 'serial' });

  test('TC-AUTH-10-E01 @serial student sees Student Profile', async ({ page, cleanup }) => {
    const family = await createFamily(cleanup);
    await grantProfile(cleanup, 'Student');
    await injectWeb(page, family.admissionNumber, family.studentPassword);
    await openProfile(page, family.admissionNumber);
    await expect(page.getByText('Student Profile').first()).toBeVisible();
    await expect(page.getByText('Personal Information')).toBeVisible();
    await expect(page.getByText('Academic Information')).toBeVisible();
    await expect(page.getByText(family.studentName.split(' ')[0], { exact: true })).toBeVisible();
    await expect(page.getByText('Throwaway', { exact: true })).toBeVisible();
    await expect(page.getByText('Academic Information').locator('xpath=ancestor::*[3]')).toContainText(family.className);
  });

  test('TC-AUTH-10-E05 admin sees My Profile with Account Information', async ({ page, signIn }) => {
    await signIn('admin');
    await openProfile(page, 'qa_admin');
    await expect(page.getByText('My Profile').first()).toBeVisible();
    await expect(page.getByText('Account Information')).toBeVisible();
    await expect(page.getByText('qa_admin', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('qa_admin@example.com').first()).toBeVisible();
    await expect(page.getByText('Admin', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('2026-2027').first()).toBeVisible();
  });

  test('TC-AUTH-10-E02 @serial student edits email', async ({ page, cleanup }) => {
    const family = await createFamily(cleanup);
    await grantProfile(cleanup, 'Student');
    await injectWeb(page, family.admissionNumber, family.studentPassword);
    await openProfile(page, family.admissionNumber);
    const email = `qa.auth.${family.admissionNumber.split('.').pop()}@example.com`;
    await page.getByRole('button', { name: 'Edit Email' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Email').fill(email);
    await dialog.getByRole('button', { name: /Update|Save/ }).click();
    await expect(dialog).toBeHidden();
    await expect(page.getByText(email).first()).toBeVisible();
    expect((await plainLogin(email, family.studentPassword)).status).toBe(200);
  });

  test('TC-AUTH-10-E03 @serial invalid student email is rejected locally', async ({ page, cleanup }) => {
    const family = await createFamily(cleanup);
    await grantProfile(cleanup, 'Student');
    await injectWeb(page, family.admissionNumber, family.studentPassword);
    await openProfile(page, family.admissionNumber);
    let put = false;
    page.on('request', (r) => { if (r.method() === 'PUT' && r.url().includes('/profile/')) put = true; });
    await page.getByRole('button', { name: 'Edit Email' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Email').fill('abc');
    await dialog.getByRole('button', { name: /Update|Save/ }).click();
    // doc: the field is type=email, so the browser blocks the submit with its own validation bubble; the text "Invalid email address" is never shown
    expect(await dialog.getByLabel('Email').evaluate((el) => el.validity.valid)).toBe(false);
    await page.waitForTimeout(800);
    expect(put).toBe(false);
    await expect(dialog).toBeVisible();
  });

  test('TC-AUTH-10-E04 @serial staff edits email and phone', async ({ page, cleanup }) => {
    const user = await createStaffUser(cleanup);
    await grantProfile(cleanup, 'Staff');
    await injectWeb(page, user.username, user.password);
    await openProfile(page, user.username);
    await expect(page.getByText('Staff Profile').first()).toBeVisible();
    await page.getByRole('button', { name: 'Edit Email & Phone' }).click();
    const dialog = page.getByRole('dialog');
    const email = `qa.auth.new.${user.email}`;
    const phone = '9876501234';
    await dialog.getByLabel('Email').fill(email);
    await dialog.getByLabel('Phone').fill(phone);
    await dialog.getByRole('button', { name: /Update|Save/ }).click();
    await expect(dialog).toBeHidden();
    await expect(page.getByText(email).first()).toBeVisible();
    await expect(page.getByText(phone).first()).toBeVisible();
    expect((await plainLogin(user.username, user.password)).status).toBe(200);
  });

  test('TC-AUTH-10-E06 @serial parent sees children and no Edit Profile button', async ({ page, cleanup }) => {
    const family = await createFamily(cleanup);
    await grantProfile(cleanup, 'Parent');
    await injectWeb(page, family.fatherEmail, family.fatherPassword);
    await openProfile(page, family.fatherEmail);
    await expect(page.getByText('My Profile').first()).toBeVisible();
    await expect(page.getByText(family.studentName.split(' ')[0]).first()).toBeVisible();
    await expect(page.getByRole('button', { name: 'Edit Profile' })).toHaveCount(0);
  });

  test('TC-AUTH-10-E07 admin edits own email on Admin Profile and restores it', async ({ page, cleanup }) => {
    const admin = await createStaffUser(cleanup, { role: 'Admin' });
    await injectWeb(page, admin.username, admin.password);
    await page.goto('/admin/profile');
    await expect(page.getByText('Profile Information')).toBeVisible();
    const swap = async (value) => {
      await page.getByRole('button', { name: 'Edit Email' }).click();
      const dialog = page.getByRole('dialog');
      await dialog.getByLabel('Email').fill(value);
      await dialog.getByRole('button', { name: 'Update' }).click();
      await toast(page, 'Admin profile updated successfully!');
      await expect(dialog).toBeHidden();
      await expect(page.getByText(value).first()).toBeVisible();
    };
    await swap(`qa.auth.changed.${admin.email}`);
    await swap(admin.email);
  });

  test('TC-AUTH-10-E12 @serial student login without a student record shows the load error', async ({ page, signIn, cleanup }) => {
    await grantProfile(cleanup, 'Student');
    await signIn('student');
    await openProfile(page, 'qa_student');
    await expect(page.getByText(/^Error loading profile:/)).toBeVisible();
    await expect(page.getByText('Student profile not found')).toBeVisible();
    await expect(page.getByText('Personal Information')).toHaveCount(0);
  });
});
