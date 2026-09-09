"""News ingest → bronze JSONL payloads (Phase-1).

Fetches real outlet pages and Google News RSS (Nigeria security queries),
normalizes to BronzePayload, and writes immutable JSONL under data/bronze/.
"""

from __future__ import annotations

import hashlib
import re
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from hummingbird_schemas import BronzePayload, SourceType

ROOT = Path(__file__).resolve().parents[2]
BRONZE_DIR = ROOT / "data" / "bronze"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-NG,en;q=0.9",
}


@dataclass
class OutletConfig:
    name: str
    list_url: str
    article_link_selector: str
    base_url: str
    title_selector: str = "h1"
    body_selector: str = "article p, .entry-content p, .post-content p, .story-content p"


OUTLETS: list[OutletConfig] = [
    OutletConfig(
        name="Punch",
        list_url="https://punchng.com/?s=kidnap",
        article_link_selector="h2 a, .post-title a, article a",
        base_url="https://punchng.com",
    ),
    OutletConfig(
        name="Premium Times",
        list_url="https://www.premiumtimesng.com/?s=kidnap",
        article_link_selector="h3 a, .entry-title a, article a",
        base_url="https://www.premiumtimesng.com",
    ),
    OutletConfig(
        name="Vanguard",
        list_url="https://www.vanguardngr.com/?s=kidnap",
        article_link_selector="h2 a, .entry-title a, article a",
        base_url="https://www.vanguardngr.com",
    ),
    OutletConfig(
        name="Daily Trust",
        list_url="https://dailytrust.com/?s=kidnap",
        article_link_selector="h2 a, .entry-title a, article a",
        base_url="https://dailytrust.com",
    ),
]

# Google News RSS is more scrape-resistant and returns real publisher URLs.
GOOGLE_NEWS_QUERIES = [
    "kidnap OR abducted OR abduction Nigeria",
    "bandits OR gunmen kidnap Nigeria",
    "armed robbery Nigeria",
    "protest insecurity Nigeria",
]

KNOWN_OUTLETS = {
    "punchng.com": "Punch",
    "premiumtimesng.com": "Premium Times",
    "vanguardngr.com": "Vanguard",
    "dailytrust.com": "Daily Trust",
    "guardian.ng": "The Guardian Nigeria",
    "channelstv.com": "Channels TV",
    "thisdaylive.com": "THISDAY",
    "tribuneonlineng.com": "Nigerian Tribune",
    "thenationonlineng.net": "The Nation",
}

SECURITY_KEYWORDS = re.compile(
    r"\b(kidnap|abduct|bandit|insurgent|robbery|protest|scam|terror|"
    r"gunmen|ransom|attack|traffick)\b",
    re.I,
)


def content_hash(url: str, body: str) -> str:
    return hashlib.sha256(f"{url}\n{body}".encode("utf-8")).hexdigest()


def is_real_article_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    if not host or "example.com" in host or host.endswith("google.com"):
        return False
    return url.startswith("http://") or url.startswith("https://")


def write_bronze(records: Iterable[BronzePayload], run_id: str) -> Path:
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    out = BRONZE_DIR / f"news_{run_id}.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for rec in records:
            if not rec.url or not is_real_article_url(rec.url):
                continue
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
        if not is_real_article_url(full):
            continue
        if cfg.base_url.split("//")[-1].split("/")[0] not in urlparse(full).netloc:
            continue
        if full not in urls:
            urls.append(full)
        if len(urls) >= limit:
            break
    return urls


def parse_article(html: str, cfg: Optional[OutletConfig] = None) -> tuple[Optional[str], str]:
    soup = BeautifulSoup(html, "html.parser")
    title_sel = (cfg.title_selector if cfg else "h1") 
    body_sel = (
        cfg.body_selector
        if cfg
        else "article p, .entry-content p, .post-content p, .story-content p, p"
    )
    title_el = soup.select_one(title_sel)
    title = title_el.get_text(strip=True) if title_el else None
    paragraphs = [p.get_text(" ", strip=True) for p in soup.select(body_sel)]
    # Prefer longer article paragraphs; drop nav crumbs
    body = "\n".join(p for p in paragraphs if len(p) > 40)
    if len(body) < 80:
        body = "\n".join(p for p in paragraphs if p)
    return title, body


