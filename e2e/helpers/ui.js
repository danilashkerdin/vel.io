/**
 * UI helpers — reroute API calls to the local backend. The frontend, when
 * served on :3000, talks to the production origin (https://vel-io.onrender.com);
 * we transparently rewrite those request URLs to the local FastAPI backend.
 * CORS for http://localhost:3000 is already enabled on the backend.
 */

const { API_BASE_URL, UI_BASE_URL } = require('./data');

const PRODUCTION_API_ORIGIN = 'https://vel-io.onrender.com';

/**
 * Rewrites API requests aimed at the production origin to the local backend.
 * `route.fetch()` performs the request server-side to the rewritten URL and
 * `route.fulfill()` replays it to the browser — this is the documented,
 * race-free pattern for forwarding a request to a different origin.
 */
async function routeApiToLocal(page) {
  await page.route(`${PRODUCTION_API_ORIGIN}/**`, async (route) => {
    const url = new URL(route.request().url());
    const target = `${API_BASE_URL}${url.pathname}${url.search}`;
    const response = await route.fetch({ url: target });
    await route.fulfill({ response });
  });
}

/** Block flaky third-party API calls not needed for assertions. */
async function silenceNoise(page) {
  await page.route(/(analytics|sentry|mixpanel|telegram)/i, (route) => route.abort());
}

/**
 * Pre-seed an authenticated session: set the JWT token + user object in
 * localStorage before the app scripts run. `user` is the API user object
 * (which includes `token`), or a plain `{ token }`.
 */
async function seedSession(page, user, extra = {}) {
  const { token, ...userData } = user;
  await page.addInitScript(({ tokenValue, userValue, extraValue }) => {
    localStorage.setItem('token', tokenValue);
    localStorage.setItem('user', JSON.stringify(userValue));
    for (const [k, v] of Object.entries(extraValue || {})) {
      localStorage.setItem(k, v);
    }
  }, {
    tokenValue: token,
    userValue: userData,
    extraValue: { onboarding_done: '1', ...extra },
  });
}

async function goto(page, path) {
  await page.goto(`${UI_BASE_URL}${path}`, { waitUntil: 'domcontentloaded' });
}

module.exports = { routeApiToLocal, silenceNoise, seedSession, goto, PRODUCTION_API_ORIGIN };