#!/usr/bin/env python3
"""Merge duplicate published incidents that share a source URL or exact headline+state.

Usage:
  DATABASE_URL=... python scripts/dedupe_incidents.py --dry-run
  DATABASE_URL=... python scripts/dedupe_incidents.py --apply
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "sync"))
from db_url import normalize_database_url  # noqa: E402

VERIFICATION_RANK = {
    "unconfirmed": 0,
    "reported": 1,
    "verified": 2,
    "official_confirmation": 3,
}


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, x: str) -> None:
        self.parent.setdefault(x, x)

    def find(self, x: str) -> str:
        self.add(x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra

    def groups(self) -> list[list[str]]:
        buckets: dict[str, list[str]] = defaultdict(list)
        for x in self.parent:
            buckets[self.find(x)].append(x)
        return [g for g in buckets.values() if len(g) > 1]


def _pick_keeper(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return max(
        rows,
        key=lambda r: (
            VERIFICATION_RANK.get(r["verification_status"], 0),
            r["corroboration_count"] or 0,
            -(r["published_at"].timestamp() if r["published_at"] else 0),
        ),
    )


def _find_duplicate_groups(cur) -> list[list[str]]:
    uf = UnionFind()

    cur.execute(
        """
        SELECT s.url, array_agg(DISTINCT i.incident_id::text) AS ids
        FROM sources s
        JOIN incident_sources isrc ON isrc.source_id = s.source_id
        JOIN incidents i ON i.incident_id = isrc.incident_id
        WHERE i.published_at IS NOT NULL
        GROUP BY s.url
        HAVING COUNT(DISTINCT i.incident_id) > 1
        """
    )
    for row in cur.fetchall():
        ids = row["ids"]
        for other in ids[1:]:
            uf.union(ids[0], other)

    cur.execute(
        """
        SELECT array_agg(incident_id::text ORDER BY published_at) AS ids
        FROM incidents
        WHERE published_at IS NOT NULL
          AND headline IS NOT NULL
          AND btrim(headline) <> ''
        GROUP BY state, btrim(headline)
        HAVING COUNT(*) > 1
        """
    )
    for row in cur.fetchall():
        ids = row["ids"]
        for other in ids[1:]:
            uf.union(ids[0], other)

    return uf.groups()


def _merge_group(cur, incident_ids: list[str], *, apply: bool) -> dict[str, Any]:
    cur.execute(
        """
        SELECT incident_id::text AS incident_id, state, headline, event_type,
               date_reported, verification_status, corroboration_count, published_at
        FROM incidents
        WHERE incident_id = ANY(%s::uuid[])
          AND published_at IS NOT NULL
        """,
        (incident_ids,),
    )
    rows = cur.fetchall()
    if len(rows) < 2:
        return {"skipped": True, "reason": "fewer than 2 published"}

    keeper = _pick_keeper(rows)
    losers = [r for r in rows if r["incident_id"] != keeper["incident_id"]]
    summary = {
        "keeper": keeper["incident_id"],
        "losers": [r["incident_id"] for r in losers],
        "state": keeper["state"],
        "headline": (keeper["headline"] or "")[:90],
        "verification": keeper["verification_status"],
    }
    if not apply:
        return summary

    keeper_id = keeper["incident_id"]
    for loser in losers:
        lid = loser["incident_id"]
        cur.execute(
            """
            INSERT INTO incident_sources (incident_id, source_id, role)
            SELECT %s, source_id, role
            FROM incident_sources
            WHERE incident_id = %s
            ON CONFLICT DO NOTHING
            """,
            (keeper_id, lid),
        )
        cur.execute(
            """
            INSERT INTO incident_fields (
              incident_id, field_name, value_json, source_id, source_span, confidence
            )
            SELECT %s, field_name, value_json, source_id, source_span, confidence
            FROM incident_fields
            WHERE incident_id = %s
            ON CONFLICT DO NOTHING
            """,
            (keeper_id, lid),
        )
        cur.execute(
            """
            INSERT INTO status_history (
              incident_id, from_status, to_status, changed_at, source_id, note
            )
            SELECT %s, from_status, to_status, changed_at, source_id,
                   COALESCE(note, '') || ' [merged from ' || %s || ']'
            FROM status_history
            WHERE incident_id = %s
            """,
            (keeper_id, lid, lid),
        )
        cur.execute(
            "UPDATE review_queue SET incident_id = %s WHERE incident_id = %s",
            (keeper_id, lid),
        )
        cur.execute("DELETE FROM incidents WHERE incident_id = %s", (lid,))

    cur.execute(
        """
        UPDATE incidents
        SET corroboration_count = (
              SELECT COUNT(*) FROM incident_sources WHERE incident_id = %s
            ),
            updated_at = now()
        WHERE incident_id = %s
        """,
        (keeper_id, keeper_id),
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="List merge groups only")
    mode.add_argument("--apply", action="store_true", help="Merge duplicates and refresh map cache")
    args = parser.parse_args()

    raw = os.environ.get("DATABASE_URL")
    if not raw:
        print("DATABASE_URL is required", file=sys.stderr)
        sys.exit(1)

    url = normalize_database_url(raw)
    apply = bool(args.apply)

    with psycopg.connect(url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            groups = _find_duplicate_groups(cur)
            print(f"duplicate groups: {len(groups)}")
            merged = 0
            for ids in groups:
                summary = _merge_group(cur, ids, apply=apply)
                if summary.get("skipped"):
                    continue
                merged += 1
                action = "MERGE" if apply else "WOULD MERGE"
                print(
                    f"  [{action}] keeper={summary['keeper'][:8]}… "
                    f"losers={len(summary['losers'])} | {summary['state']} | "
                    f"{summary['headline']!r}"
                )
            if apply and merged:
                cur.execute("SELECT refresh_geo_agg_cache()")
            if apply:
                conn.commit()
            else:
                conn.rollback()

            cur.execute("SELECT COUNT(*) AS n FROM incidents WHERE published_at IS NOT NULL")
            print(f"published incidents now: {cur.fetchone()['n']}")
            print(f"{'applied' if apply else 'dry-run'} merges: {merged}")


if __name__ == "__main__":
    main()
