// Staff F10 mark attendance, F11 history by date (web). Baseline: qa_manual with 9 seeded staff, no attendance rows for today.
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { createStaff } = require('../../helpers/staffkit');

const ROUTE = '/staff/attendance';

function isoDate(offsetDays = 0) {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

const STATUS = /^(Present|Absent|Late|Half Day)$/;

function statusButton(scope) {
  return scope.locator('button').filter({ hasText: STATUS });
}

function staffRow(page, name) {
  return page.locator('div').filter({ hasText: name }).filter({ has: statusButton(page) }).last();
}

async function setStatus(page, name, status) {
  await statusButton(staffRow(page, name)).click();
  await page.getByRole('button', { name: status, exact: true }).last().click();
}

function stat(page, label) {
  return page.locator('body').filter({ hasText: new RegExp('(^|[^0-9])[1-9][0-9]*[ \n]*' + label, 'i') });
}

test.describe('Staff attendance (web)', () => {
  test('TC-STF-10-E02 mark one absent and one late', async ({ page, signIn, api, cleanup }) => {
    const asha = unique('QA Asha');
    const ravi = unique('QA Ravi');
    await createStaff(api, cleanup, { first_name: asha, last_name: 'Verma' });
    await createStaff(api, cleanup, { first_name: ravi, last_name: 'Kumar' });
    await signIn('admin');
    await page.goto(ROUTE);
    await expect(page.getByText(asha)).toBeVisible();
    await setStatus(page, asha, 'Absent');
    await expect(page.getByText('Unsaved Changes')).toBeVisible();
    await setStatus(page, ravi, 'Late');
    await page.getByRole('button', { name: 'Save Attendance' }).click();
    await toast(page, 'Attendance saved successfully!');
    await expect(stat(page, 'ABSENT')).toBeVisible();
    await expect(stat(page, 'LATE')).toBeVisible();
    await page.getByRole('button', { name: 'Refresh' }).click();
    await expect(statusButton(staffRow(page, asha)).filter({ hasText: 'Absent' })).toBeVisible();
    await expect(statusButton(staffRow(page, ravi)).filter({ hasText: 'Late' })).toBeVisible();
    await expect(stat(page, 'ABSENT')).toBeVisible();
    await expect(stat(page, 'LATE')).toBeVisible();
  });

  test('TC-STF-11-E01 stored status reloads when the date is changed back', async ({ page, signIn, api, cleanup }) => {
    test.fail(true, 'UI-STF-02: after saving attendance, switching the date away and back shows the cached pre-save statuses (Present) instead of the saved Absent');
    const asha = unique('QA Asha');
    await createStaff(api, cleanup, { first_name: asha, last_name: 'Verma' });
    await signIn('admin');
    await page.goto(ROUTE);
    await expect(page.getByText(asha)).toBeVisible();
    await setStatus(page, asha, 'Absent');
    await page.getByRole('button', { name: 'Save Attendance' }).click();
    await toast(page, 'Attendance saved successfully!');
    const date = page.locator('input[type="date"]');
    await date.fill(isoDate(-1));
    await expect(date).toHaveValue(isoDate(-1));
    await expect(statusButton(staffRow(page, asha)).filter({ hasText: 'Present' })).toBeVisible();
    await date.fill(isoDate(0));
    await expect(date).toHaveValue(isoDate(0));
    await expect(statusButton(staffRow(page, asha)).filter({ hasText: 'Absent' })).toBeVisible();
  });
});
