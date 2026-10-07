// Exam F13 Hall ticket eligibility and F14 publish, web (P1). Own QA class, students, attendance and exam.
const { test, expect, toast } = require('../../helpers/fixtures');
const kit = require('./_kit');

test.describe.configure({ timeout: 150_000 });

async function setup(api, cleanup) {
  const klass = await kit.createQaClass(api, cleanup);
  const students = await kit.createStudents(api, cleanup, klass, ['Alpha', 'Bravo', 'Charlie']);
  await kit.markAttendance(api, cleanup, students[0], kit.ATT_DATES, 2);
  await kit.markAttendance(api, cleanup, students[1], kit.ATT_DATES, 2);
  await kit.markAttendance(api, cleanup, students[2], kit.ATT_DATES, 5);
  const exam = await kit.createExam(api, cleanup, klass, {
    exam: { attendance_from_date: '2026-09-28', attendance_to_date: '2026-10-02' },
  });
  return { klass, students, exam };
}

async function openManage(page, exam) {
  await page.goto('/exam/hall-tickets');
  await page.getByRole('row').filter({ hasText: exam.name }).getByRole('button', { name: 'Manage' }).click();
  await expect(page.getByText(`Hall Tickets - ${exam.name}`)).toBeVisible();
}

function card(page, label) {
  return page.getByText(label, { exact: true }).locator('xpath=preceding-sibling::p[1]');
}

test.describe('Exam F13 hall ticket eligibility and F14 publish (web)', () => {
  test('TC-EXM-13-E01 recompute eligibility from attendance', async ({ page, signIn, api, cleanup }) => {
    const { students, exam } = await setup(api, cleanup);
    await signIn('admin');
    await openManage(page, exam);
    await page.getByRole('button', { name: 'Recompute' }).click();
    await toast(page, 'Eligibility computed successfully');
    await expect(card(page, 'Total Students')).toHaveText('3');
    await expect(card(page, 'Eligible')).toHaveText('1');
    await expect(card(page, 'Ineligible')).toHaveText('2');
    await page.getByRole('tab', { name: /^Eligible/ }).click();
    await expect(page.getByRole('row').filter({ hasText: students[2].name })).toBeVisible();
    await expect(page.getByRole('row').filter({ hasText: students[0].name })).toHaveCount(0);
  });

  test('TC-EXM-13-E03 override attendance for an ineligible student', async ({ page, signIn, api, cleanup }) => {
    const { students, exam } = await setup(api, cleanup);
    expect((await api('POST', `/exams/${exam.id}/hall-tickets/compute`)).status).toBe(200);
    await signIn('admin');
    await openManage(page, exam);
    await page.getByRole('tab', { name: /^Ineligible/ }).click();
    const row = page.getByRole('row').filter({ hasText: students[0].name });
    await row.getByRole('button', { name: 'Attendance' }).click();
    await page.getByRole('tab', { name: /^Eligible/ }).click();
    const eligible = page.getByRole('row').filter({ hasText: students[0].name });
    await expect(eligible).toBeVisible();
    await expect(eligible).toContainText('Override');
  });

  test('TC-EXM-14-E01 publish hall tickets', async ({ page, signIn, api, cleanup }) => {
    const { exam } = await setup(api, cleanup);
    expect((await api('POST', `/exams/${exam.id}/hall-tickets/compute`)).status).toBe(200);
    await signIn('admin');
    await openManage(page, exam);
    await page.getByRole('button', { name: 'Publish Hall Tickets' }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Publish', exact: true }).click();
    await toast(page, 'Hall tickets published successfully');
    await page.goto(`/exam/exams/${exam.id}`);
    await expect(page.getByText('Hall Ticket Status', { exact: true })).toBeVisible();
    await expect(page.getByText('Published', { exact: true })).toBeVisible();
    expect((await api('GET', `/exams/${exam.id}`)).data.hall_ticket_published).toBe(true);
  });
});
