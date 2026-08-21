/**
 * API integration tests — Authentication & account management.
 * Covers /api/auth/register, /login, /me, /profile and referral bonuses.
 */
const { test, expect } = require('@playwright/test');
const { buildApi } = require('../helpers/api');
const { uniqueEmail } = require('../helpers/data');

let api;
let dispose;

test.beforeAll(async ({ playwright }) => {
  ({ api, dispose } = await buildApi(playwright));
});

test.afterAll(async () => {
  await dispose();
});

test.describe('Auth endpoints', () => {
  test('POST /api/auth/register creates a user and returns a JWT', async () => {
    const email = uniqueEmail('reg');
    const res = await api.register(email, 'Rider', 'secret123');
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.email).toBe(email);
    expect(body.username).toBe('Rider');
    expect(body.token).toBeTruthy();
    expect(body.id).toBeTruthy();
    expect(body).toHaveProperty('captures_count');
    expect(body).toHaveProperty('is_premium');
  });

  test('register rejects a duplicate email', async () => {
    const email = uniqueEmail('dup');
    await api.register(email, 'A', 'secret123');
    const res = await api.register(email, 'B', 'secret123');
    expect(res.status()).toBe(400);
    const body = await res.json();
    expect(JSON.stringify(body)).toContain('Email');
  });

  test('register rejects a too-short password (422)', async () => {
    const res = await api.register(uniqueEmail('short'), 'Rider', '12');
    expect(res.status()).toBe(422);
  });

  test('register rejects an invalid email shape (422)', async () => {
    const res = await api.register('not-an-email', 'Rider', 'secret123');
    expect(res.status()).toBe(422);
  });

  test('POST /api/auth/login returns a token for valid credentials', async () => {
    const email = uniqueEmail('login');
    await api.register(email, 'Rider', 'secret123');
    const res = await api.login(email, 'secret123');
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.token).toBeTruthy();
    expect(body.email).toBe(email);
  });

  test('login rejects a wrong password (401)', async () => {
    const email = uniqueEmail('wrongpw');
    await api.register(email, 'Rider', 'secret123');
    const res = await api.login(email, 'not-the-password');
    expect(res.status()).toBe(401);
  });

  test('login rejects an unknown email (401)', async () => {
    const res = await api.login(uniqueEmail('unknown'), 'secret123');
    expect(res.status()).toBe(401);
  });

  test('GET /api/auth/me requires auth (401 without token)', async () => {
    const res = await api.get('/api/auth/me');
    expect(res.status()).toBe(401);
  });

  test('GET /api/auth/me returns the current user', async () => {
    const { token, user } = await api.registerUser('me');
    const res = await api.get('/api/auth/me', api.authHeaders(token));
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.id).toBe(user.id);
    expect(body.email).toBe(user.email);
    expect(body.token).toBeUndefined();
  });

  test('PUT /api/auth/profile updates username and ton_wallet', async () => {
    const { token } = await api.registerUser('profile');
    const res = await api.patch('/api/auth/profile', {
      username: 'RenamedRider',
      ton_wallet: 'UQAbc123Def',
    }, api.authHeaders(token));
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.username).toBe('RenamedRider');
    expect(body.ton_wallet).toBe('UQAbc123Def');
  });

  test('invalid JWT token is rejected (401)', async () => {
    const res = await api.get('/api/auth/me', {
      headers: { Authorization: 'Bearer not-a-real-token' },
    });
    expect(res.status()).toBe(401);
  });
});

test.describe('Referral flow', () => {
  test('registering with X-Referral-ID grants the referrer a bonus', async () => {
    const { token, user } = await api.registerUser('referrer');
    const referrerId = user.id;

    const referredEmail = uniqueEmail('referee');
    const res = await api.post('/api/auth/register', {
      email: referredEmail,
      username: 'Referee',
      password: 'secret123',
    }, {
      headers: { 'X-Referral-ID': referrerId },
    });
    expect(res.status()).toBe(200);

    const me = await api.get('/api/auth/me', api.authHeaders(token));
    const myBody = await me.json();
    expect(myBody.referral_bonuses).toBe(1);
  });

  test('GET /api/referral/bonuses reflects referral count', async () => {
    const { token } = await api.registerUser('refstats');
    const res = await api.get('/api/referral/bonuses', api.authHeaders(token));
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body).toHaveProperty('referrals_count');
    expect(body).toHaveProperty('bonus_captures');
  });
});