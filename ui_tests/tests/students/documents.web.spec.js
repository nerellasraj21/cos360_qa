const { test, expect } = require('../../helpers/fixtures');

test.describe('Students F15 documents (web)', () => {
  test('TC-STU-15-E01 admin picks a student and sees the document list', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/students/studentdocuments');
    await expect(page.getByRole('heading', { name: 'Student Documents' })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText('Please select a student to view their documents.')).toBeVisible();
    await page.getByRole('button', { name: 'Select a student' }).click();
    await page.getByRole('button', { name: 'Karthik Reddy (001)' }).click();
    for (const h of ['Source', 'Name / Type', 'Date']) await expect(page.getByRole('columnheader', { name: h })).toBeVisible();
    const row = page.getByRole('row', { name: /Document Aadhaar Card/ });
    await expect(row).toBeVisible({ timeout: 20_000 });
    await expect(row.getByRole('cell', { name: 'Document', exact: true })).toBeVisible();
    await expect(row.getByRole('cell', { name: /^\d{1,2}\/\d{1,2}\/\d{4}$/ })).toBeVisible();
    await page.getByRole('button', { name: 'Clear' }).click();
    await expect(page.getByText('Please select a student to view their documents.')).toBeVisible();
  });
});
