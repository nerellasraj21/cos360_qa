// Staff F01 Designations, mobile (Expo web). Baseline: qa_manual seeded designations.
const { test, expect, unique, toast } = require('../../helpers/fixtures');

const ROUTE = '/staff/designations';

async function findDesignation(api, title) {
  const res = await api('GET', '/staff/designations/?limit=100');
  const rows = Array.isArray(res.data) ? res.data : res.data.items || [];
  return rows.find((d) => d.title === title);
}

test.describe('Staff F01 designations (mobile)', () => {
  test('TC-STF-01-E09 create a designation', async ({ page, signIn, api, cleanup }) => {
    const title = unique('QA Cook');
    await signIn('admin');
    await page.goto(ROUTE, { timeout: 180_000 });
    await expect(page.getByText('Accountant').first()).toBeVisible({ timeout: 60_000 });
    const before = await page.getByText(/\d+ designations?/).first().innerText();
    await page.getByText('Add Designation').first().click();
    await page.getByPlaceholder(/designation/i).last().fill(title);
    await page.getByText('Save', { exact: true }).last().click();
    await toast(page, 'Designation created successfully');
    const created = await findDesignation(api, title);
    expect(created).toBeTruthy();
    cleanup(() => api('DELETE', `/staff/designations/${created.id}`));
    await expect(page.getByText(title).first()).toBeVisible();
    const after = await page.getByText(/\d+ designations?/).first().innerText();
    expect(parseInt(after)).toBeGreaterThan(parseInt(before));
  });
});
