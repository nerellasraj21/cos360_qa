// Exam F17 Student and parent views, web (P1). Own QA student with an activated login.
const { test, expect } = require('../../helpers/fixtures');
const { TEMP, activateViaApi, webSubmitLogin, tag } = require('../../helpers/authkit');
const kit = require('./_kit');

test.describe.configure({ timeout: 150_000 });

test.describe('Exam F17 student marks (web)', () => {
  test('TC-EXM-17-E01 student views own marks for an exam', async ({ page, api, cleanup }) => {
    const klass = await kit.createQaClass(api, cleanup);
    const students = await kit.createStudents(api, cleanup, klass, ['Alpha', 'Bravo']);
    const exam = await kit.createExam(api, cleanup, klass);
    await kit.saveMarks(api, exam, klass, students[0], {
      'Mathematics:Written': 62,
      'Mathematics:Oral': 18,
      'English:Written': 70,
      'Environmental Studies:Written': 90,
    });
    const password = await activateViaApi(students[0].admissionNumber, TEMP.student());
    await webSubmitLogin(page, students[0].admissionNumber, password);
    await expect(page).not.toHaveURL(/login/, { timeout: 30_000 });
    await page.goto('/exam/marks');
    await page.getByRole('row').filter({ hasText: exam.name }).getByRole('button', { name: 'View My Marks' }).click();
    await expect(page.getByRole('heading', { name: exam.name })).toBeVisible();
    await expect(page.getByText(students[0].name)).toBeVisible();
    await expect(page.getByText('80 / 100', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('70 / 100', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('90 / 100', { exact: true }).first()).toBeVisible();
    // doc: components without a saved mark are not listed at all, so "Not entered" never appears; the case should say only entered components are shown
    await expect(page.getByText('Not entered')).toHaveCount(0);
    await expect(page.getByText('62').first()).toBeVisible();
    await expect(page.getByText('Mathematics', { exact: true }).first()).toBeVisible();
  });
});
