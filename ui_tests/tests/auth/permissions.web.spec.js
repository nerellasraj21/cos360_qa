// Auth F05 Permission loading, web.
const { test, expect, unique } = require('../../helpers/fixtures');
const { createStaffUser, activate, webAuthState, tag } = require('../../helpers/auth-users');

test.describe('Auth F05 permission loading (web)', () => {
  test('TC-AUTH-05-E01 admin user management page', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/admin/users');
    await expect(page.getByRole('heading', { name: 'User Management' })).toBeVisible();
    await expect(page.getByText(/\d+ users?/).first()).toBeVisible();
    await expect(page.getByRole('combobox', { name: /All Roles/ }).or(page.getByText('All Roles')).first()).toBeVisible();
    await expect(page.getByText('All Status').first()).toBeVisible();
    for (const header of ['Username', 'Email', 'Role', 'Entity', 'Status', 'Actions']) {
      await expect(page.getByRole('columnheader', { name: header, exact: true })).toBeVisible();
    }
    const first = page.locator('tbody tr').first();
    for (const name of ['View', 'Edit', 'Reset Password']) {
      await expect(first.getByRole('button', { name })).toBeVisible();
    }
  });

  test('TC-AUTH-05-E02 staff is denied the users page', async ({ page, signIn }) => {
    await signIn('staff');
    await page.goto('/admin/users');
    await expect(page.getByText('Access Denied')).toBeVisible();
    await expect(page.getByText("You don't have permission to view users.")).toBeVisible();
    await expect(page.locator('tbody tr')).toHaveCount(0);
  });

  test('TC-AUTH-05-E04 teacher matrix hides fee entries', async ({ page, signIn }) => {
    await signIn('teacher');
    await page.goto('/dashboard');
    await expect(page.locator('aside nav').getByRole('button', { name: 'Dashboard', exact: true })).toBeVisible();
    await expect(page.locator('aside nav').getByRole('button', { name: 'Fee', exact: true })).toHaveCount(0);
    await page.goto('/fee/categories');
    await page.waitForTimeout(1500);
    await expect(page.getByRole('button', { name: /add|create|new/i })).toHaveCount(0);
  });

  test('TC-AUTH-05-E03 revoked grant shows only after a new login', async ({ page, api, cleanup }) => {
    const role = await api('POST', '/admin/role-mgmt/', { body: { name: unique('QA Clerk'), description: 'auth ui test role' } });
    expect(role.status).toBe(201);
    const roleId = role.data.role.id;
    cleanup(() => api('DELETE', `/admin/role-mgmt/${roleId}`));
    for (const action of ['list', 'read', 'update']) {
      const res = await api('PUT', `/admin/role-mgmt/roles/${roleId}/permissions?resource=user_management&action=${action}&is_granted=true`);
      expect(res.status).toBe(200);
    }
    const user = await createStaffUser(api, cleanup, { roleId });
    const newPass = `QA Pass ${tag().slice(-6)}`;
    const data = await activate(user.username, user.tempPassword, newPass);
    expect(data.permissions.user_management).toEqual(expect.arrayContaining(['list', 'read', 'update']));
    await page.addInitScript((auth) => {
      if (!window.sessionStorage.getItem('__qa_injected')) {
        window.sessionStorage.setItem('__qa_injected', '1');
        window.localStorage.setItem('auth-storage', auth);
        window.localStorage.setItem('authToken', JSON.parse(auth).state.accessToken);
      }
    }, JSON.stringify(webAuthState(data)));
    await page.goto('/admin/users');
    await expect(page.getByRole('heading', { name: 'User Management' })).toBeVisible();
    const first = page.locator('tbody tr').first();
    await expect(first.getByRole('button', { name: 'Edit' })).toBeVisible();
    await expect(first.getByRole('button', { name: 'Reset Password' })).toBeVisible();
    const off = await api('PUT', `/admin/role-mgmt/roles/${roleId}/permissions?resource=user_management&action=update&is_granted=false`);
    expect(off.status).toBe(200);
    await page.reload();
    await expect(page.getByRole('heading', { name: 'User Management' })).toBeVisible();
    await expect(page.locator('tbody tr').first().getByRole('button', { name: 'Edit' })).toBeVisible();
    await expect(page.locator('tbody tr').first().getByRole('button', { name: 'Reset Password' })).toBeVisible();
    const again = await activate(user.username, user.tempPassword, newPass);
    expect(again.permissions.user_management).not.toContain('update');
    await page.evaluate((auth) => {
      window.localStorage.setItem('auth-storage', auth);
      window.localStorage.setItem('authToken', JSON.parse(auth).state.accessToken);
    }, JSON.stringify(webAuthState(again)));
    await page.reload();
    await expect(page.getByRole('heading', { name: 'User Management' })).toBeVisible();
    await expect(page.locator('tbody tr').first().getByRole('button', { name: 'View' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Edit' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Reset Password' })).toHaveCount(0);
  });
});
