// Exam F08 Exam dates, web (P1).
const { test, expect, toast } = require('../../helpers/fixtures');
const kit = require('./_kit');

test.describe('Exam F08 exam dates (web)', () => {
  test('TC-EXM-08-E01 add an exam date', async ({ page, signIn, api, cleanup }) => {
    test.fail(true, 'UI-EXM-03: in the Add Exam Date dialog the Start and End time pickers cannot be used with the mouse; clicks on the hour, minute and AM/PM items hit the dialog overlay, the popover closes and the time stays Select time');
    const klass = await kit.createQaClass(api, cleanup);
    const exam = await kit.createExam(api, cleanup, klass);
    await signIn('admin');
    await page.goto(`/exam/exams/${exam.id}`);
    await page.getByRole('button', { name: 'Dates', exact: true }).click();
    await page.getByRole('button', { name: 'Manage Dates' }).click();
    await page.getByRole('button', { name: /^(Add Date|Add First Date)$/ }).first().click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText('Add Exam Date')).toBeVisible();
    const selects = dialog.getByRole('combobox');
    await selects.nth(0).selectOption({ label: klass.name });
    await selects.nth(1).selectOption({ label: 'A' });
    await selects.nth(2).selectOption({ label: 'Mathematics' });
    await dialog.locator('input[type="date"]').fill('2026-10-20');
    for (const [index, hour, period] of [[0, '09', 'AM'], [1, '12', 'PM']]) {
      const trigger = dialog.getByRole('button', { name: /Select time|\d\d:\d\d (AM|PM)/ }).nth(index);
      await trigger.click();
      const popover = page.getByRole('dialog').filter({ hasText: 'Hour' });
      for (const item of [popover.getByRole('button', { name: period, exact: true }), popover.getByRole('button', { name: hour, exact: true }).first()]) {
        const box = await item.boundingBox({ timeout: 2000 }).catch(() => null);
        if (box) await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
      }
      await expect(trigger).toContainText(`${hour}:00 ${period}`, { timeout: 3000 });
    }
    await dialog.getByPlaceholder('Hall A').fill('QA Hall A');
    await dialog.getByRole('button', { name: 'Save' }).click();
    await toast(page, 'Exam date added');
    const row = page.getByRole('row').filter({ hasText: 'QA Hall A' });
    await expect(row).toContainText('Mathematics');
    await expect(row).toContainText(klass.name);
    await expect(row).toContainText('A');
    await expect(row).toContainText('2026-10-20');
    await expect(row).toContainText('09:00');
    await expect(row).toContainText('12:00');
  });
});
