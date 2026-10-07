// Exam F15 compute and F16 publish, mobile (P1). Own QA class, students, marks and exam.
const { test, expect } = require('../../helpers/fixtures');
const kit = require('./_kit');

const { text, openHub, tile } = kit.mobile;

test.describe.configure({ timeout: 180_000 });

async function setup(api, cleanup) {
  const klass = await kit.createQaClass(api, cleanup);
  const students = await kit.createStudents(api, cleanup, klass, ['Alpha', 'Bravo', 'Charlie']);
  const exam = await kit.createExam(api, cleanup, klass);
  const marks = [
    { 'Mathematics:Written': 62, 'Mathematics:Oral': 18, 'English:Written': 70, 'Environmental Studies:Written': 90 },
    { 'Mathematics:Written': 70, 'Mathematics:Oral': 15, 'English:Written': 60, 'Environmental Studies:Written': 80 },
    { 'Mathematics:Written': 50, 'Mathematics:Oral': 10, 'English:Written': 55, 'Environmental Studies:Written': 65 },
  ];
  for (let i = 0; i < students.length; i += 1) await kit.saveMarks(api, exam, klass, students[i], marks[i]);
  return { exam, students };
}

async function openResults(page, exam) {
  await openHub(page);
  await tile(page, 'Results');
  await text(page, exam.name).first().click({ timeout: 60_000 });
}

test.describe('Exam F15 and F16 results (mobile)', () => {
  test('TC-EXM-15-E07 compute results', async ({ page, signIn, api, cleanup }) => {
    const { exam } = await setup(api, cleanup);
    await signIn('admin');
    await openResults(page, exam);
    await text(page, /^Compute/, { exact: false }).first().click({ timeout: 30_000 });
    await expect(text(page, 'Recompute all results for this exam?').first()).toBeVisible();
    await text(page, 'Compute', { exact: true }).last().click({ timeout: 20_000 });
    await expect(text(page, 'Results Computed').first()).toBeVisible({ timeout: 30_000 });
    await expect(text(page, /PASS/, { exact: false }).first()).toBeVisible();
    await expect(text(page, '80.0%').first()).toBeVisible();
    await expect(text(page, '#1').first()).toBeVisible();
  });

  test('TC-EXM-16-E08 publish results', async ({ page, signIn, api, cleanup }) => {
    const { exam } = await setup(api, cleanup);
    expect((await api('POST', `/exams/${exam.id}/compute`)).status).toBe(200);
    await signIn('admin');
    await openResults(page, exam);
    await text(page, 'Publish', { exact: true }).first().click({ timeout: 30_000 });
    await expect(text(page, 'Publish results to students and parents?').first()).toBeVisible();
    await text(page, 'Publish', { exact: true }).last().click({ timeout: 20_000 });
    await expect(text(page, 'Results Published').first()).toBeVisible({ timeout: 30_000 });
    expect((await api('GET', `/exams/${exam.id}`)).data.status).toBe('published');
  });
});
