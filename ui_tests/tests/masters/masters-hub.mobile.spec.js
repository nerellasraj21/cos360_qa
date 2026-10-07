// Masters F15 Masters hub and Home module cards, mobile (Expo web). Baseline: qa_manual seeded menu catalog.
const { test, expect } = require('../../helpers/fixtures');

const CARDS = ['Academic Years', 'Classes and Sections', 'Subject Categories', 'Subjects', 'Class Subject Mappings', 'Holidays', 'Parents', 'Roles and Permissions'];
const ALL_MODULES = ['Students', 'Staff Management', 'Exam Management', 'Fee Management', 'Expense', 'Communication', 'Reports', 'Masters', 'Administration', 'Transport'];

async function openHome(page) {
  await page.goto('/', { timeout: 180_000 });
  await expect(page.getByLabel('Open Students', { exact: true }).filter({ visible: true })).toBeVisible({ timeout: 60_000 });
}

async function openHub(page) {
  await openHome(page);
  await page.getByLabel('Open Masters', { exact: true }).filter({ visible: true }).click();
  await expect(page.getByText('Masters Dashboard', { exact: true })).toBeVisible({ timeout: 60_000 });
}

test.describe('Masters F15 hub and menus (mobile)', () => {
  test('TC-MST-15-E05 admin hub lists the eight Masters cards', async ({ page, signIn }) => {
    await signIn('admin');
    await openHub(page);
    await expect(page.getByText('Configure and manage all master data for the school system')).toBeVisible();
    await expect(page.getByText('MASTERS SECTIONS', { exact: true })).toBeVisible();
    for (const name of CARDS) {
      await expect(page.getByText(name, { exact: true }).filter({ visible: true })).toHaveCount(1);
    }
    await expect(page.getByText('Manage classes and sections', { exact: true })).toBeVisible();
    await expect(page.getByText('Define subjects and subject details', { exact: true })).toBeVisible();
    for (const extra of ['Timetable Management', 'Locations', 'Roles & Permissions']) {
      await expect(page.getByText(extra, { exact: true }).filter({ visible: true })).toHaveCount(0);
    }
  });

  test('TC-MST-15-E06 Academic Years card opens the screen', async ({ page, signIn }) => {
    await signIn('admin');
    await openHub(page);
    await page.getByText('Academic Years', { exact: true }).last().click();
    await expect(page).toHaveURL(/\/masters\/academicyears/, { timeout: 60_000 });
    await expect(page.getByText('2026-2027').first()).toBeVisible({ timeout: 60_000 });
  });

  for (const role of ['student', 'parent']) {
    test(`TC-MST-15-E07 ${role} Home has no Masters card`, async ({ page, signIn }) => {
      await signIn(role);
      await openHome(page);
      for (const name of ['Students', 'Exam Management', 'Fee Management']) {
        await expect(page.getByLabel(`Open ${name}`, { exact: true }).filter({ visible: true })).toBeVisible();
      }
      for (const name of ALL_MODULES.filter((m) => !['Students', 'Exam Management', 'Fee Management'].includes(m))) {
        await expect(page.getByLabel(`Open ${name}`, { exact: true }).filter({ visible: true })).toHaveCount(0);
      }
    });
  }
});
