// Masters F13 Castes and sub-castes, mobile (Expo web admission form). Runs the tenant caste seed and deletes what it
// created afterwards (tenant-wide, so @serial). The caste dropdown is cached for 5 minutes with no invalidation.
const { test, expect } = require('../../helpers/fixtures');
const { call, login } = require('../../helpers/api');

const SEEDED = ['General', 'OBC', 'SC', 'ST', 'EWS'];
const SC_SUBS = ['Adi Andhra', 'Adi Dravida', 'Mala', 'Madiga', 'Chamar', 'Pasi'];

async function admin(method, path, body) {
  const { access_token: token } = await login('admin');
  return call(method, path, { token, body });
}

async function waitForDropdown(predicate) {
  const deadline = Date.now() + 330_000;
  for (;;) {
    const res = await admin('GET', '/masters/castes/dropdown?active_only=true');
    const live = new Set(((await admin('GET', '/masters/castes/?limit=1000')).data.items || []).map((c) => c.id));
    const fresh = res.status === 200 && res.data.every((c) => live.has(c.id));
    if (fresh && predicate(res.data.map((c) => c.name))) return res.data;
    if (Date.now() > deadline) throw new Error(`caste dropdown did not settle: ${JSON.stringify(res.data)}`);
    await new Promise((r) => setTimeout(r, 10_000));
  }
}

async function removeSeededCastes(created) {
  const names = created.castes_created || [];
  const list = await admin('GET', '/masters/castes/?limit=1000');
  for (const caste of (list.data.items || []).filter((c) => names.includes(c.name))) {
    const subs = await admin('GET', `/masters/castes/${caste.id}/sub-castes`);
    for (const sub of Array.isArray(subs.data) ? subs.data : subs.data.items || []) {
      await admin('DELETE', `/masters/castes/sub-castes/${sub.id}`);
    }
    await admin('DELETE', `/masters/castes/${caste.id}`);
  }
}

function visible(locator) {
  return locator.filter({ visible: true });
}

function field(page, label) {
  return visible(page.getByText(label, { exact: true })).locator('xpath=following-sibling::*[1]');
}

async function choose(page, label, option) {
  await field(page, label).click();
  await visible(page.getByText(option, { exact: true })).last().click();
}

async function listedOptions(page, label, expected) {
  await field(page, label).click();
  for (const name of expected) await expect(visible(page.getByText(name, { exact: true })).last()).toBeVisible();
}

test.describe('Masters F13 castes (mobile)', () => {
  test.describe.configure({ mode: 'serial', timeout: 480_000 });
  let created = {};

  test.beforeAll(async () => {
    test.setTimeout(400_000);
    const res = await admin('POST', '/auth/seed/caste-data');
    expect(res.status).toBe(201);
    created = res.data.details || {};
    await waitForDropdown((names) => SEEDED.every((n) => names.includes(n)));
  });

  test.afterAll(async () => {
    await removeSeededCastes(created);
  });

  test('TC-MST-13-E04 @serial caste and sub-caste cascade on the admission form', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/students/admission', { timeout: 180_000 });
    await visible(page.getByText('New Admission', { exact: true })).first().click({ timeout: 60_000 });
    await expect(visible(page.getByText('Caste (Optional)', { exact: true }))).toBeVisible({ timeout: 60_000 });
    await listedOptions(page, 'Caste (Optional)', SEEDED);
    await visible(page.getByText('SC', { exact: true })).last().click();
    await expect(field(page, 'Caste (Optional)')).toContainText('SC');
    await listedOptions(page, 'Sub Caste (Optional)', SC_SUBS);
    await visible(page.getByText('Mala', { exact: true })).last().click();
    await expect(field(page, 'Sub Caste (Optional)')).toContainText('Mala');
    await choose(page, 'Caste (Optional)', 'ST');
    await expect(field(page, 'Caste (Optional)')).toContainText('ST');
    await expect(field(page, 'Sub Caste (Optional)')).not.toContainText('Mala');
    await expect(field(page, 'Sub Caste (Optional)')).toContainText('Select');
  });
});
