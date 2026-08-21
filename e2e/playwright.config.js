// @ts-check
const { defineConfig, devices } = require('@playwright/test');

/**
 * Playwright e2e/integration test configuration for Velo.io.
 *
 * Two projects run against a live (docker-compose) stack:
 *   - api : FastAPI REST integration tests via Playwright's request context.
 *   - ui  : browser (Chromium) end-to-end tests against the static frontend.
 *
 * Environment:
 *   API_BASE_URL (default http://localhost:8000) — backend FastAPI
 *   UI_BASE_URL  (default http://localhost:3000) — frontend nginx
 *   E2E_RESET_DB (default true) — reset the database before the suite
 */
module.exports = defineConfig({
  testDir: './',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : 1,
  reporter: [
    ['list'],
    ['html', { open: 'never' }],
  ],
  timeout: 60_000,
  expect: { timeout: 10_000 },

  use: {
    baseURL: process.env.UI_BASE_URL || 'http://localhost:3000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    { name: 'api', testMatch: 'api/**/*.spec.js', fullyParallel: false },
    {
      name: 'ui',
      testMatch: 'ui/**/*.spec.js',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  globalSetup: require.resolve('./global-setup.js'),
});