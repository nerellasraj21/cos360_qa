// Exam F13 eligibility and F14 publish, mobile (P1). Own QA class, students, attendance and exam.
const { test, expect } = require('../../helpers/fixtures');
const kit = require('./_kit');

const { text, openHub, tile } = kit.mobile;

test.describe.configure({ timeout: 120_000 });

async function setup(api, cleanup) {
  const klass = await kit.createQaClass(api, cleanup);
  const students = await kit.createStudents(api, cleanup, klass, ['Alpha', 'Bravo', 'Charlie']);
  await kit.markAttendance(api, cleanup, students[0], kit.ATT_DATES, 2);
  await kit.markAttendance(api, cleanup, students[1], kit.ATT_DATES, 2);
  await kit.markAttendance(api, cleanup, students[2], kit.ATT_DATES, 5);
  const exam = await kit.createExam(api, cleanup, klass, { exam: { attendance_from_date: '2026-09-28', attendance_to_date: '2026-10-02' } });
  return { students, exam };
}

async function openManage(page, exam) {
  await openHub(page);
  await tile(page, 'Hall Tickets');
  await text(page, exam.name).first().waitFor({ timeout: 60_000 });
  await text(page, 'Manage').first().click({ timeout: 20_000 });
}

test.describe('Exam F13 and F14 hall tickets (mobile)', () => {
  test('TC-EXM-13-E10 compute eligibility', async ({ page, signIn, api, cleanup }) => {
    test.fail(true, 'UI-EXM-05: the mobile hall ticket screen crashes with Something went wrong (item.attendance_percent.toFixed is not a function) as soon as eligibility rows exist, because the API returns attendance_percent as a string');
    const { exam } = await setup(api, cleanup);
    await signIn('admin');
    await openManage(page, exam);
    await text(page, /^Compute/, { exact: false }).first().click({ timeout: 20_000 });
    await text(page, 'Compute', { exact: true }).last().click({ timeout: 20_000 });
    await expect(text(page, 'Eligibility Computed').first()).toBeVisible({ timeout: 30_000 });
    await expect(text(page, '1 eligible').first()).toBeVisible();
    await expect(text(page, '2 ineligible').first()).toBeVisible();
    await expect(text(page, 'Eligible (1)').first()).toBeVisible();
    await expect(text(page, 'Ineligible (2)').first()).toBeVisible();
  });

  test('TC-EXM-14-E09 publish hall tickets', async ({ page, signIn, api, cleanup }) => {
    test.fail(true, 'UI-EXM-05: the mobile hall ticket screen crashes with Something went wrong (item.attendance_percent.toFixed is not a function) as soon as eligibility rows exist, because the API returns attendance_percent as a string');
    test.setTimeout(120_000);
    const { exam } = await setup(api, cleanup);
    expect((await api('POST', `/exams/${exam.id}/hall-tickets/compute`)).status).toBe(200);
    await signIn('admin');
    await openManage(page, exam);
    await text(page, 'Publish', { exact: true }).first().click({ timeout: 20_000 });
    await text(page, 'Publish', { exact: true }).last().click({ timeout: 20_000 });
    await expect(text(page, 'Hall Tickets Published').first()).toBeVisible({ timeout: 30_000 });
    expect((await api('GET', `/exams/${exam.id}`)).data.hall_ticket_published).toBe(true);
  });
});
