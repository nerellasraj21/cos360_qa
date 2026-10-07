const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { seededClass, apiStudent } = require('./_kit');

test.describe('Students F21 student transport (web)', () => {
  test('TC-STU-21-E01 assign, edit the fee and delete a transport assignment', async ({ page, signIn, api, cleanup }) => {
    test.fail(true, 'UI-STU-02: choosing a trip in the Assign Transport dialog crashes the page ("Something went wrong!", Select.Item must not have an empty value) because the pricing dropdown contains a "None" item with an empty value');
    const klass = await seededClass(api);
    const kid = await apiStudent(api, cleanup, klass, { first: unique('QA Asha'), last: 'Rao' });
    cleanup(async () => {
      const list = await api('GET', `/students/student-transport/student/${kid.studentId}`);
      const rows = Array.isArray(list.data) ? list.data : (list.data && list.data.items) || [];
      for (const r of rows) await api('DELETE', `/students/student-transport/${r.id}`);
    });
    await signIn('admin');
    await page.goto('/students/studenttransport');
    await expect(page.getByRole('heading', { name: 'Student Transport' })).toBeVisible({ timeout: 30_000 });
    await page.getByRole('button', { name: 'Assign Transport' }).click();
    const d = page.getByRole('dialog', { name: 'Assign Transport' });
    await d.getByRole('combobox').nth(0).fill(kid.first);
    await page.getByRole('option', { name: new RegExp(kid.first) }).click();
    await d.getByRole('combobox').nth(1).click();
    await page.getByRole('option', { name: 'Trip #1' }).first().click();
    await page.waitForTimeout(1500);
    await expect(page.getByText('Something went wrong!')).toHaveCount(0);
    await expect(d).toBeVisible();
    await d.getByRole('combobox').nth(2).click();
    await page.getByRole('option').first().click();
    await d.getByRole('button', { name: 'Assign', exact: true }).click();
    const row = page.getByRole('row', { name: new RegExp(kid.first) });
    await expect(row).toBeVisible();
    await expect(row).toContainText('Route');
    await row.getByRole('button', { name: 'Edit' }).click();
    await page.getByRole('dialog').getByRole('spinbutton').fill('1500');
    await page.getByRole('dialog').getByRole('button', { name: /Save|Update/ }).click();
    await expect(row).toContainText('1,500');
    await row.getByRole('button', { name: 'Delete' }).click();
    await expect(page.getByRole('dialog').getByText('Delete Transport Assignment')).toBeVisible();
    await page.getByRole('dialog').getByRole('button', { name: /Delete/ }).last().click();
    await expect(row).toHaveCount(0);
  });
});
