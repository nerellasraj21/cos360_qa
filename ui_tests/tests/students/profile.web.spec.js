const { test, expect, unique } = require('../../helpers/fixtures');
const { apiClass, apiStudent, grantRole, STUDENT_GRANTS, makeLogin, signInAs } = require('./_kit');

test.describe('Students F17-F18 student self views (web)', () => {
  test('TC-STU-17-E01 @serial student sees only the own admission', async ({ page, api, cleanup }) => {
    await grantRole(api, cleanup, 'Student', STUDENT_GRANTS);
    const klass = await apiClass(api, cleanup);
    const kid = await apiStudent(api, cleanup, klass, { first: unique('QAHar'), last: 'Raju' });
    await signInAs(page, await makeLogin(api, cleanup, kid.admissionNumber));
    await page.goto('/students/admission');
    await expect(page.getByRole('heading', { name: 'Student Admissions' })).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('tbody tr')).toHaveCount(1);
    await expect(page.locator('tbody tr').first()).toContainText(`${kid.first} Raju`);
    for (const name of ['New Admission', 'Bulk Upload', 'Edit Admission', 'Deactivate Student', 'Activate Student']) {
      await expect(page.getByRole('button', { name })).toHaveCount(0);
    }
    await page.getByRole('button', { name: 'View Admission' }).click();
    const d = page.getByRole('dialog');
    await expect(d.getByRole('heading', { name: `Admission Details - ${kid.admissionNumber}` })).toBeVisible();
    await expect(d.getByRole('row', { name: `Student Name ${kid.first} Raju` })).toBeVisible();
  });

  test('TC-STU-18-E01 student profile shows personal and academic information', async ({ page, api, cleanup }) => {
    const klass = await apiClass(api, cleanup);
    const kid = await apiStudent(api, cleanup, klass, { first: unique('QAHar'), last: 'Raju' });
    await signInAs(page, await makeLogin(api, cleanup, kid.admissionNumber));
    await page.goto('/students/profile');
    await expect(page.getByRole('heading', { name: 'Student Profile' })).toBeVisible({ timeout: 30_000 });
    const main = page.getByRole('main');
    await expect(main.getByText('Personal Information')).toBeVisible();
    await expect(main.getByText('Academic Information')).toBeVisible();
    const text = (await main.innerText()).replace(/\s+/g, ' ');
    expect(text).toContain(`First Name: ${kid.first}`);
    expect(text).toContain('Last Name: Raju');
    expect(text).toContain('Email:');
    expect(text).toContain(`Admission Number: ${kid.admissionNumber}`);
    expect(text).toContain(`Class: ${klass.className}`);
    expect(text).toContain(`Section: ${klass.sectionName}`);
    expect(text).toContain('N/A');
  });
});
