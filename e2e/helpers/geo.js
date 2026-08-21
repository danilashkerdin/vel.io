/**
 * Collision-free test coordinates.
 *
 * The e2e suite runs against a single live database that is not reset between
 * tests, so two captures of the exact same polygon by different users collide
 * (the backend subtracts the occupied area → "территория уже занята").
 *
 * These helpers emit a geo-cluster per call whose base point is placed at a
 * random, well-separated location in a large mid-latitude band, so that no two
 * clusters (even across different spec files / workers) meaningfully overlap:
 *   - each cluster has its own base;
 *   - a cluster's related shapes (square, half-inside square, sponsor polygon)
 *     share that base so within-a-cluster overlap behaves exactly as the test
 *     expects;
 *   - bases are chosen in a wide region and are kept clear of the "default"
 *     Moscow sponsored area used by non-capture admin-zone tests.
 *
 * Uniqueness is probabilistic (crypto-random over a large grid) rather than
 * relying on shared in-memory counters, which Playwright does not preserve
 * across spec files.
 */

const { randomInt } = require('node:crypto');

// Spawn region: rows/cols in degrees. The full region is huge, so two random
// picks collide with negligible probability.
const SPAWN = {
  latMin: 45.0,
  latMax: 57.0,
  lonMin: 27.0,
  lonMax: 47.0,
};

const STEP = 0.045; // ~5 km cell → neighbouring clusters are clearly separated

/** The "default" Moscow sponsored band we never reuse. */
const SPONSOR_LAT_MIN = 55.70;
const SPONSOR_LAT_MAX = 55.78;
const SPONSOR_LON_MIN = 37.55;
const SPONSOR_LON_MAX = 37.70;

function isInsideSponsorBand(lat, lon) {
  return (
    lat >= SPONSOR_LAT_MIN && lat <= SPONSOR_LAT_MAX &&
    lon >= SPONSOR_LON_MIN && lon <= SPONSOR_LON_MAX
  );
}

function randomBase() {
  const rows = Math.floor((SPAWN.latMax - SPAWN.latMin) / STEP);
  const cols = Math.floor((SPAWN.lonMax - SPAWN.lonMin) / STEP);
  for (;;) {
    const row = randomInt(rows);
    const col = randomInt(cols);
    const lat = SPAWN.latMin + row * STEP;
    const lon = SPAWN.lonMin + col * STEP;
    if (!isInsideSponsorBand(lat + 0.01, lon + 0.01)) {
      return { lat, lon };
    }
  }
}

/** Returns a fresh cluster { base, square, inside, halfInside, sponsoredPolygon }. */
function nextCluster() {
  const { lat, lon } = randomBase();
  const base = { lat, lon };
  const dLat = 0.015;
  const dLon = 0.02;

  const square = [
    [lat, lon],
    [lat, lon + dLon],
    [lat - dLat, lon + dLon],
    [lat - dLat, lon],
    [lat, lon],
  ];

  // A second square fully inside `square` (for full-overlap tests).
  const inside = [
    [lat - dLat / 2, lon + dLon / 4],
    [lat - dLat / 2, lon + (3 * dLon) / 4],
    [lat - dLat, lon + (3 * dLon) / 4],
    [lat - dLat, lon + dLon / 4],
    [lat - dLat / 2, lon + dLon / 4],
  ];

  // A square half-inside `square` and half-outside (for partial-overlap tests).
  const halfInside = [
    [lat + dLat / 3, lon + dLon / 4],
    [lat + dLat / 3, lon + (3 * dLon) / 4],
    [lat - dLon - 0.005, lon + (3 * dLon) / 4],
    [lat - dLon - 0.005, lon + dLon / 4],
    [lat + dLat / 3, lon + dLon / 4],
  ];

  // A polygon that overlaps `square` so a capture over it earns a reward.
  const sponsoredPolygon = {
    type: 'Polygon',
    coordinates: [
      [
        [lon + 0.01, lat - 0.005],
        [lon + 0.03, lat - 0.005],
        [lon + 0.03, lat + 0.005],
        [lon + 0.01, lat + 0.005],
        [lon + 0.01, lat - 0.005],
      ],
    ],
  };

  return { base, square, inside, halfInside, sponsoredPolygon };
}

module.exports = { nextCluster };