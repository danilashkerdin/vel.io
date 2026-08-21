/**
 * UI end-to-end tests — Admin panel (/admin.html).
 */
const { test, expect } = require('@playwright/test');
const { routeApiToLocal, goto } = require('../helpers/ui');
const { buildApi } = require('../helpers/api');
const { ADMIN_EMAIL, ADMIN_PASSWORD } = require('../helpers/data');

let api;
let dispose;

test.beforeAll(async ({ playwright }) => {
  ({ api, dispose } = await buildApi(playwright));
});

test.afterAll(async () => {
  await dispose();
});

test.beforeEach(async ({ page }) => {
  await routeApiToLocal(page);
});

test.describe('Admin panel', () => {
  test('logs in as admin and reveals the admin app', async ({ page }) => {
    await goto(page, '/admin.html');
    await expect(page.locator('#adminLogin')).toBeVisible();

    await page.fill('#adminPassword', ADMIN_PASSWORD);
    await page.click('#adminLoginBtn');

    await expect(page.locator('#adminApp')).toBeVisible();
    await expect(page.locator('.admin-sidebar')).toBeVisible();
  });

  test('shows the error banner for invalid credentials', async ({ page }) => {
    await goto(page, '/admin.html');
    await page.fill('#adminPassword', 'wrong-password');
    await page.click('#adminLoginBtn');
    await expect(page.locator('#adminLoginError')).toBeVisible();
  });

  test('switches to the users tab and lists users', async ({ page }) => {
    // Ensure there is at least one user besides admin to list.
    await api.registerUser('ui_admin_user');
    await goto(page, '/admin.html');
    await page.fill('#adminPassword', ADMIN_PASSWORD);
    await page.click('#adminLoginBtn');
    await expect(page.locator('#adminApp')).toBeVisible();

    await page.click('#tabUsersBtn');
    await expect(page.locator('#sectionUsers')).toBeVisible();
    // The users list should render rows with the premium toggle.
    await expect(page.locator('#usersList .admin-toggle-premium').first()).toBeVisible();
  });

  test('switches to the payouts tab', async ({ page }) => {
    await goto(page, '/admin.html');
    await page.fill('#adminPassword', ADMIN_PASSWORD);
    await page.click('#adminLoginBtn');
    await expect(page.locator('#adminApp')).toBeVisible();

    await page.click('#tabPayoutsBtn');
    await expect(page.locator('#sectionPayouts')).toBeVisible();
    // Wait for the payouts fetch to complete so the route isn't still in flight.
    await expect(page.locator('#payoutsList')).not.toHaveText('Загрузка...');
  });

  test('auto-logs in when an admin session is already stored', async ({ page }) => {
    const admin = await api.loginAdmin();
    // Pre-seed the admin token + user (email must match admin@vel.io).
    await page.addInitScript(({ token, email }) => {
      localStorage.setItem('token', token);
      localStorage.setItem('user', JSON.stringify({ email }));
    }, { token: admin.token, email: ADMIN_EMAIL });

    await goto(page, '/admin.html');
    await expect(page.locator('#adminApp')).toBeVisible();
  });
});