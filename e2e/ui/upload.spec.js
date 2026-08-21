/**
 * UI end-to-end tests — Main app: GPX upload flow.
 */
const { test, expect } = require('@playwright/test');
const { routeApiToLocal, seedSession, goto } = require('../helpers/ui');
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

test.describe('GPX upload flow', () => {
  test('captures a territory from a GPX file upload', async ({ page }) => {
    // Register a fresh user and seed the session so the app stays logged in.
    const user = await api.registerUser('ui_upload');
    await seedSession(page, user);

    await goto(page, '/');
    // The app should render the map.
    await page.locator('#map').waitFor({ state: 'visible' });

    // Open the upload modal via the menu.
    await page.click('#burgerBtn');
    await page.click('#menuUploadBtn');
    await expect(page.locator('#uploadModal')).toHaveClass(/visible/);

    // Provide a valid closed GPX built on a unique cluster so the backend's
    // SHA-256 dedup and territory-subtraction never collide with other tests.
    const g = nextCluster();
    const pts = g.square
      .map((p) => `    <trkpt lat="${p[0].toFixed(6)}" lon="${p[1].toFixed(6)}"></trkpt>`)
      .join('\n');
    const gpx = `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Velo.io">
  <metadata><name>${Date.now().toString(36)}</name></metadata>
  <trk><name>Большой квадрат</name><trkseg>
${pts}
  </trkseg></trk>
</gpx>
`;
    await page.setInputFiles('#fileInput', {
      name: 'e2e_square.gpx',
      mimeType: 'application/gpx+xml',
      buffer: Buffer.from(gpx, 'utf-8'),
    });

    // The process button becomes enabled after a valid file.
    await expect(page.locator('#processBtn')).toBeEnabled();
    await expect(page.locator('#fileName')).toContainText('e2e_square.gpx');

    await page.click('#processBtn');
    // Success message appears after the upload resolves.
    await expect(page.locator('#uploadStatus')).toContainText('Захвачено');
  });

  test('rejects a non-GPX file selection with an error toast', async ({ page }) => {
    const user = await api.registerUser('ui_badext');
    await seedSession(page, user);
    await goto(page, '/');
    await page.locator('#map').waitFor({ state: 'visible' });

    await page.click('#burgerBtn');
    await page.click('#menuUploadBtn');

    await page.setInputFiles('#fileInput', {
      name: 'notes.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('not a gpx', 'utf-8'),
    });
    // Non-.gpx is rejected by the handler; the process button stays disabled.
    await expect(page.locator('#processBtn')).toBeDisabled();
  });

  test('requires authentication — redirects to /auth.html without a token', async ({ page }) => {
    await page.goto('/');
    await page.waitForURL(/auth\.html/);
  });
});