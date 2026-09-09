#!/usr/bin/env python3
"""Run local Phase-1 pipeline: demo bronze → extract → cluster → verify → enqueue."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "schemas"))
sys.path.insert(0, str(ROOT / "pipelines" / "ingest"))
sys.path.insert(0, str(ROOT / "pipelines" / "extract"))
sys.path.insert(0, str(ROOT / "pipelines" / "cluster"))
sys.path.insert(0, str(ROOT / "pipelines" / "sync"))

from news_scraper import write_demo_bronze  # noqa: E402
from extract import run_extract  # noqa: E402
from cluster import run_cluster  # noqa: E402
from verify import run_verify  # noqa: E402


def main() -> None:
    bronze = write_demo_bronze()
    extracted = run_extract(bronze)
    clustered = run_cluster(extracted)
    gold = run_verify(clustered)
    print(f"Pipeline complete. Gold candidates: {gold}")
    print("To enqueue into Postgres: python -m pipelines.sync.postgres_sync", gold)


if __name__ == "__main__":
    main()
