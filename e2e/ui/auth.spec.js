/**
 * UI end-to-end tests — Authentication page (/auth.html).
 */
const { test, expect } = require('@playwright/test');
const { routeApiToLocal, goto } = require('../helpers/ui');
const { uniqueEmail } = require('../helpers/data');

test.beforeEach(async ({ page }) => {
  await routeApiToLocal(page);
});

test.describe('Auth page', () => {
  test('switches between login and register modes', async ({ page }) => {
    await goto(page, '/auth.html');
    const submit = page.locator('#submitBtn');
    await expect(submit).toHaveText('Войти');
    await page.click('#toggleBtn');
    await expect(submit).toHaveText('Зарегистрироваться');
    await page.click('#toggleBtn');
    await expect(submit).toHaveText('Войти');
  });

  test('registers a new cyclist and redirects to the app', async ({ page }) => {
    const email = uniqueEmail('ui_cyclist');
    await goto(page, '/auth.html');
    await page.click('#toggleBtn'); // register mode
    await page.fill('#username', 'UIDemoRider');
    await page.fill('#email', email);
    await page.fill('#password', 'secret123');
    await page.click('#submitBtn');
    await page.waitForURL('**/'); // redirected to the map
    await expect(page).toHaveURL(/(\/$|\/\?)/);
  });

  test('registers an advertiser (role tab) and redirects to the app', async ({ page }) => {
    const email = uniqueEmail('ui_adv');
    await goto(page, '/auth.html');
    await page.click('#toggleBtn');
    await page.click('.role-tab[data-role="advertiser"]');
    await page.fill('#email', email);
    await page.fill('#password', 'secret123');
    await page.click('#submitBtn');
    await page.waitForURL('**/');
  });

  test('logs in an existing user', async ({ page, request }) => {
    const email = uniqueEmail('ui_login');
    // Create via API first (per-test request fixture).
    const { Api } = require('../helpers/api');
    const api = new Api(request);
    await api.register(email, 'LoginUser', 'secret123');

    await goto(page, '/auth.html');
    await page.fill('#email', email);
    await page.fill('#password', 'secret123');
    await page.click('#submitBtn');
    await page.waitForURL('**/');
  });

  test('shows an error when logging in with a wrong password', async ({ page, request }) => {
    const email = uniqueEmail('ui_wrongpw');
    const { Api } = require('../helpers/api');
    const api = new Api(request);
    await api.register(email, 'WrongPw', 'secret123');

    await goto(page, '/auth.html');
    await page.fill('#email', email);
    await page.fill('#password', 'not-the-password');
    await page.click('#submitBtn');
    await expect(page.locator('#error')).toBeVisible();
  });

  test('validates empty required fields', async ({ page }) => {
    await goto(page, '/auth.html');
    await page.click('#toggleBtn'); // register mode (requires username + email + password)
    await page.click('#submitBtn');
    await expect(page.locator('#error')).toBeVisible();
    await expect(page.locator('#error')).toHaveText('Заполните все поля');
  });
});