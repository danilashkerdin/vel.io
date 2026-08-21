/* eslint-disable no-console */
const { execFileSync } = require('child_process');
const path = require('path');

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';
const ADMIN_EMAIL = process.env.ADMIN_EMAIL || 'admin@vel.io';
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'adminpass123';

/**
 * Global setup for the Playwright e2e suite.
 *
 * 1. Resets the database to a known, clean state so every run is deterministic.
 * 2. Verifies the backend is healthy and pre-registers the admin account used
 *    by the admin API / UI tests.
 */
async function globalSetup() {
  const reset = process.env.E2E_RESET_DB !== 'false';
  if (reset) {
    console.log('[global-setup] Resetting database…');
    execFileSync('python3', [path.join(__dirname, 'reset_db.py')], {
      stdio: 'inherit',
    });
  }

  console.log(`[global-setup] Checking backend health at ${API_BASE_URL}…`);
  const { request } = require('@playwright/test');

  const api = await request.newContext({ baseURL: API_BASE_URL });
  try {
    const health = await api.get('/api/health');
    if (!health.ok()) {
      throw new Error(
        `Backend is not healthy (${health.status()}). Start it with:\n` +
          `  docker-compose up --build\n` +
          `before running the Playwright suite.`
      );
    }

    // Pre-register the admin user (idempotent — register may 409 if exists).
    const res = await api.post('/api/auth/register', {
      data: {
        email: ADMIN_EMAIL,
        username: 'admin',
        password: ADMIN_PASSWORD,
      },
    });
    if (res.status() === 200) {
      console.log(`[global-setup] Registered admin ${ADMIN_EMAIL}`);
    } else if (res.status() === 400) {
      console.log(`[global-setup] Admin ${ADMIN_EMAIL} already registered`);
    } else {
      throw new Error(
        `Failed to pre-register admin: ${res.status()} ${await res.text()}`
      );
    }
  } finally {
    await api.dispose();
  }
}

module.exports = globalSetup;