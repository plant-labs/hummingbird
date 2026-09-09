"""Corroboration gates + review queue enqueue from clustered silver candidates."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
GOLD_DIR = ROOT / "data" / "gold"

# Fields that always force human review before publish
HUMAN_REVIEW_FIELDS = {"victim_count", "casualties", "fatality_count"}


def compute_verification(candidate: dict[str, Any]) -> tuple[str, str]:
    """Return (verification_status, routing): auto_reported | review | quarantine."""
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

    if has_official and not needs_human:
        return "reported", "review"  # still human gate for first publish in MVP
    if corroboration >= 2 and not needs_human:
        return "reported", "review"
    if corroboration >= 2 and needs_human:
        return "reported", "review"
    if corroboration == 1 and has_official:
        return "reported", "review"
    if corroboration <= 1:
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
                "priority": 40 if status == "reported" else 80,
                "reason": (
                    f"corroboration={candidate.get('corroboration_count')}; "
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
