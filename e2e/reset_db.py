#!/usr/bin/env python3
"""Reset the Velo.io database for Playwright e2e tests.

Connects to the PostGIS database directly and truncates every application
table in dependency-safe order (leaf tables first, then parents). It runs
against whatever DATABASE_URL the backend uses — by default the dockerized
PostGIS reachable on localhost:5432 (`velo_io`).

Usage:
    python3 e2e/reset_db.py
    DATABASE_URL=postgresql://postgres:postgres@localhost:5432/velo_io_test python3 e2e/reset_db.py
"""

import os

import psycopg2

DEFAULT_DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/velo_io"
)

# Leaf tables first so foreign keys are never violated when truncating.
TABLES = [
    "user_achievements",
    "transactions",
    "gpx_hashes",
    "advertiser_payments",
    "advertiser_profiles",
    "user_balances",
    "notifications",
    "sponsored_territories",
    "territories",
    "users",
]


def reset(database_url: str = DEFAULT_DATABASE_URL):
    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(f'TRUNCATE {", ".join(TABLES)} RESTART IDENTITY CASCADE')
        print("Database reset complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    reset()