def outlet_for_url(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    for domain, name in KNOWN_OUTLETS.items():
        if host.endswith(domain):
            return name
    return host or "unknown"


def unwrap_google_news_link(link: str) -> str:
    """Best-effort unwrap of Google News redirect URLs."""
    if "news.google.com" not in link:
        return link
    parsed = urlparse(link)
    qs = parse_qs(parsed.query)
    for key in ("url", "q"):
        if key in qs and qs[key]:
            candidate = unquote(qs[key][0])
            if candidate.startswith("http"):
                return candidate
    return link


def fetch_google_news(client: httpx.Client, run_id: str, limit: int = 12) -> list[BronzePayload]:
    records: list[BronzePayload] = []
    seen: set[str] = set()
    for query in GOOGLE_NEWS_QUERIES:
        rss_url = (
            "https://news.google.com/rss/search?"
            f"q={quote_plus(query + ' when:7d')}"
            "&hl=en-NG&gl=NG&ceid=NG:en"
        )
        try:
            resp = client.get(rss_url, follow_redirects=True, timeout=30.0)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] google news failed for '{query}': {exc}")
            continue

        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError as exc:
            print(f"[warn] google news XML parse failed: {exc}")
            continue

        for item in root.findall("./channel/item"):
            title = (item.findtext("title") or "").strip()
            link = unwrap_google_news_link((item.findtext("link") or "").strip())
            source_name = (item.findtext("source") or "").strip() or outlet_for_url(link)
            description = BeautifulSoup(item.findtext("description") or "", "html.parser").get_text(
                " ", strip=True
            )
            if not link or link in seen or not is_real_article_url(link):
                # Google often returns news.google.com links; try to follow once
                if "news.google.com" in link and link not in seen:
                    try:
                        followed = client.get(link, follow_redirects=True, timeout=30.0)
                        link = str(followed.url)
                    except Exception:  # noqa: BLE001
                        continue
                if not is_real_article_url(link) or link in seen:
                    continue

            text_blob = f"{title}\n{description}"
            if not SECURITY_KEYWORDS.search(text_blob):
                continue

            body = description
            try:
                art = client.get(link, follow_redirects=True, timeout=30.0)
                if art.status_code < 400:
                    link = str(art.url)
                    if not is_real_article_url(link):
                        continue
                    t2, body2 = parse_article(art.text)
                    if t2:
                        title = t2
                    if len(body2) > len(body):
                        body = body2
                    source_name = outlet_for_url(link) if source_name == "unknown" else source_name
            except Exception as exc:  # noqa: BLE001
                print(f"[warn] article fetch failed {link}: {exc}")

            if len(body) < 40:
                continue
            if not is_real_article_url(link):
                continue

            seen.add(link)
            records.append(
                BronzePayload(
                    content_hash=content_hash(link, body),
                    source_type=SourceType.NEWS,
                    fetched_at=datetime.now(timezone.utc),
                    ingest_run_id=run_id,
                    url=link,
                    outlet=source_name,
                    title=title,
                    body=body,
                    payload={
                        "outlet": source_name,
                        "url": link,
                        "title": title,
                        "body": body,
                        "via": "google_news_rss",
                        "query": query,
                    },
                )
            )
            if len(records) >= limit:
                return records
    return records


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
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] list fetch failed for {cfg.name}: {exc}")
        return records

    for url in parse_list_links(list_resp.text, cfg, limit=limit):
        try:
            art = client.get(url, follow_redirects=True, timeout=30.0)
            art.raise_for_status()
            url = str(art.url)
            if not is_real_article_url(url):
                continue
            title, body = parse_article(art.text, cfg)
            text_blob = f"{title or ''}\n{body}"
            if not SECURITY_KEYWORDS.search(text_blob):
                continue
            if len(body) < 80:
                continue
            records.append(
                BronzePayload(
                    content_hash=content_hash(url, body),
                    source_type=SourceType.NEWS,
                    fetched_at=datetime.now(timezone.utc),
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
    all_records: list[BronzePayload] = []
    with httpx.Client(headers=BROWSER_HEADERS, timeout=30.0) as client:
        print("[ingest] Google News RSS")
        all_records.extend(fetch_google_news(client, run_id, limit=max(12, limit_per_outlet * 3)))
        for cfg in OUTLETS:
            print(f"[ingest] {cfg.name}")
            all_records.extend(fetch_outlet(client, cfg, run_id, limit=limit_per_outlet))

    # Dedupe by URL
    deduped: dict[str, BronzePayload] = {}
    for rec in all_records:
        if rec.url and is_real_article_url(rec.url):
            deduped[rec.url] = rec
    path = write_bronze(deduped.values(), run_id)
    print(f"[ingest] wrote {len(deduped)} bronze records → {path}")
    return path


def write_demo_bronze() -> Path:
    """Offline-only fixture. Never used by production daily workflow."""
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
    # Demo writer bypasses is_real_article_url filter intentionally for local tests.
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    out = BRONZE_DIR / f"news_{run_id}.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(rec.model_dump_json() + "\n")
    print(f"[ingest] wrote DEMO {len(records)} bronze records → {out}")
    return out


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
