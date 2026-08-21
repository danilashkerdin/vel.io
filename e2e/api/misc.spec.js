/**
 * API integration tests — Health, sharing / social (referral, OG, Telegram).
 */
const { test, expect } = require('@playwright/test');
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

test.describe('Health', () => {
  test('GET /api/health returns ok with DB connectivity', async () => {
    const res = await api.get('/api/health');
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.status).toBe('ok');
    expect(body.service).toBe('velo_io');
  });
});

test.describe('Referral sharing', () => {
  test('GET /api/referral/link returns share links for an authed user', async () => {
    const { token, user } = await api.registerUser('ref_link');
    const res = await api.get('/api/referral/link', api.authHeaders(token));
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.link).toContain(user.id);
  });
});

test.describe('OG / share pages', () => {
  test('GET /og/{id} returns a shareable HTML page for a real territory', async () => {
    const { token } = await api.registerUser('og_page');
    const id = await api.captureRideId(token, nextCluster().square);
    const res = await api.get(`/og/${id}`);
    expect(res.status()).toBe(200);
    const html = await res.text();
    expect(html).toContain('og:title');
    expect(html).toContain('public.html?t=');
  });

  test('GET /og/{id} returns 404 for an unknown territory', async () => {
    const res = await api.get('/og/00000000-0000-0000-0000-000000000000');
    expect(res.status()).toBe(404);
  });

  test('GET /api/og/territory/{id}.png returns a PNG image', async () => {
    const { token } = await api.registerUser('og_img');
    const id = await api.captureRideId(token, nextCluster().square);
    const res = await api.get(`/api/og/territory/${id}.png`);
    expect(res.status()).toBe(200);
    expect(res.headers()['content-type']).toContain('image/png');
    const buffer = await res.body();
    expect(buffer.length).toBeGreaterThan(0);
  });
});

test.describe('Telegram webhook', () => {
  test('webhook requires a configured bot (503 in test env)', async () => {
    const res = await api.post('/api/telegram/webhook', { update_id: 1 });
    // In the default env (no TELEGRAM_BOT_TOKEN) the backend refuses with 503.
    expect([400, 401, 403, 503]).toContain(res.status());
  });
});