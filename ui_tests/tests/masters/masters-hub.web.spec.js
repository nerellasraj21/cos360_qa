// Masters F15 Masters hub and menu entries, web. Baseline: qa_manual seeded menu catalog.
const { test, expect } = require('../../helpers/fixtures');
const { signInWeb } = require('../../helpers/session');

const CARDS = {
  'Academic Years': 'Configure and manage academic year cycles',
  'Classes and Sections': 'Manage classes and sections',
  'Subject Categories': 'Organize subjects into categories',
  Subjects: 'Define subjects and subject details',
  'Class Subject Mappings': 'Map subjects to classes and sections',
  Holidays: 'Configure school holidays and calendar events',
  Parents: 'Manage parent and guardian information',
  'Roles and Permissions': 'Manage roles and permissions',
};

function sidebarMasters(page) {
  return page.getByRole('button', { name: 'Masters', exact: true }).or(page.getByRole('link', { name: 'Masters', exact: true }));
}

async function expectHub(page) {
  await page.goto('/masters');
  await expect(page.getByRole('heading', { name: 'Masters Dashboard' })).toBeVisible();
  await expect(page.getByText('Configure and manage all master data for the school system')).toBeVisible();
  await expect(page.getByRole('heading', { name: /masters sections/i })).toBeVisible();
  const main = page.getByRole('main');
  for (const [name, description] of Object.entries(CARDS)) {
    await expect(main.getByRole('heading', { name, exact: true })).toBeVisible();
    await expect(main.getByText(description, { exact: true })).toBeVisible();
  }
  const cardHeadings = await main.getByRole('heading', { level: 4 }).allInnerTexts();
  expect(cardHeadings.sort()).toEqual(Object.keys(CARDS).sort());
}

test.describe('Masters F15 hub and menus (web)', () => {
  test('TC-MST-15-E01 admin hub lists the eight Masters cards', async ({ page, signIn }) => {
    await signIn('admin');
    await expectHub(page);
  });

  test('TC-MST-15-E02 Subjects card opens the subjects page', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/masters');
    await page.getByRole('main').getByRole('heading', { name: 'Subjects', exact: true }).click();
    await expect(page).toHaveURL(/\/masters\/subjects$/);
  });

  test('TC-MST-15-E03 teacher and staff see the same eight cards', async ({ browser }) => {
    for (const role of ['teacher', 'staff']) {
      const context = await browser.newContext({ baseURL: test.info().project.use.baseURL, viewport: { width: 1280, height: 800 } });
      const page = await context.newPage();
      await signInWeb(page, role);
      await expectHub(page);
      await context.close();
    }
  });

  test('TC-MST-15-E04 student and parent have no Masters sidebar entry', async ({ browser }) => {
    for (const role of ['admin', 'student', 'parent']) {
      const context = await browser.newContext({ baseURL: test.info().project.use.baseURL, viewport: { width: 1280, height: 800 } });
      const page = await context.newPage();
      await signInWeb(page, role);
      await page.goto('/');
      await expect(page.getByRole('button', { name: 'Dashboard', exact: true }).or(page.getByRole('link', { name: 'Dashboard', exact: true })).first()).toBeVisible();
      await expect(sidebarMasters(page)).toHaveCount(role === 'admin' ? 1 : 0);
      await context.close();
    }
  });
});
