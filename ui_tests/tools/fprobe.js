require('dotenv').config({ path: require('path').join(__dirname, '..', '..', '.env') });
const { chromium } = require('playwright');
const { signInWeb } = require('../helpers/session');
async function main() {
  const [role, route, ...steps] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ baseURL: 'http://localhost:5174', viewport: { width: 1280, height: 900 } });
  await signInWeb(page, role);
  await page.goto(route);
  await page.waitForTimeout(2500);
  for (const s of steps) {
    const [kind, ...rest] = s.split('::');
    const arg = rest.join('::');
    try {
      if (kind === 'click') await page.getByRole('button', { name: arg }).first().click({ timeout: 8000 });
      else if (kind === 'clicktext') await page.getByText(arg).first().click({ timeout: 8000 });
      else if (kind === 'tab') await page.getByRole('tab', { name: arg }).first().click({ timeout: 8000 });
      else if (kind === 'combo') { await page.getByRole('combobox').nth(Number(arg)).click({ timeout: 8000 }); }
      else if (kind === 'opt') await page.getByRole('option', { name: arg }).first().click({ timeout: 8000 });
      else if (kind === 'fill') { const [l, v] = arg.split('=>'); await page.getByLabel(l).first().fill(v); }
      else if (kind === 'ph') { const [l, v] = arg.split('=>'); await page.getByPlaceholder(l).first().fill(v); }
      else if (kind === 'num') { const [i, v] = arg.split('=>'); await page.getByRole('spinbutton').nth(Number(i)).fill(v); }
      else if (kind === 'sw') await page.getByRole('switch', { name: arg }).first().click();
      else if (kind === 'type') await page.keyboard.type(arg);
      else if (kind === 'opts') console.log('OPTS', JSON.stringify(await page.getByRole('option').allInnerTexts()));
      else if (kind === 'key') await page.keyboard.press(arg);
      else if (kind === 'wait') await page.waitForTimeout(Number(arg));
    } catch (e) { console.log('STEP FAIL', s, e.message.split('\n')[0]); }
    await page.waitForTimeout(900);
  }
  const dlg = page.locator('[role=dialog],[role=alertdialog]'); const sel = (await dlg.count()) ? dlg.last() : page.locator('main').first(); const snap = await sel.ariaSnapshot();
  const lines = snap.split('\n').filter((l) => !/TanStack|resolvedLocation|routesBy|flatRoutes|pendingMatches|routeTree|commitLocation|matches\d|state\d|options\d|location\d|Router\d/.test(l));
  console.log(lines.slice(Number(process.env.FROM || 0)).join('\n').slice(0, Number(process.env.MAX || 7000)));
  await browser.close();
}
main().catch((e) => { console.error(e); process.exit(1); });
