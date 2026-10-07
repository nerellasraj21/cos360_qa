// Masters F11 Parents, web. Baseline: qa_manual seeded parents (for example Venkat Raju, father of Harsha and Tanvi Raju).
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

function row(page, name) {
  return page.getByRole('row').filter({ hasText: name });
}

async function open(page) {
  await page.goto(ROUTE);
  await expect(page.getByRole('heading', { name: 'Parent Profiles' })).toBeVisible();
}

test.describe('Masters F11 parents (web)', () => {
  test('TC-MST-11-E01 list shows seeded parents', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await expect(page.getByRole('heading', { name: 'Parent Management' })).toBeVisible();
    for (const header of ['S.No.', 'Name', 'Contact', 'Relationship', 'Occupation', 'Students', 'Actions']) {
      await expect(page.getByRole('columnheader', { name: header })).toBeVisible();
    }
    const venkat = row(page, 'Venkat Raju');
    await expect(venkat).toHaveCount(1);
    for (const text of ['Male', 'venkat.raju@example.com', 'Father', 'Bank Officer', '2 students']) {
      await expect(venkat).toContainText(text);
    }
    await expect(venkat.getByRole('button', { name: 'Edit Parent' })).toBeVisible();
    await expect(venkat.getByRole('button', { name: 'Delete Parent' })).toBeVisible();
  });

  test('TC-MST-11-E02 search by phone and sort by name', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    const search = page.getByPlaceholder('Search parents...');
    await search.fill('9000100012');
    await expect(page.locator('tbody tr')).toHaveCount(1);
    await expect(page.locator('tbody tr').first()).toContainText('Venkat Raju');
    await search.fill('');
    const firstName = () => page.locator('tbody tr').first().locator('td').nth(1).innerText();
    const header = page.getByRole('columnheader', { name: 'Name' });
    await header.click();
    const asc = await firstName();
    await header.click();
    await expect.poll(firstName).not.toBe(asc);
    const desc = await firstName();
    expect(desc.localeCompare(asc)).toBeGreaterThan(0);
  });

  test('TC-MST-11-E03 add a parent with email', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Parent One');
    const email = `${slug(name)}@example.com`;
    removeLater(api, cleanup, name);
    await signIn('admin');
    await open(page);
    await page.getByRole('button', { name: 'Add Parent' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText('Create Parent Profile')).toBeVisible();
    await dialog.getByPlaceholder("Enter parent's full name").fill(name);
    await dialog.getByPlaceholder('Enter email address').fill(email);
    await expect(dialog.getByRole('button', { name: 'Father' })).toBeVisible();
    await dialog.getByRole('button', { name: 'Save' }).click();
    await toast(page, 'Parent profile created successfully');
    await expect(dialog).toBeHidden();
    await expect(row(page, name)).toContainText('0 students');
    const created = await findParent(api, name);
    expect(created.email).toBe(email);
    expect(created.relation_to_student).toBe('Father');
  });

  test('TC-MST-11-E04 full name is required', async ({ page, signIn }) => {
    await signIn('admin');
    await open(page);
    await page.getByRole('button', { name: 'Add Parent' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByPlaceholder('Enter email address').fill('qa.noname@example.com');
    let posted = false;
    page.on('request', (r) => { if (r.method() === 'POST' && r.url().includes('/parents')) posted = true; });
    await dialog.getByRole('button', { name: 'Save' }).click();
    await toast(page, 'Parent name is required');
    expect(posted).toBe(false);
    await expect(dialog).toBeVisible();
  });

  test('TC-MST-11-E05 edit occupation', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Parent One');
    await createParentViaApi(api, cleanup, name, { email: `${slug(name)}@example.com` });
    await signIn('admin');
    await open(page);
    await page.getByPlaceholder('Search parents...').fill(name);
    await row(page, name).getByRole('button', { name: 'Edit Parent' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText('Edit Parent Profile')).toBeVisible();
    await expect(dialog.getByPlaceholder("Enter parent's full name")).toHaveValue(name);
    await dialog.getByPlaceholder('Enter occupation/profession').fill('Engineer');
    await dialog.getByRole('button', { name: 'Save' }).click();
    await toast(page, 'Parent profile updated successfully');
    await expect(row(page, name)).toContainText('Engineer');
    expect((await findParent(api, name)).occupation).toBe('Engineer');
  });

  test('TC-MST-11-E06 edit a phone-only parent', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Parent Two');
    const phone = `9${Date.now().toString().slice(-9)}`;
    await createParentViaApi(api, cleanup, name, { phone });
    await signIn('admin');
    await open(page);
    await page.getByPlaceholder('Search parents...').fill(name);
    await row(page, name).getByRole('button', { name: 'Edit Parent' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByPlaceholder('Enter email address')).toHaveValue('');
    const patch = page.waitForRequest((r) => r.method() === 'PATCH' && r.url().includes('/parents/'));
    await dialog.getByPlaceholder('Enter occupation/profession').fill('Farmer');
    await dialog.getByRole('button', { name: 'Save' }).click();
    const body = (await patch).postDataJSON();
    expect(body).not.toHaveProperty('email');
    await toast(page, 'Parent profile updated successfully');
    await expect(dialog).toBeHidden();
    expect((await findParent(api, name)).occupation).toBe('Farmer');
  });

  test('TC-MST-11-E07 delete a parent', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Parent One');
    await createParentViaApi(api, cleanup, name, { email: `${slug(name)}@example.com` });
    await signIn('admin');
    await open(page);
    await page.getByPlaceholder('Search parents...').fill(name);
    await row(page, name).getByRole('button', { name: 'Delete Parent' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText('Delete Parent Profile')).toBeVisible();
    await expect(dialog).toContainText(`Are you sure you want to delete the profile for "${name}"?`);
    await dialog.getByRole('button', { name: 'Delete', exact: true }).click();
    await toast(page, 'Parent profile deleted successfully');
    await expect(row(page, name)).toHaveCount(0);
    expect(await findParent(api, name)).toBeUndefined();
  });

  test('TC-MST-11-E08 staff can add and edit but not delete', async ({ page, signIn }) => {
    await signIn('staff');
    await open(page);
    await expect(page.getByRole('button', { name: 'Add Parent' })).toBeVisible();
    const venkat = row(page, 'Venkat Raju');
    await expect(venkat.getByRole('button', { name: 'Edit Parent' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Delete Parent' })).toHaveCount(0);
  });

  test('TC-MST-11-E09 teacher gets an empty list without Add', async ({ page, signIn }) => {
    await signIn('teacher');
    const listed = page.waitForResponse((r) => r.request().method() === 'GET' && /\/api\/v1\/parents\/?(\?|$)/.test(r.url()));
    await page.goto(ROUTE);
    expect((await listed).status()).toBe(403);
    await expect(page.getByText('No parent profiles found.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Add Parent' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Create First Parent Profile' })).toHaveCount(0);
  });
});
