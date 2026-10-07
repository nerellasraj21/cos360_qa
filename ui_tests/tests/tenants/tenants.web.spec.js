// TEN F09, F12-F15 web (P1). Baseline: qa_manual, Full plan, five system roles plus leftovers of other test runs.
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { createStaffUser, webSubmitLogin, activateViaApi } = require('../../helpers/authkit');

const TEXT_FIELDS = ['school_name', 'contact_no', 'alt_contact_no', 'school_email', 'address', 'city', 'state', 'district', 'pin_code', 'country', 'academic_year', 'installation_date', 'school_board'];

async function schoolGuard(api, cleanup) {
  const res = await api('GET', '/school-settings');
  expect([200, 404]).toContain(res.status);
  const saved = res.status === 404 ? null : res.data;
  cleanup(async () => {
    const body = saved ? Object.fromEntries(TEXT_FIELDS.map((k) => [k, saved[k] ?? null])) : {};
    await api('PUT', '/school-settings', { body });
  });
  return saved;
}

function field(page, placeholder) {
  return page.getByPlaceholder(placeholder, { exact: true });
}

async function createRoleViaApi(api, cleanup, name) {
  const res = await api('POST', '/admin/role-mgmt/', { body: { name, description: 'QA custom role' } });
  expect([200, 201], JSON.stringify(res.data)).toContain(res.status);
  cleanup(() => api('DELETE', `/admin/role-mgmt/${res.data.role.id}`));
  return res.data.role;
}

async function roleByName(api, name) {
  const res = await api('GET', '/admin/role-mgmt/roles/');
  return res.data.roles.find((r) => r.name === name);
}

async function searchUser(page, username) {
  await page.getByPlaceholder('Search username or email...').fill(username);
  const row = page.getByRole('row').filter({ hasText: username });
  await expect(row).toHaveCount(1, { timeout: 15_000 });
  return row;
}

