"""Normalize DATABASE_URL values from .env / GitHub Secrets / Railway."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def normalize_database_url(raw: str) -> str:
    """Strip quotes / prefixes that break psycopg URI parsing."""
    url = (raw or "").strip()
    if not url:
        return url

    # Common paste mistakes from .env files and secret UIs
    if (url.startswith('"') and url.endswith('"')) or (url.startswith("'") and url.endswith("'")):
        url = url[1:-1].strip()
    if url.startswith("DATABASE_URL="):
        url = url.split("=", 1)[1].strip().strip('"').strip("'")

    if not (url.startswith("postgresql://") or url.startswith("postgres://")):
        raise ValueError(
            "DATABASE_URL must start with postgresql:// or postgres:// "
            "(do not wrap the secret in quotes)"
        )

    # Neon sometimes adds channel_binding=require; drop it for broader client compatibility
    parsed = urlparse(url)
    if parsed.query:
        pairs = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k != "channel_binding"]
        url = urlunparse(parsed._replace(query=urlencode(pairs)))

    return url
