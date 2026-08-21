/**
 * API integration tests — Territories: capture, overlap/subtraction, GPX
 * upload, queries, CRUD, leaderboard, activity, achievements.
 */
const { test, expect } = require('@playwright/test');
const { buildApi } = require('../helpers/api');
const { nextCluster } = require('../helpers/geo');
const { OPEN_ROUTE, BIG_SQUARE_GPX, OPEN_ROUTE_GPX, WAYPOINTS_ONLY_GPX } = require('../helpers/data');

let api;
let adminToken;
let dispose;

function buf(text) {
  return Buffer.from(text, 'utf8');
}

test.beforeAll(async ({ playwright }) => {
  ({ api, dispose } = await buildApi(playwright));
  ({ token: adminToken } = await api.loginAdmin());
});

test.afterAll(async () => {
  await dispose();
});

/** Register a user and (optionally) demote from free-slot premium to free tier. */
async function freeUser(prefix = 'free') {
  const u = await api.registerUser(prefix);
  await api.patch(`/api/admin/users/${u.user.id}?is_premium=false`, {}, api.authHeaders(adminToken));
  return u;
}

test.describe('Capture ride', () => {
  test('captures a new territory from a closed loop', async () => {
    const { token } = await api.registerUser('cap_ok');
    const res = await api.captureRide(token, nextCluster().square);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.area).toBeGreaterThan(0);
    expect(body.id).toBeTruthy();
    expect(body.name).toBe('Поездка');
    expect(body).toHaveProperty('polygon');
    expect(body).toHaveProperty('created_at');
    expect(body).toHaveProperty('expires_at');
  });

  test('rejects too few points (400)', async () => {
    const { token } = await api.registerUser('cap_few');
    const res = await api.captureRide(token, [nextCluster().base]);
    expect(res.status()).toBe(400);
  });

  test('rejects an open (non-closed) path (400)', async () => {
    const { token } = await api.registerUser('cap_open');
    const res = await api.captureRide(token, OPEN_ROUTE);
    expect(res.status()).toBe(400);
    const body = await res.json();
    expect(JSON.stringify(body).toLowerCase()).toContain('замкнут');
  });

  test('requires authentication (401)', async () => {
    const res = await api.post('/api/capture-ride', { points: nextCluster().square, name: 'x' }, {});
    expect(res.status()).toBe(401);
  });

  test('increments the user captures_count', async () => {
    const { token, user } = await api.registerUser('cap_count');
    await api.captureRide(token, nextCluster().square);
    const me = await (await api.get('/api/auth/me', api.authHeaders(token))).json();
    expect(me.captures_count).toBe(user.captures_count + 1);
  });
});

test.describe('Free tier limit', () => {
  test('free user is limited to 1 capture per week (402 on 2nd)', async () => {
    const { token } = await freeUser('limit_free');
    const r1 = await api.captureRide(token, nextCluster().square);
    expect(r1.status()).toBe(200);
    const r2 = await api.captureRide(token, nextCluster().square);
    expect(r2.status()).toBe(402);
  });

  test('premium user bypasses the weekly limit', async () => {
    const { token, user } = await api.registerUser('cap_premium');
    await api.patch(`/api/admin/users/${user.id}?is_premium=true`, {}, api.authHeaders(adminToken));
    const r1 = await api.captureRide(token, nextCluster().square);
    expect(r1.status()).toBe(200);
    const r2 = await api.captureRide(token, nextCluster().square);
    expect(r2.status()).toBe(200);
  });
});

