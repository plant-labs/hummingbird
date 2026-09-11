#!/usr/bin/env python3
"""Apply production schema migrations (001 + 002 only; never seed)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "sync"))
from db_url import normalize_database_url  # noqa: E402

MIGRATIONS = [
    ROOT / "infra" / "postgres" / "001_init.sql",
    ROOT / "infra" / "postgres" / "002_refresh_geo_agg.sql",
    ROOT / "infra" / "postgres" / "004_geo_outcome.sql",
]


def main() -> None:
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        print("DATABASE_URL is required", file=sys.stderr)
        sys.exit(1)

    try:
        url = normalize_database_url(raw)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    with psycopg.connect(url) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
              filename TEXT PRIMARY KEY,
              applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        for path in MIGRATIONS:
            row = conn.execute(
                "SELECT 1 FROM schema_migrations WHERE filename = %s",
                (path.name,),
            ).fetchone()
            if row:
                print(f"skip {path.name}")
                continue
            sql = path.read_text(encoding="utf-8")
            print(f"apply {path.name}")
            conn.execute(sql)
            conn.execute(
                "INSERT INTO schema_migrations (filename) VALUES (%s)",
                (path.name,),
            )
        conn.commit()
    print("migrations complete")


if __name__ == "__main__":
    main()
