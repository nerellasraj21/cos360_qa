// Reports and dashboards F01 home, F07 attendance reports, F10 academic report, F11 transport report (mobile, P1).
const { test, expect } = require('../../helpers/fixtures');
const { visibleText } = require('../../helpers/auth-users');

async function open(page, route, waitFor) {
  await page.goto(route, { timeout: 180_000 });
  await expect(visibleText(page, waitFor).first()).toBeVisible({ timeout: 60_000 });
}

async function openReport(page, card, banner) {
  await open(page, '/reports', card);
  await visibleText(page, card).first().click();
  await expect(visibleText(page, banner).first()).toBeVisible({ timeout: 60_000 });
}

test.describe('Reports F01 mobile home', () => {
  test('TC-RPT-01-E06 admin home tab', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page, '/', 'Modules');
    await expect(visibleText(page, 'Dashboard').first()).toBeVisible();
    await expect(visibleText(page, /^Good (Morning|Afternoon|Evening),/, { exact: false }).first()).toBeVisible();
    await expect(visibleText(page, 'qa_admin', { exact: false }).first()).toBeVisible();
    const date = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
    await expect(visibleText(page, date, { exact: false }).first()).toBeVisible();
    await expect(visibleText(page, 'Q').first()).toBeVisible();
    const modules = ['Students', 'Staff Management', 'Exam Management', 'Fee Management', 'Expense', 'Communication', 'Reports', 'Masters', 'Administration', 'Transport'];
    for (const name of modules) await expect(visibleText(page, name).first()).toBeVisible();
    const text = await page.locator('body').innerText();
    let last = -1;
    for (const name of modules) {
      const at = text.indexOf(name, Math.max(last, 0));
      expect(at, `${name} after previous card`).toBeGreaterThan(last);
      last = at;
    }
  });
});

test.describe('Reports F07 attendance reports (mobile)', () => {
  test('TC-RPT-07-E01 student attendance report, last 7 days', async ({ page, signIn }) => {
    await signIn('admin');
    await openReport(page, 'Student Reports', 'Student Attendance Report');
    await visibleText(page, 'Last 7D').first().click();
    for (const tile of ['Present', 'Absent', 'Late', 'Present Rate']) await expect(visibleText(page, tile).first()).toBeVisible({ timeout: 60_000 });
    await expect(visibleText(page, 'ATTENDANCE RECORDS').first()).toBeVisible();
  });

  test('TC-RPT-07-E04 staff attendance report, last 30 days', async ({ page, signIn }) => {
    await signIn('admin');
    await openReport(page, 'Staff Reports', 'Staff Attendance Report');
    await visibleText(page, 'Last 30D').first().click();
    for (const tile of ['Present', 'Absent', 'Rate']) await expect(visibleText(page, tile).first()).toBeVisible({ timeout: 60_000 });
    await expect(visibleText(page, 'RECORDS').first()).toBeVisible();
  });
});

test.describe('Reports F10 academic report (mobile)', () => {
  test('TC-RPT-10-E01 exam overview', async ({ page, signIn }) => {
    await signIn('admin');
    await openReport(page, 'Academic Reports', 'Academic / Exam Overview');
    for (const tile of ['Published', 'Active', 'Draft']) await expect(visibleText(page, tile).first()).toBeVisible({ timeout: 60_000 });
    await expect(visibleText(page, 'ALL EXAMS').first()).toBeVisible();
    for (const exam of ['Unit Test 1 - Class 1B', 'Unit Test 1 - Class 2A', 'Half Yearly Examination 2026']) {
      await expect(visibleText(page, exam).first()).toBeVisible();
    }
  });
});

test.describe('Reports F11 transport report (mobile)', () => {
  test('TC-RPT-11-E01 transport overview', async ({ page, signIn }) => {
    await signIn('admin');
    await openReport(page, 'Transport Reports', 'Transport Overview');
    for (const tile of ['Routes', 'Vehicles', 'Trips']) await expect(visibleText(page, tile).first()).toBeVisible({ timeout: 60_000 });
    await expect(visibleText(page, 'ROUTES').first()).toBeVisible();
    await expect(visibleText(page, 'VEHICLES').first()).toBeVisible();
    await expect(visibleText(page, 'Route 1 - Kukatpally').first()).toBeVisible();
    await expect(visibleText(page, 'Route 2 - Uppal').first()).toBeVisible();
  });
});
