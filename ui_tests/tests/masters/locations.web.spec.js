// Masters F12 Locations, web (admission form address cascade). qa_manual has no states and the location seed writes
// the shared tables of every tenant, so these tests create their own QA states, districts and mandals and delete
// them afterwards (shared data, so @serial). The states dropdown is cached for 5 minutes with no invalidation.
const { test, expect, unique } = require('../../helpers/fixtures');
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
  const m2 = await post('/masters/locations/mandals', { district_id: a2.id, name: `QA Mandal A2 ${tag}` });
  const data = { a, b, a1, a2, b1, m1, m2 };
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
  for (const m of [data.m1, data.m2]) if (m) await admin('DELETE', `/masters/locations/mandals/${m.id}`);
  for (const d of [data.a1, data.a2, data.b1]) if (d) await admin('DELETE', `/masters/locations/districts/${d.id}`);
  for (const s of [data.a, data.b]) if (s) await admin('DELETE', `/masters/locations/states/${s.id}`);
}

function dropdown(page, label) {
  return page.getByText(label, { exact: true }).locator('xpath=..').getByRole('combobox');
}

async function choose(page, label, option) {
  await dropdown(page, label).click();
  await page.getByRole('option', { name: option, exact: true }).click();
  await expect(dropdown(page, label)).toContainText(option);
}

async function openAddressStep(page) {
  await page.goto('/students/admission');
  await page.getByRole('button', { name: 'New Admission' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByText('New Student Admission')).toBeVisible();
  await dialog.getByRole('combobox', { name: 'Select Class' }).click();
  await page.getByRole('option', { name: 'Class 1', exact: true }).click();
  await dialog.getByLabel('First Name *').fill('QA Location Probe');
  await dialog.getByRole('button', { name: 'Next' }).click();
  await expect(dialog.getByText('Step 2 of 5')).toBeVisible();
  await dialog.locator('#father_name').fill('QA Father');
  await dialog.locator('#father_phone').fill('9000999111');
  await dialog.getByRole('button', { name: 'Next' }).click();
  await expect(dialog.getByText('Step 3 of 5')).toBeVisible();
  await expect(dropdown(page, 'State (Optional)')).toBeVisible();
}

test.describe('Masters F12 locations (web)', () => {
  test.describe.configure({ mode: 'serial', timeout: 480_000 });
  let loc;

  test.beforeAll(async () => {
    test.setTimeout(400_000);
    loc = await createLocations();
  });

  test.afterAll(async () => {
    await removeLocations(loc);
  });

  test('TC-MST-12-E01 @serial district list follows the chosen state', async ({ page, signIn }) => {
    // doc: precondition should use QA states created through the API (the location seed writes the shared tables of every tenant); expected names become the QA state's districts.
    await signIn('admin');
    await openAddressStep(page);
    await expect(dropdown(page, 'District (Optional)')).toBeDisabled();
    await expect(dropdown(page, 'Mandal (Optional)')).toBeDisabled();
    await choose(page, 'State (Optional)', loc.a.name);
    const district = dropdown(page, 'District (Optional)');
    await expect(district).toBeEnabled();
    await expect(dropdown(page, 'Mandal (Optional)')).toBeDisabled();
    await expect(dropdown(page, 'Mandal (Optional)')).toContainText('-- Select Mandal --');
    await district.click();
    const options = page.getByRole('option');
    await expect(options.first()).toBeVisible();
    expect((await options.allInnerTexts()).map((t) => t.trim()).sort()).toEqual([loc.a1.name, loc.a2.name].sort());
  });

  test('TC-MST-12-E02 @serial changing the state clears district and mandal', async ({ page, signIn }) => {
    // doc: the case's "Karnataka" is replaced by a second QA state.
    await signIn('admin');
    await openAddressStep(page);
    await choose(page, 'State (Optional)', loc.a.name);
    await choose(page, 'District (Optional)', loc.a1.name);
    await choose(page, 'Mandal (Optional)', loc.m1.name);
    await choose(page, 'State (Optional)', loc.b.name);
    await expect(dropdown(page, 'District (Optional)')).toContainText('-- Select District --');
    await expect(dropdown(page, 'Mandal (Optional)')).toContainText('-- Select Mandal --');
    await expect(dropdown(page, 'Mandal (Optional)')).toBeDisabled();
  });
});