test.describe('TEN web P1', () => {
  test('TC-TEN-09-E01 super admin dashboard is empty for the tenant admin', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/superorg');
    await expect(page.getByText('Super Admin Dashboard')).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Tenants (0)' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'System Health' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'System Logs' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Plans (0)' })).toBeVisible();
    await expect(page.getByText('No tenants found')).toBeVisible();
    await page.getByRole('tab', { name: 'System Health' }).click();
    await expect(page.getByRole('tab', { name: 'System Health' })).toHaveAttribute('data-state', 'active');
    await expect(page.getByText('No tenants found')).toHaveCount(0);
    await page.getByRole('tab', { name: 'Plans (0)' }).click();
    await expect(page.getByText('No plans available')).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Tenants (0)' })).toBeVisible();
  });

  test('TC-TEN-12-E02 @serial save school settings and reload', async ({ page, signIn, api, cleanup }) => {
    await schoolGuard(api, cleanup);
    await signIn('admin');
    await page.goto('/settings/school');
    await expect(page.getByRole('heading', { name: 'School Settings' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Save Settings' })).toBeVisible();
    await field(page, 'e.g. Greenfield High School').fill('QA Public School');
    await field(page, '9900099000').fill('9900099000');
    await field(page, '503001').fill('503001');
    const board = page.getByRole('combobox').filter({ has: page.getByRole('option', { name: 'CBSE' }) });
    await board.selectOption('CBSE');
    await page.getByRole('button', { name: 'Save Settings' }).click();
    await toast(page, 'School settings saved successfully');
    await expect(page.getByText('Not configured yet')).toHaveCount(0);
    await page.reload();
    await expect(field(page, 'e.g. Greenfield High School')).toHaveValue('QA Public School');
    await expect(field(page, '9900099000')).toHaveValue('9900099000');
    await expect(field(page, '503001')).toHaveValue('503001');
    await expect(board).toHaveValue('CBSE');
    await expect(page.getByText('Not configured yet')).toHaveCount(0);
  });

  test('TC-TEN-13-E01 user list', async ({ page, signIn, api }) => {
    const first = await api('GET', '/admin/users/?limit=20&page=1');
    await signIn('admin');
    await page.goto('/admin/users');
    await expect(page.getByText('User Management').first()).toBeVisible();
    await expect(page.getByText('View and manage all user accounts across the organization')).toBeVisible();
    await expect(page.getByText(`${first.data.total} users`)).toBeVisible();
    await expect(page.getByText(`Page 1 of ${first.data.total_pages}`)).toBeVisible();
    await expect(page.locator('tbody tr')).toHaveCount(20);
    const names = await page.locator('tbody tr td:first-child').allInnerTexts();
    expect(names.map((n) => n.trim())).toEqual(first.data.users.map((u) => u.username));
    const sorted = [...names].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
    expect(names).toEqual(sorted);
  });

  test('TC-TEN-13-E05 edit a staff email and restore it', async ({ page, signIn, cleanup }) => {
    // doc: use a throwaway staff user created through the API instead of the seeded Lakshmi Narayana Rao, so seeded rows stay untouched.
    const staff = await createStaffUser(cleanup);
    await signIn('admin');
    await page.goto('/admin/users');
    let row = await searchUser(page, staff.username);
    await expect(row).toContainText(staff.username);
    await row.getByRole('button', { name: 'Edit' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText('Edit User')).toBeVisible();
    await dialog.getByLabel('Email').fill('qa.lakshmi@example.com');
    await dialog.getByRole('button', { name: 'Save Changes' }).click();
    await toast(page, 'User updated successfully');
    await expect(dialog).toBeHidden();
    row = await searchUser(page, staff.username);
    await expect(row).toContainText('qa.lakshmi@example.com');
    await row.getByRole('button', { name: 'Edit' }).click();
    await dialog.getByLabel('Email').fill(staff.username);
    await dialog.getByRole('button', { name: 'Save Changes' }).click();
    await toast(page, 'User updated successfully');
    row = await searchUser(page, staff.username);
    await expect(row).not.toContainText('qa.lakshmi@example.com');
  });

  test('TC-TEN-13-E08 reset a staff password and sign in with it', async ({ page, signIn, browser, cleanup }) => {
    // doc: use a throwaway staff user created through the API instead of the seeded Venkatesh Kumar, so seeded logins keep their passwords.
    const staff = await createStaffUser(cleanup);
    // doc: the case needs a staff member who already finished the first login; the admin reset does not clear the first-login flag, so a never-activated user would land on "Set Your Password" (Known gaps 18).
    await activateViaApi(staff.username, staff.password);
    const newPassword = 'QA Reset 2026';
    await signIn('admin');
    await page.goto('/admin/users');
    const row = await searchUser(page, staff.username);
    await row.getByRole('button', { name: 'Reset Password' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('New Password').fill(newPassword);
    await dialog.getByLabel('Confirm Password').fill(newPassword);
    await dialog.getByRole('button', { name: 'Reset Password' }).click();
    await toast(page, 'Password reset successfully');
    const context = await browser.newContext({ baseURL: 'http://localhost:5174' });
    const other = await context.newPage();
    await webSubmitLogin(other, staff.username, newPassword);
    await expect(other).not.toHaveURL(/login/, { timeout: 30_000 });
    await expect(other.getByText('Set New Password')).toHaveCount(0);
    await expect(other.getByRole('button', { name: 'Dashboard' })).toBeVisible({ timeout: 30_000 });
    await context.close();
  });

  test('TC-TEN-14-E02 add a role', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Web Librarian');
    await signIn('admin');
    await page.goto('/masters/rolespermissions');
    await expect(page.getByText('User Roles Management')).toBeVisible();
    await page.getByRole('button', { name: 'Add Role' }).click();
    await page.getByPlaceholder('e.g., Librarian').fill(name);
    await page.getByPlaceholder('Role description (optional)').fill('QA custom role');
    await page.getByRole('button', { name: 'Create', exact: true }).click();
    await toast(page, 'Role created successfully');
    const created = await roleByName(api, name);
    expect(created).toBeTruthy();
    cleanup(() => api('DELETE', `/admin/role-mgmt/${created.id}`));
    const row = page.getByRole('row').filter({ hasText: name });
    await expect(row).toBeVisible();
    await expect(row).toContainText('Active');
    await expect(row).toContainText('QA custom role');
  });

  test('TC-TEN-15-E03 add a role permission', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Web Librarian');
    const role = await createRoleViaApi(api, cleanup, name);
    await signIn('admin');
    await page.goto('/masters/rolespermissions');
    await expect(page.getByText('User Roles Management')).toBeVisible();
    await page.getByRole('button', { name: 'Add Permission' }).click();
    await page.getByRole('button', { name: 'Select role' }).click();
    await page.getByRole('button', { name, exact: true }).click();
    await page.getByRole('button', { name: 'Select resource' }).click();
    await page.getByRole('button', { name: /^students$/i }).click();
    await page.getByRole('button', { name: 'Select action' }).click();
    await page.getByRole('button', { name: /^list$/i }).click();
    await expect(page.getByRole('checkbox', { name: 'Permission Granted' })).toBeChecked();
    await page.getByRole('button', { name: 'Create', exact: true }).click();
    await toast(page, 'Permission created successfully');
    const perms = await api('GET', `/auth/resource-permissions/role/${role.id}`);
    expect(perms.status).toBe(200);
    const list = Array.isArray(perms.data) ? perms.data : perms.data.items || perms.data.permissions || [];
    const found = list.find((p) => p.resource === 'students' && p.action === 'list');
    expect(found).toBeTruthy();
    expect(found.is_granted).toBe(true);
    cleanup(() => api('DELETE', `/auth/resource-permissions/${found.id}`));
    await page.getByRole('button', { name: 'Permissions', exact: true }).click();
    await page.getByRole('button', { name: 'All Roles' }).click();
    await page.getByRole('button', { name, exact: true }).click();
    const permRow = page.getByRole('row').filter({ hasText: name });
    await expect(permRow).toHaveCount(1);
    await expect(permRow).toContainText(/students/i);
    await expect(permRow).toContainText(/list/i);
    // the granted state is an icon without text; it is asserted through the API above
  });
});
