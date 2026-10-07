const path = require('path');
const fs = require('fs');
const { execFileSync } = require('child_process');
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { openAdmission, searchAdmission, createAdmissionUi, phone, trackAdmission, apiStudent, seededClass, userCleanup } = require('./_kit');

const PHOTO = path.join(__dirname, 'files', 'qa-photo.jpg');

test.describe('Students F01-F10 admission (web)', () => {
  test('TC-STU-01-E01 students dashboard cards and navigation', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/students');
    await expect(page.getByRole('heading', { name: 'Students Dashboard' })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText('Comprehensive management of student data, admissions, and records')).toBeVisible();
    await expect(page.getByText('STUDENTS SECTIONS')).toBeVisible();
    const main = page.getByRole('main');
    for (const name of ['Admission', 'Attendance', 'Student Documents', 'Student Certificates', 'Certificate Types', 'Certificate Templates']) {
      await expect(main.getByText(name, { exact: true }).first()).toBeVisible();
    }
    await expect(main.getByText('Student Transport')).toHaveCount(0);
    await expect(page.locator('aside').getByText('Student Transport')).toHaveCount(0);
    await main.getByText('Admission', { exact: true }).first().click();
    await expect(page).toHaveURL(/\/students\/admission$/);
    await expect(page.getByRole('heading', { name: 'Student Admissions' })).toBeVisible();
  });

  test('TC-STU-02-E01 new admission dialog opens with the next number', async ({ page, signIn }) => {
    await signIn('admin');
    await openAdmission(page);
    await page.getByRole('button', { name: 'New Admission' }).click();
    const d = page.getByRole('dialog', { name: 'New Student Admission' });
    await expect(d).toBeVisible();
    await expect(d.getByText('Student & Academic Details')).toBeVisible();
    await expect(d.getByText('Step 1 of 5')).toBeVisible();
    const number = d.getByRole('textbox', { name: 'Admission Number' });
    await expect(number).toHaveAttribute('placeholder', 'e.g. 001');
    await expect(number).not.toHaveValue('');
    const value = await number.inputValue();
    await expect(d.getByText('Next available:')).toBeVisible();
    await expect(d.getByText('Next available:').locator('strong')).toHaveText(value);
    await expect(d.getByRole('combobox', { name: '-- Select Admission Type --' })).toContainText('Regular');
  });

  test('TC-STU-03-E01 create an admission through the five steps', async ({ page, signIn, api, cleanup }) => {
    test.fail(true, 'UI-STU-01: a new admission with only the Joining Class/Section filled has no current class or section, so the table shows N/A for Class and Section');
    await signIn('admin');
    const first = unique('QA Asha');
    trackAdmission(api, cleanup, first);
    await openAdmission(page);
    const number = await createAdmissionUi(page, { first, last: 'Rao', father: 'QA Ramesh Rao', email: `${first.replace(/\s/g, '.').toLowerCase()}@example.com`, phone: phone(), sync: false });
    await toast(page, 'Student admission created successfully!');
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await searchAdmission(page, first);
    const row = page.locator('tbody tr').first();
    await expect(row).toContainText(number);
    await expect(row).toContainText(`${first} Rao`);
    await expect(row).toContainText('Class 2');
    await expect(row).toContainText('2-A');
    await expect(row).toContainText('Active');
  });

  test('TC-STU-04-E01 second child with the same father email shares one parent record', async ({ page, signIn, api, cleanup }) => {
    await signIn('admin');
    const klass = await seededClass(api);
    const email = `${unique('QA').replace(/\s/g, '.').toLowerCase()}@example.com`;
    const asha = await apiStudent(api, cleanup, klass, { first: unique('QA Asha'), last: 'Rao', father: 'QA Ramesh Rao', fatherEmail: email, phone: phone() });
    const ravi = unique('QA Ravi');
    trackAdmission(api, cleanup, ravi);
    const newPhone = phone();
    await openAdmission(page);
    await createAdmissionUi(page, { first: ravi, last: 'Rao', father: 'QA Ramesh Rao', email, phone: newPhone });
    await toast(page, 'Student admission created successfully!');
    await searchAdmission(page, asha.first);
    await expect(page.locator('tbody tr').first()).toContainText(asha.first);
    await page.getByRole('button', { name: 'View Admission' }).first().click();
    const d = page.getByRole('dialog');
    await expect(d.getByRole('row', { name: `Father Phone ${newPhone}` })).toBeVisible();
    const both = await api('GET', '/students/admission/?limit=100');
    const fathers = both.data.items.filter((a) => [asha.first, ravi].includes(a.student.first_name)).map((a) => a.student.father.id);
    expect(fathers).toHaveLength(2);
    expect(fathers[0]).toBe(fathers[1]);
  });

  test('TC-STU-05-E02 upload and remove a student photo', async ({ page, signIn, api, cleanup }) => {
    await signIn('admin');
    const klass = await seededClass(api);
    const kid = await apiStudent(api, cleanup, klass, { first: unique('QA Photo'), last: 'Rao' });
    await openAdmission(page);
    await searchAdmission(page, kid.first);
    await page.getByRole('button', { name: 'Edit Admission' }).first().click();
    const d = page.getByRole('dialog');
    await expect(d.getByText('Student Photo')).toBeVisible();
    await d.locator('input[type=file]').first().setInputFiles(PHOTO);
    await toast(page, 'Photo uploaded successfully');
    await d.getByRole('button', { name: 'Remove photo' }).click();
    await toast(page, 'Photo removed successfully');
    await expect(d.getByRole('button', { name: 'Remove photo' })).toHaveCount(0);
  });

  test('TC-STU-06-E01 admission table columns and pagination', async ({ page, signIn }) => {
    await signIn('admin');
    await openAdmission(page);
    for (const h of ['S.No.', 'Admission No.', 'Student Name', 'Class', 'Section', 'Academic Year', 'Admission Date', 'Status', 'Actions']) {
      await expect(page.getByRole('columnheader', { name: h, exact: true })).toBeVisible();
    }
    await expect(page.locator('tbody tr')).toHaveCount(10);
    const range = page.getByText(/^1-10 of \d+$/);
    await expect(range).toBeVisible();
    const total = Number((await range.innerText()).split(' of ')[1]);
    expect(total).toBeGreaterThanOrEqual(30);
    const dates = (await page.locator('tbody tr td:nth-child(7)').allInnerTexts()).map((t) => {
      const [m, d, y] = t.trim().split('/').map(Number);
      return new Date(y, m - 1, d).getTime();
    });
    for (let i = 1; i < dates.length; i++) expect(dates[i - 1]).toBeGreaterThanOrEqual(dates[i]);
    await page.getByRole('button', { name: 'Next', exact: true }).click();
    await expect(page.getByText(/^11-20 of \d+$/)).toBeVisible();
    await expect(page.locator('tbody tr')).toHaveCount(10);
  });

  test('TC-STU-07-E01 view an admission', async ({ page, signIn }) => {
    await signIn('admin');
    await openAdmission(page);
    await searchAdmission(page, 'Harsha Raju');
    await page.getByRole('button', { name: 'View Admission' }).first().click();
    const d = page.getByRole('dialog');
    await expect(d.getByRole('heading', { name: /^Admission Details - / })).toBeVisible();
    await expect(d.getByText('Harsha Raju').first()).toBeVisible();
    await expect(d.getByRole('row', { name: 'Admitted Class Class 1' })).toBeVisible();
    await expect(d.getByRole('row', { name: 'Current Section 1-B' })).toBeVisible();
    await expect(d.getByRole('row', { name: 'Father Name Venkat Raju' })).toBeVisible();
    await expect(d.getByRole('row', { name: 'Father Email venkat.raju@example.com' })).toBeVisible();
    await expect(d.getByRole('row', { name: 'City Hyderabad' })).toBeVisible();
    await expect(d.getByRole('row', { name: 'Guardian Name N/A' })).toBeVisible();
    await d.getByRole('button', { name: 'Close' }).last().click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
  });

  test('TC-STU-08-E01 edit last name and current section', async ({ page, signIn, api, cleanup }) => {
    await signIn('admin');
    const klass = await seededClass(api);
    const kid = await apiStudent(api, cleanup, klass, { first: unique('QA Asha'), last: 'Rao' });
    await openAdmission(page);
    await searchAdmission(page, kid.first);
    await page.getByRole('button', { name: 'Edit Admission' }).first().click();
    const d = page.getByRole('dialog');
    await d.getByRole('textbox', { name: 'Last Name' }).fill('Rao-Edited');
    await d.getByRole('combobox', { name: 'Select section' }).last().click();
    await page.getByRole('option', { name: '2-B', exact: true }).click();
    await d.getByRole('button', { name: 'Update Admission' }).click();
    await toast(page, 'Student admission updated successfully!');
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await searchAdmission(page, kid.first);
    const row = page.locator('tbody tr').first();
    await expect(row).toContainText(`${kid.first} Rao-Edited`);
    await expect(row).toContainText('2-B');
    await page.getByRole('button', { name: 'View Admission' }).first().click();
    await expect(page.getByRole('dialog').getByRole('row', { name: 'Current Section 2-B' })).toBeVisible();
  });

  test('TC-STU-09-E01 deactivate and reactivate a student', async ({ page, signIn, api, cleanup }) => {
    await signIn('admin');
    const klass = await seededClass(api);
    const kid = await apiStudent(api, cleanup, klass, { first: unique('QA Mobile'), last: 'Kid' });
    await openAdmission(page);
    await searchAdmission(page, kid.first);
    await page.getByRole('button', { name: 'Deactivate Student' }).first().click();
    const d = page.getByRole('dialog');
    await expect(d.getByText('Disable Student').first()).toBeVisible();
    await expect(d.getByText(`Are you sure you want to disable ${kid.first} Kid?`)).toBeVisible();
    await d.getByRole('button', { name: 'Disable' }).click();
    await toast(page, 'Student disabled successfully!');
    const row = page.locator('tbody tr').first();
    await expect(row).toContainText('Inactive');
    await page.getByRole('button', { name: 'Activate Student' }).first().click();
    await expect(page.getByRole('dialog').getByText('Enable Student').first()).toBeVisible();
    await page.getByRole('dialog').getByRole('button', { name: 'Enable' }).click();
    await toast(page, 'Student enabled successfully!');
    await expect(row).toContainText('Active');
    await expect(row).not.toContainText('Inactive');
  });

  test('TC-STU-10-E02 bulk upload three valid rows', async ({ page, signIn, api, cleanup }, testInfo) => {
    await signIn('admin');
    const tagText = unique('QA Bulk');
    const rows = [1, 2, 3].map((n) => ({ 'First name': `${tagText} ${n}`, 'joining class': 'Class 2', 'joining section': '2-A', 'Father name': `QA Bulk Father ${n}`, 'Father phone': phone(), 'Address Line 1': 'QA Bulk Road' }));
    const file = testInfo.outputPath('bulk.xlsx');
    fs.mkdirSync(path.dirname(file), { recursive: true });
    execFileSync('python', [path.join(__dirname, '_xlsx.py'), file, JSON.stringify(rows)]);
    cleanup(async () => {
      const res = await api('GET', '/students/admission/?limit=100');
      for (const a of res.data.items.filter((x) => x.student.first_name.startsWith(tagText))) {
        await api('DELETE', `/students/admission/${a.id}`);
        for (const name of [a.admission_number, `${a.admission_number}.mother`]) {
          const users = await api('GET', `/admin/users/?search=${encodeURIComponent(name)}&limit=50`);
          const u = ((users.data && users.data.users) || []).find((r) => r.username === name);
          if (u) await api('PATCH', `/admin/users/${u.id}`, { body: { is_active: false } });
        }
      }
    });
    await openAdmission(page);
    await page.getByRole('button', { name: 'Bulk Upload' }).click();
    const d = page.getByRole('dialog', { name: 'Bulk Admission Upload' });
    const chooser = page.waitForEvent('filechooser');
    await d.getByRole('button', { name: 'Browse File' }).click();
    await (await chooser).setFiles(file);
    await d.getByRole('button', { name: 'Upload', exact: true }).click();
    await expect(d.getByText('3 of 3 admission(s) created')).toBeVisible({ timeout: 30_000 });
    for (const n of [1, 2, 3]) await expect(d.getByText(new RegExp(`Row \\d+: ${tagText} ${n} \\(`))).toBeVisible();
    await d.getByRole('button', { name: 'Close' }).last().click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await searchAdmission(page, tagText);
    await expect(page.locator('tbody tr')).toHaveCount(3);
  });
});
