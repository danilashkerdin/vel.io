/**
 * API integration tests — Payments: balance, transactions, payouts, premium
 * status and Star-invoice validation.
 */
const { test, expect } = require('@playwright/test');
const { buildApi } = require('../helpers/api');

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

test.describe('Balance & transactions', () => {
  test('GET /api/balance returns zeroed balance for a new user', async () => {
    const { token } = await api.registerUser('bal_new');
    const res = await api.get('/api/balance', api.authHeaders(token));
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.balance_rub).toBe(0);
    expect(body.total_earned_rub).toBe(0);
    expect(Array.isArray(body.sponsored_territories)).toBe(true);
  });

  test('GET /api/transactions requires auth', async () => {
    expect((await api.get('/api/transactions')).status()).toBe(401);
  });

  test('GET /api/transactions returns a list for a user', async () => {
    const { token } = await api.registerUser('txn_list');
    const res = await api.get('/api/transactions', api.authHeaders(token));
    expect(res.status()).toBe(200);
    expect(Array.isArray(await res.json())).toBe(true);
  });

  test('admin can credit a user balance and it appears in /api/balance', async () => {
    const { token, user } = await api.registerUser('bal_credit');
    const res = await api.post(
      `/api/admin/users/${user.id}/balance`,
      { amount: 1000 },
      api.authHeaders(adminToken)
    );
    expect(res.status()).toBe(200);

    const balance = await (await api.get('/api/balance', api.authHeaders(token))).json();
    expect(balance.balance_rub).toBe(1000);
  });
});

test.describe('Payment status', () => {
  test('GET /api/payment/status returns premium & free-limit fields', async () => {
    const { token } = await api.registerUser('pay_status');
    const res = await api.get('/api/payment/status', api.authHeaders(token));
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body).toHaveProperty('is_premium');
    expect(body).toHaveProperty('captures_count');
    expect(body).toHaveProperty('free_limit');
    expect(body).toHaveProperty('captures_remaining');
  });
});

test.describe('Star invoice', () => {
  test('requires auth (401)', async () => {
    const res = await api.get('/api/payment/create-star-invoice?purpose=premium');
    expect(res.status()).toBe(401);
  });

  test('rejects an invalid purpose (400)', async () => {
    const { token } = await api.registerUser('star_bad');
    const res = await api.post(
      '/api/payment/create-star-invoice?purpose=bogus',
      {},
      api.authHeaders(token)
    );
    expect(res.status()).toBe(400);
  });

  test('premium invoice is not created when Telegram is not configured (503)', async () => {
    const { token } = await api.registerUser('star_prem');
    const res = await api.post(
      '/api/payment/create-star-invoice?purpose=premium',
      {},
      api.authHeaders(token)
    );
    // In the default test env (no TELEGRAM_BOT_TOKEN) the backend returns 503.
    expect([400, 503]).toContain(res.status());
  });

  test('sponsored invoice is forbidden for non-advertisers (403)', async () => {
    const { token } = await api.registerUser('star_cyc');
    const res = await api.post(
      '/api/payment/create-star-invoice?purpose=sponsored&business_name=X&monthly_budget_stars=1000',
      {},
      api.authHeaders(token)
    );
    expect(res.status()).toBe(403);
  });
});

test.describe('Payout flow', () => {
  test('request-payout requires ≥ 500₽ balance (400)', async () => {
    const { token } = await api.registerUser('payo_low');
    const res = await api.post('/api/payment/request-payout', {}, api.authHeaders(token));
    expect(res.status()).toBe(400);
    const body = await res.json();
    expect(JSON.stringify(body)).toContain('500');
  });

  test('request-payout requires a TON wallet (400)', async () => {
    const { token, user } = await api.registerUser('payo_nowal');
    await api.post(`/api/admin/users/${user.id}/balance`, { amount: 1000 }, api.authHeaders(adminToken));
    const res = await api.post('/api/payment/request-payout', {}, api.authHeaders(token));
    expect(res.status()).toBe(400);
    expect(JSON.stringify(await res.json())).toMatch(/кошел|wallet/i);
  });

  test('full payout flow: balance → wallet → request → pending transaction', async () => {
    // Register a user and set a wallet + balance.
    const { token, user } = await api.registerUser('payo_full');
    await api.patch('/api/auth/profile', { ton_wallet: 'UQABC123XYZ' }, api.authHeaders(token));
    await api.post(`/api/admin/users/${user.id}/balance`, { amount: 1500 }, api.authHeaders(adminToken));

    const res = await api.post('/api/payment/request-payout', {}, api.authHeaders(token));
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.success).toBe(true);
    expect(body.amount_rub).toBe(1500);
    expect(body.status).toBe('pending');

    // A pending transaction should now appear in history.
    const txns = await (await api.get('/api/transactions', api.authHeaders(token))).json();
    const payout = txns.find((t) => t.type === 'payout' && t.status === 'pending');
    expect(payout).toBeTruthy();
    expect(payout.amount_rub).toBeLessThan(0);
  });

  test('only one pending payout at a time (400)', async () => {
    const { token, user } = await api.registerUser('payo_dup');
    await api.patch('/api/auth/profile', { ton_wallet: 'UQZZZ' }, api.authHeaders(token));
    await api.post(`/api/admin/users/${user.id}/balance`, { amount: 2000 }, api.authHeaders(adminToken));

    expect((await api.post('/api/payment/request-payout', {}, api.authHeaders(token))).status()).toBe(200);
    const second = await api.post('/api/payment/request-payout', {}, api.authHeaders(token));
    expect(second.status()).toBe(400);
  });
});