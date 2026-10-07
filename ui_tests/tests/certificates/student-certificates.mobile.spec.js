const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { apiClass, apiStudent, apiType, cleanupCertificates, PDF } = require('./_kit');

const vis = (page, text) => page.getByText(text, { exact: true }).locator('visible=true');

test.describe('Certificates F05 issue a certificate (mobile)', () => {
  test('TC-CER-05-E04 issue a certificate by uploading a file', async ({ page, signIn, api, cleanup }) => {
    test.fail(true, 'UI-CER-01: mobile Issue Certificate with an attached file fails with the error toast "Value error, Expected UploadFile, received: <class str>" (the file is sent as a string; seen on Expo web, native not verified)');
    test.setTimeout(240_000);
    const klass = await apiClass(api, cleanup);
    const kid = await apiStudent(api, cleanup, klass, { first: unique('QAHar'), last: 'Tmp' });
    const type = await apiType(api, cleanup, unique('QA Bonafide'));
    await cleanupCertificates(api, cleanup, kid.studentId);
    await signIn('admin');
    await page.goto('/students/studentcertificates', { timeout: 180_000 });
    await vis(page, 'Select class').first().click({ timeout: 90_000 });
    await page.getByText(klass.className, { exact: true }).last().click({ force: true });
    await vis(page, 'Select student').first().click();
    await page.getByText(kid.name, { exact: false }).last().click({ force: true });
    await expect(vis(page, `Upload for ${kid.name}`)).toBeVisible({ timeout: 30_000 });
    await vis(page, 'Issue Certificate').first().click();
    await vis(page, 'Select type').first().click();
    await page.getByText(type.name, { exact: true }).last().click({ force: true });
    await page.getByPlaceholder('YYYY-MM-DD').locator('visible=true').first().fill(new Date().toISOString().slice(0, 10));
    const chooser = page.waitForEvent('filechooser');
    await page.getByText('Tap to attach file', { exact: false }).locator('visible=true').first().click();
    await (await chooser).setFiles(PDF);
    await vis(page, 'Issue Certificate').last().click();
    await toast(page, 'Certificate issued successfully');
    await expect(page.getByText(type.name, { exact: false }).locator('visible=true').first()).toBeVisible({ timeout: 30_000 });
  });
});
