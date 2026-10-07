// Exam F01 Exam settings, mobile (P1). Tenant-wide singleton: restored in cleanup.
const { test, expect } = require('../../helpers/fixtures');
const kit = require('./_kit');

const { vis, text, openHub, tile } = kit.mobile;

test.describe('Exam F01 exam settings (mobile)', () => {
  test('TC-EXM-01-E06 save the minimum attendance @serial', async ({ page, signIn, api, cleanup }) => {
    test.setTimeout(240_000);
    const original = await api('GET', '/exam-settings');
    if (original.status === 200) {
      const { id, ...rest } = original.data;
      cleanup(() => api('PUT', '/exam-settings', { body: rest }));
    }
    await signIn('admin');
    await openHub(page);
    await tile(page, 'Exam Settings');
    await expect(text(page, 'Board Configuration').first()).toBeVisible({ timeout: 60_000 });
    const attendance = vis(page.getByPlaceholder('75'));
    await attendance.fill('80');
    await text(page, 'Save Settings').first().click();
    await expect(text(page, 'Saved').first()).toBeVisible({ timeout: 15_000 });
    await expect(text(page, 'Exam settings updated.').first()).toBeVisible();
    const after = await api('GET', '/exam-settings');
    expect(after.data.hall_ticket_min_attendance).toBe('80.00');
    expect(after.data.grace_max_per_subject).toBeNull();
    await page.goBack();
    await expect(text(page, 'Exam Management').first()).toBeVisible({ timeout: 60_000 });
    await tile(page, 'Exam Settings');
    await expect(vis(page.getByPlaceholder('75'))).toHaveValue(/^80(\.00)?$/, { timeout: 30_000 });
  });
});
