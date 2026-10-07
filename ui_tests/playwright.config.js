const path = require('path');
const { defineConfig, devices } = require('@playwright/test');
require('dotenv').config({ path: path.join(__dirname, '.env') });
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });
const APP_ROOT = path.resolve(path.join(__dirname, '..'), process.env.COS360_APP || '../COS360_Full_App');

const API_URL = process.env.QA_API_URL || 'http://127.0.0.1:8100/api/v1';
const TENANT = process.env.UI_TENANT || 'qa_manual';
const WEB_URL = process.env.WEB_URL || 'http://localhost:5174';
const MOBILE_URL = process.env.MOBILE_URL || 'http://localhost:8082';

if (!/^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?\//.test(API_URL + '/')) {
  throw new Error(`E2E refuses to run against a non-local API: ${API_URL}`);
}
if (!TENANT.startsWith('qa_')) {
  throw new Error(`E2E only runs against qa_ tenants, got ${TENANT}`);
}

const wantsWeb = !process.argv.includes('--project=mobile');
const wantsMobile = !process.argv.includes('--project=web');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  workers: process.env.CI ? 2 : 3,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }], ['json', { outputFile: path.join(__dirname, '..', 'reports', 'ui-results.json') }]],
  use: {
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'web',
      testMatch: /.*\.web\.spec\.js/,
      use: { baseURL: WEB_URL, viewport: { width: 1280, height: 800 } },
    },
    {
      name: 'mobile',
      testMatch: /.*\.mobile\.spec\.js/,
      use: {
        baseURL: MOBILE_URL,
        ...devices['Pixel 5'],
        viewport: { width: 390, height: 844 },
      },
    },
  ],
  webServer: [
    // filtered below
    {
      command: 'python scripts/qa/run_test_api.py',
      cwd: path.join(APP_ROOT, 'backend'),
      url: `${API_URL.replace(/\/api\/v1$/, '')}/health`,
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5174 --strictPort',
      cwd: path.join(APP_ROOT, 'web'),
      url: WEB_URL,
      reuseExistingServer: true,
      timeout: 300_000,
      env: { VITE_API_BASE_URL: API_URL, VITE_DEFAULT_TENANT: TENANT },
    },
    {
      command: 'npx expo start --web --port 8082',
      cwd: path.join(APP_ROOT, 'mobile'),
      url: MOBILE_URL,
      reuseExistingServer: true,
      timeout: 240_000,
      env: { EXPO_PUBLIC_API_URL: API_URL, CI: '1' },
    },
  ].filter((server) => (server.cwd.endsWith('web') ? wantsWeb : server.cwd.endsWith('mobile') ? wantsMobile : true)),
});
