const { test, expect } = require('../../helpers/fixtures');
const { credentials } = require('../../helpers/api');
const { webSubmitLogin } = require('../../helpers/authkit');

const menu = (page, name) => page.getByRole('button', { name, exact: true });

test.describe('Auth F03 login (web)', () => {
  test('TC-AUTH-03-E01 admin signs in and lands on the dashboard', async ({ page }) => {
    const { username, password } = credentials('admin');
    await webSubmitLogin(page, username, password);
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByText(`Welcome back, ${username} (Admin)`)).toBeVisible();
    await expect(page.getByText(username, { exact: true }).first()).toBeVisible();
    await expect(page.getByText('2026-2027').first()).toBeVisible();
  });

  test('TC-AUTH-03-E02 wrong password shows the error banner', async ({ page }) => {
    const { username } = credentials('staff');
    await webSubmitLogin(page, username, 'QA Wrong 999');
    await expect(page.getByText('Invalid Credentials')).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
    const stored = await page.evaluate(() => ({ token: localStorage.getItem('authToken'), auth: localStorage.getItem('auth-storage') }));
    expect(stored.token).toBeNull();
    expect(stored.auth === null || !JSON.parse(stored.auth).state.accessToken).toBe(true);
  });

  test('TC-AUTH-03-E03 the eye button reveals and hides the password', async ({ page }) => {
    await page.goto('/login');
    const field = page.getByLabel('Password', { exact: true });
    await field.fill('QA Secret 1');
    await expect(field).toHaveAttribute('type', 'password');
    await page.getByRole('button', { name: 'Show password' }).click();
    await expect(field).toHaveAttribute('type', 'text');
    await expect(field).toHaveValue('QA Secret 1');
    await page.getByRole('button', { name: 'Hide password' }).click();
    await expect(field).toHaveAttribute('type', 'password');
    await expect(page.getByRole('button', { name: 'Show password' })).toBeVisible();
  });

  test('TC-AUTH-03-E04 each role lands on the dashboard with its own menu', async ({ page }) => {
    const expected = { staff: 'Staff', teacher: 'Teacher', student: 'Student', parent: 'Parent' };
    for (const [role, label] of Object.entries(expected)) {
      const { username, password } = credentials(role);
      await page.goto('/login');
      await page.evaluate(() => { localStorage.clear(); sessionStorage.clear(); });
      await webSubmitLogin(page, username, password);
      await expect(page).toHaveURL(/\/dashboard/);
      await expect(page.getByText(`Welcome back, ${username} (${label})`)).toBeVisible();
      if (role === 'teacher') await expect(menu(page, 'Fee')).toHaveCount(0);
      else await expect(menu(page, 'Fee')).toBeVisible();
      if (role === 'student' || role === 'parent') {
        for (const name of ['Dashboard', 'Students', 'Fee', 'Exam']) await expect(menu(page, name)).toBeVisible();
        for (const name of ['Staff', 'Masters', 'Administration', 'Expense']) await expect(menu(page, name)).toHaveCount(0);
      }
    }
  });

  test('TC-AUTH-03-E05 the button is disabled and relabelled while the request runs', async ({ page }) => {
    const { username, password } = credentials('admin');
    await page.route('**/auth/login', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 3000));
      await route.continue();
    });
    await webSubmitLogin(page, username, password);
    const busy = page.getByRole('button', { name: 'Logging in...' });
    await expect(busy).toBeVisible();
    await expect(busy).toBeDisabled();
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 20_000 });
  });

  test('TC-AUTH-03-E06 a signed-in user opening /login is sent to the dashboard', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/login');
    await expect(page).toHaveURL(/\/dashboard/);
  });
});
