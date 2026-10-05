// Link check (navigation only, no clicks and no form submissions).
// Precondition: qa_school tenant with the five QA users; web served at WEB_URL pointed at the QA API.
const { test, expect } = require('@playwright/test');
const { ROLES } = require('../../helpers/api');
const { signInWeb } = require('../../helpers/session');
const { checkRoute, FAILING, saveReport, summarise } = require('../../helpers/linkcheck');
const routes = require('../../helpers/web-routes.json');

const NOT_FOUND = [/^\s*404\s*$/m, /page not found/i, /could not be found/i];

function report(title, results) {
  console.log(`\n${title}: ${JSON.stringify(summarise(results))}`);
  for (const r of results.filter((x) => x.status !== 'ok')) {
    console.log(`  [${r.status}] ${r.route}${r.finalPath !== r.route ? ` -> ${r.finalPath}` : ''} ${r.notes.join(' | ')}`);
  }
}

async function visitAll(page, urls) {
  const results = [];
  for (const route of urls) results.push(await checkRoute(page, route, { notFound: NOT_FOUND }));
  return results;
}

test.describe('web links', () => {
  test.setTimeout(30 * 60_000);

  test('every static route opens for admin', async ({ page }) => {
    await signInWeb(page, 'admin');
    const results = await visitAll(page, routes.static);
    saveReport('link-check-web-routes', results);
    report('web routes (admin)', results);
    const failing = results.filter((r) => FAILING.has(r.status)).map((r) => `${r.route} [${r.status}]`);
    expect(failing, 'broken web routes').toEqual([]);
  });

  for (const role of ROLES) {
    test(`every menu link works for ${role}`, async ({ page }) => {
      const data = await signInWeb(page, role);
      const flatten = (items) => (items || []).flatMap((item) => [item.path || item.url, ...flatten(item.children)]);
      const urls = [...new Set(flatten(data.menu).filter((u) => u && u.startsWith('/')))];
      expect(urls.length, `menu links found for ${role}`).toBeGreaterThan(0);
      const results = await visitAll(page, urls);
      saveReport(`link-check-web-menu-${role}`, results);
      report(`web menu (${role}, ${urls.length} links)`, results);
      const failing = results.filter((r) => FAILING.has(r.status)).map((r) => `${r.route} [${r.status}]`);
      expect(failing, `broken menu links for ${role}`).toEqual([]);
    });
  }
});
