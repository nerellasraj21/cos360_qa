// Masters F14 School settings (School Registration), web. Tenant-wide state: every test is @serial and restores the
// text fields it found. The API has no delete, so a tenant that started with no row (404) is left with an empty row,
// and an uploaded logo URL cannot be cleared.
const { test, expect, toast } = require('../../helpers/fixtures');
const { signInWeb } = require('../../helpers/session');
const { login } = require('../../helpers/api');

const ROUTE = '/settings/school';
const TEXT_FIELDS = ['school_name', 'contact_no', 'alt_contact_no', 'school_email', 'address', 'city', 'state', 'district', 'pin_code', 'country', 'academic_year', 'installation_date', 'school_board'];
const PNG = Buffer.concat([Buffer.from('89504e470d0a1a0a', 'hex'), Buffer.alloc(1000, 48)]);

async function guard(api, cleanup) {
  const res = await api('GET', '/school-settings');
  expect([200, 404]).toContain(res.status);
  const saved = res.status === 404 ? null : res.data;
  cleanup(async () => {
    const body = saved ? Object.fromEntries(TEXT_FIELDS.map((k) => [k, saved[k] ?? null])) : {};
    await api('PUT', '/school-settings', { body });
  });
  return saved;
}

function field(page, placeholder) {
  return page.getByPlaceholder(placeholder, { exact: true });
}

