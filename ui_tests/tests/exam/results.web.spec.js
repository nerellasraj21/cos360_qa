// Exam F15 Result computation and F16 view and export, web (P1).
const fs = require('fs');
const { test, expect, toast } = require('../../helpers/fixtures');
const kit = require('./_kit');

test.describe.configure({ timeout: 150_000 });

async function seededExamId(api, name) {
  const list = kit.rows(await api('GET', '/exams'));
  return list.find((e) => e.exam_name === name).id;
}

test.describe('Exam F15 compute and F16 export (web)', () => {
  test('TC-EXM-15-E01 compute results for an exam with marks', async ({ page, signIn, api, cleanup }) => {
    const klass = await kit.createQaClass(api, cleanup);
    const students = await kit.createStudents(api, cleanup, klass, ['Alpha', 'Bravo', 'Charlie']);
    const exam = await kit.createExam(api, cleanup, klass);
    const marks = [
      { 'Mathematics:Written': 62, 'Mathematics:Oral': 18, 'English:Written': 70, 'Environmental Studies:Written': 90 },
      { 'Mathematics:Written': 70, 'Mathematics:Oral': 15, 'English:Written': 60, 'Environmental Studies:Written': 80 },
      { 'Mathematics:Written': 50, 'Mathematics:Oral': 10, 'English:Written': 55, 'Environmental Studies:Written': 65 },
    ];
    for (let i = 0; i < students.length; i += 1) await kit.saveMarks(api, exam, klass, students[i], marks[i]);
    await signIn('admin');
    await page.goto('/exam/results');
    await page.getByRole('row').filter({ hasText: exam.name }).getByRole('button', { name: 'View Results' }).click();
    await expect(page.getByText(`Results - ${exam.name}`)).toBeVisible();
    await page.getByRole('button', { name: 'Compute Results' }).click();
    await toast(page, 'Aggregates computed successfully');
    for (const header of ['Total', '%', 'Grade', 'GPA', 'Rank', 'Result']) {
      await expect(page.getByRole('columnheader', { name: header })).toBeVisible();
    }
    for (const student of students) await expect(page.getByRole('row').filter({ hasText: student.name })).toBeVisible();
    await expect(page.getByRole('row').filter({ hasText: students[0].name })).toContainText('240');
    await expect(page.getByText('Showing 3 of 3 students')).toBeVisible();
  });

  test('TC-EXM-16-E02 export seeded results to CSV', async ({ page, signIn, api }) => {
    const id = await seededExamId(api, 'Unit Test 1 - Class 1B');
    await signIn('admin');
    await page.goto(`/exam/results/${id}`);
    await expect(page.getByText('Results - Unit Test 1 - Class 1B')).toBeVisible();
    await expect(page.getByRole('row').filter({ hasText: 'Advik Mehta' })).toBeVisible();
    await page.getByRole('button', { name: 'Export' }).click();
    const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Export to CSV' }).click()]);
    expect(download.suggestedFilename()).toBe('Unit Test 1 - Class 1B_results.csv');
    const file = test.info().outputPath('results.csv');
    await download.saveAs(file);
    const lines = fs.readFileSync(file, 'utf8').split(/\r?\n/).filter(Boolean);
    const header = lines[0];
    for (const column of ['S.No.', 'Student', 'Adm#', 'English', 'Hindi', 'Telugu', 'Mathematics', 'Environmental Studies', 'Total', '%', 'Grade', 'GPA', 'Rank', 'Result']) {
      expect(header).toContain(column);
    }
    expect(lines.length).toBeGreaterThanOrEqual(4);
    const advik = lines.find((l) => l.includes('Advik Mehta'));
    expect(advik).toContain('78');
  });
});
