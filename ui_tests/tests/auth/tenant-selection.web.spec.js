const { test, expect } = require('../../helpers/fixtures');

test.describe('Auth F01 organisation selection (web)', () => {
  test('TC-AUTH-01-E01 login page loads the tenant years from the default tenant', async ({ page, api }) => {
    const requests = [];
    page.on('request', (r) => {
      if (r.url().includes('/auth/academic-years')) requests.push(r.headers()['cschema']);
    });
    await page.goto('/login');
    await expect(page.getByText('Welcome!')).toBeVisible();
    const select = page.getByRole('button', { name: /^\d{4}-\d{4}/ }).first();
    await expect(select).toContainText('2026-2027 (Current)', { timeout: 20_000 });
    await expect(page.getByRole('button', { name: 'Login' })).toBeEnabled();
    expect(requests.length).toBeGreaterThan(0);
    expect(requests[0]).toBe('qa_manual');
    await select.click();
    await expect(page.getByRole('button', { name: /\(Current\)/ })).toHaveCount(2);
  });
});
