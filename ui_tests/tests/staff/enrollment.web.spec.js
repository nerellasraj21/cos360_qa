// Staff F02 enroll, F04 qualifications, F05 photo, F06 list, F07 edit/delete, F08 bulk upload (web). Baseline: qa_manual with 9 seeded staff.
const fs = require('fs');
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { phone, createStaff, findStaffByPhone, removeStaff, makeBulkFile } = require('../../helpers/staffkit');

const ROUTE = '/staff/enrollment';

function row(page, text) {
  return page.getByRole('row').filter({ hasText: text });
}

async function search(page, text) {
  await page.getByPlaceholder('Search staff...').fill(text);
}

test.describe('Staff enrollment (web)', () => {
  test('TC-STF-02-E01 enroll a staff member', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Kiran');
    const mobile = phone();
    await signIn('admin');
    await page.goto(ROUTE);
    await page.getByRole('button', { name: 'Add Staff' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByPlaceholder('Enter first name').fill(name);
    await dialog.getByPlaceholder('Enter phone number').fill(mobile);
    await dialog.getByPlaceholder('Enter residential address').fill('12 MG Road');
    await dialog.getByRole('button', { name: 'Save' }).click();
    await toast(page, 'Staff enrollment created successfully');
    const created = await findStaffByPhone(api, mobile);
    expect(created).toBeTruthy();
    cleanup(() => removeStaff(api, created));
    await expect(dialog).toBeHidden();
    await search(page, name);
    const r = row(page, name);
    await expect(r).toBeVisible();
    await expect(r).toContainText('Not Assigned');
    await expect(r).toContainText('Active');
    const users = await api('GET', `/admin/users/?search=${mobile}&limit=10`);
    const list = Array.isArray(users.data) ? users.data : users.data.items || users.data.users || [];
    const login = list.find((u) => u.username === mobile);
    expect(login).toBeTruthy();
    expect(JSON.stringify(login)).toMatch(/Staff/);
  });

  test('TC-STF-04-E01 enroll with two qualifications', async ({ page, signIn, api, cleanup }) => {
    test.fail(true, 'UI-STF-01: View Staff Details right after enrolling shows no qualifications (create caches the response without them for 5 minutes)');
    const name = unique('QA Quals');
    const mobile = phone();
    await signIn('admin');
    await page.goto(ROUTE);
    await page.getByRole('button', { name: 'Add Staff' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByPlaceholder('Enter first name').fill(name);
    await dialog.getByPlaceholder('Enter phone number').fill(mobile);
    await dialog.getByPlaceholder('Enter residential address').fill('6 QA Street');
    const addQual = dialog.getByRole('button', { name: 'Add Qualification' });
    await addQual.click();
    await dialog.getByRole('combobox').filter({ hasText: 'Select level' }).first().click();
    await page.getByRole('option', { name: 'Graduation (B.Tech / B.Sc / B.Com)' }).click();
    await dialog.locator('input[id^="react-select"]').first().fill('B.Tech');
    await page.keyboard.press('Enter');
    await dialog.getByPlaceholder('e.g. 2018').first().fill('2016');
    await dialog.getByPlaceholder('e.g. 78.50').first().fill('72.5');
    await addQual.click();
    await dialog.getByRole('combobox').filter({ hasText: 'Select level' }).first().click();
    await page.getByRole('option', { name: 'Post Graduation (M.Tech / MBA)' }).click();
    await dialog.locator('input[id^="react-select"]').nth(1).fill('MBA');
    await page.keyboard.press('Enter');
    await dialog.getByPlaceholder('e.g. 2018').nth(1).fill('2018');
    await dialog.getByPlaceholder('e.g. 78.50').nth(1).fill('68');
    await dialog.getByRole('button', { name: 'Save' }).click();
    await toast(page, 'Staff enrollment created successfully');
    const created = await findStaffByPhone(api, mobile);
    expect(created).toBeTruthy();
    cleanup(() => removeStaff(api, created));
    const stored = await api('GET', `/staff/${created.id}/qualifications`);
    expect(stored.data).toHaveLength(2);
    await search(page, name);
    await row(page, name).getByRole('button', { name: 'View Staff Details' }).click();
    const view = page.getByRole('dialog');
    await expect(view).toContainText('Year: 2016');
    await expect(view).toContainText('Year: 2018');
    await expect(view).toContainText('72.50%');
    await expect(view).toContainText('68.00%');
  });

  test('TC-STF-05-E01 upload a staff photo', async () => {
    test.skip(true, 'blocked: saved photos do not render because /media requests without a cschema header get 400 (docs/modules/staff.md Known gaps)');
  });

  test('TC-STF-06-E01 list columns and search', async ({ page, signIn, api, cleanup }) => {
    const first = unique('QA Meena');
    const created = await createStaff(api, cleanup, { first_name: first, last_name: 'Rao', is_active: false });
    expect(created.is_active).toBe(false);
    await signIn('admin');
    await page.goto(ROUTE);
    for (const h of ['S.No.', 'Name', 'Contact', 'Designation', 'Department', 'Status', 'Actions']) {
      await expect(page.getByRole('columnheader', { name: h, exact: true })).toBeVisible();
    }
    const principal = row(page, 'Lakshmi Narayana Rao');
    await expect(principal).toBeVisible();
    await expect(principal).toContainText('Principal');
    await expect(principal).toContainText('Administration');
    await expect(principal).toContainText('Active');
    await expect(page.getByText(/1-5 of \d+/)).toBeVisible();
    await search(page, first);
    const r = row(page, first);
    await expect(r).toBeVisible();
    await expect(r).toContainText('Inactive');
  });

  test('TC-STF-07-E01 edit the department', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Asha');
    const created = await createStaff(api, cleanup, { first_name: name, last_name: 'Verma', department: 'Primary' });
    await signIn('admin');
    await page.goto(ROUTE);
    await search(page, name);
    await row(page, name).getByRole('button', { name: 'Edit Staff' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText('Edit Staff Enrollment')).toBeVisible();
    const dept = dialog.getByPlaceholder('Enter department name');
    await dept.fill('Science');
    await dialog.getByRole('button', { name: 'Save' }).click();
    await toast(page, 'Staff enrollment updated successfully');
    await expect(dialog).toBeHidden();
    await expect(row(page, name)).toContainText('Science');
    const after = await api('GET', `/staff/enrollment/${created.id}`);
    expect(after.data.department).toBe('Science');
    expect(after.data.first_name).toBe(name);
    expect(after.data.phone).toBe(created.phone);
  });

  test('TC-STF-07-E05 delete a staff member', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Kiran');
    const created = await createStaff(api, cleanup, { first_name: name });
    await signIn('admin');
    await page.goto(ROUTE);
    await search(page, name);
    await row(page, name).getByRole('button', { name: 'Delete Staff' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toContainText('Delete Staff Enrollment');
    const text = (await dialog.innerText()).replace(/\s+/g, ' ');
    expect(text).toContain(`Are you sure you want to delete the enrollment for "${name}`);
    expect(text).toContain('This action cannot be undone and will remove all associated attendance records.');
    await dialog.getByRole('button', { name: 'Delete' }).click();
    await toast(page, 'Staff enrollment deleted successfully');
    await expect(row(page, name)).toHaveCount(0);
    const gone = await api('GET', `/staff/enrollment/${created.id}`);
    expect(gone.status).toBe(404);
  });

  test('TC-STF-08-E02 bulk upload two staff', async ({ page, signIn, api, cleanup }) => {
    const tag = unique('QA Bulk').replace(/\s+/g, '');
    const p1 = phone();
    const p2 = phone();
    const e1 = `${tag.toLowerCase()}.1@qa.example`;
    const e2 = `${tag.toLowerCase()}.2@qa.example`;
    const file = makeBulkFile([
      { 'First Name': `${tag}One`, Phone: p1, Address: '8 QA Street', Email: e1 },
      { 'First Name': `${tag}Two`, Phone: p2, Address: '9 QA Street', Email: e2 },
    ]);
    cleanup(() => fs.unlinkSync(file));
    cleanup(async () => {
      for (const p of [p1, p2]) await removeStaff(api, await findStaffByPhone(api, p));
    });
    await signIn('admin');
    await page.goto(ROUTE);
    await page.getByRole('button', { name: 'Bulk Upload' }).click();
    const dialog = page.getByRole('dialog');
    const chooser = page.waitForEvent('filechooser');
    await dialog.getByRole('button', { name: 'Browse File' }).click();
    await (await chooser).setFiles(file);
    await dialog.getByRole('button', { name: 'Upload' }).click();
    await expect(dialog).toContainText('2 of 2 staff member(s) created');
    await expect(dialog).toContainText(`Row 2: ${tag}One (${e1})`);
    await expect(dialog).toContainText(`Row 3: ${tag}Two (${e2})`);
    await dialog.getByRole('button', { name: 'Close' }).last().click();
    await search(page, tag);
    await expect(row(page, `${tag}One`)).toBeVisible();
    await expect(row(page, `${tag}Two`)).toBeVisible();
  });
});
