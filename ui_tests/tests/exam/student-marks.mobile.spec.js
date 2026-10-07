// Exam F17 Student views, mobile (P1). Own QA student with an activated login (activated through the API).
const { test, expect } = require('../../helpers/fixtures');
const { TEMP, activateViaApi } = require('../../helpers/authkit');
const { mobileFormSignInAs } = require('../../helpers/auth-users');
const kit = require('./_kit');

const { text } = kit.mobile;

test.describe('Exam F17 student marks (mobile)', () => {
  test('TC-EXM-17-E08 student opens an exam and sees own marks', async ({ page, api, cleanup }) => {
    test.setTimeout(300_000);
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
    await mobileFormSignInAs(page, students[0].admissionNumber, password);
    await page.goto('/exam', { timeout: 180_000 });
    await text(page, 'Exams').first().click({ timeout: 90_000 });
    await text(page, exam.name).first().click({ timeout: 60_000 });
    for (const subject of ['Mathematics', 'English', 'Environmental Studies']) {
      await expect(text(page, subject).first()).toBeVisible({ timeout: 60_000 });
    }
    await expect(text(page, /80/, { exact: false }).first()).toBeVisible();
    await expect(text(page, /70/, { exact: false }).first()).toBeVisible();
    await expect(text(page, /90/, { exact: false }).first()).toBeVisible();
  });
});
