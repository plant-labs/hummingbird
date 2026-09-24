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

from hummingbird_schemas.geo import centroid_for_lga
from db_url import normalize_database_url
from notify import notify_pending_review, require_human_approval

ROOT = Path(__file__).resolve().parents[2]


def db_conninfo() -> str:
    return normalize_database_url(
        os.getenv(
            "DATABASE_URL",
            "postgresql://hummingbird:hummingbird@localhost:5432/hummingbird",
        )
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
                    if cur.rowcount:
                        count += 1
                        notify_pending_review(item)
        conn.commit()
    print(f"[sync] enqueued {count} review items")
    return count


def _candidate_urls(candidate_wrap: dict[str, Any]) -> list[str]:
    candidate = candidate_wrap.get("candidate") or candidate_wrap
    primary = candidate.get("primary") or {}
    members = candidate.get("members") or [primary]
    urls: list[str] = []
    for m in members:
        bronze = m.get("bronze") or {}
        url = (bronze.get("url") or "").strip()
        if url and "example.com" not in url:
            urls.append(url)
    return urls


def _find_published_by_urls(cur, urls: list[str]) -> Optional[UUID]:
    """Return an existing published incident that already links any of these source URLs."""
    if not urls:
        return None
    cur.execute(
        """
        SELECT i.incident_id
        FROM incidents i
        JOIN incident_sources isrc ON isrc.incident_id = i.incident_id
        JOIN sources s ON s.source_id = isrc.source_id
        WHERE i.published_at IS NOT NULL
          AND s.url = ANY(%s)
        ORDER BY i.published_at ASC
        LIMIT 1
        """,
        (urls,),
    )
    row = cur.fetchone()
    return row[0] if row else None


def _find_published_by_headline(cur, state: str, headline: str) -> Optional[UUID]:
    """Exact state + headline match among published incidents (any date)."""
    state = (state or "").strip()
    headline = (headline or "").strip()
    if not state or not headline:
        return None
    cur.execute(
        """
        SELECT incident_id FROM incidents
        WHERE published_at IS NOT NULL
          AND state = %s
          AND btrim(headline) = %s
        ORDER BY published_at ASC
        LIMIT 1
        """,
        (state, headline),
    )
    row = cur.fetchone()
    return row[0] if row else None


def _already_published(cur, preview: dict[str, Any], candidate_wrap: dict[str, Any] | None = None) -> bool:
    """Skip duplicates: shared source URL, or same state + headline."""
    if candidate_wrap and _find_published_by_urls(cur, _candidate_urls(candidate_wrap)):
        return True
    headline = (preview.get("headline") or "").strip()
    state = (preview.get("state") or "").strip()
    return _find_published_by_headline(cur, state, headline) is not None


def _attach_sources_to_incident(cur, incident_id: UUID, source_ids: list[UUID]) -> None:
    for i, sid in enumerate(source_ids):
        role = "primary" if i == 0 else "corroborating"
        cur.execute(
            """
            INSERT INTO incident_sources (incident_id, source_id, role)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (str(incident_id), str(sid), role),
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
        (str(incident_id), str(incident_id)),
    )


def process_gold_candidates(gold_path: Path) -> dict[str, int]:
    """Enqueue candidates for human review; optionally auto-publish when approval is off."""
    human_gate = require_human_approval()
    stats = {
        "auto_published": 0,
        "enqueued": 0,
        "skipped_duplicate": 0,
        "merged_into_existing": 0,
        "quarantined": 0,
    }
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

                    if _already_published(cur, preview, item):
                        stats["skipped_duplicate"] += 1
                        continue

                    # Human approval gate: never publish until /moderation approve.
                    if human_gate or route != "auto_publish":
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
                        if cur.rowcount:
                            stats["enqueued"] += 1
                            notify_pending_review(item)
                        continue

                    verification = item.get("verification_status") or "reported"
                    incident_id, created = publish_incident_from_candidate(
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
                    if created:
                        stats["auto_published"] += 1
                    else:
                        stats["merged_into_existing"] += 1

            if stats["auto_published"] or stats["merged_into_existing"]:
                cur.execute("SELECT refresh_geo_agg_cache()")
        conn.commit()
    print(f"[sync] human_approval={human_gate} {stats}")
    return stats



def _row_scalar(row: Any, key: str) -> Any:
    """Support both tuple and dict_row cursors."""
    if row is None:
        raise RuntimeError(f"expected a row with {key}")
    if isinstance(row, dict):
        return row[key]
    return row[0]


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
    return _row_scalar(cur.fetchone(), "source_id")



def publish_incident_from_candidate(
    cur,
    candidate_wrap: dict[str, Any],
    verification_status: str = "verified",
) -> tuple[UUID, bool]:
    """Publish a new incident, or attach sources to an existing duplicate.

    Returns (incident_id, created) where created=False means merged into an existing row.
    """
    candidate = candidate_wrap.get("candidate") or candidate_wrap
    primary = candidate.get("primary") or {}
    bronze = primary.get("bronze") or {}
    extraction = primary.get("extraction") or {}
    members = candidate.get("members") or [primary]

    source_ids: list[UUID] = []
    for m in members:
        sid = _upsert_source(cur, m.get("bronze") or {})
        source_ids.append(sid)

    urls = _candidate_urls(candidate_wrap)
    headline = extraction.get("headline") or bronze.get("title") or ""
    state = extraction.get("state") or "Unknown"

    existing = _find_published_by_urls(cur, urls) or _find_published_by_headline(
        cur, state, headline
    )
    if existing:
        _attach_sources_to_incident(cur, existing, source_ids)
        return existing, False

    raw_lga = extraction.get("lga")
    lga = raw_lga.strip() if isinstance(raw_lga, str) and raw_lga.strip() else "Unspecified"
    location_precision = (
        "state"
        if lga == "Unspecified"
        else (extraction.get("location_precision") or "lga")
    )
    lat_lng = centroid_for_lga(state, None if lga == "Unspecified" else lga)
    lat, lng = (lat_lng or (9.0, 8.0))
    if extraction.get("lat") is not None and extraction.get("lng") is not None:
        try:
            lat = float(extraction["lat"])
            lng = float(extraction["lng"])
        except (TypeError, ValueError):
            pass

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
            location_precision,
            verification_status,
            min(1.0, 0.4 + 0.2 * len(source_ids)),
            candidate.get("corroboration_count") or len(source_ids),
            extraction.get("current_status") or "ongoing",
            headline,
        ),
    )
    incident_id = _row_scalar(cur.fetchone(), "incident_id")

    _attach_sources_to_incident(cur, incident_id, source_ids)
    primary_source = source_ids[0]

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
    return incident_id, True



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
            incident_id, _created = publish_incident_from_candidate(
                cur, payload, verification_status=verification
            )
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

