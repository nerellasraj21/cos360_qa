// Staff F03 first login of a new staff account (web). The account is enrolled through the API with a phone number only.
const { test, expect, unique } = require('../../helpers/fixtures');
const { TEMP, webSubmitLogin, call, activeYear } = require('../../helpers/authkit');
const { createStaff } = require('../../helpers/staffkit');

test.describe('Staff first login (web)', () => {
  test('TC-STF-03-E01 temporary password then Set Your Password', async ({ page, api, cleanup }) => {
    const staff = await createStaff(api, cleanup, { first_name: unique('QA Kiran') });
    const temp = TEMP.staff();
    const fresh = `QA Pass ${Date.now().toString(36)}`;
    await webSubmitLogin(page, staff.phone, temp);
    await expect(page).toHaveURL(/\/set-password/);
    await expect(page.getByText('Set Your Password')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Dashboard', exact: true })).toHaveCount(0);
    await page.getByLabel('New Password').fill(fresh);
    await page.getByLabel('Confirm Password').fill(fresh);
    await page.getByRole('button', { name: 'Set Password' }).click();
    await expect(page).not.toHaveURL(/set-password|login/, { timeout: 20_000 });
    await expect(page.getByRole('button', { name: 'Dashboard', exact: true })).toBeVisible();
    const year = await activeYear();
    const old = await call('POST', '/auth/login', { body: { username: staff.phone, password: temp, academic_year_id: year.id } });
    expect(old.status).toBe(401);
    const now = await call('POST', '/auth/login', { body: { username: staff.phone, password: fresh, academic_year_id: year.id } });
    expect(now.status).toBe(200);
    expect(JSON.stringify(now.data)).toMatch(/Staff/);
  });
});
