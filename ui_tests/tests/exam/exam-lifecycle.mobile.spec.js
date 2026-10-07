// Exam F09 lifecycle, mobile (P1).
const { test, expect } = require('../../helpers/fixtures');
const kit = require('./_kit');

const { text, openHub, tile } = kit.mobile;

test.describe('Exam F09 exam lifecycle (mobile)', () => {
  test('TC-EXM-09-E09 activate a draft exam', async ({ page, signIn, api, cleanup }) => {
    test.setTimeout(240_000);
    const klass = await kit.createQaClass(api, cleanup);
    const exam = await kit.createExam(api, cleanup, klass);
    expect((await api('POST', `/exams/${exam.id}/deactivate`)).status).toBe(200);
    await signIn('admin');
    await openHub(page);
    await tile(page, 'Exams');
    await text(page, exam.name).first().click({ timeout: 60_000 });
    await expect(text(page, 'Activate').first()).toBeVisible({ timeout: 60_000 });
    await text(page, 'Activate').first().click();
    await expect(text(page, 'Activate Exam').first()).toBeVisible();
    await text(page, 'Activate', { exact: true }).last().click();
    await expect(text(page, 'Exam Activated').first()).toBeVisible({ timeout: 30_000 });
    await expect(text(page, 'Deactivate').first()).toBeVisible();
    expect((await api('GET', `/exams/${exam.id}`)).data.status).toBe('active');
  });
});
