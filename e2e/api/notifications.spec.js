/**
 * API integration tests — Notifications.
 */
const { test, expect } = require('@playwright/test');
const { buildApi } = require('../helpers/api');
const { nextCluster } = require('../helpers/geo');

let api;
let dispose;

/** Returns { square, nearbySquare } for a fresh unique cluster. */
function cluster() {
  const g = nextCluster();
  const nearbySquare = g.square.map(([lat, lng]) => [lat + 0.002, lng + 0.002]);
  return { ...g, nearbySquare };
}

test.beforeAll(async ({ playwright }) => {
  ({ api, dispose } = await buildApi(playwright));
});

test.afterAll(async () => {
  await dispose();
});

test.describe('Notifications', () => {
  test('requires auth (401)', async () => {
    expect((await api.get('/api/notifications')).status()).toBe(401);
  });

  test('returns unread count and items for an authenticated user', async () => {
    const { token } = await api.registerUser('notif_new');
    const res = await api.get('/api/notifications', api.authHeaders(token));
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body).toHaveProperty('unread');
    expect(Array.isArray(body.items)).toBe(true);
  });

  test('a nearby capture by another user creates a notification', async () => {
    const g = cluster();
    const { token: t1 } = await api.registerUser('notif_a');
    expect((await api.captureRide(t1, g.square)).status()).toBe(200);

    const { token: t2 } = await api.registerUser('notif_b');
    expect((await api.captureRide(t2, g.nearbySquare)).status()).toBe(200);

    const res = await api.get('/api/notifications', api.authHeaders(t1));
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.unread).toBeGreaterThan(0);
    expect(body.items.length).toBeGreaterThan(0);
  });

  test('capturing near your own territory does NOT create a notification', async () => {
    const g = cluster();
    const { token } = await api.registerUser('notif_self');
    expect((await api.captureRide(token, g.square)).status()).toBe(200);
    expect((await api.captureRide(token, g.nearbySquare)).status()).toBe(200);

    const res = await api.get('/api/notifications', api.authHeaders(token));
    const body = await res.json();
    expect(body.unread).toBe(0);
  });

  test('POST /api/notifications/read-all marks notifications as read', async () => {
    const g = cluster();
    const { token: t1 } = await api.registerUser('notif_mark_a');
    expect((await api.captureRide(t1, g.square)).status()).toBe(200);

    const { token: t2 } = await api.registerUser('notif_mark_b');
    expect((await api.captureRide(t2, g.nearbySquare)).status()).toBe(200);

    const res = await api.post('/api/notifications/read-all', {}, api.authHeaders(t1));
    expect(res.status()).toBe(200);

    const after = await (await api.get('/api/notifications', api.authHeaders(t1))).json();
    expect(after.unread).toBe(0);
  });
});