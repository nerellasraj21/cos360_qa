// TEN F06, F12-F16 mobile (P1). Baseline: qa_manual, Full plan, five system roles plus leftovers of other test runs.
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { credentials, call } = require('../../helpers/api');
const { mobileOpenForm, mobileSubmitLogin } = require('../../helpers/authkit');

function vis(page, text, exact = true) {
  return page.getByText(text, { exact }).locator('visible=true');
}

async function openAdmin(page, signIn, role = 'admin') {
  await signIn(role);
  await page.goto('/', { timeout: 180_000 });
  await page.getByLabel('Open Administration', { exact: true }).locator('visible=true').first().click({ timeout: 60_000 });
  await expect(vis(page, 'ADMINISTRATION SECTIONS').first()).toBeVisible({ timeout: 60_000 });
}

async function roleByName(api, name) {
  const res = await api('GET', '/admin/role-mgmt/roles/');
  return res.data.roles.find((r) => r.name === name);
}

test.describe('TEN mobile P1', () => {
  test('TC-TEN-06-E01 menu management lists the catalog menus', async ({ page, signIn }) => {
    await openAdmin(page, signIn);
    await vis(page, 'Menu Management').first().click();
    await expect(vis(page, 'Configure sidebar navigation items').first()).toBeVisible({ timeout: 60_000 });
    for (const name of ['Dashboard', 'Billing Admin', 'Masters', 'Students']) {
      await expect(vis(page, name).first()).toBeVisible({ timeout: 60_000 });
    }
  });

  test('TC-TEN-12-E11 school settings screen layout', async ({ page, signIn }) => {
    await openAdmin(page, signIn);
    await vis(page, 'School Settings').first().click();
    await expect(vis(page, 'Save Settings').first()).toBeVisible({ timeout: 60_000 });
    for (const name of ['Branding', 'School Logo', 'Principal Signature', 'Basic Information', 'Address']) {
      await expect(vis(page, name).first()).toBeVisible();
    }
  });

  test('TC-TEN-13-E13 user management overview and account list', async ({ page, signIn, api }) => {
    const list = await api('GET', '/admin/users/?limit=20&page=1');
    await openAdmin(page, signIn);
    await vis(page, 'User Management').first().click();
    await expect(vis(page, 'USER CATEGORIES').first()).toBeVisible({ timeout: 60_000 });
    for (const name of ['Staff Members', 'Students', 'Parents', 'Roles & Permissions']) {
      await expect(vis(page, name).first()).toBeVisible();
    }
    await expect(vis(page, 'SYSTEM LOGIN ACCOUNTS').first()).toBeVisible();
    await expect(page.getByPlaceholder('Search by username, name...').locator('visible=true').first()).toBeVisible();
    for (const chip of ['All Roles', 'Admin', 'Parent', 'Staff', 'Student', 'Teacher']) {
      await expect(vis(page, chip).first()).toBeVisible();
    }
    const firstUser = list.data.users[0];
    await expect(vis(page, `@${firstUser.username}`, false).first()).toBeVisible({ timeout: 30_000 });
    await expect(vis(page, `1 / ${list.data.total_pages}`).first()).toBeVisible();
  });

  test('TC-TEN-14-E09 add a role', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Mobile Role');
    await openAdmin(page, signIn);
    await vis(page, 'Role Management').first().click();
    await vis(page, 'Add Role').first().click({ timeout: 60_000 });
    await page.getByPlaceholder('Enter role name').locator('visible=true').first().fill(name);
    await vis(page, 'Create').last().click();
    await toast(page, 'Role created successfully');
    const created = await roleByName(api, name);
    expect(created).toBeTruthy();
    cleanup(() => api('DELETE', `/admin/role-mgmt/${created.id}`));
    await expect(vis(page, name).first()).toBeVisible();
  });

  test('TC-TEN-15-E12 add a role permission', async ({ page, signIn, api, cleanup }) => {
    test.fail(true, 'UI-TEN-01: mobile Add Permission loads its resource chips from /auth/available-resources, which has no "students" (nor exams, communications and others) although the web list and the permission catalog do, so the documented permission cannot be chosen');
    const name = unique('QA Mobile Role');
    const made = await api('POST', '/admin/role-mgmt/', { body: { name, description: 'QA custom role' } });
    expect([200, 201]).toContain(made.status);
    const roleId = made.data.role.id;
    cleanup(() => api('DELETE', `/admin/role-mgmt/${roleId}`));
    await openAdmin(page, signIn);
    await vis(page, 'Permission Management').first().click();
    await vis(page, 'Permissions').first().click({ timeout: 60_000 });
    await vis(page, 'Add Permission').first().click();
    await vis(page, name).last().click();
    await vis(page, 'students').last().click({ timeout: 15_000 });
    await vis(page, 'list').last().click();
    await vis(page, 'Create').last().click();
    await toast(page, 'Permission created successfully');
    const perms = await api('GET', `/auth/resource-permissions/role/${roleId}`);
    const rows = Array.isArray(perms.data) ? perms.data : perms.data.items || perms.data.permissions || [];
    const found = rows.find((p) => p.resource === 'students' && p.action === 'list');
    expect(found).toBeTruthy();
    expect(found.is_granted).toBe(true);
    cleanup(() => api('DELETE', `/auth/resource-permissions/${found.id}`));
    await vis(page, name).first().click();
    await expect(vis(page, 'students', false).first()).toBeVisible();
  });

  test('TC-TEN-16-E02 each organisation lists only its own accounts', async ({ page }) => {
    test.setTimeout(240_000);
    const { username, password } = credentials('admin');
    const probe = await call('GET', '/auth/academic-years');
    expect(probe.status).toBe(200);
    const other = await fetch(`${process.env.QA_API_URL || 'http://127.0.0.1:8100/api/v1'}/auth/academic-years`, { headers: { cschema: 'qa_school' } });
    test.skip(other.status !== 200, 'qa_school is not provisioned in this environment');
    await mobileOpenForm(page, 'qa_school');
    await mobileSubmitLogin(page, username, password);
    await page.waitForFunction(() => !location.pathname.includes('login'), null, { timeout: 60_000 });
    await page.goto('/admin/users', { timeout: 180_000 });
    await expect(vis(page, 'SYSTEM LOGIN ACCOUNTS').first()).toBeVisible({ timeout: 60_000 });
    const search = page.getByPlaceholder('Search by username, name...').locator('visible=true').first();
    await expect(vis(page, 'Karthik Reddy', false)).toHaveCount(0);
    await expect(vis(page, '@001 ', false)).toHaveCount(0);
    await search.fill('Karthik');
    await page.waitForTimeout(1500);
    await expect(vis(page, 'Karthik Reddy', false)).toHaveCount(0);
    await search.fill('qa_admin');
    await expect(vis(page, '@qa_admin', false).first()).toBeVisible({ timeout: 30_000 });
  });
});
