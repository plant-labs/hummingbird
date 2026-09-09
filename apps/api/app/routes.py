from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .config import get_settings
from .db import db_available, fetch_all, fetch_one, get_conn
from .demo_store import demo_store

router = APIRouter()

STATUS_ORDER = ["unconfirmed", "reported", "verified", "official_confirmation"]


class ReviewAction(BaseModel):
    notes: str | None = None


def _parse_types(types: str | None) -> list[str] | None:
    if not types:
        return None
    return [t.strip() for t in types.split(",") if t.strip()]


@router.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "store": "postgres" if db_available() else "demo"}


@router.get("/map/bubbles")
def map_bubbles(
    level: str = Query("lga", pattern="^(lga|state)$"),
    types: str | None = None,
    min_status: str = "reported",
    include_unconfirmed: bool = False,
) -> list[dict[str, Any]]:
    type_list = _parse_types(types)
    if not db_available():
        return demo_store.bubbles(
            level=level,
            types=type_list,
            min_status=min_status,
            include_unconfirmed=include_unconfirmed,
        )

    statuses = ["reported", "verified", "official_confirmation"]
    if include_unconfirmed or min_status == "unconfirmed":
        statuses = STATUS_ORDER[:]

    # Prefer cache; fall back to live aggregation
    cached = fetch_all(
        """
        SELECT geo_id, level, name, state, lga, lat, lng, count, intensity,
               by_type, dominant_verification
        FROM geo_agg_cache
        WHERE level = %s OR (%s = 'state' AND level = 'state')
        ORDER BY count DESC
        """,
        (level, level),
    )
    if cached and level == "lga":
        rows = [r for r in cached if r["level"] == "lga"]
        if type_list:
            # filter by recomputing from incidents when type filter present
            pass
        else:
            return [
                {
                    **r,
                    "by_type": r["by_type"] or {},
                    "dominant_verification": r["dominant_verification"],
                }
                for r in rows
            ]
    if cached and level == "state":
        # Aggregate LGA cache up to state if needed
        state_rows = [r for r in cached if r["level"] == "state"]
        if state_rows:
            return [
                {
                    **r,
                    "by_type": r["by_type"] or {},
                    "dominant_verification": r["dominant_verification"],
                }
                for r in state_rows
            ]

    sql = """
      SELECT
        CASE WHEN %s = 'state' OR i.lga IS NULL OR btrim(i.lga) = ''
          THEN 'state:' || lower(i.state)
          ELSE lower(i.state) || ':' || lower(btrim(i.lga))
        END AS geo_id,
        CASE WHEN %s = 'state' OR i.lga IS NULL OR btrim(i.lga) = ''
          THEN 'state' ELSE 'lga' END AS level,
        CASE WHEN %s = 'state' OR i.lga IS NULL OR btrim(i.lga) = ''
          THEN i.state ELSE i.lga END AS name,
        i.state,
        CASE WHEN %s = 'state' THEN NULL ELSE NULLIF(btrim(i.lga), '') END AS lga,
        AVG(ST_Y(i.geom::geometry)) AS lat,
        AVG(ST_X(i.geom::geometry)) AS lng,
        COUNT(*)::INT AS count,
        LN(COUNT(*) + 1)::REAL AS intensity
      FROM incidents i
      WHERE i.published_at IS NOT NULL
        AND i.verification_status::text = ANY(%s)
        AND i.geom IS NOT NULL
        AND (%s::text[] IS NULL OR i.event_type::text = ANY(%s))
      GROUP BY 1, 2, 3, 4, 5
      ORDER BY count DESC
    """
    return fetch_all(
        sql,
        (level, level, level, level, statuses, type_list, type_list),
    )


@router.get("/map/bubbles/{geo_id}/incidents")
def bubble_incidents(
    geo_id: str,
    types: str | None = None,
    min_status: str = "reported",
    include_unconfirmed: bool = False,
) -> list[dict[str, Any]]:
    type_list = _parse_types(types)
    if not db_available():
        rows = demo_store.incidents_for_geo(
            geo_id,
            types=type_list,
            min_status=min_status,
            include_unconfirmed=include_unconfirmed,
        )
        return [
            {
                "incident_id": r["incident_id"],
                "event_type": r["event_type"],
                "date_occurred": r.get("date_occurred"),
                "date_reported": r["date_reported"],
                "state": r["state"],
                "lga": r.get("lga"),
                "lat": r.get("lat"),
                "lng": r.get("lng"),
                "verification_status": r["verification_status"],
                "confidence_score": r["confidence_score"],
                "corroboration_count": r["corroboration_count"],
                "current_status": r["current_status"],
                "headline": r.get("headline"),
            }
            for r in rows
        ]

    statuses = ["reported", "verified", "official_confirmation"]
    if include_unconfirmed or min_status == "unconfirmed":
        statuses = STATUS_ORDER[:]

    if geo_id.startswith("state:"):
        state = geo_id.split(":", 1)[1]
        sql = """
          SELECT incident_id, event_type, date_occurred, date_reported, state, lga,
                 ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lng,
                 verification_status, confidence_score, corroboration_count,
                 current_status, headline
          FROM incidents
          WHERE published_at IS NOT NULL
            AND verification_status::text = ANY(%s)
            AND lower(state) = %s
            AND (%s::text[] IS NULL OR event_type::text = ANY(%s))
          ORDER BY date_reported DESC
        """
        return fetch_all(sql, (statuses, state, type_list, type_list))

    state, lga = geo_id.split(":", 1)
    sql = """
      SELECT incident_id, event_type, date_occurred, date_reported, state, lga,
             ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lng,
             verification_status, confidence_score, corroboration_count,
             current_status, headline
      FROM incidents
      WHERE published_at IS NOT NULL
        AND verification_status::text = ANY(%s)
        AND lower(state) = %s
        AND lower(btrim(COALESCE(lga, ''))) = %s
        AND (%s::text[] IS NULL OR event_type::text = ANY(%s))
      ORDER BY date_reported DESC
    """
    return fetch_all(sql, (statuses, state, lga, type_list, type_list))


