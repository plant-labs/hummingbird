from __future__ import annotations

import asyncio
import base64
import json
import logging
from datetime import date, datetime, timezone
from typing import Any, AsyncIterator
from uuid import uuid4

import httpx
from fastapi import APIRouter, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from psycopg.types.json import Json
from pydantic import BaseModel

from .config import get_settings
from .db import db_available, fetch_all, fetch_one, get_conn
from .demo_store import demo_store

router = APIRouter()
logger = logging.getLogger("hummingbird.reports")

STATUS_ORDER = ["unconfirmed", "reported", "verified", "official_confirmation"]

EVENT_TYPES = {
    "kidnap",
    "robbery",
    "terrorism",
    "protest",
    "scam",
    "battle",
    "explosion",
    "other",
}
INCIDENT_STATUSES = {
    "ongoing",
    "in_negotiation",
    "released",
    "rescued",
    "casualty_confirmed",
    "unresolved",
}
NIGERIA_STATES = {
    "Abia",
    "Adamawa",
    "Akwa Ibom",
    "Anambra",
    "Bauchi",
    "Bayelsa",
    "Benue",
    "Borno",
    "Cross River",
    "Delta",
    "Ebonyi",
    "Edo",
    "Ekiti",
    "Enugu",
    "FCT",
    "Gombe",
    "Imo",
    "Jigawa",
    "Kaduna",
    "Kano",
    "Katsina",
    "Kebbi",
    "Kogi",
    "Kwara",
    "Lagos",
    "Nasarawa",
    "Niger",
    "Ogun",
    "Ondo",
    "Osun",
    "Oyo",
    "Plateau",
    "Rivers",
    "Sokoto",
    "Taraba",
    "Yobe",
    "Zamfara",
}
MAX_ATTACHMENT_BYTES = 4 * 1024 * 1024


class ReviewAction(BaseModel):
    notes: str | None = None


class ReportResponse(BaseModel):
    queue_id: str
    notified: bool = False
    message: str = "Report queued for investigation"


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


def _normalize_state(raw: str) -> str:
    key = raw.strip()
    for state in NIGERIA_STATES:
        if state.lower() == key.lower():
            return state
    raise HTTPException(400, f"Unknown state: {raw}")


def _parse_optional_float(raw: str | None, field: str) -> float | None:
    if raw is None or not str(raw).strip():
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise HTTPException(400, f"Invalid {field}") from exc


def _parse_optional_int(raw: str | None, field: str) -> int | None:
    if raw is None or not str(raw).strip():
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise HTTPException(400, f"Invalid {field}") from exc


def _parse_optional_date(raw: str | None, field: str) -> str | None:
    if raw is None or not str(raw).strip():
        return None
    try:
        return date.fromisoformat(raw.strip()).isoformat()
    except ValueError as exc:
        raise HTTPException(400, f"Invalid {field} (use YYYY-MM-DD)") from exc


async def _read_attachment(upload: UploadFile | None) -> dict[str, Any] | None:
    if upload is None or not upload.filename:
        return None
    data = await upload.read()
    if not data:
        return None
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(400, "Attachment must be 4 MB or smaller")
    content_type = upload.content_type or "application/octet-stream"
    if not (
        content_type.startswith("image/")
        or content_type in {"application/pdf", "application/octet-stream"}
    ):
        # Allow common browser PDF/octet fallbacks when extension is pdf/image
        name = (upload.filename or "").lower()
        if not (name.endswith(".pdf") or name.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))):
            raise HTTPException(400, "Attachment must be an image or PDF")
    return {
        "filename": upload.filename,
        "content_type": content_type,
        "size": len(data),
        "data_base64": base64.b64encode(data).decode("ascii"),
    }


