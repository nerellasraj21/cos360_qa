const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { apiClass, apiStudent, apiType, cleanupCertificates, selectStudent, apiUpload, PDF } = require('./_kit');

async function setup(api, cleanup) {
  const klass = await apiClass(api, cleanup);
  const kid = await apiStudent(api, cleanup, klass, { first: unique('QACer'), last: 'Tmp' });
  const type = await apiType(api, cleanup, unique('QA Bonafide'));
  await cleanupCertificates(api, cleanup, kid.studentId);
  return { klass, kid, type };
}

async function selectHarsha(page) {
  await page.goto('/students/studentcertificates');
  await expect(page.getByRole('heading', { name: 'Student Certificates' })).toBeVisible({ timeout: 30_000 });
  await page.getByRole('button', { name: 'Select class' }).click();
  await page.getByRole('button', { name: 'Class 1', exact: true }).click();
  await page.getByRole('button', { name: 'All sections' }).click();
  await page.getByRole('button', { name: '1-B', exact: true }).click();
  await page.getByRole('button', { name: 'Select student' }).click();
  await page.getByRole('button', { name: 'Harsha Raju (004)' }).click();
}

test.describe('Certificates F03-F07 student certificates (web)', () => {
  test('TC-CER-03-E01 pick class, section and student', async ({ page, signIn }) => {
    await signIn('admin');
    await selectHarsha(page);
    const main = page.getByRole('main');
    await expect(main.getByText('Selected:')).toBeVisible();
    await expect(main.getByText('Harsha Raju').first()).toBeVisible();
    await expect(main.getByText('004').first()).toBeVisible();
    await expect(main.getByText('Upload for Harsha Raju')).toBeVisible();
    await expect(main.getByRole('button', { name: 'Received Document' })).toBeVisible();
    await expect(main.getByRole('button', { name: 'Issue Certificate' })).toBeVisible();
    await expect(main.getByText(/Certificates . Harsha Raju\s*\(\d+ total\)/)).toBeVisible();
  });

  test('TC-CER-04-E01 upload a received document', async ({ page, signIn, api, cleanup }) => {
    const { klass, kid, type } = await setup(api, cleanup);
    await signIn('admin');
    await selectStudent(page, klass, kid);
    await expect(page.getByText(/\(0 total\)/)).toBeVisible();
    await page.getByRole('button', { name: 'Select type' }).click();
    await page.getByRole('button', { name: type.name, exact: true }).click();
    const chooser = page.waitForEvent('filechooser');
    await page.getByRole('button', { name: 'Choose File' }).click();
    await (await chooser).setFiles(PDF);
    await page.getByRole('textbox', { name: /Optional remarks/ }).fill('QA received copy');
    await page.getByRole('button', { name: 'Upload Document' }).click();
    await toast(page, 'Document uploaded successfully!');
    const row = page.getByRole('row', { name: new RegExp(type.name) });
    await expect(row).toBeVisible();
    await expect(row).toContainText('QA received copy');
    await expect(row).toContainText('Uploaded');
    await expect(page.getByText(/\(1 total\)/)).toBeVisible();
  });

  test('TC-CER-05-E01 issue a certificate by uploading a file', async ({ page, signIn, api, cleanup }) => {
    const { klass, kid, type } = await setup(api, cleanup);
    await signIn('admin');
    await selectStudent(page, klass, kid);
    await page.getByRole('button', { name: 'Issue Certificate' }).first().click();
    await page.getByRole('button', { name: 'Upload Certificate File' }).click();
    await page.getByRole('button', { name: 'Select type' }).click();
    await page.getByRole('button', { name: type.name, exact: true }).click();
    await page.getByText('Issue Date').locator('..').locator('input').fill(new Date().toISOString().slice(0, 10));
    const chooser = page.waitForEvent('filechooser');
    await page.getByRole('button', { name: 'Choose File' }).click();
    await (await chooser).setFiles(PDF);
    await page.getByRole('button', { name: 'Issue Certificate' }).last().click();
    await toast(page, 'Certificate issued successfully!');
    const row = page.getByRole('row', { name: new RegExp(type.name) });
    await expect(row).toBeVisible();
    await expect(row).toContainText('Uploaded');
    await expect(row).toContainText(String(new Date().getFullYear()));
  });

  test('TC-CER-06-E01 generate an issuable certificate preview', async ({ page, signIn }) => {
    await signIn('admin');
    await selectHarsha(page);
    await page.getByRole('button', { name: 'Issue Certificate' }).first().click();
    await page.getByRole('button', { name: 'Generate Issuable' }).click();
    await page.getByRole('textbox', { name: 'Enter school name' }).fill('QA Demo School');
    await page.getByRole('button', { name: 'Select certificate type (Bonafide, TC, Conduct, etc.)' }).click();
    await page.getByRole('button', { name: 'Bonafide Certificate', exact: true }).click();
    await expect(page.getByText('Certificate Preview')).toBeVisible({ timeout: 20_000 });
    const frame = page.frameLocator('iframe').first();
    await expect(frame.locator('body')).toContainText('Harsha Raju', { timeout: 20_000 });
    const text = (await frame.locator('body').innerText()).replace(/\s+/g, ' ');
    expect(text).toContain('Harsha Raju');
    expect(text).toContain('004');
    expect(text).toContain('Class 1');
    expect(text).toContain('1-B');
    expect(text).toContain('2026-2027');
    expect(text).toContain('QA Demo School');
  });

  test('TC-CER-07-E01 certificate list shows both rows', async ({ page, signIn, api, cleanup }) => {
    const { klass, kid, type } = await setup(api, cleanup);
    await apiUpload('received', kid.studentId, type.id, { remarks: 'QA received copy' });
    await apiUpload('issued', kid.studentId, type.id, {});
    await signIn('admin');
    await selectStudent(page, klass, kid);
    await expect(page.getByText(/\(2 total\)/)).toBeVisible({ timeout: 20_000 });
    const rows = page.getByRole('row', { name: new RegExp(type.name) });
    await expect(rows).toHaveCount(2);
    for (const i of [0, 1]) {
      await expect(rows.nth(i)).toContainText('Uploaded');
      await expect(rows.nth(i).getByRole('button').first()).toBeVisible();
    }
  });
});
