// Masters F11 Parents, mobile (Expo web). Baseline: qa_manual seeded parents (Venkat Raju, father of Harsha and Tanvi Raju).
// Parents created here also create a Parent-role login; DELETE /parents/{id} removes the profile only, the login stays.
const { test, expect, unique, toast } = require('../../helpers/fixtures');

const ROUTE = '/masters/parents';

function slug(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '.');
}

async function findParent(api, name) {
  const res = await api('GET', `/parents/search?search_query=${encodeURIComponent(name)}&limit=100`);
  return (res.data.items || []).find((p) => p.name === name);
}

function removeLater(api, cleanup, name) {
  cleanup(async () => {
    const parent = await findParent(api, name);
    if (parent) await api('DELETE', `/parents/${parent.id}`);
  });
}

async function createParentViaApi(api, cleanup, name, body) {
  const res = await api('POST', '/parents/', { body: { name, relation_to_student: 'Father', ...body } });
  expect([200, 201]).toContain(res.status);
  cleanup(() => api('DELETE', `/parents/${res.data.id}`));
  return res.data;
}

async function open(page) {
  await page.goto(ROUTE, { timeout: 180_000 });
  await expect(page.getByText(/\d+ registered parents/)).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText('Anil Kumar').first()).toBeVisible({ timeout: 60_000 });
}

async function openAdd(page) {
  await page.getByLabel('Add', { exact: true }).click();
  await expect(page.getByPlaceholder("Parent's full name")).toBeVisible();
}

async function search(page, text) {
  await page.getByPlaceholder('Search by name, email or phone...').fill(text);
}

test.describe('Masters F11 parents (mobile)', () => {
  test('TC-MST-11-E10 search shows the Venkat Raju card', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await search(page, 'venkat.raju');
    await expect(page.getByText('Venkat Raju', { exact: true })).toBeVisible();
    for (const text of ['Father', '9000100012', 'venkat.raju@example.com', 'Bank Officer', 'Harsha Raju, Tanvi Raju']) {
      await expect(page.getByText(text, { exact: true })).toBeVisible();
    }
    await expect(page.getByText('Anil Kumar')).toHaveCount(0);
  });

  test('TC-MST-11-E11 invalid email is rejected', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await openAdd(page);
    await page.getByPlaceholder("Parent's full name").fill('QA M Parent');
    await page.getByPlaceholder('email@example.com').fill('bad');
    await page.getByText('Add Parent', { exact: true }).last().click();
    await toast(page, 'Enter a valid email address');
    await expect(page.getByText('Validation').first()).toBeVisible();
  });

  test('TC-MST-11-E12 short Aadhar is rejected', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await openAdd(page);
    await page.getByPlaceholder("Parent's full name").fill('QA M Parent');
    await page.getByPlaceholder('email@example.com').fill('qa.m.aadhar@example.com');
    await page.getByPlaceholder('12-digit Aadhar number').fill('12345678901');
    await page.getByText('Add Parent', { exact: true }).last().click();
    await toast(page, 'Aadhar number must be 12 digits');
    await expect(page.getByText('Validation').first()).toBeVisible();
  });

  test('TC-MST-11-E13 add a mother with email', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA M Parent');
    const email = `${slug(name)}@example.com`;
    removeLater(api, cleanup, name);
    await signIn('admin');
    await open(page);
    await openAdd(page);
    await page.getByPlaceholder("Parent's full name").fill(name);
    await page.getByText('Father', { exact: true }).last().click();
    await page.getByText('Mother', { exact: true }).last().click();
    await page.getByPlaceholder('email@example.com').fill(email);
    await page.getByText('Add Parent', { exact: true }).last().click();
    await toast(page, 'Parent Added');
    await toast(page, 'The parent profile was created');
    await search(page, name);
    await expect(page.getByText(name, { exact: true })).toBeVisible();
    await expect(page.getByText('No linked students')).toBeVisible();
    const created = await findParent(api, name);
    expect(created.relation_to_student).toBe('Mother');
    expect(created.email).toBe(email);
  });

  test('TC-MST-11-E14 annual income is saved and shown on reopen', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA M Parent');
    await createParentViaApi(api, cleanup, name, { email: `${slug(name)}@example.com`, relation_to_student: 'Mother' });
    await signIn('admin');
    await open(page);
    await search(page, name);
    await expect(page.getByText(name, { exact: true })).toBeVisible();
    await page.getByLabel('Edit', { exact: true }).first().click();
    await expect(page.getByText('Edit Parent', { exact: true })).toBeVisible();
    await page.getByText('Select income range', { exact: true }).click();
    await page.getByText('3 to 5 lakhs', { exact: true }).last().click();
    await page.getByText('Save Changes', { exact: true }).click();
    await toast(page, 'Parent Updated');
    await toast(page, 'The parent profile was saved');
    await expect.poll(async () => (await findParent(api, name)).salary_range).toBe('3l_5l');
    await page.getByLabel('Edit', { exact: true }).first().click();
    await expect(page.getByText('Edit Parent', { exact: true })).toBeVisible();
    await expect(page.getByText('3 to 5 lakhs', { exact: true })).toBeVisible();
  });

  test('TC-MST-11-E15 delete a parent', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA M Parent');
    await createParentViaApi(api, cleanup, name, { email: `${slug(name)}@example.com`, relation_to_student: 'Mother' });
    await signIn('admin');
    await open(page);
    await search(page, name);
    await expect(page.getByText(name, { exact: true })).toBeVisible();
    await page.getByLabel('Delete', { exact: true }).first().click();
    await expect(page.getByText('Delete Parent', { exact: true })).toBeVisible();
    await page.getByText('Delete', { exact: true }).last().click();
    await toast(page, 'Parent Deleted');
    await toast(page, 'The parent profile was removed');
    await expect(page.getByText(name, { exact: true })).toHaveCount(0);
    expect(await findParent(api, name)).toBeUndefined();
  });

  test('TC-MST-11-E16 email or phone is required on add', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await openAdd(page);
    await page.getByPlaceholder("Parent's full name").fill('QA M Parent 3');
    let posted = false;
    page.on('request', (r) => { if (r.method() === 'POST' && r.url().includes('/parents')) posted = true; });
    await page.getByText('Add Parent', { exact: true }).last().click();
    await toast(page, 'Email or phone is required to create the parent login');
    expect(posted).toBe(false);
  });
});
