"""Cluster extracted silver rows into candidate incidents (entity resolution)."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
SILVER_DIR = ROOT / "data" / "silver"


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def cluster_key(extraction: dict[str, Any]) -> str:
    """Same location + date + event_type within tolerance → one cluster."""
    return "|".join(
        [
            _norm(extraction.get("event_type")),
            _norm(extraction.get("state")),
            _norm(extraction.get("lga")),
            _norm(str(extraction.get("date_reported") or "")),
        ]
    )


def run_cluster(extracted_path: Path) -> Path:
    SILVER_DIR.mkdir(parents=True, exist_ok=True)
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)

    with extracted_path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            ext = row.get("extraction") or {}
            if ext.get("rejected"):
                continue
            buckets[cluster_key(ext)].append(row)

    out = SILVER_DIR / f"clustered_{extracted_path.stem}.jsonl"
    with out.open("w", encoding="utf-8") as dst:
        for key, members in buckets.items():
            # Prefer member with most cited fields as cluster representative
            members_sorted = sorted(
                members,
                key=lambda m: len((m.get("extraction") or {}).get("fields") or []),
                reverse=True,
            )
            primary = members_sorted[0]
            outlets = {
                (m.get("bronze") or {}).get("outlet")
                for m in members_sorted
                if (m.get("bronze") or {}).get("outlet")
            }
            candidate = {
                "cluster_id": str(uuid4()),
                "cluster_key": key,
                "member_count": len(members_sorted),
                "independent_outlets": sorted(outlets),
                "corroboration_count": len(outlets),
                "primary": primary,
                "members": members_sorted,
                "clustered_at": datetime.now(timezone.utc).isoformat(),
            }
            dst.write(json.dumps(candidate) + "\n")

    print(f"[cluster] {len(buckets)} clusters → {out}")
    return out


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("extracted_path", type=Path)
    args = parser.parse_args()
    run_cluster(args.extracted_path)
