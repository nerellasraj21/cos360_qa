// Exam F05 Remark grade sets, web (P1).
const { test, expect, unique, toast } = require('../../helpers/fixtures');

test.describe('Exam F05 remark grade sets (web)', () => {
  test('TC-EXM-05-E01 create a remark set with two options', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Primary Remarks');
    cleanup(async () => {
      const list = await api('GET', '/remark-grades');
      for (const s of list.data.filter((x) => (x.name || x.set_name) === name)) await api('DELETE', `/remark-grades/${s.id}`);
    });
    await signIn('admin');
    await page.goto('/exam/grading');
    await page.getByRole('button', { name: /Open/ }).nth(2).click();
    await page.getByRole('button', { name: 'New Set' }).first().click();
    const dialog = page.getByRole('dialog');
    await dialog.getByPlaceholder('Primary Remarks Set').fill(name);
    await expect(dialog.getByPlaceholder('A', { exact: true }).first()).toHaveValue('A');
    await expect(dialog.getByPlaceholder('Excellent', { exact: true }).first()).toHaveValue('Excellent');
    await dialog.getByRole('button', { name: 'Add Option' }).click();
    await dialog.getByPlaceholder('A', { exact: true }).nth(1).fill('B');
    await dialog.getByPlaceholder('Excellent', { exact: true }).nth(1).fill('Good');
    await dialog.getByRole('button', { name: 'Save Set' }).click();
    await toast(page, 'Remark grade set created successfully');
    const row = page.getByRole('row').filter({ hasText: name });
    await expect(row).toContainText('A: Excellent');
    await expect(row).toContainText('B: Good');
    await expect(page.getByRole('row').filter({ hasText: 'Co-Scholastic Grading' })).toBeVisible();
  });
});
