"""Corroboration gates + routing for auto-publish vs human review."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
GOLD_DIR = ROOT / "data" / "gold"

# Fatality fields always force human review before publish.
# victim_count may auto-publish with a source citation (still labeled Reported).
HUMAN_REVIEW_FIELDS = {"casualties", "fatality_count"}

# Default 1 so the live map fills from daily news; set to 2 for stricter methodology.
AUTO_PUBLISH_MIN_SOURCES = int(os.getenv("AUTO_PUBLISH_MIN_SOURCES", "1"))


def compute_verification(candidate: dict[str, Any]) -> tuple[str, str]:
    """Return (verification_status, route).

    Routes:
      - auto_publish: enough independent outlets (or official), no casualty/headcount fields
      - review: needs human (casualty fields, or weak cases still worth reviewing)
      - quarantine: too weak
    """
    outlets = candidate.get("independent_outlets") or []
    corroboration = int(candidate.get("corroboration_count") or len(outlets))
    members = candidate.get("members") or []

    source_types = set()
    for m in members:
        st = ((m.get("bronze") or {}).get("source_type")) or "news"
        source_types.add(st)

    has_official = "official" in source_types
    fields = ((candidate.get("primary") or {}).get("extraction") or {}).get("fields") or []
    field_names = {f.get("field_name") for f in fields}
    needs_human = bool(field_names & HUMAN_REVIEW_FIELDS)

    strong = has_official or corroboration >= max(AUTO_PUBLISH_MIN_SOURCES, 1)
    # Stricter label when only one non-official source
    status = "reported" if (has_official or corroboration >= 2) else (
        "reported" if corroboration >= 1 else "unconfirmed"
    )

    if strong and not needs_human and corroboration >= 1:
        return status, "auto_publish"
    if (strong or corroboration >= 1) and needs_human:
        return status, "review"
    if corroboration == 1:
        return "unconfirmed", "review"
    return "unconfirmed", "quarantine"


def run_verify(clustered_path: Path) -> Path:
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    out = GOLD_DIR / f"candidates_{clustered_path.stem}.jsonl"
    queued = 0
    with clustered_path.open(encoding="utf-8") as src, out.open("w", encoding="utf-8") as dst:
        for line in src:
            if not line.strip():
                continue
            candidate = json.loads(line)
            status, route = compute_verification(candidate)
            primary_ext = (candidate.get("primary") or {}).get("extraction") or {}
            item = {
                "queue_id": str(uuid4()),
                "verification_status": status,
                "route": route,
                "priority": 20 if route == "auto_publish" else (40 if status == "reported" else 80),
                "reason": (
                    f"route={route}; corroboration={candidate.get('corroboration_count')}; "
                    f"outlets={candidate.get('independent_outlets')}"
                ),
                "candidate": candidate,
                "publish_preview": {
                    "event_type": primary_ext.get("event_type"),
                    "state": primary_ext.get("state"),
                    "lga": primary_ext.get("lga"),
                    "headline": primary_ext.get("headline"),
                    "current_status": primary_ext.get("current_status"),
                    "corroboration_count": candidate.get("corroboration_count"),
                    "verification_status": status,
                },
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            dst.write(json.dumps(item) + "\n")
            queued += 1
    print(f"[verify] {queued} candidates → {out}")
    return out


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("clustered_path", type=Path)
    args = parser.parse_args()
    run_verify(args.clustered_path)
