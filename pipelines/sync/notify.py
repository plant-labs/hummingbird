"""Notify moderators when a review_queue item becomes pending.

Used by the tip API and the daily pipeline. Supports Resend email and an
optional Slack/Discord webhook (REPORT_NOTIFY_WEBHOOK or REVIEW_NOTIFY_WEBHOOK).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("hummingbird.notify")


def require_human_approval() -> bool:
    """When true (default), pipeline candidates never auto-publish to the map."""
    raw = (os.getenv("REQUIRE_HUMAN_APPROVAL") or "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _webhook_url() -> str:
    return (
        (os.getenv("REVIEW_NOTIFY_WEBHOOK") or "").strip()
        or (os.getenv("REPORT_NOTIFY_WEBHOOK") or "").strip()
    )


def _moderation_url() -> str:
    base = (os.getenv("PUBLIC_WEB_URL") or os.getenv("WEB_APP_URL") or "").strip().rstrip("/")
    if not base:
        return "/moderation"
    return f"{base}/moderation"


def _preview(item: dict[str, Any]) -> dict[str, Any]:
    return item.get("publish_preview") or {}


def _source_urls(item: dict[str, Any]) -> list[str]:
    preview = _preview(item)
    urls: list[str] = []
    single = (preview.get("source_url") or "").strip()
    if single:
        urls.append(single)
    candidate = item.get("candidate") or {}
    primary = candidate.get("primary") or {}
    members = candidate.get("members") or ([primary] if primary else [])
    for m in members:
        bronze = m.get("bronze") or {}
        url = (bronze.get("url") or "").strip()
        if url and url not in urls and "example.com" not in url:
            urls.append(url)
    tip = item.get("tip") or {}
    # tip source already on preview
    _ = tip
    return urls


def _route_label(item: dict[str, Any]) -> str:
    route = (item.get("route") or "").strip()
    if route == "crowd_tip":
        return "Crowd tip"
    if route == "auto_publish":
        return "Pipeline (was auto-publish)"
    if route:
        return f"Pipeline ({route})"
    return "Pipeline"


def _summary_text(item: dict[str, Any]) -> str:
    preview = _preview(item)
    headline = preview.get("headline") or "Untitled candidate"
    place = ", ".join(p for p in [preview.get("lga"), preview.get("state")] if p) or "Unknown place"
    et = preview.get("event_type") or "unknown"
    return f"{_route_label(item)}: {headline} ({et} · {place})"


def _email_html(item: dict[str, Any]) -> str:
    preview = _preview(item)
    urls = _source_urls(item)
    mod_url = _moderation_url()
    lines = [
        f"<p><strong>{_route_label(item)}</strong> needs review before it can appear on the map.</p>",
        f"<p><strong>Headline:</strong> {preview.get('headline') or 'Untitled'}</p>",
        f"<p><strong>Type:</strong> {preview.get('event_type') or 'unknown'}<br/>",
        f"<strong>Place:</strong> {', '.join(p for p in [preview.get('lga'), preview.get('state')] if p) or '—'}<br/>",
        f"<strong>Verification:</strong> {preview.get('verification_status') or '—'}<br/>",
        f"<strong>Queue id:</strong> {item.get('queue_id')}</p>",
    ]
    if item.get("reason"):
        lines.append(f"<p><strong>Reason:</strong> {item.get('reason')}</p>")
    tip = item.get("tip") or {}
    if tip.get("description"):
        lines.append(f"<p><strong>Tip details:</strong> {tip.get('description')}</p>")
    if urls:
        link_bits = "".join(f'<li><a href="{u}">{u}</a></li>' for u in urls[:5])
        lines.append(f"<p><strong>Sources:</strong></p><ul>{link_bits}</ul>")
    lines.append(f'<p><a href="{mod_url}">Open moderation queue</a> to approve or reject.</p>')
    return "\n".join(lines)


def _send_email(item: dict[str, Any]) -> bool:
    api_key = (os.getenv("RESEND_API_KEY") or "").strip()
    to_addr = (os.getenv("MODERATOR_NOTIFY_EMAIL") or "").strip()
    from_addr = (os.getenv("NOTIFY_FROM_EMAIL") or "").strip() or "Hummingbird <onboarding@resend.dev>"
    if not api_key or not to_addr:
        logger.info(
            "email notify skipped (set RESEND_API_KEY and MODERATOR_NOTIFY_EMAIL) queue_id=%s",
            item.get("queue_id"),
        )
        return False
    preview = _preview(item)
    subject = f"[Hummingbird] Review: {preview.get('headline') or item.get('queue_id')}"
    payload = {
        "from": from_addr,
        "to": [to_addr],
        "subject": subject[:200],
        "html": _email_html(item),
        "text": f"{_summary_text(item)}\n\nApprove or reject: {_moderation_url()}",
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
        logger.info("email notify sent queue_id=%s to=%s", item.get("queue_id"), to_addr)
        return True
    except Exception:
        logger.exception("email notify failed queue_id=%s", item.get("queue_id"))
        return False


def _send_webhook(item: dict[str, Any]) -> bool:
    webhook = _webhook_url()
    if not webhook:
        return False
    preview = _preview(item)
    tip = item.get("tip") or {}
    payload = {
        "text": f"Hummingbird review needed — {_summary_text(item)}",
        "queue_id": item.get("queue_id"),
        "route": item.get("route"),
        "event_type": preview.get("event_type"),
        "state": preview.get("state"),
        "lga": preview.get("lga"),
        "headline": preview.get("headline"),
        "source_url": (_source_urls(item) or [None])[0],
        "source_urls": _source_urls(item),
        "has_attachment": preview.get("has_attachment"),
        "contact_email": tip.get("contact_email"),
        "moderation_url": _moderation_url(),
        "reason": item.get("reason"),
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(webhook, json=payload)
            resp.raise_for_status()
        return True
    except Exception:
        logger.exception("webhook notify failed queue_id=%s", item.get("queue_id"))
        return False


def notify_pending_review(item: dict[str, Any]) -> bool:
    """Send email and/or webhook for a newly pending review item. Returns True if any channel succeeded."""
    logger.info(
        "pending review notify queue_id=%s route=%s headline=%s",
        item.get("queue_id"),
        item.get("route"),
        (_preview(item).get("headline")),
    )
    emailed = _send_email(item)
    hooked = _send_webhook(item)
    return emailed or hooked
