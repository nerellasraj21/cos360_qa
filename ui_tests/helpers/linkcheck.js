const fs = require('fs');
const path = require('path');

const REPORTS = path.join(__dirname, '..', '..', 'reports');

async function checkRoute(page, route, { notFound, settleMs = 1500 }) {
  const pageErrors = [];
  const apiFailures = [];
  const onPageError = (error) => pageErrors.push(String(error.message || error).slice(0, 200));
  const onResponse = (response) => {
    const url = response.url();
    if (url.includes('/api/v1/') && response.status() >= 400) {
      apiFailures.push({ status: response.status(), method: response.request().method(), path: new URL(url).pathname });
    }
  };
  page.on('pageerror', onPageError);
  page.on('response', onResponse);

  const result = { route, status: 'ok', finalPath: route, notes: [] };
  try {
    await page.goto(route, { waitUntil: 'domcontentloaded', timeout: 45_000 });
    await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
    await page.waitForTimeout(settleMs);
    const url = new URL(page.url());
    result.finalPath = url.pathname + url.search;
    const text = ((await page.locator('body').innerText().catch(() => '')) || '').trim();

    if (notFound.some((pattern) => pattern.test(text))) {
      result.status = 'not-found';
    } else if (pageErrors.length) {
      result.status = 'crashed';
      result.notes.push(...pageErrors.slice(0, 2));
    } else if (text.length < 15) {
      result.status = 'blank';
    } else if (url.pathname !== route.split('?')[0] && url.pathname.replace(/\/$/, '') !== route.replace(/\/$/, '')) {
      result.status = 'redirected';
    }
    const serverErrors = apiFailures.filter((f) => f.status >= 500);
    const denied = apiFailures.filter((f) => f.status === 401 || f.status === 403);
    const other = apiFailures.filter((f) => f.status >= 400 && f.status < 500 && f.status !== 401 && f.status !== 403);
    if (serverErrors.length) {
      if (result.status === 'ok' || result.status === 'redirected') result.status = 'api-error';
      result.notes.push(...serverErrors.slice(0, 3).map((f) => `${f.method} ${f.status} ${f.path}`));
    }
    if (denied.length) result.notes.push(`denied: ${denied.slice(0, 3).map((f) => `${f.method} ${f.status} ${f.path}`).join('; ')}`);
    if (other.length) result.notes.push(`client errors: ${other.slice(0, 3).map((f) => `${f.method} ${f.status} ${f.path}`).join('; ')}`);
  } catch (error) {
    result.status = 'load-failed';
    result.notes.push(String(error.message || error).split('\n')[0].slice(0, 200));
  } finally {
    page.off('pageerror', onPageError);
    page.off('response', onResponse);
  }
  return result;
}

const FAILING = new Set(['not-found', 'crashed', 'blank', 'load-failed', 'api-error']);

function saveReport(name, results) {
  fs.mkdirSync(REPORTS, { recursive: true });
  fs.writeFileSync(path.join(REPORTS, `${name}.json`), JSON.stringify(results, null, 1));
}

function summarise(results) {
  const counts = {};
  for (const r of results) counts[r.status] = (counts[r.status] || 0) + 1;
  return counts;
}

module.exports = { checkRoute, FAILING, saveReport, summarise };
