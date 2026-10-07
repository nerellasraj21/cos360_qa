// Exam F04 Subject grade schemes, web (P1).
const { test, expect, unique, toast } = require('../../helpers/fixtures');

test.describe('Exam F04 subject grade schemes (web)', () => {
  test('TC-EXM-04-E01 create a two band subject scheme', async ({ page, signIn, api, cleanup }) => {
    test.fail(true, 'UI-EXM-01: band From % and To % number inputs have no step, so the browser blocks decimals such as 32.99 and the scheme cannot be saved');
    const name = unique('QA Science Grading');
    cleanup(async () => {
      const list = await api('GET', '/grade-schemes/subject');
      for (const s of list.data.filter((x) => (x.name || x.scheme_name) === name)) await api('DELETE', `/grade-schemes/subject/${s.id}`);
    });
    await signIn('admin');
    await page.goto('/exam/grading');
    await page.getByRole('button', { name: /Open/ }).nth(1).click();
    await expect(page.getByText('Per-subject grade calculation')).toBeVisible();
    await page.getByRole('button', { name: 'New Scheme' }).first().click();
    const dialog = page.getByRole('dialog');
    await dialog.getByPlaceholder('Science Grading').fill(name);
    const bands = [[0, 32.99, 'F', 0, false], [33, 100, 'P', 1, true]];
    for (let i = 0; i < bands.length; i += 1) {
      await dialog.getByRole('button', { name: 'Add Band' }).click();
      const row = dialog.locator('tbody tr').nth(i);
      const [from, to, label, gpa, pass] = bands[i];
      await row.getByRole('spinbutton').nth(0).fill(String(from));
      await row.getByRole('spinbutton').nth(1).fill(String(to));
      await row.getByRole('textbox').nth(0).fill(label);
      await row.getByRole('spinbutton').nth(2).fill(String(gpa));
      if (pass === false) await row.getByRole('checkbox').uncheck();
    }
    await dialog.getByRole('button', { name: 'Save Scheme' }).click();
    await toast(page, 'Subject grade scheme created successfully');
    await expect(page.getByRole('row').filter({ hasText: name })).toContainText('2 bands');
  });
});
