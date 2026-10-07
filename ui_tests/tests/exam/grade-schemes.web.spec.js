// Exam F03 Exam grade schemes, web (P1).
const { test, expect, unique, toast } = require('../../helpers/fixtures');

async function fillBands(dialog, bands) {
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
}

test.describe('Exam F03 exam grade schemes (web)', () => {
  test('TC-EXM-03-E01 create a six band scheme', async ({ page, signIn, api, cleanup }) => {
    test.fail(true, 'UI-EXM-01: band From % and To % number inputs have no step, so the browser blocks decimals such as 89.99 and the scheme cannot be saved');
    const name = unique('QA Standard');
    cleanup(async () => {
      const list = await api('GET', '/grade-schemes/exam');
      for (const s of list.data.filter((x) => (x.name || x.scheme_name) === name)) await api('DELETE', `/grade-schemes/exam/${s.id}`);
    });
    await signIn('admin');
    await page.goto('/exam/grading');
    await page.getByRole('button', { name: /Open/ }).nth(0).click();
    await expect(page.getByText('Map total percentage ranges')).toBeVisible();
    await page.getByRole('button', { name: 'New Scheme' }).first().click();
    const dialog = page.getByRole('dialog');
    await dialog.getByPlaceholder('CBSE Standard').fill(name);
    await fillBands(dialog, [
      [90, 100, 'A+', 4, true],
      [80, 89.99, 'A', 3.5, true],
      [70, 79.99, 'B', 3, true],
      [60, 69.99, 'C', 2, true],
      [35, 59.99, 'D', 1, true],
      [0, 34.99, 'F', 0, false],
    ]);
    await dialog.getByRole('button', { name: 'Save Scheme' }).click();
    await toast(page, 'Exam grade scheme created successfully');
    const row = page.getByRole('row').filter({ hasText: name });
    await expect(row).toContainText('6 bands');
  });
});
