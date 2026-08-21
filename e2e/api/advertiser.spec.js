/**
 * API integration tests — Advertiser account, profile and zones.
 */
const { test, expect } = require('@playwright/test');
const { buildApi } = require('../helpers/api');

let api;
let adminToken;
let dispose;

/** Registers a brand-new advertiser user. */
async function makeAdvertiser(prefix = 'adv') {
  const email = `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}@test.dev`;
  const res = await api.register(email, 'Busy', 'secret123', {
    body: { is_advertiser: true },
  });
  expect(res.status()).toBe(200);
  const user = await res.json();
  expect(user.is_advertiser).toBe(true);
  return { token: user.token, user, email };
}

test.beforeAll(async ({ playwright }) => {
  ({ api, dispose } = await buildApi(playwright));
  ({ token: adminToken } = await api.loginAdmin());
});

test.afterAll(async () => {
  await dispose();
});

test.describe('Advertiser access control', () => {
  test('advertiser endpoints require the advertiser role (403 for cyclist)', async () => {
    const { token } = await api.registerUser('adv_cyclist');
    const res = await api.get('/api/advertiser/profile', api.authHeaders(token));
    expect(res.status()).toBe(403);
  });

  test('GET /api/advertiser/tiers is public', async () => {
    const res = await api.get('/api/advertiser/tiers');
    expect(res.status()).toBe(200);
    const tiers = await res.json();
    expect(Array.isArray(tiers)).toBe(true);
  });
});

test.describe('Advertiser profile', () => {
  test('advertiser can read and update their business profile', async () => {
    const { token } = await makeAdvertiser();
    const initial = await api.get('/api/advertiser/profile', api.authHeaders(token));
    expect(initial.status()).toBe(200);

    const res = await api.put(
      '/api/advertiser/profile',
      {
        business_name: 'Пекарня Велё',
        contact_phone: '+79990001122',
        contact_telegram: '@velo_bakery',
        website: 'https://example.com',
        description: 'Свежая выпечка у метро',
      },
      api.authHeaders(token)
    );
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.business_name).toBe('Пекарня Велё');
    expect(body.website).toBe('https://example.com');
  });

  test('advertiser dashboard returns zone/payment stats', async () => {
    const { token } = await makeAdvertiser();
    const res = await api.get('/api/advertiser/dashboard', api.authHeaders(token));
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body).toHaveProperty('active_zones');
    expect(body).toHaveProperty('total_zones');
    expect(body).toHaveProperty('total_spent_stars');
    expect(Array.isArray(body.recent_payments)).toBe(true);
  });

  test('advertiser payments list is accessible', async () => {
    const { token } = await makeAdvertiser();
    const res = await api.get('/api/advertiser/payments', api.authHeaders(token));
    expect(res.status()).toBe(200);
    expect(Array.isArray(await res.json())).toBe(true);
  });

  test('my-advertiser-zones is empty for a fresh advertiser', async () => {
    const { token } = await makeAdvertiser();
    const res = await api.get('/api/my-advertiser-zones', api.authHeaders(token));
    expect(res.status()).toBe(200);
    expect(await res.json()).toEqual([]);
  });
});

test.describe('Advertiser zone editing rules', () => {
  test('a non-owner advertiser cannot edit a zone (403)', async () => {
    const { token } = await makeAdvertiser();
    const zone = await api.createSponsoredZone(adminToken, { business_name: 'Чужое' });
    const res = await api.patch(
      `/api/my-advertiser-zones/${zone.id}`,
      { business_name: 'Hack' },
      api.authHeaders(token)
    );
    expect(res.status()).toBe(403);
  });

  test('editing a nonexistent zone returns 404', async () => {
    const { token } = await makeAdvertiser();
    const res = await api.patch(
      '/api/my-advertiser-zones/00000000-0000-0000-0000-000000000000',
      { color: '#112233' },
      api.authHeaders(token)
    );
    expect(res.status()).toBe(404);
  });
});