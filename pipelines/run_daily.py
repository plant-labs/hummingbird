#!/usr/bin/env python3
"""Daily Hummingbird pipeline: scrape → extract → cluster → verify → Postgres publish."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "schemas"))
sys.path.insert(0, str(ROOT / "pipelines" / "ingest"))
sys.path.insert(0, str(ROOT / "pipelines" / "extract"))
sys.path.insert(0, str(ROOT / "pipelines" / "cluster"))
sys.path.insert(0, str(ROOT / "pipelines" / "sync"))

from news_scraper import run_news_ingest, write_demo_bronze  # noqa: E402
from extract import run_extract  # noqa: E402
from cluster import run_cluster  # noqa: E402
from verify import run_verify  # noqa: E402
from postgres_sync import process_gold_candidates  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Hummingbird daily incident pipeline")
    parser.add_argument("--demo", action="store_true", help="Use offline demo bronze")
    parser.add_argument("--limit", type=int, default=8, help="Articles per outlet")
    parser.add_argument("--skip-db", action="store_true", help="Stop after gold; do not write Postgres")
    args = parser.parse_args()

    bronze = write_demo_bronze() if args.demo else run_news_ingest(limit_per_outlet=args.limit)
    extracted = run_extract(bronze)
    clustered = run_cluster(extracted)
    gold = run_verify(clustered)
    print(f"[daily] gold={gold}")

    if args.skip_db:
        return

    stats = process_gold_candidates(gold)
    print(f"[daily] done: {stats}")


if __name__ == "__main__":
    main()