def _build_tip_candidate(
    *,
    event_type: str,
    headline: str,
    description: str,
    state: str,
    date_reported: str,
    date_occurred: str | None,
    lga: str | None,
    lat: float | None,
    lng: float | None,
    current_status: str,
    victim_count: int | None,
    victim_type: str | None,
    source_url: str | None,
    contact_name: str | None,
    contact_email: str | None,
    attachment: dict[str, Any] | None,
) -> dict[str, Any]:
    queue_id = str(uuid4())
    location_precision = "state"
    if lat is not None and lng is not None:
        location_precision = "exact"
    elif lga:
        location_precision = "lga"

    fields: list[dict[str, Any]] = [
        {
            "field_name": "state",
            "value": state,
            "source_span": description[:500],
            "confidence": 0.4,
        },
        {
            "field_name": "event_type",
            "value": event_type,
            "source_span": description[:500],
            "confidence": 0.4,
        },
    ]
    if lga:
        fields.append(
            {
                "field_name": "lga",
                "value": lga,
                "source_span": description[:500],
                "confidence": 0.35,
            }
        )
    if victim_count is not None:
        fields.append(
            {
                "field_name": "victim_count",
                "value": victim_count,
                "source_span": description[:500],
                "confidence": 0.3,
            }
        )
    if victim_type:
        fields.append(
            {
                "field_name": "victim_type",
                "value": victim_type,
                "source_span": description[:500],
                "confidence": 0.3,
            }
        )
    fields.append(
        {
            "field_name": "current_status",
            "value": current_status,
            "source_span": description[:500],
            "confidence": 0.3,
        }
    )

    synthetic_url = source_url or f"urn:hummingbird:crowd-tip:{queue_id}"
    now = datetime.now(timezone.utc).isoformat()

    bronze = {
        "url": synthetic_url,
        "outlet": "Crowd tip",
        "source_type": "crowd",
        "title": headline,
        "body": description,
        "fetched_at": now,
        "content_hash": f"crowd-{queue_id}",
        "reliability_tier": 5,
    }
    extraction = {
        "event_type": event_type,
        "state": state,
        "lga": lga,
        "headline": headline,
        "date_occurred": date_occurred,
        "date_reported": date_reported,
        "location_precision": location_precision,
        "lat": lat,
        "lng": lng,
        "current_status": current_status,
        "fields": fields,
    }
    cluster_candidate = {
        "corroboration_count": 0,
        "independent_outlets": 1,
        "primary": {"bronze": bronze, "extraction": extraction},
        "members": [{"bronze": bronze, "extraction": extraction}],
    }

    return {
        "queue_id": queue_id,
        "verification_status": "unconfirmed",
        "route": "crowd_tip",
        "priority": 40,
        "reason": "Crowd tip — investigate before publish",
        "created_at": now,
        "publish_preview": {
            "event_type": event_type,
            "state": state,
            "lga": lga,
            "headline": headline,
            "date_occurred": date_occurred,
            "date_reported": date_reported,
            "location_precision": location_precision,
            "lat": lat,
            "lng": lng,
            "current_status": current_status,
            "verification_status": "unconfirmed",
            "corroboration_count": 0,
            "source_url": source_url,
            "has_attachment": bool(attachment),
        },
        "candidate": cluster_candidate,
        "tip": {
            "description": description,
            "contact_name": contact_name,
            "contact_email": contact_email,
            "attachment": (
                {
                    "filename": attachment["filename"],
                    "content_type": attachment["content_type"],
                    "size": attachment["size"],
                    "data_base64": attachment["data_base64"],
                }
                if attachment
                else None
            ),
        },
    }


def _notify_new_report(candidate: dict[str, Any]) -> bool:
    settings = get_settings()
    webhook = (settings.report_notify_webhook or "").strip()
    preview = candidate.get("publish_preview") or {}
    tip = candidate.get("tip") or {}
    payload = {
        "text": (
            f"New Hummingbird tip: {preview.get('headline')} "
            f"({preview.get('event_type')} · {preview.get('state')})"
        ),
        "queue_id": candidate.get("queue_id"),
        "event_type": preview.get("event_type"),
        "state": preview.get("state"),
        "lga": preview.get("lga"),
        "headline": preview.get("headline"),
        "source_url": preview.get("source_url"),
        "has_attachment": preview.get("has_attachment"),
        "contact_email": tip.get("contact_email"),
    }
    logger.info(
        "crowd tip queued queue_id=%s headline=%s state=%s attachment=%s",
        candidate.get("queue_id"),
        preview.get("headline"),
        preview.get("state"),
        preview.get("has_attachment"),
    )
    if not webhook:
        return False
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(webhook, json=payload)
            resp.raise_for_status()
        return True
    except Exception:
        logger.exception("report notify webhook failed")
        return False


