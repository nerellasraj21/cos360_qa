// Exam F12 Marks summary, web (P1). Own QA class, students and exam.
const { test, expect } = require('../../helpers/fixtures');
const kit = require('./_kit');

test.describe.configure({ timeout: 120_000 });

test.describe('Exam F12 marks summary (web)', () => {
  test('TC-EXM-12-E01 summary lists class-section, students and subjects', async ({ page, signIn, api, cleanup }) => {
    const klass = await kit.createQaClass(api, cleanup);
    const students = await kit.createStudents(api, cleanup, klass, ['Alpha', 'Bravo', 'Charlie']);
    const exam = await kit.createExam(api, cleanup, klass);
    await signIn('teacher');
    await page.goto('/exam/marks');
    await page.getByRole('row').filter({ hasText: exam.name }).getByRole('button', { name: 'Enter Marks' }).click();
    await expect(page).toHaveURL(/\/summary$/);
    await expect(page.getByRole('heading', { name: 'Mark Entry' })).toBeVisible();
    await expect(page.getByText(new RegExp(`${exam.name}\\s*\\S\\s*State`))).toBeVisible();
    await expect(page.getByText(klass.dash, { exact: true }).first()).toBeVisible();
    await expect(page.getByText('3/3', { exact: true })).toBeVisible();
    for (const student of students) await expect(page.getByText(student.name)).toBeVisible();
    const table = page.getByRole('table');
    await expect(table).toContainText('Mathematics');
    await expect(table).toContainText('Written');
    await expect(table).toContainText('[80]');
    await expect(table).toContainText('Oral');
    await expect(table).toContainText('[20]');
    await expect(table).toContainText('English');
    await expect(table).toContainText('Environmental Studies');
  });
});
