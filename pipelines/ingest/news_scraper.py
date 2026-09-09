"""News ingest → bronze JSONL payloads (Phase-1).

Scrapers fetch article listings, normalize to BronzePayload, and write
immutable JSON lines under data/bronze/ for Databricks or local extract jobs.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from hummingbird_schemas import BronzePayload, SourceType

ROOT = Path(__file__).resolve().parents[2]
BRONZE_DIR = ROOT / "data" / "bronze"


@dataclass
class OutletConfig:
    name: str
    list_url: str
    article_link_selector: str
    base_url: str
    title_selector: str = "h1"
    body_selector: str = "article p, .entry-content p, .post-content p"


# Conservative starters — selectors may need tuning per site redesigns.
OUTLETS: list[OutletConfig] = [
    OutletConfig(
        name="Punch",
        list_url="https://punchng.com/?s=kidnap",
        article_link_selector="h2 a, .post-title a",
        base_url="https://punchng.com",
    ),
    OutletConfig(
        name="Premium Times",
        list_url="https://www.premiumtimesng.com/?s=kidnap",
        article_link_selector="h3 a, .entry-title a",
        base_url="https://www.premiumtimesng.com",
    ),
    OutletConfig(
        name="Vanguard",
        list_url="https://www.vanguardngr.com/?s=kidnap",
        article_link_selector="h2 a, .entry-title a",
        base_url="https://www.vanguardngr.com",
    ),
    OutletConfig(
        name="Daily Trust",
        list_url="https://dailytrust.com/?s=kidnap",
        article_link_selector="h2 a, .entry-title a",
        base_url="https://dailytrust.com",
    ),
]

SECURITY_KEYWORDS = re.compile(
    r"\b(kidnap|abduct|bandit|insurgent|robbery|protest|scam|terror|"
    r"gunmen|ransom|attack)\b",
    re.I,
)


def content_hash(url: str, body: str) -> str:
    return hashlib.sha256(f"{url}\n{body}".encode("utf-8")).hexdigest()


def write_bronze(records: Iterable[BronzePayload], run_id: str) -> Path:
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    out = BRONZE_DIR / f"news_{run_id}.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(rec.model_dump_json() + "\n")
    return out


def parse_list_links(html: str, cfg: OutletConfig, limit: int = 10) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    for a in soup.select(cfg.article_link_selector):
        href = a.get("href")
        if not href:
            continue
        full = urljoin(cfg.base_url, href)
        if full not in urls:
            urls.append(full)
        if len(urls) >= limit:
            break
    return urls


def parse_article(html: str, cfg: OutletConfig) -> tuple[Optional[str], str]:
    soup = BeautifulSoup(html, "html.parser")
    title_el = soup.select_one(cfg.title_selector)
    title = title_el.get_text(strip=True) if title_el else None
    paragraphs = [p.get_text(" ", strip=True) for p in soup.select(cfg.body_selector)]
    body = "\n".join(p for p in paragraphs if p)
    return title, body


def fetch_outlet(
    client: httpx.Client,
    cfg: OutletConfig,
    run_id: str,
    limit: int = 5,
) -> list[BronzePayload]:
    records: list[BronzePayload] = []
    try:
        list_resp = client.get(cfg.list_url, follow_redirects=True, timeout=30.0)
        list_resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001 — continue other outlets
        print(f"[warn] list fetch failed for {cfg.name}: {exc}")
        return records

    for url in parse_list_links(list_resp.text, cfg, limit=limit):
        try:
            art = client.get(url, follow_redirects=True, timeout=30.0)
            art.raise_for_status()
            title, body = parse_article(art.text, cfg)
            text_blob = f"{title or ''}\n{body}"
            if not SECURITY_KEYWORDS.search(text_blob):
                continue
            if len(body) < 80:
                continue
            fetched_at = datetime.now(timezone.utc)
            ch = content_hash(url, body)
            records.append(
                BronzePayload(
                    content_hash=ch,
                    source_type=SourceType.NEWS,
                    fetched_at=fetched_at,
                    ingest_run_id=run_id,
                    url=url,
                    outlet=cfg.name,
                    title=title,
                    body=body,
                    payload={
                        "outlet": cfg.name,
                        "url": url,
                        "title": title,
                        "body": body,
                        "list_url": cfg.list_url,
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] article fetch failed {url}: {exc}")
    return records


def run_news_ingest(limit_per_outlet: int = 5) -> Path:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    headers = {
        "User-Agent": "HummingbirdBot/0.1 (+https://github.com/hummingbird; research)"
    }
    all_records: list[BronzePayload] = []
    with httpx.Client(headers=headers) as client:
        for cfg in OUTLETS:
            print(f"[ingest] {cfg.name}")
            all_records.extend(fetch_outlet(client, cfg, run_id, limit=limit_per_outlet))
    path = write_bronze(all_records, run_id)
    print(f"[ingest] wrote {len(all_records)} bronze records → {path}")
    return path


def write_demo_bronze() -> Path:
    """Offline-friendly sample bronze for local pipeline tests."""
    run_id = "demo_" + uuid.uuid4().hex[:8]
    samples = [
        {
            "outlet": "Punch",
            "url": "https://example.com/punch/demo-kaduna",
            "title": "Gunmen abduct travelers on Kaduna-Abuja highway",
            "body": (
                "Gunmen abducted 12 travelers along the Kaduna-Abuja highway in Chikun "
                "Local Government Area of Kaduna State on Monday. Police said negotiations "
                "have not begun. No casualty figure was confirmed."
            ),
        },
        {
            "outlet": "Daily Trust",
            "url": "https://example.com/dailytrust/demo-kaduna",
            "title": "12 passengers kidnapped on Kaduna road",
            "body": (
                "At least 12 passengers were kidnapped on the Kaduna-Abuja road near Chikun, "
                "Kaduna State. Residents said the victims were travelers. The incident is ongoing."
            ),
        },
        {
            "outlet": "Vanguard",
            "url": "https://example.com/vanguard/demo-lagos-scam",
            "title": "Investment scam hits Lagos Island residents",
            "body": (
                "An investment scam syndicate defrauded residents in Lagos Island, Lagos State. "
                "Victims were promised crypto returns. Police advise the public to be wary."
            ),
        },
    ]
    records: list[BronzePayload] = []
    now = datetime.now(timezone.utc)
    for s in samples:
        body = s["body"]
        records.append(
            BronzePayload(
                content_hash=content_hash(s["url"], body),
                source_type=SourceType.NEWS,
                fetched_at=now,
                ingest_run_id=run_id,
                url=s["url"],
                outlet=s["outlet"],
                title=s["title"],
                body=body,
                payload=s,
            )
        )
    return write_bronze(records, run_id)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Hummingbird news → bronze ingest")
    parser.add_argument("--demo", action="store_true", help="Write demo bronze without network")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    if args.demo:
        write_demo_bronze()
    else:
        run_news_ingest(limit_per_outlet=args.limit)