@router.post("/reports", response_model=ReportResponse)
async def submit_report(
    event_type: str = Form(...),
    headline: str = Form(...),
    description: str = Form(...),
    state: str = Form(...),
    date_reported: str = Form(...),
    date_occurred: str | None = Form(default=None),
    lga: str | None = Form(default=None),
    lat: str | None = Form(default=None),
    lng: str | None = Form(default=None),
    current_status: str = Form(default="ongoing"),
    victim_count: str | None = Form(default=None),
    victim_type: str | None = Form(default=None),
    source_url: str | None = Form(default=None),
    contact_name: str | None = Form(default=None),
    contact_email: str | None = Form(default=None),
    attachment: UploadFile | None = File(default=None),
) -> ReportResponse:
    """Public tip line — enqueues review_queue only; never auto-publishes."""
    event_type = event_type.strip().lower()
    if event_type not in EVENT_TYPES:
        raise HTTPException(400, "Invalid event_type")
    current_status = (current_status or "ongoing").strip().lower()
    if current_status not in INCIDENT_STATUSES:
        raise HTTPException(400, "Invalid current_status")

    headline = headline.strip()
    description = description.strip()
    if len(headline) < 8:
        raise HTTPException(400, "Headline is too short")
    if len(description) < 20:
        raise HTTPException(400, "Description is too short")

    state_norm = _normalize_state(state)
    date_reported_norm = _parse_optional_date(date_reported, "date_reported")
    if not date_reported_norm:
        raise HTTPException(400, "date_reported is required")
    date_occurred_norm = _parse_optional_date(date_occurred, "date_occurred")
    lat_f = _parse_optional_float(lat, "lat")
    lng_f = _parse_optional_float(lng, "lng")
    if (lat_f is None) ^ (lng_f is None):
        raise HTTPException(400, "Provide both lat and lng, or neither")
    victim_n = _parse_optional_int(victim_count, "victim_count")
    lga_norm = lga.strip() if lga and lga.strip() else None
    victim_type_norm = victim_type.strip() if victim_type and victim_type.strip() else None
    source_url_norm = source_url.strip() if source_url and source_url.strip() else None
    contact_name_norm = contact_name.strip() if contact_name and contact_name.strip() else None
    contact_email_norm = contact_email.strip() if contact_email and contact_email.strip() else None

    attachment_meta = await _read_attachment(attachment)
    candidate = _build_tip_candidate(
        event_type=event_type,
        headline=headline,
        description=description,
        state=state_norm,
        date_reported=date_reported_norm,
        date_occurred=date_occurred_norm,
        lga=lga_norm,
        lat=lat_f,
        lng=lng_f,
        current_status=current_status,
        victim_count=victim_n,
        victim_type=victim_type_norm,
        source_url=source_url_norm,
        contact_name=contact_name_norm,
        contact_email=contact_email_norm,
        attachment=attachment_meta,
    )

    if not db_available():
        demo_store.enqueue_tip(candidate)
    else:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO review_queue (queue_id, candidate_json, status, priority, reason)
                    VALUES (%s, %s, 'pending', %s, %s)
                    """,
                    (
                        candidate["queue_id"],
                        Json(candidate),
                        candidate["priority"],
                        candidate["reason"],
                    ),
                )

    notified = _notify_new_report(candidate)
    return ReportResponse(queue_id=candidate["queue_id"], notified=notified)


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


def _sanitize_review_row(row: dict[str, Any]) -> dict[str, Any]:
    """Drop attachment binary from list payloads; keep filename/size metadata."""
    out = dict(row)
    candidate = out.get("candidate_json")
    if isinstance(candidate, str):
        try:
            candidate = json.loads(candidate)
        except json.JSONDecodeError:
            return out
    if not isinstance(candidate, dict):
        return out
    tip = candidate.get("tip")
    if isinstance(tip, dict):
        tip = dict(tip)
        att = tip.get("attachment")
        if isinstance(att, dict) and "data_base64" in att:
            tip["attachment"] = {
                "filename": att.get("filename"),
                "content_type": att.get("content_type"),
                "size": att.get("size"),
                "present": True,
            }
        candidate = {**candidate, "tip": tip}
    out["candidate_json"] = candidate
    return out


@router.get("/review")
def list_review(
    status: str = "pending",
    authorization: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    _require_moderator(authorization)
    if not db_available():
        return [_sanitize_review_row(r) for r in demo_store.list_review(status=status)]
    rows = fetch_all(
        """
        SELECT queue_id, incident_id, candidate_json, status, priority, reason,
               reviewer_notes, created_at, reviewed_at, reviewed_by
        FROM review_queue
        WHERE status = %s
        ORDER BY priority ASC, created_at ASC
        """,
        (status,),
    )
    return [_sanitize_review_row(r) for r in rows]


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
