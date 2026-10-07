// Masters F13 Castes and sub-castes, web (admission form dropdowns). qa_manual starts with no castes.
// E01/E02 run the tenant caste seed and delete what it created afterwards (tenant-wide, so @serial). The caste
// dropdown is cached for 5 minutes with no invalidation, so the tests wait until the API dropdown matches.
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

async function seedCastes() {
  const res = await admin('POST', '/auth/seed/caste-data');
  expect(res.status).toBe(201);
  await waitForDropdown((names) => SEEDED.every((n) => names.includes(n)));
  return res.data.details || {};
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

function dropdown(page, label) {
  return page.getByText(label, { exact: true }).locator('xpath=..').getByRole('combobox');
}

async function openAdmission(page) {
  await page.goto('/students/admission');
  await page.getByRole('button', { name: 'New Admission' }).click();
  await expect(page.getByRole('dialog').getByText('New Student Admission')).toBeVisible();
  await expect(dropdown(page, 'Caste (Optional)')).toBeVisible();
}

test.describe('Masters F13 castes (web)', () => {
  test.describe.configure({ mode: 'serial', timeout: 480_000 });

  test('TC-MST-13-E03 @serial caste list is empty before the seed', async ({ page, signIn, api }) => {
    const list = await api('GET', '/masters/castes/?limit=1000');
    expect(list.data.total_count).toBe(0);
    await waitForDropdown((names) => names.length === 0);
    await signIn('admin');
    await openAdmission(page);
    const caste = dropdown(page, 'Caste (Optional)');
    if (await caste.isEnabled()) {
      await caste.click();
      await page.waitForTimeout(800);
    }
    await expect(page.getByRole('option')).toHaveCount(0);
  });

  test.describe('with the caste seed', () => {
    let created = {};
    test.beforeAll(async () => {
      test.setTimeout(400_000);
      created = await seedCastes();
    });
    test.afterAll(async () => {
      await removeSeededCastes(created);
    });

    test('TC-MST-13-E01 @serial caste dropdown lists the seeded castes', async ({ page, signIn }) => {
      await signIn('admin');
      await openAdmission(page);
      await dropdown(page, 'Caste (Optional)').click();
      const options = page.getByRole('option');
      await expect(options.first()).toBeVisible();
      const labels = (await options.allInnerTexts()).map((t) => t.trim().replace(/\s*\(.*\)$/, ''));
      expect(labels.sort()).toEqual([...SEEDED].sort());
    });

    test('TC-MST-13-E02 @serial sub-castes follow the caste and clear on change', async ({ page, signIn }) => {
      await signIn('admin');
      await openAdmission(page);
      await dropdown(page, 'Caste (Optional)').click();
      await page.getByRole('option', { name: /^SC\b/ }).click();
      const sub = dropdown(page, 'Sub Caste (Optional)');
      await expect(sub).toBeEnabled();
      await sub.click();
      const options = page.getByRole('option');
      await expect(options.first()).toBeVisible();
      const labels = (await options.allInnerTexts()).map((t) => t.trim().replace(/\s*\(.*\)$/, ''));
      expect(labels.sort()).toEqual([...SC_SUBS].sort());
      await page.getByRole('option', { name: /^Mala\b/ }).click();
      await expect(sub).toContainText('Mala');
      await dropdown(page, 'Caste (Optional)').click();
      await page.getByRole('option', { name: /^ST\b/ }).click();
      await expect(dropdown(page, 'Caste (Optional)')).toContainText('ST');
      await expect(sub).not.toContainText('Mala');
      await expect(sub).toContainText('Select');
    });
  });
});
