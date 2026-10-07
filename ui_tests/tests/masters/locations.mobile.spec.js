// Masters F12 Locations, mobile (Expo web). E03 uses its own QA states, districts and mandals (the location seed
// writes the shared tables of every tenant) and deletes them afterwards (shared data, so @serial). The states dropdown
// is cached for 5 minutes with no invalidation. E04 to E06 use the flat Locations screen.
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { call, login } = require('../../helpers/api');

async function admin(method, path, body) {
  const { access_token: token } = await login('admin');
  return call(method, path, { token, body });
}

async function post(path, body) {
  const res = await admin('POST', path, body);
  if (res.status !== 201) throw new Error(`${path}: ${res.status} ${JSON.stringify(res.data)}`);
  return res.data;
}

async function createLocations() {
  const tag = unique('QA').split(' ')[1];
  const a = await post('/masters/locations/states', { name: `QA State A ${tag}` });
  const b = await post('/masters/locations/states', { name: `QA State B ${tag}` });
  const a1 = await post('/masters/locations/districts', { state_id: a.id, name: `QA Dist A1 ${tag}` });
  const a2 = await post('/masters/locations/districts', { state_id: a.id, name: `QA Dist A2 ${tag}` });
  const b1 = await post('/masters/locations/districts', { state_id: b.id, name: `QA Dist B1 ${tag}` });
  const m1 = await post('/masters/locations/mandals', { district_id: a1.id, name: `QA Mandal A1 ${tag}` });
  const data = { a, b, a1, a2, b1, m1 };
  const deadline = Date.now() + 330_000;
  for (;;) {
    const res = await admin('GET', '/masters/locations/states/dropdown?active_only=true');
    const live = new Set(((await admin('GET', '/masters/locations/states?limit=1000')).data.items || []).map((s) => s.id));
    const ids = res.data.map((s) => s.id);
    if (ids.every((id) => live.has(id)) && ids.includes(a.id) && ids.includes(b.id)) return data;
    if (Date.now() > deadline) throw new Error('states dropdown did not pick up the QA states');
    await new Promise((r) => setTimeout(r, 10_000));
  }
}

async function removeLocations(data) {
  if (!data) return;
  if (data.m1) await admin('DELETE', `/masters/locations/mandals/${data.m1.id}`);
  for (const d of [data.a1, data.a2, data.b1]) if (d) await admin('DELETE', `/masters/locations/districts/${d.id}`);
  for (const s of [data.a, data.b]) if (s) await admin('DELETE', `/masters/locations/states/${s.id}`);
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
  await expect(field(page, label)).toContainText(option);
}

async function openAddressStep(page) {
  await page.goto('/students/admission', { timeout: 180_000 });
  await visible(page.getByText('New Admission', { exact: true })).first().click({ timeout: 60_000 });
  await expect(visible(page.getByText('Caste (Optional)', { exact: true }))).toBeVisible({ timeout: 60_000 });
  await visible(page.getByPlaceholder('Enter first name')).fill('QA Location Probe');
  const number = visible(page.getByPlaceholder('e.g. 2026001'));
  if (!(await number.inputValue())) await number.fill(`QA${Date.now().toString().slice(-7)}`);
  if (!(await visible(page.getByText('Joining Class *', { exact: true })).count())) {
    await visible(page.getByText('Academic Details', { exact: true })).first().click();
  }
  await choose(page, 'Academic Year *', '2026-2027');
  await choose(page, 'Joining Class *', 'Class 1');
  await visible(page.getByText('Next', { exact: true })).last().click();
  await expect(visible(page.getByText('Parent Information')).first()).toBeVisible();
  await visible(page.getByPlaceholder('Father name', { exact: true })).fill('QA Father');
  await visible(page.getByPlaceholder('10-digit phone number')).first().fill('9000999111');
  await visible(page.getByText('Next', { exact: true })).last().click();
  await expect(visible(page.getByText('State (Optional)', { exact: true }))).toBeVisible();
}

test.describe('Masters F12 locations (mobile)', () => {
  test.describe('admission address cascade', () => {
    test.describe.configure({ mode: 'serial', timeout: 480_000 });
    let loc;

    test.beforeAll(async () => {
      test.setTimeout(400_000);
      loc = await createLocations();
    });

    test.afterAll(async () => {
      await removeLocations(loc);
    });

    test('TC-MST-12-E03 @serial state, district and mandal cascade and clear', async ({ page, signIn }) => {
      // doc: precondition should use QA states created through the API (the location seed writes the shared tables of every tenant).
      await signIn('admin');
      await openAddressStep(page);
      await expect(field(page, 'District (Optional)')).toContainText('Select a state first');
      await choose(page, 'State (Optional)', loc.a.name);
      await expect(field(page, 'Mandal (Optional)')).toContainText('Select a district first');
      await field(page, 'District (Optional)').click();
      await expect(visible(page.getByText(loc.a1.name, { exact: true })).last()).toBeVisible();
      await expect(visible(page.getByText(loc.a2.name, { exact: true })).last()).toBeVisible();
      await expect(visible(page.getByText(loc.b1.name, { exact: true }))).toHaveCount(0);
      await visible(page.getByText(loc.a1.name, { exact: true })).last().click();
      await choose(page, 'Mandal (Optional)', loc.m1.name);
      await choose(page, 'State (Optional)', loc.b.name);
      await expect(field(page, 'District (Optional)')).toContainText('Select district');
      await expect(field(page, 'District (Optional)')).not.toContainText(loc.a1.name);
      await expect(field(page, 'Mandal (Optional)')).toContainText('Select a district first');
    });
  });

  test('TC-MST-12-E04 flat Locations screen shows no rows', async () => {
    test.skip(true, 'blocked: mobile Locations screen calls a missing endpoint (Known gaps 14)');
  });

  test('TC-MST-12-E05 add a location on the flat screen', async () => {
    test.skip(true, 'blocked: the flat create endpoint does not exist, the save shows "Create Failed" (Known gaps 14)');
  });

  test('TC-MST-12-E06 location name is required', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/masters/locations', { timeout: 180_000 });
    await expect(visible(page.getByText('Locations', { exact: true })).first()).toBeVisible({ timeout: 60_000 });
    await visible(page.getByLabel('Add', { exact: true })).click();
    await expect(visible(page.getByText('Add Location', { exact: true }))).toBeVisible();
    let posted = false;
    page.on('request', (r) => { if (r.method() === 'POST' && r.url().includes('/locations')) posted = true; });
    await visible(page.getByText('Create', { exact: true })).click();
    await toast(page, 'Location name is required');
    await expect(visible(page.getByText('Validation', { exact: true })).first()).toBeVisible();
    expect(posted).toBe(false);
  });
});
