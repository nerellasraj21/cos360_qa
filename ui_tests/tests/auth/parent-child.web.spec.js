// Auth F09 Parent child selection, web. Own throwaway family (two children, one father login with password set).
const { test, expect } = require('../../helpers/fixtures');
const { createFamily, injectWebSession } = require('../../helpers/auth-users');

async function setup(page, api, cleanup) {
  const family = await createFamily(api, cleanup);
  await injectWebSession(page, family.login);
  await page.goto('/dashboard');
  const navbar = page.getByRole('combobox').filter({ hasText: family.children[0].firstName });
  await expect(navbar).toBeVisible({ timeout: 20_000 });
  return { family, navbar };
}

test.describe('Auth F09 parent child selection (web)', () => {
  test('TC-AUTH-09-E01 navbar shows the first child with class and section', async ({ page, api, cleanup }) => {
    const { family, navbar } = await setup(page, api, cleanup);
    await expect(navbar).toContainText(`${family.children[0].firstName} Tmp`);
    await expect(navbar).toContainText(`${family.klass.className} - ${family.klass.sectionName}`);
  });

  test('TC-AUTH-09-E02 select the second child', async ({ page, api, cleanup }) => {
    const { family, navbar } = await setup(page, api, cleanup);
    const second = family.children[1];
    await navbar.click();
    await page.getByPlaceholder('Search students...').fill(second.admissionNumber);
    await page.getByRole('dialog').getByText(`${second.firstName} Tmp`).first().click();
    const after = page.getByRole('combobox').filter({ hasText: second.firstName });
    await expect(after).toBeVisible();
    await after.click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText('Selected', { exact: true })).toHaveCount(1);
    await expect(dialog.locator('div').filter({ hasText: `${second.firstName} Tmp` }).filter({ hasText: 'Selected' }).last()).toBeVisible();
  });

  test('TC-AUTH-09-E03 selection survives a reload', async ({ page, api, cleanup }) => {
    const { family, navbar } = await setup(page, api, cleanup);
    const second = family.children[1];
    await navbar.click();
    await page.getByRole('dialog').getByText(`${second.firstName} Tmp`).first().click();
    await expect(page.getByRole('combobox').filter({ hasText: second.firstName })).toBeVisible();
    await page.reload();
    await expect(page.getByRole('combobox').filter({ hasText: second.firstName })).toBeVisible({ timeout: 20_000 });
  });

  test('TC-AUTH-09-E04 parent without children has no selector', async ({ page, signIn }) => {
    await signIn('parent');
    await page.goto('/dashboard');
    await expect(page.getByText('qa_parent').first()).toBeVisible();
    await expect(page.getByPlaceholder('Select student...')).toHaveCount(0);
    await expect(page.getByText('Year').first()).toBeVisible();
  });

  test('TC-AUTH-09-E05 search with no match', async ({ page, api, cleanup }) => {
    const { navbar } = await setup(page, api, cleanup);
    await navbar.click();
    await page.getByPlaceholder('Search students...').fill('QA Nobody');
    await expect(page.getByText('No students found.')).toBeVisible();
  });
});
