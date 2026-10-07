// Masters F14 School settings, mobile (Expo web). Tenant-wide state: every test is @serial and restores the text
// fields it found. An uploaded logo URL cannot be cleared through the API.
const { test, expect, toast } = require('../../helpers/fixtures');

const ROUTE = '/admin/school-settings';
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

function visible(locator) {
  return locator.filter({ visible: true });
}

async function open(page) {
  await page.goto(ROUTE, { timeout: 180_000 });
  await expect(visible(page.getByText('Save Settings', { exact: true }))).toBeVisible({ timeout: 60_000 });
  await expect(visible(page.getByText('Branding', { exact: true }))).toBeVisible();
}

test.describe('Masters F14 school settings (mobile)', () => {
  test.describe.configure({ mode: 'serial', timeout: 300_000 });

  test('TC-MST-14-E09 @serial school name is required', async ({ page, signIn, api, cleanup }) => {
    await guard(api, cleanup);
    await signIn('admin');
    await open(page);
    let put = false;
    page.on('request', (r) => { if (r.method() === 'PUT' && r.url().includes('/school-settings')) put = true; });
    await visible(page.getByPlaceholder('School Name *', { exact: true })).fill('');
    await visible(page.getByText('Save Settings', { exact: true })).click();
    await toast(page, 'School name is required');
    await expect(visible(page.getByText('Error', { exact: true })).first()).toBeVisible();
    expect(put).toBe(false);
  });

  test('TC-MST-14-E10 @serial save name and contact, then reopen', async ({ page, signIn, api, cleanup }) => {
    await guard(api, cleanup);
    await signIn('admin');
    await open(page);
    await visible(page.getByPlaceholder('School Name *', { exact: true })).fill('QA School M');
    await visible(page.getByPlaceholder('Contact Number', { exact: true })).fill('9900099001');
    await visible(page.getByText('Save Settings', { exact: true })).click();
    await toast(page, 'Saved');
    await toast(page, 'School settings have been updated.');
    await page.goto('/', { timeout: 180_000 });
    await expect(visible(page.getByLabel('Open Students', { exact: true }))).toBeVisible({ timeout: 60_000 });
    await open(page);
    await expect(visible(page.getByPlaceholder('School Name *', { exact: true }))).toHaveValue('QA School M');
    await expect(visible(page.getByPlaceholder('Contact Number', { exact: true }))).toHaveValue('9900099001');
    expect((await api('GET', '/school-settings')).data).toMatchObject({ school_name: 'QA School M', contact_no: '9900099001' });
  });

  test('TC-MST-14-E11 @serial upload a school logo', async ({ page, signIn, api, cleanup }) => {
    await guard(api, cleanup);
    await signIn('admin');
    await open(page);
    const chooser = page.waitForEvent('filechooser');
    await visible(page.getByText('School Logo', { exact: true })).locator('xpath=preceding-sibling::*[1]').click();
    await (await chooser).setFiles({ name: 'qa-logo-m.png', mimeType: 'image/png', buffer: PNG });
    await toast(page, 'Uploaded');
    await toast(page, 'School logo has been updated.');
    const after = await api('GET', '/school-settings');
    expect(after.data.image_url).toMatch(/^\/media\/[^/]+\/school\/images\/school_image_url\./);
    await expect(visible(page.getByText('School Logo', { exact: true })).locator('xpath=preceding-sibling::*[1]').locator('img')).toHaveCount(1);
  });

  test('TC-MST-14-E12 @serial teacher has no access', async ({ page, signIn }) => {
    await signIn('teacher');
    await page.goto('/', { timeout: 180_000 });
    await visible(page.getByLabel('Open Administration', { exact: true })).click();
    const card = visible(page.getByText('School Settings', { exact: true })).locator('xpath=..');
    await expect(card).toContainText(/No access . contact admin/);
    await page.goto(ROUTE, { timeout: 180_000 });
    await expect(visible(page.getByText('Access Denied')).first()).toBeVisible({ timeout: 60_000 });
    await expect(visible(page.getByText('Save Settings', { exact: true }))).toHaveCount(0);
  });
});
