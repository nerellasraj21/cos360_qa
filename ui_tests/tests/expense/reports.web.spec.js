// Expense F13 summary, F14 reports, F15 audit, web. Read-only. Summary totals are derived from the API because QA
// transactions (which cannot be deleted) add to the seeded 12 rows; the seeded baseline itself is asserted from the API too.
const { test, expect } = require('../../helpers/fixtures');
const { list, inr } = require('./kit');

test.describe('Expense F13-F15 summary, reports, audit (web)', () => {
  test('TC-EXP-13-E01 summary shows totals and the Utilities block', async ({ page, signIn, api }) => {
    await signIn('admin');
    await page.goto('/expense/summary');
    await expect(page.getByRole('heading', { name: 'Expense Summary' })).toBeVisible();
    const main = page.getByRole('main');
    await expect(async () => {
      const all = list(await api('GET', '/expense/transactions/?limit=1000')).filter((t) => t.status !== 'cancelled');
      const seeded = all.filter((t) => String(t.idempotency_key).startsWith('demo-seed'));
      expect(seeded).toHaveLength(12);
      expect(seeded.reduce((s, t) => s + Number(t.amount), 0)).toBeCloseTo(209949, 2);
      const total = all.reduce((s, t) => s + Number(t.amount), 0);
      const types = list(await api('GET', '/expense/types/?limit=1000'));
      const typeTotal = (name) => {
        const id = types.find((t) => t.name === name).id;
        return all.filter((t) => t.expense_type_id === id).reduce((s, t) => s + Number(t.amount), 0);
      };
      await page.reload();
      await expect(main).toContainText(`₹${inr(total)}`, { timeout: 5000 });
      await expect(main).toContainText(new RegExp(`Total Entries\\s*${all.length}`), { timeout: 5000 });
      await expect(main.getByRole('button', { name: new RegExp(`^Electricity Bill.*₹${inr(typeTotal('Electricity Bill'))}`) })).toBeVisible({ timeout: 5000 });
      await expect(main.getByRole('button', { name: new RegExp(`^Water Bill.*₹${inr(typeTotal('Water Bill'))}`) })).toBeVisible({ timeout: 5000 });
      await expect(main.getByRole('button', { name: new RegExp(`^Internet and Telephone.*₹${inr(typeTotal('Internet and Telephone'))}`) })).toBeVisible({ timeout: 5000 });
    }).toPass({ timeout: 40_000 });
    await expect(main.getByText('Category Total:').first()).toBeVisible();
    await expect(main).toContainText('Utilities');
    await expect(main).toContainText('Categories5');
    const footer = main.getByText('Grand Total', { exact: true });
    await expect(footer).toHaveCount(2);
  });

  test('TC-EXP-14-E01 by-category report for September 2026', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/expense/reports');
    await expect(page.getByRole('button', { name: 'By Category' })).toBeVisible();
    const dates = page.getByRole('main').locator('input[type="date"], input[type="text"]');
    await dates.nth(0).fill('2026-09-01');
    await dates.nth(1).fill('2026-09-30');
    await page.getByRole('button', { name: 'Generate Report' }).click();
    const main = page.getByRole('main');
    await expect(main).toContainText('₹2,09,949.00');
    await expect(main).toContainText(/12\s*Total Transactions|Total Transactions\s*12/);
    await expect(main.getByText('Category Breakdown')).toBeVisible();
    const rows = main.locator('tbody tr');
    await expect(rows).toHaveCount(5);
    await expect(rows.first()).toContainText('Infrastructure');
    await expect(rows.first()).toContainText('₹80,750.00');
    await expect(rows.first()).toContainText('%');
    for (const header of ['Total Amount', 'Transactions', 'Average', '% of Total']) {
      await expect(main.getByRole('columnheader', { name: header })).toBeVisible();
    }
    await expect(main.locator('p').filter({ hasText: /^Categories$/ }).locator('xpath=following-sibling::p[1]')).toHaveText('0');
  });

  test('TC-EXP-15-E01 audit logs are empty for a transaction', async ({ page, signIn }) => {
    test.fail(true, 'UI-EXP-01: the audit summary counters (Total Logs, Creation, Updates, Approvals) render blank instead of 0 because the live summary endpoint returns total_entries/action_breakdown while the web reads total_logs/creation_logs/update_logs/approval_logs');
    await signIn('admin');
    await page.goto('/expense/audit');
    await page.getByRole('tab', { name: 'Transaction Audit' }).click();
    await page.getByRole('row').filter({ hasText: 'Chart paper and markers for classrooms' }).getByRole('button', { name: 'View Audit' }).click();
    const main = page.getByRole('main');
    await expect(main.getByText('Audit Summary for Selected Transaction')).toBeVisible();
    // doc: the counters sit under the table on the Transaction Audit tab, not on the Audit Logs tab
    for (const label of ['Total Logs', 'Creation', 'Updates', 'Approvals']) {
      await expect(main.getByText(label, { exact: true }).locator('xpath=preceding-sibling::div[1]')).toHaveText('0');
    }
    await page.getByRole('tab', { name: 'Audit Logs' }).click();
    await expect(page.getByRole('tabpanel', { name: 'Audit Logs' }).getByText('No audit logs found for this transaction')).toBeVisible();
  });
});
