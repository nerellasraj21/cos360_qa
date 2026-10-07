// Exam F18 Audit log, mobile (P1). Seeded exam, read only.
const { test, expect } = require('../../helpers/fixtures');
const kit = require('./_kit');

const { text, vis, openHub, tile } = kit.mobile;

test.describe('Exam F18 audit log (mobile)', () => {
  test('TC-EXM-18-E07 search the audit log of a seeded exam', async ({ page, signIn }) => {
    test.setTimeout(180_000);
    await signIn('admin');
    await openHub(page);
    await tile(page, 'Audit Log');
    await expect(text(page, 'Exam Audit Logs').first()).toBeVisible({ timeout: 60_000 });
    await expect(vis(page.getByPlaceholder('Search by name, board, or status…'))).toBeVisible();
    await text(page, 'View Log').first().waitFor({ timeout: 30_000 });
    const card = page.locator('div').filter({ hasText: 'Half Yearly Examination 2026' }).filter({ has: page.getByText('View Log') }).last();
    await card.getByText('View Log').locator('visible=true').first().click();
    await expect(vis(page.getByPlaceholder('Search action, actor, description...'))).toBeVisible({ timeout: 60_000 });
    await expect(text(page, /hall.tickets.computed/i, { exact: false }).first()).toBeVisible();
    await expect(text(page, /hall.tickets.published/i, { exact: false }).first()).toBeVisible();
    await vis(page.getByPlaceholder('Search action, actor, description...')).fill('publish');
    await expect(text(page, /hall.tickets.published/i, { exact: false }).first()).toBeVisible();
    await expect(text(page, /hall.tickets.computed/i, { exact: false })).toHaveCount(0);
  });
});
