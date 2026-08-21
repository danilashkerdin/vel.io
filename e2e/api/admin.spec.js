/**
 * API integration tests — Admin panel: auth gating, user management,
 * sponsored-territory CRUD and payout processing.
 */
const { test, expect } = require('@playwright/test');
const { buildApi } = require('../helpers/api');
const { nextCluster } = require('../helpers/geo');
const { ADMIN_EMAIL } = require('../helpers/data');

let api;
let adminToken;
let dispose;

test.beforeAll(async ({ playwright }) => {
  ({ api, dispose } = await buildApi(playwright));
  ({ token: adminToken } = await api.loginAdmin());
});

test.afterAll(async () => {
  await dispose();
});

test.describe('Admin authorization', () => {
  test('admin endpoints reject non-admin users (403)', async () => {
    const { token } = await api.registerUser('admin_nonadmin');
    const res = await api.get('/api/admin/users', api.authHeaders(token));
    expect(res.status()).toBe(403);
    expect(JSON.stringify(await res.json())).toMatch(/администратор/i);
  });

  test('admin endpoints require auth (401)', async () => {
    expect((await api.get('/api/admin/users')).status()).toBe(401);
  });

  test('admin can list all users', async () => {
    const res = await api.get('/api/admin/users?limit=100', api.authHeaders(adminToken));
    expect(res.status()).toBe(200);
    const users = await res.json();
    expect(Array.isArray(users)).toBe(true);
    const admin = users.find((u) => u.email === ADMIN_EMAIL);
    expect(admin).toBeTruthy();
  });

  test('admin can view a user detail', async () => {
    const { user } = await api.registerUser('admin_detail');
    const res = await api.get(`/api/admin/users/${user.id}`, api.authHeaders(adminToken));
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.id).toBe(user.id);
    expect(body).toHaveProperty('territory_count');
    expect(body).toHaveProperty('total_area');
    expect(body).toHaveProperty('balance_rub');
  });

  test('admin GET tiers returns the configured star tiers', async () => {
    const res = await api.get('/api/admin/tiers', api.authHeaders(adminToken));
    expect(res.status()).toBe(200);
    const tiers = await res.json();
    expect(Array.isArray(tiers)).toBe(true);
    expect(tiers.length).toBeGreaterThanOrEqual(1);
    expect(tiers[0]).toHaveProperty('name');
    expect(tiers[0]).toHaveProperty('stars');
  });
});

test.describe('Admin user management', () => {
  test('admin can flip a user premium flag', async () => {
    const { user } = await api.registerUser('admin_prem');
    const res = await api.patch(
      `/api/admin/users/${user.id}?is_premium=true`,
      {},
      api.authHeaders(adminToken)
    );
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.ok).toBe(true);
    expect(body.is_premium).toBe(true);
  });

  test('admin can credit and debit user balance', async () => {
    const { user } = await api.registerUser('admin_bal');
    const add = await api.post(
      `/api/admin/users/${user.id}/balance`,
      { amount: 250 },
      api.authHeaders(adminToken)
    );
    expect(add.status()).toBe(200);
    expect((await add.json()).balance_rub).toBe(250);

    const sub = await api.post(
      `/api/admin/users/${user.id}/balance`,
      { amount: -100 },
      api.authHeaders(adminToken)
    );
    expect(sub.status()).toBe(200);
    expect((await sub.json()).balance_rub).toBe(150);
  });

  test('admin balance is never negative', async () => {
    const { user } = await api.registerUser('admin_balneg');
    const res = await api.post(
      `/api/admin/users/${user.id}/balance`,
      { amount: -50 },
      api.authHeaders(adminToken)
    );
    expect(res.status()).toBe(200);
    expect((await res.json()).balance_rub).toBe(0);
  });
});

test.describe('Sponsored territory CRUD (admin)', () => {
  test('admin creates a sponsored zone', async () => {
    const res = await api.createSponsoredZone(adminToken, {
      business_name: `Shop ${Date.now()}`,
    });
    expect(res.response.status()).toBe(200);
    expect(res.id).toBeTruthy();
  });

  test('admin can list zones and reads back created zone', async () => {
    const biz = `Biz ${Date.now()}`;
    const { id } = await api.createSponsoredZone(adminToken, { business_name: biz });
    const res = await api.get('/api/admin/sponsored-territories', api.authHeaders(adminToken));
    expect(res.status()).toBe(200);
    const zones = await res.json();
    const zone = zones.find((z) => z.id === id);
    expect(zone.business_name).toBe(biz);
    expect(zone.is_active).toBe(true);
  });

  test('admin can update a zone', async () => {
    const { id } = await api.createSponsoredZone(adminToken, { business_name: 'Before' });
    const res = await api.patch(
      `/api/admin/sponsored-territories/${id}`,
      { business_name: 'After', monthly_budget_rub: 9000, is_active: true },
      api.authHeaders(adminToken)
    );
    expect(res.status()).toBe(200);
    const listed = await (await api.get('/api/admin/sponsored-territories', api.authHeaders(adminToken))).json();
    const updated = listed.find((z) => z.id === id);
    expect(updated.business_name).toBe('After');
    expect(updated.monthly_budget_rub).toBe(9000);
  });

  test('admin can delete a zone', async () => {
    const { id } = await api.createSponsoredZone(adminToken, { business_name: 'Ghost' });
    const res = await api.delete(`/api/admin/sponsored-territories/${id}`, api.authHeaders(adminToken));
    expect(res.status()).toBe(200);
    const listed = await (await api.get('/api/admin/sponsored-territories', api.authHeaders(adminToken))).json();
    expect(listed.some((z) => z.id === id)).toBe(false);
  });

  test('admin cannot delete a nonexistent zone (404)', async () => {
    const res = await api.delete(
      '/api/admin/sponsored-territories/00000000-0000-0000-0000-000000000000',
      api.authHeaders(adminToken)
    );
    expect(res.status()).toBe(404);
  });
});

