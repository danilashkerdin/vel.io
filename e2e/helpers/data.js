/**
 * Shared data & constants for Velo.io e2e tests.
 */

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';
const UI_BASE_URL = process.env.UI_BASE_URL || 'http://localhost:3000';
const ADMIN_EMAIL = process.env.ADMIN_EMAIL || 'admin@vel.io';
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'adminpass123';

/** Small closed square around Moscow used as the canonical capture. */
const SQUARE = [
  [55.748, 37.615],
  [55.748, 37.63],
  [55.738, 37.63],
  [55.738, 37.615],
  [55.748, 37.615],
];

/** A square fully inside SQUARE (for subtraction tests). */
const SQUARE_INSIDE = [
  [55.746, 37.62],
  [55.746, 37.624],
  [55.742, 37.624],
  [55.742, 37.62],
  [55.746, 37.62],
];

/** A square overlapping SQUARE by ~half (for partial subtraction). */
const SQUARE_HALF_INSIDE = [
  [55.75, 37.62],
  [55.75, 37.628],
  [55.742, 37.628],
  [55.742, 37.62],
  [55.75, 37.62],
];

/** A distant square that does not overlap SQUARE. */
const SQUARE_FAR_AWAY = [
  [55.8, 37.5],
  [55.8, 37.51],
  [55.79, 37.51],
  [55.79, 37.5],
  [55.8, 37.5],
];

/** Open/not-closed route (should be rejected by the closure detector). */
const OPEN_ROUTE = [
  [55.75, 37.5],
  [55.752, 37.502],
  [55.74, 37.51],
];

/** A large ~1 km² closed square for area achievements. */
const LARGE_SQUARE = [
  [55.75, 37.6],
  [55.76, 37.64],
  [55.74, 37.64],
  [55.74, 37.6],
  [55.75, 37.6],
];

/** GeoJSON polygon covering SQUARE — used to create sponsored zones. */
const SPONSORED_POLYGON = {
  type: 'Polygon',
  coordinates: [
    [
      [37.61, 55.74],
      [37.63, 55.74],
      [37.63, 55.75],
      [37.61, 55.75],
      [37.61, 55.74],
    ],
  ],
};

/** A minimal, valid closed-square GPX payload (matches backend fixture). */
const BIG_SQUARE_GPX = `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Velo.io">
  <trk><name>Большой квадрат</name><trkseg>
    <trkpt lat="55.74800" lon="37.61500"></trkpt>
    <trkpt lat="55.74800" lon="37.63000"></trkpt>
    <trkpt lat="55.73800" lon="37.63000"></trkpt>
    <trkpt lat="55.73800" lon="37.61500"></trkpt>
    <trkpt lat="55.74800" lon="37.61500"></trkpt>
  </trkseg></trk>
</gpx>
`;

/** A valid GPX that is NOT closed (should fail with 400). */
const OPEN_ROUTE_GPX = `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Velo.io">
  <trk><name>Незамкнутый</name><trkseg>
    <trkpt lat="55.75000" lon="37.50000"></trkpt>
    <trkpt lat="55.75200" lon="37.50200"></trkpt>
    <trkpt lat="55.75000" lon="37.51000"></trkpt>
    <trkpt lat="55.74000" lon="37.51000"></trkpt>
    <trkpt lat="55.74000" lon="37.50000"></trkpt>
  </trkseg></trk>
</gpx>
`;

/** GPX containing only waypoints (no track/route) — fails validation. */
const WAYPOINTS_ONLY_GPX = `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Velo.io">
  <wpt lat="55.75" lon="37.6"></wpt>
  <wpt lat="55.76" lon="37.6"></wpt>
</gpx>
`;

/** Bounding box that covers Moscow / the test squares. */
const MOSCOW_BBOX = { north: 56, south: 55, east: 38, west: 37 };

/**
 * Returns a stable unique suffix for a test user/email so parallel/isolated
 * tests never collide (DB is shared across the suite).
 */
let counter = 0;
function unique(prefix = 'user') {
  counter += 1;
  const stamp = Date.now().toString(36);
  return `${prefix}_${stamp}_${counter}`;
}

function uniqueEmail(prefix = 'user') {
  return `${unique(prefix).toLowerCase()}@test.dev`;
}

module.exports = {
  API_BASE_URL,
  UI_BASE_URL,
  ADMIN_EMAIL,
  ADMIN_PASSWORD,
  SQUARE,
  SQUARE_INSIDE,
  SQUARE_HALF_INSIDE,
  SQUARE_FAR_AWAY,
  OPEN_ROUTE,
  LARGE_SQUARE,
  SPONSORED_POLYGON,
  BIG_SQUARE_GPX,
  OPEN_ROUTE_GPX,
  WAYPOINTS_ONLY_GPX,
  MOSCOW_BBOX,
  unique,
  uniqueEmail,
};