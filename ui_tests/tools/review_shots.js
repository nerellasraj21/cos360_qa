const fs = require('fs');
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '..', '..', '.env') });
const { chromium, devices } = require('@playwright/test');
const { credentials, TENANT } = require('../helpers/api');
const { signInWeb } = require('../helpers/session');

const OUT = path.join(__dirname, '..', '..', 'reports', 'design');
fs.mkdirSync(OUT, { recursive: true });

const WEB = ['/dashboard', '/students', '/students/admission', '/fee/collection', '/exam/exams', '/masters/classesandsections', '/communication', '/settings/school'];
const MOBILE = ['/', '/students', '/fees', '/exam', '/profile', '/calendar'];

(async () => {
  const browser = await chromium.launch();

  const loginCtx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const loginPage = await loginCtx.newPage();
  await loginPage.goto('http://127.0.0.1:5174/login');
  await loginPage.waitForTimeout(3000);
  await loginPage.screenshot({ path: path.join(OUT, 'web_login.png') });
  await loginCtx.close();

  const webCtx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const web = await webCtx.newPage();
  await signInWeb(web, 'admin');
  for (const route of WEB) {
    await web.goto(`http://127.0.0.1:5174${route}`, { waitUntil: 'domcontentloaded' });
    await web.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    await web.waitForTimeout(2000);
    await web.screenshot({ path: path.join(OUT, `web${route.replace(/\W+/g, '_')}.png`) });
    console.log('web', route);
  }
  await webCtx.close();

  const mCtx = await browser.newContext({ ...devices['Pixel 5'], viewport: { width: 390, height: 844 } });
  const m = await mCtx.newPage();
  await m.goto('http://127.0.0.1:8082/login');
  await m.waitForTimeout(4000);
  await m.screenshot({ path: path.join(OUT, 'mobile_login_org.png') });
  const { username, password } = credentials('admin');
  await m.getByPlaceholder('Enter organization name').fill(TENANT);
  await m.getByText('Continue', { exact: true }).click();
  await m.waitForTimeout(1500);
  await m.screenshot({ path: path.join(OUT, 'mobile_login_credentials.png') });
  await m.getByPlaceholder('Enter your username').fill(username);
  await m.getByPlaceholder('Enter your password').fill(password);
  await m.getByText('Sign In', { exact: true }).click();
  await m.waitForFunction(() => !location.pathname.includes('login'), null, { timeout: 60000 });
  await m.waitForTimeout(4000);
  for (const route of MOBILE) {
    await m.goto(`http://127.0.0.1:8082${route}`, { waitUntil: 'domcontentloaded' });
    await m.waitForTimeout(5000);
    await m.screenshot({ path: path.join(OUT, `mobile${route.replace(/\W+/g, '_') || '_home'}.png`) });
    console.log('mobile', route);
  }
  await browser.close();
})();
