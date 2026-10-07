// Exam F09 Edit, clone, activate, deactivate, delete, web (P1).
const { test, expect, toast } = require('../../helpers/fixtures');
const kit = require('./_kit');

test.describe('Exam F09 exam lifecycle (web)', () => {
  test('TC-EXM-09-E01 rename an exam from the list', async ({ page, signIn, api, cleanup }) => {
    const klass = await kit.createQaClass(api, cleanup);
    const exam = await kit.createExam(api, cleanup, klass);
    await signIn('admin');
    await page.goto('/exam/exams');
    await page.getByPlaceholder('Search exams...').fill(exam.name);
    const row = page.getByRole('row').filter({ hasText: exam.name });
    await row.getByRole('button', { name: 'Edit Exam' }).click();
    const dialog = page.getByRole('dialog');
    const input = dialog.getByRole('textbox').first();
    await expect(input).toHaveValue(exam.name);
    await input.fill(`${exam.name} v2`);
    await dialog.getByRole('button', { name: 'Save Changes' }).click();
    await toast(page, 'Exam updated successfully');
    await expect(page.getByRole('row').filter({ hasText: `${exam.name} v2` })).toBeVisible();
    const after = await api('GET', `/exams/${exam.id}`);
    expect(after.data.exam_name).toBe(`${exam.name} v2`);
  });

  test('TC-EXM-09-E03 activate a draft exam', async ({ page, signIn, api, cleanup }) => {
    const klass = await kit.createQaClass(api, cleanup);
    const exam = await kit.createExam(api, cleanup, klass);
    expect((await api('POST', `/exams/${exam.id}/deactivate`)).status).toBe(200);
    await signIn('admin');
    await page.goto(`/exam/exams/${exam.id}`);
    await expect(page.getByText(/^draft$/i).first()).toBeVisible();
    await page.getByRole('button', { name: 'Activate', exact: true }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Activate', exact: true }).click();
    await toast(page, 'Exam activated');
    await expect(page.getByText(/^active$/i).first()).toBeVisible();
    await expect(page.getByRole('button', { name: 'Deactivate' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Activate', exact: true })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Delete', exact: true })).toHaveCount(0);
    expect((await api('GET', `/exams/${exam.id}`)).data.status).toBe('active');
  });

  test('TC-EXM-09-E05 clone an exam', async ({ page, signIn, api, cleanup }) => {
    const klass = await kit.createQaClass(api, cleanup);
    const exam = await kit.createExam(api, cleanup, klass);
    const copyName = `Copy of ${exam.name}`;
    cleanup(async () => {
      const list = await api('GET', '/exams');
      for (const e of kit.rows(list).filter((x) => x.exam_name === copyName)) await api('DELETE', `/exams/${e.id}`);
    });
    await signIn('admin');
    await page.goto(`/exam/exams/${exam.id}`);
    await page.getByRole('button', { name: 'Clone', exact: true }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('textbox')).toHaveValue(`${exam.name} (Copy)`);
    await dialog.getByRole('button', { name: 'Clone', exact: true }).click();
    await toast(page, 'Exam cloned successfully');
    await expect(page.getByRole('heading', { name: copyName })).toBeVisible();
    await expect(page.getByText(/^draft$/i).first()).toBeVisible();
    await expect(page.getByText('Configured Subjects')).toBeVisible();
    await expect(page.getByText('Mathematics', { exact: true })).toHaveCount(0);
  });
});
