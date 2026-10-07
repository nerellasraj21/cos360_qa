const fs = require('fs');
const path = require('path');
const base = require('@playwright/test');
const { call, login, TENANT } = require('./api');
const { signInWeb, signInMobileViaForm } = require('./session');

const STATE_DIR = path.join(__dirname, '..', '.auth');

function unique(prefix) {
  return `${prefix} ${Date.now().toString(36).slice(-5)}${Math.floor(Math.random() * 90 + 10)}`;
}

async function mobileState(browser, project, role) {
  const file = path.join(STATE_DIR, `mobile-${TENANT}-${role}.json`);
  if (fs.existsSync(file) && Date.now() - fs.statSync(file).mtimeMs < 20 * 60 * 1000) {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  }
  const context = await browser.newContext({ ...project.use });
  const page = await context.newPage();
  await signInMobileViaForm(page, role);
  const state = await context.storageState();
  await context.close();
  fs.mkdirSync(STATE_DIR, { recursive: true });
  fs.writeFileSync(file, JSON.stringify(state));
  return state;
}

const test = base.test.extend({
  signIn: async ({ page, browser }, use, testInfo) => {
    const mobile = testInfo.project.name === 'mobile';
    await use(async (role) => {
      if (!mobile) return signInWeb(page, role);
      const state = await mobileState(browser, testInfo.project, role);
      const origin = (state.origins || []).find((o) => o.origin.includes(':8082')) || (state.origins || [])[0];
      const entries = origin ? origin.localStorage : [];
      await page.addInitScript((items) => {
        for (const { name, value } of items) window.localStorage.setItem(name, value);
      }, entries);
      return login(role);
    });
  },
  api: async ({}, use) => {
    const sessions = {};
    await use(async (method, apiPath, { role = 'admin', body } = {}) => {
      sessions[role] = sessions[role] || (await login(role));
      return call(method, apiPath, { token: sessions[role].access_token, body });
    });
  },
  cleanup: async ({}, use) => {
    const tasks = [];
    await use((fn) => tasks.push(fn));
    for (const fn of tasks.reverse()) {
      try {
        await fn();
      } catch (error) {
        console.warn(`cleanup failed: ${error.message}`);
      }
    }
  },
});

async function toast(page, text) {
  await base.expect(page.getByText(text, { exact: false }).first()).toBeVisible({ timeout: 15_000 });
}

module.exports = { test, expect: base.expect, unique, toast, TENANT };