test.describe('Overlap & subtraction', () => {
  test('fully overlapping territory is rejected ("занята")', async () => {
    const { token: t1 } = await freeUser('ovl_a');
    const { token: t2 } = await freeUser('ovl_b');
    const g = nextCluster();
    expect((await api.captureRide(t1, g.square)).status()).toBe(200);
    const r2 = await api.captureRide(t2, g.inside);
    expect(r2.status()).toBe(400);
    const body = await r2.json();
    expect(JSON.stringify(body).toLowerCase()).toContain('занята');
  });

  test('partial overlap subtracts the occupied portion', async () => {
    const { token: t1 } = await freeUser('ovl_c');
    const { token: t2 } = await freeUser('ovl_d');
    const g = nextCluster();
    const r1 = await api.captureRide(t1, g.square);
    expect(r1.status()).toBe(200);
    const fullSquareArea = (await r1.json()).area;

    const r2 = await api.captureRide(t2, g.halfInside);
    expect(r2.status()).toBe(200);
    const d2 = await r2.json();
    expect(d2.area).toBeLessThan(fullSquareArea);
  });

  test('non-overlapping capture gets the full area', async () => {
    const { token: t1 } = await freeUser('ovl_e');
    const { token: t2 } = await freeUser('ovl_f');
    const g1 = nextCluster();
    const g2 = nextCluster();
    expect((await api.captureRide(t1, g1.square)).status()).toBe(200);
    const r2 = await api.captureRide(t2, g2.square);
    expect(r2.status()).toBe(200);
    const d2 = await r2.json();
    expect(d2.area).toBeGreaterThan(500000);
  });

  test('a user cannot subtract from their own territory', async () => {
    const { token } = await freeUser('iso_self');
    const g = nextCluster();
    const r1 = await api.captureRide(token, g.square);
    expect(r1.status()).toBe(200);
    const r2 = await api.captureRide(token, g.inside);
    expect(r2.status()).toBe(200);
  });
});

test.describe('GPX upload', () => {
  test('uploads a valid closed GPX and creates a territory', async () => {
    const { token } = await api.registerUser('gpx_ok');
    const g = nextCluster();
    const gpx = gpxWithCoords(g.square, 'upload_ok');
    const res = await api.uploadGpx(token, {
      name: 'big_square.gpx',
      mimeType: 'application/gpx+xml',
      buffer: buf(gpx),
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.area).toBeGreaterThan(0);
    expect(body.id).toBeTruthy();
  });

  test('rejects a non-.gpx extension (400)', async () => {
    const { token } = await api.registerUser('gpx_ext');
    const res = await api.uploadGpx(token, {
      name: 'track.txt',
      mimeType: 'text/plain',
      buffer: buf(BIG_SQUARE_GPX),
    });
    expect(res.status()).toBe(400);
  });

  test('rejects an open (unclosed) GPX (400)', async () => {
    const { token } = await api.registerUser('gpx_open');
    const res = await api.uploadGpx(token, {
      name: 'open.gpx',
      mimeType: 'application/gpx+xml',
      buffer: buf(OPEN_ROUTE_GPX),
    });
    expect(res.status()).toBe(400);
  });

  test('rejects a GPX with only waypoints (400)', async () => {
    const { token } = await api.registerUser('gpx_wpt');
    const res = await api.uploadGpx(token, {
      name: 'points.gpx',
      mimeType: 'application/gpx+xml',
      buffer: buf(WAYPOINTS_ONLY_GPX),
    });
    expect(res.status()).toBe(400);
  });

  test('rejects re-using a GPX already captured by another user (400)', async () => {
    const { token: t1 } = await api.registerUser('gpx_reuse1');
    const { token: t2 } = await api.registerUser('gpx_reuse2');
    const g = nextCluster();
    const gpx = gpxWithCoords(g.square, 'reuse');
    const file = { name: 'same.gpx', mimeType: 'application/gpx+xml', buffer: buf(gpx) };
    expect((await api.uploadGpx(t1, file)).status()).toBe(200);
    const r2 = await api.uploadGpx(t2, file);
    expect(r2.status()).toBe(400);
    const body = await r2.json();
    expect(JSON.stringify(body).toLowerCase()).toContain('уже использован');
  });

  test('requires authentication (401)', async () => {
    const res = await api.post('/api/upload-gpx', {}, { multipart: { file: null } });
    expect(res.status()).toBe(401);
  });
});

test.describe('Territory queries', () => {
  test('GET /api/territories returns territories in the bbox', async () => {
    const { token } = await api.registerUser('q_bbox');
    const g = nextCluster();
    expect((await api.captureRide(token, g.square)).status()).toBe(200);
    const res = await api.get(`/api/territories?${new URLSearchParams({
      north: g.base.lat + 1, south: g.base.lat - 1, east: g.base.lon + 1, west: g.base.lon - 1,
    })}`);
    expect(res.status()).toBe(200);
    const items = await res.json();
    expect(Array.isArray(items)).toBe(true);
    expect(items.length).toBeGreaterThanOrEqual(1);
  });

  test('GET /api/territories returns [] for an empty area', async () => {
    const res = await api.get('/api/territories?north=50&south=49&east=31&west=30');
    expect(res.status()).toBe(200);
    expect(await res.json()).toEqual([]);
  });

  test('GET /api/territories/public/{id} returns territory detail', async () => {
    const { token, username } = await api.registerUser('q_public');
    const id = await api.captureRideId(token, nextCluster().square);
    const res = await api.get(`/api/territories/public/${id}`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.id).toBe(id);
    expect(body.username).toBe(username);
    expect(body).toHaveProperty('polygon');
  });

  test('GET /api/territories/public/{id} returns 404 for unknown', async () => {
    const res = await api.get('/api/territories/public/00000000-0000-0000-0000-000000000000');
    expect(res.status()).toBe(404);
  });

  test('GET /api/my-territories lists the current user territories', async () => {
    const { token } = await api.registerUser('q_mine');
    const id = await api.captureRideId(token, nextCluster().square);
    const res = await api.get('/api/my-territories', api.authHeaders(token));
    expect(res.status()).toBe(200);
    const items = await res.json();
    expect(items.some((t) => t.id === id)).toBe(true);
  });

  test('GET /api/initial-view returns the default Moscow center with no captures', async () => {
    const { token } = await api.registerUser('q_view');
    const res = await api.get('/api/initial-view', api.authHeaders(token));
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.lat).toBe(55.751244);
    expect(body.lon).toBe(37.618423);
  });

  test('GET /api/users/{id}/territories lists a user captures', async () => {
    const { token, user } = await api.registerUser('q_user_terr');
    const id = await api.captureRideId(token, nextCluster().square);
    const res = await api.get(`/api/users/${user.id}/territories`);
    expect(res.status()).toBe(200);
    const items = await res.json();
    expect(items.some((t) => t.id === id)).toBe(true);
  });
});

