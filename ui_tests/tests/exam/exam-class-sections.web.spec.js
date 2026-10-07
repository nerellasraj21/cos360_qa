// Exam F07 Class-sections and subject configs, web (P1). Seeded exam, read only.
const { test, expect } = require('../../helpers/fixtures');

test.describe('Exam F07 class-sections and subject configs (web)', () => {
  test('TC-EXM-07-E01 configured subjects grouped by class-section', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/exam/exams');
    await page.getByRole('row').filter({ hasText: 'Half Yearly Examination 2026' }).click();
    await expect(page.getByRole('heading', { name: 'Half Yearly Examination 2026' })).toBeVisible();
    await expect(page.getByText('Configured Subjects')).toBeVisible();
    const headings = [];
    for (const cls of ['1', '2', '3', '4', '5']) {
      for (const section of ['A', 'B']) headings.push(new RegExp(`^Class ${cls}\\s*\\S\\s*${cls}-${section}$`));
    }
    for (const heading of headings) await expect(page.getByText(heading)).toHaveCount(1);
  });
});
