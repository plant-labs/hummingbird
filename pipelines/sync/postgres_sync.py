"""Sync gold review candidates into Postgres review_queue; publish approved incidents."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from hummingbird_schemas.geo import centroid_for_state

ROOT = Path(__file__).resolve().parents[2]


def db_conninfo() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://hummingbird:hummingbird@localhost:5432/hummingbird",
    )


def enqueue_candidates(gold_path: Path) -> int:
    count = 0
    with psycopg.connect(db_conninfo()) as conn:
        with conn.cursor() as cur:
            with gold_path.open(encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    item = json.loads(line)
                    cur.execute(
                        """
                        INSERT INTO review_queue (queue_id, candidate_json, status, priority, reason)
                        VALUES (%s, %s, 'pending', %s, %s)
                        ON CONFLICT (queue_id) DO NOTHING
                        """,
                        (
                            item["queue_id"],
                            Json(item),
                            item.get("priority", 100),
                            item.get("reason"),
                        ),
                    )
                    count += 1
        conn.commit()
    print(f"[sync] enqueued {count} review items")
    return count


def _already_published(cur, preview: dict[str, Any]) -> bool:
    """Skip duplicates: same state + headline within 3 days."""
    headline = (preview.get("headline") or "").strip()
    state = (preview.get("state") or "").strip()
    if not headline or not state:
        return False
    cur.execute(
        """
        SELECT 1 FROM incidents
        WHERE state = %s
          AND headline = %s
          AND published_at IS NOT NULL
          AND date_reported >= CURRENT_DATE - INTERVAL '3 days'
        LIMIT 1
        """,
        (state, headline),
    )
    return cur.fetchone() is not None


def process_gold_candidates(gold_path: Path) -> dict[str, int]:
    """Auto-publish strong candidates; enqueue the rest for human review."""
    stats = {"auto_published": 0, "enqueued": 0, "skipped_duplicate": 0, "quarantined": 0}
    with psycopg.connect(db_conninfo()) as conn:
        with conn.cursor() as cur:
            with gold_path.open(encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    item = json.loads(line)
                    route = item.get("route") or "review"
                    preview = item.get("publish_preview") or {}

                    if route == "quarantine":
                        stats["quarantined"] += 1
                        continue

                    if _already_published(cur, preview):
                        stats["skipped_duplicate"] += 1
                        continue

                    if route == "auto_publish":
                        verification = item.get("verification_status") or "reported"
                        incident_id = publish_incident_from_candidate(
                            cur, item, verification_status=verification
                        )
                        cur.execute(
                            """
                            INSERT INTO review_queue (
                              queue_id, incident_id, candidate_json, status, priority, reason,
                              reviewed_at, reviewed_by
                            ) VALUES (%s, %s, %s, 'approved', %s, %s, now(), 'auto_publish')
                            ON CONFLICT (queue_id) DO NOTHING
                            """,
                            (
                                item["queue_id"],
                                str(incident_id),
                                Json(item),
                                item.get("priority", 20),
                                item.get("reason"),
                            ),
                        )
                        stats["auto_published"] += 1
                    else:
                        cur.execute(
                            """
                            INSERT INTO review_queue (queue_id, candidate_json, status, priority, reason)
                            VALUES (%s, %s, 'pending', %s, %s)
                            ON CONFLICT (queue_id) DO NOTHING
                            """,
                            (
                                item["queue_id"],
                                Json(item),
                                item.get("priority", 100),
                                item.get("reason"),
                            ),
                        )
                        stats["enqueued"] += 1

            if stats["auto_published"]:
                cur.execute("SELECT refresh_geo_agg_cache()")
        conn.commit()
    print(f"[sync] {stats}")
    return stats



def _upsert_source(cur, bronze: dict[str, Any]) -> UUID:
    url = bronze.get("url") or f"urn:hummingbird:{bronze.get('content_hash')}"
    if "example.com" in str(url):
        raise ValueError(f"refusing to publish demo/example URL: {url}")
    source_id = uuid4()
    cur.execute(
        """
        INSERT INTO sources (source_id, url, outlet, source_type, fetched_at, raw_ref, reliability_tier, excerpt)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (url) DO UPDATE SET fetched_at = EXCLUDED.fetched_at
        RETURNING source_id
        """,
        (
            str(source_id),
            url,
            bronze.get("outlet") or "unknown",
            bronze.get("source_type") or "news",
            bronze.get("fetched_at") or datetime.now(timezone.utc).isoformat(),
            bronze.get("content_hash"),
            2 if (bronze.get("source_type") or "news") == "news" else 5,
            (bronze.get("body") or "")[:280],
        ),
    )
    row = cur.fetchone()
    return row[0]



def publish_incident_from_candidate(
    cur,
    candidate_wrap: dict[str, Any],
    verification_status: str = "verified",
) -> UUID:
    candidate = candidate_wrap.get("candidate") or candidate_wrap
    primary = candidate.get("primary") or {}
    bronze = primary.get("bronze") or {}
    extraction = primary.get("extraction") or {}
    members = candidate.get("members") or [primary]

    source_ids: list[UUID] = []
    for m in members:
        sid = _upsert_source(cur, m.get("bronze") or {})
        source_ids.append(sid)

    state = extraction.get("state") or "Unknown"
    lga = extraction.get("lga")
    lat_lng = centroid_for_state(state)
    lat, lng = (lat_lng or (9.0, 8.0))

    incident_id = uuid4()
    cur.execute(
        """
        INSERT INTO incidents (
          incident_id, event_type, date_occurred, date_reported, state, lga, geom,
          location_precision, verification_status, confidence_score, corroboration_count,
          current_status, headline, published_at
        ) VALUES (
          %s, %s, %s, %s, %s, %s,
          ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
          %s, %s, %s, %s, %s, %s, now()
        )
        RETURNING incident_id
        """,
        (
            str(incident_id),
            extraction.get("event_type") or "other",
            extraction.get("date_occurred"),
            extraction.get("date_reported") or date.today().isoformat(),
            state,
            lga,
            lng,
            lat,
            extraction.get("location_precision") or "state",
            verification_status,
            min(1.0, 0.4 + 0.2 * len(source_ids)),
            candidate.get("corroboration_count") or len(source_ids),
            extraction.get("current_status") or "ongoing",
            extraction.get("headline") or bronze.get("title"),
        ),
    )
    incident_id = cur.fetchone()[0]

    primary_source = source_ids[0]
    cur.execute(
        """
        INSERT INTO incident_sources (incident_id, source_id, role)
        VALUES (%s, %s, 'primary')
        ON CONFLICT DO NOTHING
        """,
        (str(incident_id), str(primary_source)),
    )
    for sid in source_ids[1:]:
        cur.execute(
            """
            INSERT INTO incident_sources (incident_id, source_id, role)
            VALUES (%s, %s, 'corroborating')
            ON CONFLICT DO NOTHING
            """,
            (str(incident_id), str(sid)),
        )

    for field in extraction.get("fields") or []:
        cur.execute(
            """
            INSERT INTO incident_fields (incident_id, field_name, value_json, source_id, source_span, confidence)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                str(incident_id),
                field["field_name"],
                Json(field.get("value")),
                str(primary_source),
                field["source_span"],
                field.get("confidence", 0.5),
            ),
        )

    cur.execute(
        """
        INSERT INTO status_history (incident_id, from_status, to_status, source_id, note)
        VALUES (%s, NULL, %s, %s, %s)
        """,
        (
            str(incident_id),
            extraction.get("current_status") or "ongoing",
            str(primary_source),
            "Published from pipeline",
        ),
    )
    return incident_id



