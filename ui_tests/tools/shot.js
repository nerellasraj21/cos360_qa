const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '..', '..', '.env') });
const { chromium, devices } = require('@playwright/test');
const { credentials, TENANT } = require('../helpers/api');

(async () => {
  const routes = process.argv.slice(2);
  const { username, password } = credentials('admin');
  const browser = await chromium.launch();
  const context = await browser.newContext({ ...devices['Pixel 5'], viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  await page.goto('http://127.0.0.1:8082/login');
  await page.getByPlaceholder('Enter organization name').fill(TENANT);
  await page.getByText('Continue', { exact: true }).click();
  await page.getByPlaceholder('Enter your username').fill(username);
  await page.getByPlaceholder('Enter your password').fill(password);
  await page.getByText('Sign In', { exact: true }).click();
  await page.waitForFunction(() => !location.pathname.includes('login'), null, { timeout: 45000 });
  await page.waitForTimeout(3000);
  for (const route of routes) {
    await page.goto(`http://127.0.0.1:8082${route}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(6000);
    const name = route.replace(/\W+/g, '_') || 'root';
    await page.screenshot({ path: path.join(__dirname, '..', '..', 'reports', `shot${name}.png`) });
    console.log(route, '->', new URL(page.url()).pathname, 'text length', (await page.locator('body').innerText()).trim().length);
  }
  await browser.close();
})();
