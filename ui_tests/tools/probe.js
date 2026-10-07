require('dotenv').config({ path: require('path').join(__dirname, '..', '..', '.env') });
const { chromium } = require('playwright');
const { signInWeb, signInMobileViaForm } = require('../helpers/session');

const BASES = { web: process.env.QA_WEB_URL || 'http://localhost:5174', mobile: process.env.QA_MOBILE_URL || 'http://localhost:8082' };

async function main() {
  const [app, role, route, ...rest] = process.argv.slice(2);
  if (!BASES[app] || !role || !route) {
    console.error('usage: node tools/probe.js <web|mobile> <admin|staff|teacher|student|parent> <path> [--click "Text"]... [--shot file.png]');
    process.exit(2);
  }
  const clicks = [];
  let shot = null;
  for (let i = 0; i < rest.length; i += 2) {
    if (rest[i] === '--click') clicks.push(rest[i + 1]);
    if (rest[i] === '--shot') shot = rest[i + 1];
  }
  const browser = await chromium.launch();
  const viewport = app === 'mobile' ? { width: 400, height: 860 } : { width: 1440, height: 900 };
  const page = await browser.newPage({ baseURL: BASES[app], viewport });
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  if (role !== 'none') await (app === 'web' ? signInWeb(page, role) : signInMobileViaForm(page, role));
  await page.goto(route, { timeout: 180000 });
  await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(app === 'mobile' ? 4000 : 1500);
  for (const text of clicks) {
    await page.getByText(text, { exact: false }).first().click({ timeout: 10000 }).catch((e) => errors.push(`click "${text}": ${e.message.split('\n')[0]}`));
    await page.waitForTimeout(1200);
  }
  const info = await page.evaluate(() => {
    const vis = (el) => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
    const txt = (el) => (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
    const uniq = (a) => [...new Set(a.filter(Boolean))];
    return {
      url: location.pathname + location.search,
      headings: uniq([...document.querySelectorAll('h1,h2,h3,h4,[role=heading]')].filter(vis).map(txt)).slice(0, 40),
      buttons: uniq([...document.querySelectorAll('button,[role=button],a[href]')].filter(vis).map((b) => txt(b) || b.getAttribute('aria-label'))).slice(0, 80),
      fields: uniq([...document.querySelectorAll('input,select,textarea')].filter(vis).map((f) => {
        const id = f.id && document.querySelector(`label[for="${f.id}"]`);
        return [id && txt(id), f.getAttribute('placeholder'), f.getAttribute('name'), f.getAttribute('aria-label')].filter(Boolean).join(' | ');
      })).slice(0, 80),
      labels: uniq([...document.querySelectorAll('label')].filter(vis).map(txt)).slice(0, 80),
      text: txt(document.body).slice(0, 4000),
    };
  });
  if (shot) await page.screenshot({ path: shot, fullPage: false });
  console.log(JSON.stringify({ ...info, errors }, null, 1));
  await browser.close();
}

main().catch((e) => { console.error(e); process.exit(1); });
