// Staff F09 drivers list as consumed by the trip form (web). Baseline: qa_manual seeded drivers Ramesh Yadav and Mohan Singh.
const { test, expect } = require('../../helpers/fixtures');

test.describe('Staff drivers (web)', () => {
  test('TC-STF-09-E01 trip form offers only drivers', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/masters/trips');
    await page.getByRole('button', { name: 'Create Trip' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText('Create New Trip')).toBeVisible();
    await dialog.getByText('Select driver...').click();
    const list = page.locator('div').filter({ hasText: /^Select driver\.\.\./ }).last();
    await expect(list).toContainText('Ramesh Yadav');
    await expect(list).toContainText('Mohan Singh');
    const rest = (await list.innerText()).replace('Select driver...', '').replace('Ramesh Yadav', '').replace('Mohan Singh', '');
    expect(rest.trim()).toBe('');
    await dialog.getByRole('button', { name: 'Cancel' }).click();
    await expect(dialog).toBeHidden();
  });
});