test.describe('Territory CRUD', () => {
  test('PATCH /api/territories/{id} updates editable fields', async () => {
    const { token } = await api.registerUser('crud_upd');
    const id = await api.captureRideId(token, nextCluster().square);
    const res = await api.patch(`/api/territories/${id}`, {
      name: 'Обновлённое имя',
      color: '#FF00FF',
      description: 'Описание',
      link_url: 'https://example.com',
    }, api.authHeaders(token));
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.name).toBe('Обновлённое имя');
    expect(body.color).toBe('#FF00FF');
  });

  test('PATCH rejects an invalid colour (422)', async () => {
    const { token } = await api.registerUser('crud_brcolor');
    const id = await api.captureRideId(token, nextCluster().square);
    const res = await api.patch(`/api/territories/${id}`, { color: 'red' }, api.authHeaders(token));
    expect(res.status()).toBe(422);
  });

  test('PATCH forbids editing another user territory (403)', async () => {
    const { token: owner } = await api.registerUser('crud_owner');
    const { token: other } = await api.registerUser('crud_other');
    const id = await api.captureRideId(owner, nextCluster().square);
    const res = await api.patch(`/api/territories/${id}`, { name: 'hax' }, api.authHeaders(other));
    expect(res.status()).toBe(403);
  });

  test('DELETE /api/territories/{id} removes the territory', async () => {
    const { token } = await api.registerUser('crud_del');
    const id = await api.captureRideId(token, nextCluster().square);
    const res = await api.delete(`/api/territories/${id}`, api.authHeaders(token));
    expect(res.status()).toBe(200);
    const mine = await (await api.get('/api/my-territories', api.authHeaders(token))).json();
    expect(mine.some((t) => t.id === id)).toBe(false);
  });

  test('DELETE is forbidden for non-owner (403)', async () => {
    const { token: owner } = await api.registerUser('crud_del2');
    const { token: other } = await api.registerUser('crud_del3');
    const id = await api.captureRideId(owner, nextCluster().square);
    const res = await api.delete(`/api/territories/${id}`, api.authHeaders(other));
    expect(res.status()).toBe(403);
  });
});

