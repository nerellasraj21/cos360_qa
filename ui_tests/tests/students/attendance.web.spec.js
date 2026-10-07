const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { apiClass, apiStudent, grantRole, STUDENT_GRANTS, PARENT_GRANTS, makeLogin, signInAs } = require('./_kit');

const TRIGGER = /^(Present|Absent|Late|Half Day|Leave)$/;

async function loadClass(page, klass) {
  await page.goto('/students/attendance');
  await expect(page.getByRole('heading', { name: 'Student Attendance' })).toBeVisible({ timeout: 30_000 });
  await page.getByRole('button', { name: 'Select Class' }).first().click();
  await page.getByRole('button', { name: klass.className, exact: true }).click();
  await page.getByRole('button', { name: 'Select Section' }).click();
  await page.getByRole('button', { name: klass.sectionName, exact: true }).click();
  await expect(page.getByText('students total')).toBeVisible({ timeout: 20_000 });
}

function studentRow(page, student) {
  return page
    .locator('div')
    .filter({ has: page.getByText(student.name, { exact: true }) })
    .filter({ has: page.getByRole('button', { name: TRIGGER }) })
    .last();
}

async function setStatus(page, student, status) {
  const row = studentRow(page, student);
  await row.getByRole('button', { name: TRIGGER }).first().click();
  await row.getByRole('button', { name: status, exact: true }).last().click();
}

async function statusOf(page, student) {
  return (await studentRow(page, student).getByRole('button', { name: TRIGGER }).innerText()).trim();
}

async function classWithStudents(api, cleanup, names) {
  const klass = await apiClass(api, cleanup);
  const students = [];
  for (const first of names) students.push(await apiStudent(api, cleanup, klass, { first: unique(first), last: 'Tmp' }));
  return { klass, students };
}

async function attendanceRows(api, studentId) {
  const res = await api('GET', `/student/attendance/student/${studentId}/filter?start_date=2026-01-01&end_date=2026-12-31`);
  return res.data;
}

test.describe('Students F11-F13 attendance (web)', () => {
  test('TC-STU-11-E01 teacher marks absent and late and saves', async ({ page, signIn, api, cleanup }) => {
    const { klass, students } = await classWithStudents(api, cleanup, ['QAAdv', 'QAHar', 'QANik']);
    await signIn('teacher');
    await loadClass(page, klass);
    await expect(page.getByText('100% Present')).toBeVisible();
    await expect(page.getByText('Unsaved Changes')).toHaveCount(0);
    await setStatus(page, students[1], 'Absent');
    await setStatus(page, students[0], 'Late');
    await expect(page.getByText('Unsaved Changes')).toBeVisible();
    await page.getByRole('button', { name: 'Save Attendance' }).click();
    await toast(page, 'Attendance saved successfully!');
    await page.getByRole('button', { name: 'Refresh' }).click();
    await expect(page.getByText('students total')).toBeVisible();
    await expect.poll(() => statusOf(page, students[0])).toBe('Late');
    await expect.poll(() => statusOf(page, students[1])).toBe('Absent');
    await expect.poll(() => statusOf(page, students[2])).toBe('Present');
    const tiles = await page.getByRole('main').innerText();
    expect(tiles).toMatch(/1\s*ABSENT/i);
    expect(tiles).toMatch(/1\s*LATE/i);
    expect(tiles).toMatch(/33%\s*Present/i);
    expect((await attendanceRows(api, students[1].studentId)).map((r) => r.status)).toEqual(['absent']);
  });

  test('TC-STU-12-E01 teacher changes an absent student to present', async ({ page, signIn, api, cleanup }) => {
    const { klass, students } = await classWithStudents(api, cleanup, ['QAAdv', 'QAHar']);
    await api('POST', '/student/attendance/', { body: { student_id: students[1].studentId, date: new Date().toISOString().slice(0, 10), status: 'absent' } });
    await signIn('teacher');
    await loadClass(page, klass);
    await expect.poll(() => statusOf(page, students[1])).toBe('Absent');
    await setStatus(page, students[1], 'Present');
    await page.getByRole('button', { name: 'Save Attendance' }).click();
    await toast(page, 'Attendance saved successfully!');
    await page.getByRole('button', { name: 'Refresh' }).click();
    await expect.poll(() => statusOf(page, students[1])).toBe('Present');
    const rows = await attendanceRows(api, students[1].studentId);
    expect(rows).toHaveLength(1);
    expect(rows[0].status).toBe('present');
  });

  test('TC-STU-13-E01 @serial student sees own attendance for a date range', async ({ page, api, cleanup }) => {
    await grantRole(api, cleanup, 'Student', STUDENT_GRANTS);
    const klass = await apiClass(api, cleanup);
    const kid = await apiStudent(api, cleanup, klass, { first: unique('QAHar'), last: 'Tmp', admissionDate: '2026-09-01' });
    const days = [['2026-09-25', 'present'], ['2026-09-28', 'absent'], ['2026-09-29', 'late'], ['2026-09-30', 'half_day'], ['2026-10-01', 'leave']];
    for (const [date, status] of days) await api('POST', '/student/attendance/', { body: { student_id: kid.studentId, date, status } });
    await signInAs(page, await makeLogin(api, cleanup, kid.admissionNumber));
    await page.goto('/students/attendance');
    await expect(page.getByRole('heading', { name: 'My Attendance' })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText('Filter by Date')).toBeVisible();
    const from = page.locator('input[type="date"]').nth(0);
    const to = page.locator('input[type="date"]').nth(1);
    await from.fill('2026-09-25');
    await to.fill('2026-10-01');
    await expect(from).toHaveValue('2026-09-25');
    const main = page.getByRole('main');
    for (const label of ['Total Days', 'Present', 'Absent', 'Late', 'Half Day', 'Leave']) {
      await expect(main.getByText(label, { exact: true }).first()).toBeVisible({ timeout: 20_000 });
    }
    await expect(main.getByText('Attendance Records')).toBeVisible();
    const text = await main.innerText();
    expect(text).toMatch(/5\W*\s*Total Days/i);
    for (const label of ['Present', 'Absent', 'Late', 'Half Day', 'Leave']) expect(text.replace(/\W+/g, ' ')).toContain(`1 ${label} `);
    const order = ['Leave', 'Half Day', 'Late', 'Absent', 'Present'];
    const list = text.slice(text.indexOf('Attendance Records'));
    const positions = order.map((s) => list.search(new RegExp(s, 'i')));
    expect(positions.every((p) => p >= 0)).toBe(true);
    for (let i = 1; i < positions.length; i++) expect(positions[i]).toBeGreaterThan(positions[i - 1]);
  });

  test('TC-STU-19-E01 @serial parent sees the first child and the child attendance title', async ({ page, api, cleanup }) => {
    await grantRole(api, cleanup, 'Parent', PARENT_GRANTS);
    const klass = await apiClass(api, cleanup);
    const kid = await apiStudent(api, cleanup, klass, { first: unique('QAHar'), last: 'Raju' });
    await signInAs(page, await makeLogin(api, cleanup, kid.fatherEmail));
    await page.goto('/dashboard');
    await expect(page.getByRole('combobox').filter({ hasText: kid.first })).toBeVisible({ timeout: 30_000 });
    await page.goto('/students/attendance');
    await expect(page.getByRole('heading', { name: "Children's Attendance" })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(`${kid.first} Raju's Attendance`)).toBeVisible();
  });
});
