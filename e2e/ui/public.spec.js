/**
 * UI end-to-end tests — Public territory share page (/public.html).
 */
const { test, expect } = require('@playwright/test');
const { routeApiToLocal, goto } = require('../helpers/ui');
const { buildApi } = require('../helpers/api');
const { nextCluster } = require('../helpers/geo');

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

test.describe('Public territory page', () => {
  test('renders a shared territory from ?t=<id>', async ({ page }) => {
    const { token, username } = await api.registerUser('ui_public');
    const id = await api.captureRideId(token, nextCluster().square);

    await goto(page, `/public.html?t=${id}`);
    await expect(page.locator('#tName')).not.toHaveText('Территория не найдена');
    await expect(page.locator('#map')).toBeVisible();
    // The user name is shown near the territory.
    await expect(page.locator('#tUser')).toContainText(username);
  });

  test('shows "not found" when no territory id is given', async ({ page }) => {
    await goto(page, '/public.html');
    await expect(page.locator('#tName')).toHaveText('Территория не найдена');
  });
});