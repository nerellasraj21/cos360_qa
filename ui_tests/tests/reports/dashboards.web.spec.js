// Reports and dashboards F01 dashboard, F02 masters hub, F03 reports hub, F06 fee reports (web, P1).
const { test, expect } = require('../../helpers/fixtures');

test.describe('Reports F01 web dashboard', () => {
  test('TC-RPT-01-E01 admin dashboard cards', async ({ page, signIn }) => {
    // doc: the card order is Students, Staff, Fee, Expense, Communication, Reports, Masters, Administration, Transport, Billing Admin, Exam, Timetable, Calendar (Exam is not third)
    await signIn('admin');
    await page.goto('/');
    await page.waitForURL(/\/dashboard$/);
    await expect(page.getByRole('heading', { name: 'Dashboard', level: 1 })).toBeVisible();
    await expect(page.getByText(/Welcome back, .+ \(Admin\)/)).toBeVisible();
    const titles = await page.getByRole('main').getByRole('heading', { level: 4 }).allInnerTexts();
    expect(titles).toEqual([
      'Students', 'Staff', 'Fee', 'Expense', 'Communication', 'Reports', 'Masters', 'Administration', 'Transport',
      'Billing Admin', 'Exam', 'Timetable', 'Calendar',
    ]);
    for (const name of ['Billing Admin', 'Exam', 'Timetable', 'Calendar']) {
      await expect(page.getByText(`Open ${name.toLowerCase()}`, { exact: true })).toBeVisible();
    }
  });
});

test.describe('Reports F02 masters hub', () => {
  test('TC-RPT-02-E02 masters dashboard sections', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/masters');
    await expect(page.getByRole('heading', { name: 'Masters Dashboard', level: 1 })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Masters Sections' })).toBeVisible();
    const titles = await page.getByRole('main').getByRole('heading', { level: 4 }).allInnerTexts();
    expect(titles).toEqual([
      'Academic Years', 'Classes and Sections', 'Subject Categories', 'Subjects', 'Class Subject Mappings', 'Holidays', 'Parents',
      'Roles and Permissions',
    ]);
  });
});

test.describe('Reports F03 reports hub', () => {
  test('TC-RPT-03-E01 reports hub lists fee and expense reports', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/reports');
    await expect(page.getByRole('heading', { name: 'Reports', level: 1 })).toBeVisible();
    await expect(page.getByText('Comprehensive analytics and reporting across all school modules')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Reports Sections' })).toBeVisible();
    const titles = await page.getByRole('main').getByRole('heading', { level: 4 }).allInnerTexts();
    expect(titles).toEqual(['Fee Reports', 'Expense Reports']);
  });
});

test.describe('Reports F06 fee reports page', () => {
  test('TC-RPT-06-E01 collection summary loads with statistics and rows', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/reports');
    await page.getByRole('heading', { name: 'Fee Reports', level: 4 }).click();
    await expect(page.getByRole('heading', { name: 'Fee Reports & Export' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Collection Summary' })).toHaveAttribute('aria-selected', 'true');
    for (const metric of ['Total Collected', 'Total Due', 'Collection %', 'Payment Methods']) {
      await expect(page.getByRole('cell', { name: metric, exact: true })).toBeVisible();
    }
    await expect(page.getByRole('columnheader', { name: 'Transaction #', exact: true })).toBeVisible();
    await expect(page.locator('tbody tr').nth(5)).toBeVisible();
    await expect(page.getByText('Select at least one filter to generate a report')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Export' })).toBeDisabled();
  });

  test('TC-RPT-06-E06 export a class-filtered report as Excel', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/fee/reports');
    await page.getByRole('combobox', { name: 'All Classes' }).click();
    await page.getByRole('option', { name: 'Class 1', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Excel' })).toBeVisible();
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Export' }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/\.xlsx$/);
    await expect(page.getByText('Report exported successfully').first()).toBeVisible({ timeout: 15_000 });
  });
});