def approve_queue_item(queue_id: str, reviewer: str = "moderator") -> Optional[str]:
    with psycopg.connect(db_conninfo()) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT * FROM review_queue WHERE queue_id = %s AND status = 'pending'",
                (queue_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            payload = row["candidate_json"]
            verification = payload.get("verification_status") or "verified"
            if verification == "unconfirmed":
                verification = "verified"  # explicit human elevates after review
            incident_id = publish_incident_from_candidate(cur, payload, verification_status=verification)
            cur.execute(
                """
                UPDATE review_queue
                SET status = 'approved', reviewed_at = now(), reviewed_by = %s, incident_id = %s
                WHERE queue_id = %s
                """,
                (reviewer, str(incident_id), queue_id),
            )
            cur.execute("SELECT refresh_geo_agg_cache()")
        conn.commit()
    return str(incident_id)


def reject_queue_item(queue_id: str, reviewer: str = "moderator", notes: str = "") -> bool:
    with psycopg.connect(db_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE review_queue
                SET status = 'rejected', reviewed_at = now(), reviewed_by = %s, reviewer_notes = %s
                WHERE queue_id = %s AND status = 'pending'
                """,
                (reviewer, notes, queue_id),
            )
            updated = cur.rowcount
        conn.commit()
    return updated > 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("gold_path", type=Path)
    parser.add_argument(
        "--enqueue-only",
        action="store_true",
        help="Only enqueue to review_queue (no auto-publish)",
    )
    args = parser.parse_args()
    if args.enqueue_only:
        enqueue_candidates(args.gold_path)
    else:
        process_gold_candidates(args.gold_path)