async function open(page) {
  await page.goto(ROUTE);
  await expect(page.getByRole('heading', { name: 'School Settings' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save Settings' })).toBeVisible();
}

function board(page) {
  return page.getByRole('combobox').filter({ has: page.getByRole('option', { name: 'CBSE' }) });
}

function uploadButton(page, box) {
  return page.getByText(box, { exact: true }).locator('xpath=..').getByRole('button', { name: 'Upload' });
}

async function upload(page, box, file) {
  const chooser = page.waitForEvent('filechooser');
  await uploadButton(page, box).click();
  await (await chooser).setFiles(file);
}

test.describe('Masters F14 school settings (web)', () => {
  test.describe.configure({ mode: 'serial' });

  test('TC-MST-14-E01 @serial not configured state', async ({ page, signIn, api, cleanup }) => {
    const saved = await guard(api, cleanup);
    if (saved) {
      // doc: qa_manual keeps a settings row after the first run of E02 (no delete endpoint), so the 404 precondition is reproduced by answering GET /school-settings with 404.
      await page.route(/\/api\/v1\/school-settings$/, (route) => (route.request().method() === 'GET'
        ? route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'School settings not configured yet.' }) })
        : route.continue()));
    }
    await signIn('admin');
    await page.goto('/');
    await page.getByRole('button', { name: 'Administration', exact: true }).click();
    await page.getByRole('button', { name: 'School Settings', exact: true }).or(page.getByRole('link', { name: 'School Settings', exact: true })).first().click();
    await expect(page).toHaveURL(/\/settings\/school/);
    await expect(page.getByRole('heading', { name: 'School Settings' })).toBeVisible();
    await expect(page.getByText('Manage school registration and identity information')).toBeVisible();
    await expect(page.getByText('Not configured yet')).toBeVisible();
    await expect(field(page, 'e.g. Greenfield High School')).toHaveValue('');
    await expect(field(page, '9900099000')).toHaveValue('');
    await expect(field(page, 'school@example.com')).toHaveValue('');
    await expect(field(page, '503001')).toHaveValue('');
    await expect(field(page, 'India')).toHaveValue('India');
  });

  test('TC-MST-14-E02 @serial save basic settings and reload', async ({ page, signIn, api, cleanup }) => {
    await guard(api, cleanup);
    await signIn('admin');
    await open(page);
    await field(page, 'e.g. Greenfield High School').fill('QA School');
    await field(page, '9900099000').fill('9900099000');
    await board(page).selectOption('CBSE');
    await field(page, '503001').fill('503001');
    await page.getByRole('button', { name: 'Save Settings' }).click();
    await toast(page, 'School settings saved successfully');
    await expect(page.getByText('Not configured yet')).toHaveCount(0);
    await page.reload();
    await open(page);
    await expect(field(page, 'e.g. Greenfield High School')).toHaveValue('QA School');
    await expect(field(page, '9900099000')).toHaveValue('9900099000');
    await expect(board(page)).toHaveValue('CBSE');
    await expect(field(page, '503001')).toHaveValue('503001');
    await expect(page.getByText('Not configured yet')).toHaveCount(0);
    const res = await api('GET', '/school-settings');
    expect(res.data).toMatchObject({ school_name: 'QA School', contact_no: '9900099000', school_board: 'CBSE', pin_code: '503001' });
  });

  test('TC-MST-14-E03 @serial client-side format errors block the save', async ({ page, signIn, api, cleanup }) => {
    test.fail(true, 'UI-MST-30: School Email is a native type=email input in a form without noValidate, so "bad" triggers the browser bubble and none of the three inline errors appear');
    await guard(api, cleanup);
    await signIn('admin');
    await open(page);
    let put = false;
    page.on('request', (r) => { if (r.method() === 'PUT' && r.url().includes('/school-settings')) put = true; });
    await field(page, '9900099000').fill('12345');
    await field(page, '503001').fill('12');
    await field(page, 'school@example.com').fill('bad');
    await page.getByRole('button', { name: 'Save Settings' }).click();
    await expect(page.getByText('Must be exactly 10 digits')).toBeVisible();
    await expect(page.getByText('Must be exactly 6 digits')).toBeVisible();
    await expect(page.getByText('Invalid email address')).toBeVisible();
    await page.waitForTimeout(1000);
    expect(put).toBe(false);
  });

  test('TC-MST-14-E04 @serial custom board name persists', async ({ page, signIn, api, cleanup }) => {
    await guard(api, cleanup);
    await signIn('admin');
    await open(page);
    await board(page).selectOption('Custom');
    await field(page, 'Enter board name').fill('QA Open Board');
    await page.getByRole('button', { name: 'Save Settings' }).click();
    await toast(page, 'School settings saved successfully');
    await page.reload();
    await open(page);
    await expect(board(page)).toHaveValue('Custom');
    await expect(field(page, 'Enter board name')).toHaveValue('QA Open Board');
    expect((await api('GET', '/school-settings')).data.school_board).toBe('QA Open Board');
  });

  test('TC-MST-14-E05 @serial upload a school logo', async ({ page, signIn, api, cleanup }) => {
    await guard(api, cleanup);
    const token = (await login('admin')).access_token;
    const tenantId = JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString()).tenant_id;
    await signIn('admin');
    await open(page);
    await upload(page, 'School Logo', { name: 'qa-logo.png', mimeType: 'image/png', buffer: PNG });
    await toast(page, 'School logo uploaded successfully');
    const img = page.getByRole('img', { name: 'School Logo' });
    await expect(img).toHaveAttribute('src', /\/media\/[^/]+\/school\/images\/school_image_url\.png$/);
    const after = await api('GET', '/school-settings');
    expect(after.data.image_url).toMatch(/^\/media\/[^/]+\/school\/images\//);
    expect(after.data.image_url).toContain(`/media/${tenantId}/`);
  });

  test('TC-MST-14-E06 @serial signature over 2 MB is rejected', async ({ page, signIn, api, cleanup }) => {
    const saved = await guard(api, cleanup);
    await signIn('admin');
    await open(page);
    const big = Buffer.concat([PNG, Buffer.alloc(3 * 1024 * 1024, 48)]);
    await upload(page, 'Principal Signature', { name: 'qa-signature.png', mimeType: 'image/png', buffer: big });
    await toast(page, 'Failed to upload signature');
    const after = await api('GET', '/school-settings');
    expect(after.status === 404 ? null : after.data.principal_signature_url).toBe(saved ? saved.principal_signature_url ?? null : null);
    if (!(saved && saved.principal_signature_url)) await expect(page.getByRole('img', { name: 'Principal Signature' })).toHaveCount(0);
  });

  test('TC-MST-14-E07 @serial pdf logo is rejected', async ({ page, signIn, api, cleanup }) => {
    await guard(api, cleanup);
    await signIn('admin');
    await open(page);
    await upload(page, 'School Logo', { name: 'notes.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4\n%QA\n') });
    await toast(page, 'Failed to upload school logo');
  });

  test('TC-MST-14-E08 @serial teacher gets a blank form and student has no Administration menu', async ({ page, signIn, browser, api, cleanup }) => {
    await guard(api, cleanup);
    await signIn('teacher');
    await page.goto('/');
    await page.getByRole('button', { name: 'Administration', exact: true }).click();
    const reads = [];
    page.on('response', (r) => { if (/\/api\/v1\/school-settings$/.test(r.url()) && r.request().method() === 'GET') reads.push(r.status()); });
    await page.getByRole('button', { name: 'School Settings', exact: true }).or(page.getByRole('link', { name: 'School Settings', exact: true })).first().click();
    await expect(page.getByRole('heading', { name: 'School Settings' })).toBeVisible();
    await expect(page.getByText('Not configured yet')).toBeVisible();
    await expect(field(page, 'e.g. Greenfield High School')).toHaveValue('');
    expect(reads.length).toBeGreaterThan(0);
    expect(reads.every((s) => s === 403)).toBe(true);
    await page.getByRole('button', { name: 'Save Settings' }).click();
    await toast(page, 'Failed to save school settings');

    const context = await browser.newContext({ baseURL: test.info().project.use.baseURL, viewport: { width: 1280, height: 800 } });
    const student = await context.newPage();
    await signInWeb(student, 'student');
    await student.goto('/');
    await expect(student.getByRole('button', { name: 'Dashboard', exact: true }).or(student.getByRole('link', { name: 'Dashboard', exact: true })).first()).toBeVisible();
    await expect(student.getByRole('button', { name: 'Administration', exact: true }).or(student.getByRole('link', { name: 'Administration', exact: true }))).toHaveCount(0);
    await context.close();
  });
});