test.describe('Sponsored public listing & rewards', () => {
  test('an active sponsored zone is returned by the public bbox endpoint', async () => {
    const g = nextCluster();
    await api.createSponsoredZone(adminToken, {
      business_name: 'PublicZone',
      color: '#00FF00',
      polygon: g.sponsoredPolygon,
    });
    const res = await api.get(`/api/sponsored-territories?north=${g.base.lat + 1}&south=${g.base.lat - 1}&east=${g.base.lon + 1}&west=${g.base.lon - 1}`);
    expect(res.status()).toBe(200);
    const zones = await res.json();
    expect(zones.length).toBeGreaterThanOrEqual(1);
    expect(zones[0]).toHaveProperty('business_name');
    expect(zones[0]).toHaveProperty('polygon');
  });

  test('capturing over a sponsored zone returns sponsored_rewards', async () => {
    const g = nextCluster();
    await api.createSponsoredZone(adminToken, {
      business_name: 'RewardZone',
      monthly_budget_rub: 5000,
      polygon: g.sponsoredPolygon,
    });
    const { token } = await api.registerUser('spon_cap');
    const res = await api.captureRide(token, g.square);
    expect(res.status()).toBe(200);
    const body = await res.json();
    const rewards = body.sponsored_rewards || [];
    expect(rewards.length).toBeGreaterThanOrEqual(1);
    const reward = rewards.find((r) => r.business_name === 'RewardZone');
    expect(reward).toBeTruthy();
    expect(reward.your_share_monthly_rub).toBe(500); // 10% of 5000₽
  });

  test('captured sponsored zone appears in GET /api/my-sponsored', async () => {
    const g = nextCluster();
    await api.createSponsoredZone(adminToken, {
      business_name: 'OwnZone',
      polygon: g.sponsoredPolygon,
    });
    const { token } = await api.registerUser('spon_own');
    const capture = await api.captureRide(token, g.square);
    expect(capture.status()).toBe(200);
    const res = await api.get('/api/my-sponsored', api.authHeaders(token));
    expect(res.status()).toBe(200);
    const owned = await res.json();
    expect(owned.some((z) => z.business_name === 'OwnZone')).toBe(true);
  });
});

test.describe('Admin payouts', () => {
  test('pending payouts returns users with a positive balance', async () => {
    const { token, user } = await api.registerUser('payout_pending');
    await api.post(`/api/admin/users/${user.id}/balance`, { amount: 700 }, api.authHeaders(adminToken));
    await api.patch('/api/auth/profile', { ton_wallet: 'UQPAY' }, api.authHeaders(token));
    await api.post('/api/payment/request-payout', {}, api.authHeaders(token));

    const res = await api.get('/api/admin/payouts/pending', api.authHeaders(adminToken));
    expect(res.status()).toBe(200);
    const pending = await res.json();
    const entry = pending.find((p) => p.user_id === user.id);
    expect(entry).toBeTruthy();
    expect(entry.balance_rub).toBe(700);
  });

  test('admin can process a payout, zeroing the balance', async () => {
    const { token, user } = await api.registerUser('payout_process');
    await api.post(`/api/admin/users/${user.id}/balance`, { amount: 1200 }, api.authHeaders(adminToken));
    const res = await api.post(
      `/api/admin/payouts/process/${user.id}`,
      {},
      api.authHeaders(adminToken)
    );
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.success).toBe(true);
    expect(body.amount_rub).toBe(1200);

    const balance = await (await api.get('/api/balance', api.authHeaders(token))).json();
    expect(balance.balance_rub).toBe(0);
  });

  test('payout history records processed payouts', async () => {
    const { user } = await api.registerUser('payout_hist');
    await api.post(`/api/admin/users/${user.id}/balance`, { amount: 800 }, api.authHeaders(adminToken));
    await api.post(`/api/admin/payouts/process/${user.id}`, {}, api.authHeaders(adminToken));

    const res = await api.get('/api/admin/payouts/history?limit=50', api.authHeaders(adminToken));
    expect(res.status()).toBe(200);
    const history = await res.json();
    const entry = history.find((h) => h.user_id === user.id && h.status === 'completed');
    expect(entry).toBeTruthy();
    expect(entry.amount_rub).toBe(800);
  });
});