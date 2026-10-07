const { test, expect } = require('../../helpers/fixtures');
const { credentials } = require('../../helpers/api');
const { mobileOpenForm, mobileSubmitLogin, createFamily, activateViaApi } = require('../../helpers/authkit');

const shown = (page, text, exact = false) => page.getByText(text, { exact }).locator('visible=true').first();

test.describe('Auth F03 login (mobile)', () => {
  test('TC-AUTH-03-E07 admin signs in and sees the dashboard', async ({ page }) => {
    const { username, password } = credentials('admin');
    await mobileOpenForm(page);
    await mobileSubmitLogin(page, username, password);
    await expect(shown(page, username, true)).toBeVisible({ timeout: 60_000 });
    await expect(shown(page, /Good (Morning|Afternoon|Evening)/)).toBeVisible();
    await expect(shown(page, 'Modules', true)).toBeVisible();
    for (const tab of ['Home', 'Settings', 'Alerts', 'Profile']) {
      await expect(shown(page, tab, true)).toBeVisible();
    }
  });

  test('TC-AUTH-03-E08 empty fields show both required messages and send nothing', async ({ page }) => {
    let posted = false;
    page.on('request', (r) => { if (r.url().includes('/auth/login')) posted = true; });
    await mobileOpenForm(page);
    await page.getByText('Sign In', { exact: true }).click();
    await expect(page.getByText('Username is required')).toBeVisible();
    await expect(page.getByText('Password is required')).toBeVisible();
    await page.waitForTimeout(1000);
    expect(posted).toBe(false);
  });

  test('TC-AUTH-03-E09 a 5 character password is rejected locally', async ({ page }) => {
    let posted = false;
    page.on('request', (r) => { if (r.url().includes('/auth/login')) posted = true; });
    const { username } = credentials('admin');
    await mobileOpenForm(page);
    await mobileSubmitLogin(page, username, '12345');
    await expect(page.getByText('Password must be at least 6 characters')).toBeVisible();
    await page.waitForTimeout(1000);
    expect(posted).toBe(false);
  });

  test('TC-AUTH-03-E10 wrong password shows the banner and keeps the form', async ({ page }) => {
    const { username } = credentials('staff');
    await mobileOpenForm(page);
    await mobileSubmitLogin(page, username, 'QA Wrong 999');
    await expect(page.getByText('Invalid Credentials')).toBeVisible({ timeout: 30_000 });
    await expect(page.getByPlaceholder('Enter your username')).toBeVisible();
  });

  test('TC-AUTH-03-E11 student and parent see their modules', async ({ page, cleanup }) => {
    // doc: precondition uses a throwaway family (seeded students keep their own passwords), not seeded student 001
    const family = await createFamily(cleanup);
    const studentPassword = await activateViaApi(family.admissionNumber, family.studentPassword);
    const parentPassword = await activateViaApi(family.fatherEmail, family.parentPassword);
    await mobileOpenForm(page);
    await mobileSubmitLogin(page, family.admissionNumber, studentPassword);
    await expect(shown(page, 'Modules', true)).toBeVisible({ timeout: 60_000 });
    for (const name of ['Students', 'Exam Management', 'Fee Management']) await expect(shown(page, name, true)).toBeVisible();
    await expect(page.getByText('Staff Management', { exact: true }).locator('visible=true')).toHaveCount(0);
    await page.evaluate(() => window.localStorage.clear());
    await mobileOpenForm(page);
    await mobileSubmitLogin(page, family.fatherEmail, parentPassword);
    await expect(shown(page, 'Modules', true)).toBeVisible({ timeout: 60_000 });
    for (const name of ['Students', 'Exam Management', 'Fee Management']) await expect(shown(page, name, true)).toBeVisible();
  });
});
