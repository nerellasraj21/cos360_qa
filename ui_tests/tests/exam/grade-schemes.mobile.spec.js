// Exam F03 Exam grade schemes, mobile (P1).
const { test, expect, unique } = require('../../helpers/fixtures');
const kit = require('./_kit');

const { vis, text, openHub, tile } = kit.mobile;

test.describe('Exam F03 exam grade schemes (mobile)', () => {
  test('TC-EXM-03-E10 create a one band scheme', async ({ page, signIn, api, cleanup }) => {
    test.setTimeout(240_000);
    const name = unique('QA Mobile Scheme');
    cleanup(async () => {
      const list = await api('GET', '/grade-schemes/exam');
      for (const s of list.data.filter((x) => (x.name || x.scheme_name) === name)) await api('DELETE', `/grade-schemes/exam/${s.id}`);
    });
    await signIn('admin');
    await openHub(page);
    await tile(page, 'Grading');
    await text(page, 'Exam Grade Schemes').last().click();
    await expect(text(page, 'New Scheme').first()).toBeVisible({ timeout: 60_000 });
    await text(page, 'New Scheme').first().click();
    await vis(page.getByPlaceholder('e.g. CBSE 10-Point')).fill(name);
    await text(page, 'Add Band').first().click();
    await vis(page.getByPlaceholder('A+')).first().fill('P');
    await vis(page.getByPlaceholder('0', { exact: true })).first().fill('0');
    await vis(page.getByPlaceholder('100', { exact: true })).first().fill('100');
    await vis(page.getByPlaceholder('10.0')).first().fill('1');
    await text(page, 'Create Scheme').first().click();
    await expect(text(page, 'Created').first()).toBeVisible({ timeout: 15_000 });
    await expect(text(page, name).first()).toBeVisible();
  });
});
