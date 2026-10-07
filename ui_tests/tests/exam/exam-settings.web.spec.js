// Exam F01 Exam settings, web (P1). Tenant-wide singleton: restored in cleanup.
const { test, expect, toast } = require('../../helpers/fixtures');

async function snapshot(api, cleanup) {
  const res = await api('GET', '/exam-settings');
  if (res.status !== 200) return null;
  const { id, ...rest } = res.data;
  cleanup(() => api('PUT', '/exam-settings', { body: rest }));
  return rest;
}

test.describe('Exam F01 exam settings (web)', () => {
  test('TC-EXM-01-E01 save attendance and fee thresholds @serial', async ({ page, signIn, api, cleanup }) => {
    await snapshot(api, cleanup);
    await signIn('admin');
    await page.goto('/exam/settings');
    await expect(page.getByText('Configure school-wide exam defaults')).toBeVisible();
    await page.getByLabel('Minimum Attendance %').fill('80');
    await page.getByLabel('Minimum Fee Paid %').fill('50');
    await page.getByRole('button', { name: 'Save Settings' }).click();
    await toast(page, 'Exam settings saved successfully');
    await page.reload();
    await expect(page.getByLabel('Minimum Attendance %')).toHaveValue('80');
    await expect(page.getByLabel('Minimum Fee Paid %')).toHaveValue('50');
    const res = await api('GET', '/exam-settings');
    expect(res.data.hall_ticket_min_attendance).toBe('80.00');
    expect(res.data.hall_ticket_min_fee_paid_pct).toBe('50.00');
  });
});