test.describe('Leaderboard & activity', () => {
  test('GET /api/leaderboard lists users ordered by area', async () => {
    const { token: big } = await freeUser('lb_big');
    const { token: small } = await freeUser('lb_small');
    const g1 = nextCluster();
    const g2 = nextCluster();
    expect((await api.captureRide(big, g1.square)).status()).toBe(200);
    expect((await api.captureRide(small, g2.square)).status()).toBe(200);

    const res = await api.get('/api/leaderboard?limit=100&sort=area');
    expect(res.status()).toBe(200);
    const items = await res.json();
    expect(Array.isArray(items)).toBe(true);
    const first = items[0];
    expect(first).toHaveProperty('username');
    expect(first).toHaveProperty('total_area');
    expect(first).toHaveProperty('territories_count');
  });

  test('GET /api/activity returns recent captures newest-first', async () => {
    const { token } = await api.registerUser('act');
    expect((await api.captureRide(token, nextCluster().square)).status()).toBe(200);
    const res = await api.get('/api/activity?limit=10');
    expect(res.status()).toBe(200);
    const items = await res.json();
    expect(items.length).toBeGreaterThanOrEqual(1);
    const times = items.map((i) => new Date(i.created_at).getTime());
    expect([...times].sort((a, b) => b - a)).toEqual(times);
  });
});

test.describe('Achievements & share', () => {
  test('POST /api/share unlocks the first_share achievement', async () => {
    const { token } = await api.registerUser('ach_share');
    const res = await api.post('/api/share', {}, api.authHeaders(token));
    expect(res.status()).toBe(200);
    const ach = await (await api.get('/api/achievements', api.authHeaders(token))).json();
    expect(ach.some((a) => a.type === 'first_share')).toBe(true);
  });

  test('first capture unlocks first_capture achievement', async () => {
    const { token } = await api.registerUser('ach_first');
    expect((await api.captureRide(token, nextCluster().square)).status()).toBe(200);
    const ach = await (await api.get('/api/achievements', api.authHeaders(token))).json();
    expect(ach.some((a) => a.type === 'first_capture')).toBe(true);
  });

  test('GET /api/achievements/all returns progress for all types', async () => {
    const { token } = await api.registerUser('ach_all');
    const res = await api.get('/api/achievements/all', api.authHeaders(token));
    expect(res.status()).toBe(200);
    const items = await res.json();
    expect(items.length).toBeGreaterThan(0);
    items.forEach((i) => {
      expect(i).toHaveProperty('type');
      expect(i).toHaveProperty('unlocked');
    });
  });
});

test.describe('Route planner', () => {
  test('POST /api/plan-route validates minimum points (400)', async () => {
    const { token } = await api.registerUser('plan_few');
    const res = await api.post('/api/plan-route', { points: [[55.7, 37.6], [55.8, 37.6]] }, api.authHeaders(token));
    expect(res.status()).toBe(400);
  });

  test('plan-route is public (no auth required)', async () => {
    const res = await api.post('/api/plan-route', { points: [[55.7, 37.6], [55.8, 37.6], [55.7, 37.7]] });
    expect(res.status()).not.toBe(401);
  });
});

/** Builds a GPX string from an array of [lat, lon, ...] coordinates. */
function gpxWithCoords(points, name) {
  const pts = points
    .map((p) => `    <trkpt lat="${p[0].toFixed(6)}" lon="${p[1].toFixed(6)}"></trkpt>`)
    .join('\n');
  return `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Velo.io">
  <metadata><name>${name}_${Date.now().toString(36)}</name></metadata>
  <trk><name>${name}</name><trkseg>
${pts}
  </trkseg></trk>
</gpx>
`;
}