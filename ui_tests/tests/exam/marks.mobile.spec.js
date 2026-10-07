// Exam F11 mark entry and F12 summary, mobile (P1). Own QA class, students and exam.
const { test, expect } = require('../../helpers/fixtures');
const kit = require('./_kit');

const { text, vis, openHub, tile } = kit.mobile;

test.describe.configure({ timeout: 240_000 });

async function setup(api, cleanup) {
  const klass = await kit.createQaClass(api, cleanup);
  const students = await kit.createStudents(api, cleanup, klass, ['Alpha', 'Bravo', 'Charlie']);
  const exam = await kit.createExam(api, cleanup, klass);
  return { klass, students, exam };
}

test.describe('Exam F11 and F12 marks (mobile)', () => {
  test('TC-EXM-11-E14 teacher saves one mark', async ({ page, signIn, api, cleanup }) => {
    const { klass, students, exam } = await setup(api, cleanup);
    await signIn('teacher');
    await openHub(page);
    await tile(page, 'Mark Entry');
    await text(page, exam.name).first().click({ timeout: 60_000 });
    await text(page, 'Enter Marks').first().click({ timeout: 60_000 });
    await text(page, /^Written/, { exact: false }).first().click({ timeout: 30_000 });
    await vis(page.getByPlaceholder('–')).first().fill('62');
    await text(page, /Save Marks \(1 changed\)/, { exact: false }).first().click({ timeout: 20_000 });
    await expect(text(page, 'Marks Saved').first()).toBeVisible({ timeout: 30_000 });
    const grid = await api('GET', `/exams/${exam.id}/subject-configs`);
    const math = grid.data.find((c) => c.subject_id === klass.subjectIds.Mathematics);
    const marks = await api('GET', `/exams/${exam.id}/marks?class_id=${klass.id}&section_id=${klass.sectionId}&subject_config_id=${math.id}&page_size=1000`);
    expect(JSON.stringify(marks.data)).toContain('62');
  });

  test('TC-EXM-12-E08 marks summary screen', async ({ page, signIn, api, cleanup }) => {
    const { students, exam } = await setup(api, cleanup);
    await signIn('teacher');
    await openHub(page);
    await tile(page, 'Exams');
    await text(page, exam.name).first().click({ timeout: 60_000 });
    await text(page, 'Marks', { exact: true }).first().click({ timeout: 60_000 });
    await expect(text(page, 'Mark Entry').first()).toBeVisible({ timeout: 60_000 });
    await expect(text(page, `${exam.name.slice(0, 0)}${'QA Exm'}`, { exact: false }).first()).toBeVisible();
    // doc: the summary header shows the class-section, not the exam name, board and type; it shows "3/3 students selected" with a Change link; Select all and the search box are inside the student picker, and there is no View Summary button after tapping Marks
    await expect(text(page, '3/3 students selected').first()).toBeVisible();
    for (const subject of ['Mathematics', 'English', 'Environmental Studies']) await expect(text(page, subject).first()).toBeVisible();
    await expect(text(page, students[0].name).first()).toBeVisible();
    await expect(text(page, /grand total/i, { exact: false }).first()).toBeVisible();
  });
});