@router.get("/incidents/{incident_id}")
def incident_detail(incident_id: str) -> dict[str, Any]:
    if not db_available():
        detail = demo_store.get_incident(incident_id)
        if not detail:
            raise HTTPException(404, "Incident not found")
        return detail

    incident = fetch_one(
        """
        SELECT incident_id, event_type, date_occurred, date_reported, state, lga,
               ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lng,
               location_precision, verification_status, confidence_score,
               corroboration_count, current_status, headline, published_at
        FROM incidents WHERE incident_id = %s
        """,
        (incident_id,),
    )
    if not incident:
        raise HTTPException(404, "Incident not found")

    fields = fetch_all(
        """
        SELECT field_name, value_json AS value, source_id, source_span, confidence
        FROM incident_fields WHERE incident_id = %s
        """,
        (incident_id,),
    )
    history = fetch_all(
        """
        SELECT from_status, to_status, changed_at, source_id, note
        FROM status_history WHERE incident_id = %s ORDER BY changed_at
        """,
        (incident_id,),
    )
    sources = fetch_all(
        """
        SELECT isrc.role, s.source_id, s.url, s.outlet, s.source_type, s.fetched_at,
               s.reliability_tier, s.excerpt, s.published_at
        FROM incident_sources isrc
        JOIN sources s ON s.source_id = isrc.source_id
        WHERE isrc.incident_id = %s
        ORDER BY isrc.linked_at
        """,
        (incident_id,),
    )
    return {
        **incident,
        "fields": fields,
        "status_history": history,
        "sources": [
            {
                "role": s["role"],
                "source": {
                    "source_id": s["source_id"],
                    "url": s["url"],
                    "outlet": s["outlet"],
                    "source_type": s["source_type"],
                    "fetched_at": s["fetched_at"],
                    "reliability_tier": s["reliability_tier"],
                    "excerpt": s["excerpt"],
                    "published_at": s.get("published_at"),
                },
            }
            for s in sources
        ],
    }


@router.get("/incidents/{incident_id}/sources")
def incident_sources(incident_id: str) -> list[dict[str, Any]]:
    detail = incident_detail(incident_id)
    return detail.get("sources") or []


@router.get("/stream")
async def event_stream() -> StreamingResponse:
    async def gen() -> AsyncIterator[str]:
        # Lightweight heartbeat SSE; Postgres LISTEN can be wired when DB is up
        yield f"data: {json.dumps({'event': 'connected', 'store': 'postgres' if db_available() else 'demo'})}\n\n"
        while True:
            await asyncio.sleep(15)
            yield f"data: {json.dumps({'event': 'heartbeat'})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


def _require_moderator(authorization: str | None) -> None:
    settings = get_settings()
    expected = f"Bearer {settings.moderator_token}"
    if authorization != expected:
        raise HTTPException(401, "Moderator auth required")


@router.get("/review")
def list_review(
    status: str = "pending",
    authorization: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    _require_moderator(authorization)
    if not db_available():
        return demo_store.list_review(status=status)
    return fetch_all(
        """
        SELECT queue_id, incident_id, candidate_json, status, priority, reason,
               reviewer_notes, created_at, reviewed_at, reviewed_by
        FROM review_queue
        WHERE status = %s
        ORDER BY priority ASC, created_at ASC
        """,
        (status,),
    )


@router.post("/review/{queue_id}/approve")
def approve_review(
    queue_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_moderator(authorization)
    if not db_available():
        incident_id = demo_store.approve(queue_id, "moderator")
        if not incident_id:
            raise HTTPException(404, "Queue item not found")
        return {"approved": True, "incident_id": incident_id}

    # Inline publish using sync module path
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root / "pipelines" / "sync"))
    sys.path.insert(0, str(root / "packages" / "schemas"))
    from postgres_sync import approve_queue_item

    incident_id = approve_queue_item(queue_id, reviewer="moderator")
    if not incident_id:
        raise HTTPException(404, "Queue item not found or not pending")
    return {"approved": True, "incident_id": incident_id}


@router.post("/review/{queue_id}/reject")
def reject_review(
    queue_id: str,
    body: ReviewAction | None = None,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_moderator(authorization)
    notes = (body.notes if body else None) or ""
    if not db_available():
        ok = demo_store.reject(queue_id, "moderator", notes)
        if not ok:
            raise HTTPException(404, "Queue item not found")
        return {"rejected": True}

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE review_queue
                SET status = 'rejected', reviewed_at = now(), reviewed_by = 'moderator',
                    reviewer_notes = %s
                WHERE queue_id = %s AND status = 'pending'
                """,
                (notes, queue_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(404, "Queue item not found")
    return {"rejected": True}
