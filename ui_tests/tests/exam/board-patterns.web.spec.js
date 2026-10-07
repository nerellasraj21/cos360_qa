// Exam F02 Board patterns, web (P1).
const { test, expect, toast } = require('../../helpers/fixtures');

test.describe('Exam F02 board patterns (web)', () => {
  test('TC-EXM-02-E01 create a CBSE primary pattern', async ({ page, signIn, api, cleanup }) => {
    const drop = async () => {
      const list = await api('GET', '/board-patterns');
      for (const p of list.data.filter((x) => x.board === 'CBSE' && x.level === 'primary')) await api('DELETE', `/board-patterns/${p.id}`);
    };
    await drop();
    cleanup(drop);
    await signIn('admin');
    await page.goto('/exam/board-patterns');
    await page.getByRole('button', { name: 'New Pattern' }).first().click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText('Create Board Pattern')).toBeVisible();
    await expect(dialog.getByText('CBSE', { exact: true })).toBeVisible();
    await expect(dialog.getByText('Primary', { exact: true })).toBeVisible();
    await dialog.getByPlaceholder('FA1').fill('QA FA1');
    await dialog.locator('select').selectOption('formative');
    await dialog.getByPlaceholder('10').fill('10');
    await dialog.getByPlaceholder('2').fill('2');
    await dialog.getByRole('button', { name: 'Save Pattern' }).click();
    await toast(page, 'Board pattern created successfully');
    const created = page.getByRole('row').filter({ hasText: 'CBSE' });
    await expect(created).toContainText('Primary');
    await expect(created).toContainText('1 types');
  });
});
