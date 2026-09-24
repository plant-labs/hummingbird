from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import get_settings
from .db_url import normalize_database_url

_pool: ConnectionPool | None = None
_db_ok_cached: bool | None = None
_db_ok_checked_at = 0.0
_DB_OK_TTL_SEC = 30.0


def _database_url() -> str:
    return normalize_database_url(get_settings().database_url)


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=_database_url(),
            kwargs={"row_factory": dict_row},
            min_size=1,
            max_size=8,
            open=True,
        )
    return _pool


@contextmanager
def get_conn() -> Iterator[psycopg.Connection]:
    with _get_pool().connection() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def db_available() -> bool:
    """Cached reachability check — avoids a fresh connect+SELECT 1 on every request."""
    global _db_ok_cached, _db_ok_checked_at
    if get_settings().use_demo_store:
        return False
    now = time.monotonic()
    if _db_ok_cached is not None and (now - _db_ok_checked_at) < _DB_OK_TTL_SEC:
        return _db_ok_cached
    try:
        with get_conn() as conn:
            conn.execute("SELECT 1")
        _db_ok_cached = True
    except Exception:
        _db_ok_cached = False
    _db_ok_checked_at = now
    return _db_ok_cached


def fetch_all(sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return list(cur.fetchall())


def fetch_one(sql: str, params: tuple[Any, ...] | None = None) -> dict[str, Any] | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()
