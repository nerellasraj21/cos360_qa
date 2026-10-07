const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { typeIdByName } = require('./_kit');

const SEEDED_TEMPLATES = ['Bonafide Certificate', 'Conduct Certificate', 'Study Certificate', 'Transfer Certificate'];

async function templates(api) {
  const res = await api('GET', '/issuable-certificates/templates/');
  return res.data || [];
}

test.describe('Certificates F01-F02 types and templates (web)', () => {
  test('TC-CER-01-E01 create a certificate type', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Bonafide');
    cleanup(async () => {
      const id = await typeIdByName(api, name);
      if (id) await api('DELETE', `/certificates/types/${id}`);
    });
    await signIn('admin');
    await page.goto('/students/certificatetypes');
    await expect(page.getByRole('heading', { name: 'Certificate Types' })).toBeVisible({ timeout: 30_000 });
    await page.getByRole('button', { name: 'Add Certificate Type' }).click();
    const d = page.getByRole('dialog', { name: 'Create Certificate Type' });
    await expect(d).toBeVisible();
    await d.getByRole('textbox', { name: 'Name *' }).fill(name);
    await d.getByRole('textbox', { name: 'Description' }).fill('QA enrollment proof');
    await d.getByRole('button', { name: 'Save' }).click();
    await toast(page, 'Certificate type created successfully');
    await page.getByPlaceholder('Search name or description...').fill(name);
    const row = page.getByRole('row', { name: new RegExp(name) });
    await expect(row).toBeVisible();
    await expect(row).toContainText('QA enrollment proof');
    await expect(row.getByRole('cell').first()).toHaveText(/^\d+$/);
  });

  test('TC-CER-02-E01 @serial load the default templates', async ({ page, signIn, api, cleanup }) => {
    const before = (await templates(api)).map((t) => t.id);
    cleanup(async () => {
      for (const t of await templates(api)) {
        if (!before.includes(t.id)) await api('DELETE', `/issuable-certificates/templates/${t.id}/`);
      }
    });
    await signIn('admin');
    await page.goto('/students/certificatetemplates');
    await expect(page.getByRole('heading', { name: 'Certificate Templates' })).toBeVisible({ timeout: 30_000 });
    for (const n of SEEDED_TEMPLATES) await expect(page.getByText(n, { exact: true }).first()).toBeVisible();
    await page.getByRole('button', { name: 'Load Default Templates' }).click();
    await toast(page, 'Default templates added successfully');
    // doc: the default cards are named "Bonafide Certificate (Class I-X)" (en dash), "Permanent Bonafide Certificate (After Class X)", "Conduct Certificate (Class I-X)", "Conduct Certificate - Permanent (After Class X)", "Transfer Certificate (Before Class X)", "Transfer Certificate - Permanent (After Class X)"
    for (const n of [/^Bonafide Certificate \(Class I.X\)$/, /^Permanent Bonafide Certificate \(After Class X\)$/, /^Conduct Certificate \(Class I.X\)$/, /^Conduct Certificate . Permanent \(After Class X\)$/, /^Transfer Certificate \(Before Class X\)$/, /^Transfer Certificate . Permanent \(After Class X\)$/]) {
      await expect(page.getByText(n).first()).toBeVisible({ timeout: 15_000 });
    }
    await expect(page.getByText('Status: Active')).toHaveCount(10);
  });

  test('TC-CER-02-E02 create a custom template with variables', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Custom Bonafide');
    cleanup(async () => {
      for (const t of await templates(api)) if (t.name === name) await api('DELETE', `/issuable-certificates/templates/${t.id}/`);
    });
    await signIn('admin');
    await page.goto('/students/certificatetemplates');
    await page.getByRole('button', { name: 'Create Template' }).click();
    await page.getByPlaceholder('e.g., Bonafide Certificate').fill(name);
    await page.getByRole('radio', { name: 'green' }).check();
    const editor = page.getByRole('textbox').last();
    await editor.click();
    await page.keyboard.type('This is to certify that ');
    await page.getByRole('button', { name: 'Insert Variable' }).click();
    await page.getByText('student_name', { exact: false }).first().click();
    await page.keyboard.type(' studies in ');
    await page.getByRole('button', { name: 'Insert Variable' }).click();
    await page.getByText('class_name', { exact: false }).first().click();
    await page.getByRole('button', { name: 'Create Template' }).last().click();
    await toast(page, `Template "${name}" created successfully`);
    const card = page.locator('div').filter({ hasText: name }).filter({ has: page.getByRole('button', { name: 'Preview' }) }).last();
    await expect(card).toContainText('green');
    await expect(card).toContainText('Variables: 2 fields');
  });
});
