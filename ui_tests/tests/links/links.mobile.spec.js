// Link check (navigation only, no taps and no form submissions).
// Precondition: qa_school tenant with the five QA users; Expo web served at MOBILE_URL pointed at the QA API.
const { test, expect } = require('@playwright/test');
const { signInMobileViaForm } = require('../../helpers/session');
const { checkRoute, FAILING, saveReport, summarise } = require('../../helpers/linkcheck');
const routes = require('../../helpers/mobile-routes.json');

const NOT_FOUND = [/this screen doesn'?t exist/i, /unmatched route/i, /page could not be found/i];
const SKIP = new Set(['/modal', '/permission-test', '/login', '/forgot-password', '/set-password']);

test.describe('mobile links', () => {
  test.setTimeout(45 * 60_000);

  test('every static screen opens for admin', async ({ page }) => {
    await signInMobileViaForm(page, 'admin');
    const results = [];
    for (const route of routes.static.filter((r) => !SKIP.has(r))) {
      results.push(await checkRoute(page, route, { notFound: NOT_FOUND, settleMs: 2500 }));
    }
    saveReport('link-check-mobile-routes', results);
    console.log(`\nmobile screens (admin): ${JSON.stringify(summarise(results))}`);
    for (const r of results.filter((x) => x.status !== 'ok')) {
      console.log(`  [${r.status}] ${r.route}${r.finalPath !== r.route ? ` -> ${r.finalPath}` : ''} ${r.notes.join(' | ')}`);
    }
    const failing = results.filter((r) => FAILING.has(r.status)).map((r) => `${r.route} [${r.status}]`);
    expect(failing, 'broken mobile screens').toEqual([]);
  });
});
