// Expense F01 hub, web. Baseline: qa_manual seeded expense data; counts are read from the API because QA rows accumulate.
const { test, expect } = require('../../helpers/fixtures');
const { list } = require('./kit');

test.describe('Expense F01 hub (web)', () => {
  test('TC-EXP-01-E01 hub shows header, stat cards and section cards', async ({ page, signIn, api }) => {
    await signIn('admin');
    await page.goto('/');
    await page.getByRole('button', { name: 'Expense', exact: true }).first().click();
    await expect(page).toHaveURL(/\/expense\/?$/);
    await expect(page.getByRole('heading', { name: 'Expense Management' })).toBeVisible();
    await expect(page.getByText('Track, approve, and analyse all school expenses in one place')).toBeVisible();
    const main = page.getByRole('main');
    await expect(async () => {
      const cats = list(await api('GET', '/expense/categories/?limit=1000')).length;
      const types = list(await api('GET', '/expense/types/?limit=1000')).length;
      const txns = list(await api('GET', '/expense/transactions/?limit=1000')).length;
      await page.reload();
      await expect(main).toContainText(new RegExp(`(^|\\D)${cats}\\s*Expense Categories`), { timeout: 5000 });
      await expect(main).toContainText(new RegExp(`(^|\\D)${types}\\s*Expense Types`), { timeout: 5000 });
      await expect(main).toContainText(new RegExp(`(^|\\D)${txns}\\s*Total Transactions`), { timeout: 5000 });
    }).toPass({ timeout: 40_000 });
    await expect(page.getByText('Expense Sections')).toBeVisible();
    for (const name of ['Categories', 'Types', 'Transactions', 'Departments', 'Summary']) {
      await expect(main.getByText(name, { exact: true }).first()).toBeVisible();
    }
    await expect(main.getByRole('button', { name: 'Open' })).toHaveCount(5);
    await main.getByRole('button', { name: 'Open' }).first().click();
    await expect(page).toHaveURL(/\/expense\/categories/);
  });
});
