const { test, expect, unique } = require('../../helpers/fixtures');
const { apiClass, apiStudent, apiType, cleanupCertificates, apiUpload, grantRole, STUDENT_GRANTS, PARENT_GRANTS, makeLogin, signInAs } = require('./_kit');

async function setup(api, cleanup) {
  const klass = await apiClass(api, cleanup);
  const kid = await apiStudent(api, cleanup, klass, { first: unique('QAHar'), last: 'Raju' });
  const type = await apiType(api, cleanup, unique('QA Bonafide'));
  await cleanupCertificates(api, cleanup, kid.studentId);
  await apiUpload('received', kid.studentId, type.id, { remarks: 'QA received copy' });
  await apiUpload('issued', kid.studentId, type.id, {});
  return { klass, kid, type };
}

test.describe('Certificates F11-F13 role views (web)', () => {
  test('TC-CER-11-E01 @serial student sees only own certificates', async ({ page, api, cleanup }) => {
    await grantRole(api, cleanup, 'Student', STUDENT_GRANTS);
    const { kid, type } = await setup(api, cleanup);
    await signInAs(page, await makeLogin(api, cleanup, kid.admissionNumber));
    await page.goto('/students/studentcertificates');
    await expect(page.getByRole('heading', { name: 'My Certificates' })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText('Certificates').first()).toBeVisible();
    await expect(page.getByText(/\(2 total\)/)).toBeVisible({ timeout: 20_000 });
    for (const h of ['S.No.', 'Certificate Type', 'Issue Date', 'Remarks', 'File', 'Download']) {
      await expect(page.getByRole('columnheader', { name: h })).toBeVisible();
    }
    await expect(page.getByRole('row', { name: new RegExp(type.name) })).toHaveCount(2);
  });

  test('TC-CER-12-E01 @serial parent sees the selected child certificates', async ({ page, api, cleanup }) => {
    await grantRole(api, cleanup, 'Parent', PARENT_GRANTS);
    const { klass, kid, type } = await setup(api, cleanup);
    await signInAs(page, await makeLogin(api, cleanup, kid.fatherEmail));
    await page.goto('/students/studentcertificates');
    await expect(page.getByRole('heading', { name: 'Certificates', exact: true })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(`Certificates — ${kid.first} Raju (${klass.className} - ${klass.sectionName})`)).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(/\(2 total\)/)).toBeVisible();
    await expect(page.getByRole('row', { name: new RegExp(type.name) })).toHaveCount(2);
  });

  test('TC-CER-13-E01 teacher views certificates without the upload card', async ({ page, signIn, api, cleanup }) => {
    const { kid, type } = await setup(api, cleanup);
    await signIn('teacher');
    await page.goto('/students/studentcertificates');
    await expect(page.getByRole('heading', { name: 'Student Certificates' })).toBeVisible({ timeout: 30_000 });
    await page.getByRole('button', { name: 'Select a student' }).click();
    await page.getByRole('button', { name: new RegExp(kid.admissionNumber) }).click();
    await expect(page.getByText(`Certificates for ${kid.first} Raju`)).toBeVisible({ timeout: 20_000 });
    for (const h of ['Certificate Type', 'Issue Date', 'Remarks', 'File', 'Actions']) {
      await expect(page.getByRole('columnheader', { name: h })).toBeVisible();
    }
    await expect(page.getByRole('row', { name: new RegExp(type.name) })).toHaveCount(2);
    await expect(page.getByRole('button', { name: 'Download Certificate' }).first()).toBeVisible();
    await expect(page.getByText('Upload for')).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Upload Document' })).toHaveCount(0);
  });
});
