// Exam F18 Audit log, web (P1). Seeded exam, read only.
const { test, expect } = require('../../helpers/fixtures');

test.describe('Exam F18 audit log (web)', () => {
  test('TC-EXM-18-E01 view the audit log of a seeded exam', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/exam/audit');
    await expect(page.getByText('Select an exam to view its activity history')).toBeVisible();
    await page.getByRole('row').filter({ hasText: 'Unit Test 1 - Class 1B' }).getByRole('button', { name: /View Log/ }).click();
    await expect(page.getByText('Audit Log - Unit Test 1 - Class 1B')).toBeVisible();
    const published = page.getByText('results published', { exact: true });
    const computed = page.getByText('results computed', { exact: true });
    await expect(published).toBeVisible();
    await expect(computed).toBeVisible();
    const pubBox = await published.boundingBox();
    const compBox = await computed.boundingBox();
    expect(pubBox.y).toBeLessThan(compBox.y);
    await expect(page.locator('time').first()).not.toBeEmpty();
  });
});
