// Auth F06 Role-based menu, web.
const { test, expect } = require('../../helpers/fixtures');
const { sidebarTop, sidebarChildren, expandSidebar } = require('../../helpers/auth-users');

async function open(page, signIn, role) {
  await signIn(role);
  await page.goto('/dashboard');
  await expect(page.locator('aside nav').getByRole('button', { name: 'Dashboard', exact: true })).toBeVisible();
}

test.describe('Auth F06 role-based menu (web)', () => {
  test('TC-AUTH-06-E01 admin sidebar order', async ({ page, signIn }) => {
    await open(page, signIn, 'admin');
    expect(await sidebarTop(page)).toEqual([
      'Dashboard', 'Students', 'Staff', 'Fee', 'Expense', 'Communication', 'Reports', 'Masters',
      'Administration', 'Transport', 'Billing Admin', 'Exam', 'Timetable', 'Calendar',
    ]);
  });

  test('TC-AUTH-06-E03 student sidebar', async ({ page, signIn }) => {
    await open(page, signIn, 'student');
    expect(await sidebarTop(page)).toEqual(['Dashboard', 'Students', 'Fee', 'Exam']);
    await expandSidebar(page, 'Students');
    expect(await sidebarChildren(page, 'Students')).toEqual(['Admission', 'Attendance', 'Student Documents', 'Student Certificates']);
    await expandSidebar(page, 'Fee');
    expect(await sidebarChildren(page, 'Fee')).toEqual(['My Receipts', 'My Transactions']);
    await expandSidebar(page, 'Exam');
    expect(await sidebarChildren(page, 'Exam')).toEqual(['Exams', 'Marks', 'Hall Tickets', 'Results']);
  });

  test('TC-AUTH-06-E02 teacher sidebar', async ({ page, signIn }) => {
    await open(page, signIn, 'teacher');
    const top = await sidebarTop(page);
    expect(top).not.toContain('Fee');
    expect(top).toContain('Administration');
    await expandSidebar(page, 'Students');
    expect(await sidebarChildren(page, 'Students')).toEqual([
      'Admission', 'Attendance', 'Student Documents', 'Student Certificates', 'Certificate Types', 'Certificate Templates',
    ]);
    await expandSidebar(page, 'Transport');
    const transport = await sidebarChildren(page, 'Transport');
    expect(transport).not.toContain('Route Stops');
    expect(transport).not.toContain('Transport Trips');
    await expandSidebar(page, 'Administration');
    expect(await sidebarChildren(page, 'Administration')).toEqual(['Users', 'School Settings']);
  });

  test('TC-AUTH-06-E04 parent sidebar', async ({ page, signIn }) => {
    await open(page, signIn, 'parent');
    expect(await sidebarTop(page)).toEqual(['Dashboard', 'Students', 'Fee', 'Exam']);
    await expandSidebar(page, 'Fee');
    expect(await sidebarChildren(page, 'Fee')).toEqual(['My Fees', 'My Receipts', 'My Transactions']);
  });

  test('TC-AUTH-06-E05 administration cards', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/admin');
    await expect(page.getByText('ADMINISTRATION SECTIONS')).toBeVisible();
    await expect(page.getByText('Manage users')).toBeVisible();
    await expect(page.getByText('Manage school settings')).toBeVisible();
    await page.getByText('Manage users').click();
    await expect(page).toHaveURL(/\/admin\/users/);
  });

  test('TC-AUTH-06-E06 staff administration and masters children', async ({ page, signIn }) => {
    await open(page, signIn, 'staff');
    await expandSidebar(page, 'Administration');
    expect(await sidebarChildren(page, 'Administration')).toEqual(['Users', 'School Settings']);
    await expandSidebar(page, 'Masters');
    const masters = await sidebarChildren(page, 'Masters');
    for (const name of ['Academic Years', 'Classes and Sections', 'Subject Categories', 'Subjects', 'Class Subject Mappings', 'Holidays', 'Parents', 'Roles and Permissions']) {
      expect(masters).toContain(name);
    }
    expect(masters).not.toContain('School Registration');
  });
});
