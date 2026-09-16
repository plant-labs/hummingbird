#!/usr/bin/env python3
"""One-off: merge BBC manhunt duplicates into Borgu Al Jazeera incident.

Keeper: cf0b219b-92c9-420e-86aa-2346b53176c2
Losers: 4ded7218-…, c8c1dc77-…
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "sync"))
from db_url import normalize_database_url  # noqa: E402

KEEPER = "cf0b219b-92c9-420e-86aa-2346b53176c2"
LOSERS = [
    "4ded7218-5653-4154-8a13-689d9d70523a",
    "c8c1dc77-a22c-451b-9630-e466392c3df3",
]
BBC_URLS = [
    "https://www.bbc.com/news/articles/c0rewkerdpyo",
    "https://www.bbc.com/news/articles/cj031jp3g6jo",
]


def main() -> None:
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        print("DATABASE_URL is required", file=sys.stderr)
        sys.exit(1)

    url = normalize_database_url(raw)
    with psycopg.connect(url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM incidents WHERE incident_id = %s", (KEEPER,))
            if not cur.fetchone():
                print(f"keeper missing: {KEEPER}", file=sys.stderr)
                sys.exit(1)

            cur.execute(
                "SELECT source_id::text AS source_id, url FROM sources WHERE url = ANY(%s)",
                (BBC_URLS,),
            )
            sources = cur.fetchall()
            by_url = {s["url"]: s["source_id"] for s in sources}

            for bbc_url in BBC_URLS:
                sid = by_url.get(bbc_url)
                if not sid:
                    print(f"missing source row for {bbc_url}", file=sys.stderr)
                    sys.exit(1)
                cur.execute(
                    """
                    INSERT INTO incident_sources (incident_id, source_id, role)
                    VALUES (%s, %s, 'corroborating')
                    ON CONFLICT DO NOTHING
                    """,
                    (KEEPER, sid),
                )

            cur.execute(
                """
                SELECT source_span FROM incident_fields
                WHERE incident_id = ANY(%s::uuid[])
                  AND field_name = 'victim_count'
                LIMIT 1
                """,
                (LOSERS,),
            )
            span_row = cur.fetchone()
            span = (span_row and span_row["source_span"]) or (
                "ader says as many as 500 people may have been abduc"
            )
            primary_sid = by_url[BBC_URLS[0]]
            cur.execute(
                """
                INSERT INTO incident_fields (
                  incident_id, field_name, value_json, source_id, source_span, confidence
                ) VALUES (%s, 'victim_count', '500'::jsonb, %s, %s, 0.85)
                ON CONFLICT (incident_id, field_name, source_id)
                DO UPDATE SET value_json = EXCLUDED.value_json,
                              source_span = EXCLUDED.source_span,
                              confidence = EXCLUDED.confidence
                """,
                (KEEPER, primary_sid, span),
            )

            cur.execute(
                """
                UPDATE incidents
                SET corroboration_count = (
                      SELECT COUNT(*) FROM incident_sources WHERE incident_id = %s
                    ),
                    updated_at = now()
                WHERE incident_id = %s
                """,
                (KEEPER, KEEPER),
            )

            cur.execute(
                "DELETE FROM incidents WHERE incident_id = ANY(%s::uuid[])",
                (LOSERS,),
            )
            deleted = cur.rowcount
            cur.execute("SELECT refresh_geo_agg_cache()")
            conn.commit()
            print(f"merged BBC sources into {KEEPER}; deleted {deleted} duplicate incidents")


if __name__ == "__main__":
    main()
