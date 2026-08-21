/**
 * API client helpers built on top of Playwright's request fixture.
 *
 * Every method returns the raw fetch Response; tests assert on it directly.
 * Auth helpers register/login fresh users so tests stay isolated.
 */

const { expect } = require('@playwright/test');
const {
  API_BASE_URL,
  ADMIN_EMAIL,
  ADMIN_PASSWORD,
} = require('./data');

class Api {
  constructor(request, baseURL = API_BASE_URL) {
    this.request = request;
    this.baseURL = baseURL;
  }

  url(path) {
    return `${this.baseURL}${path}`;
  }

  /** Raw GET/POST helpers that always return the Response object. */

  get(path, opts = {}) {
    return this.request.get(this.url(path), opts);
  }

  post(path, data, opts = {}) {
    return this.request.post(this.url(path), {
      data,
      ...opts,
    });
  }

  delete(path, opts = {}) {
    return this.request.delete(this.url(path), opts);
  }

  patch(path, data, opts = {}) {
    return this.request.patch(this.url(path), { data, ...opts });
  }

  /** Auth'd helpers — pass an Authorization header for JWT-protected routes. */

  async register(email, username, password = 'secret123', opts = {}) {
    return this.post('/api/auth/register', {
      email,
      username,
      password,
      ...opts.body,
    }, opts.extra);
  }

  async login(email, password) {
    return this.post('/api/auth/login', { email, password });
  }

  /** Registers a brand-new user and returns { response, token, user }. */
  async registerUser(prefix = 'user', opts = {}) {
    const { uniqueEmail } = require('./data');
    const email = opts.email || uniqueEmail(prefix);
    const username = opts.username || `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;
    const password = opts.password || 'secret123';

    const res = await this.register(email, username, password, opts);
    if (res.status() !== 200) {
      throw new Error(
        `register(${email}) failed: ${res.status()} ${await res.text()}`
      );
    }
    const body = await res.json();
    return { response: res, email, username, password, user: body, token: body.token };
  }

  /** Logs in as the shared admin account. Returns { token, user }. */
  async loginAdmin(password = ADMIN_PASSWORD) {
    const res = await this.login(ADMIN_EMAIL, password);
    if (res.status() !== 200) {
      throw new Error(
        `admin login failed: ${res.status()} ${await res.text()}`
      );
    }
    const body = await res.json();
    return { token: body.token, user: body };
  }

  authHeaders(token) {
    return { headers: { Authorization: `Bearer ${token}` } };
  }

  /** Capture a ride territory via the JSON endpoint (JWT required). */
  captureRide(token, points, name = 'test') {
    return this.post('/api/capture-ride', { points, name }, this.authHeaders(token));
  }

  async captureRideId(token, points, name = 'test') {
    const res = await this.captureRide(token, points, name);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    return body.id;
  }

  /** Upload a GPX file (JWT required). `file` is { name, mimeType, buffer }. */
  uploadGpx(token, file) {
    return this.request.post(this.url('/api/upload-gpx'), {
      headers: { Authorization: `Bearer ${token}` },
      multipart: { file },
    });
  }

  /** Create a sponsored zone as admin. Returns { id, response }. */
  async createSponsoredZone(adminToken, overrides = {}) {
    const { data: spare } = require('./data');
    const payload = {
      business_name: 'E2E Test Shop',
      description: 'Created by Playwright',
      monthly_budget_rub: 5000,
      color: '#FF0000',
      polygon: spare.SPONSORED_POLYGON,
      ...overrides,
    };
    const res = await this.post(
      '/api/admin/sponsored-territories',
      payload,
      this.authHeaders(adminToken)
    );
    if (res.status() !== 200) {
      throw new Error(
        `createSponsoredZone failed: ${res.status()} ${await res.text()}`
      );
    }
    const body = await res.json();
    return { response: res, id: body.id };
  }
}

/** Register a user (unique email) then return it; convenience one-liner. */
async function makeUser(request, prefix = 'user') {
  const api = new Api(request);
  return api.registerUser(prefix);
}

/**
 * Creates an Api bound to a dedicated APIRequestContext.
 *
 * The Playwright `request` fixture is scoped to a single test, so to use an
 * Api across an entire spec file we create our own context from the
 * `playwright` fixture in beforeAll and dispose it in afterAll.
 *
 * Usage in a spec:
 *   let api, dispose;
 *   test.beforeAll(async ({ playwright }) => {
 *     ({ api, dispose } = await buildApi(playwright));
 *   });
 *   test.afterAll(async () => { await dispose(); });
 */
async function buildApi(playwright) {
  const context = await playwright.request.newContext();
  return { api: new Api(context), dispose: () => context.dispose() };
}

module.exports = { Api, makeUser, buildApi };