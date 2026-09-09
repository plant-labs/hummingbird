from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Optional

import psycopg
from psycopg.rows import dict_row

from .config import get_settings


def try_connect() -> Optional[psycopg.Connection]:
    settings = get_settings()
    try:
        conn = psycopg.connect(settings.database_url, row_factory=dict_row)
        conn.execute("SELECT 1")
        return conn
    except Exception:
        return None


@contextmanager
def get_conn() -> Iterator[psycopg.Connection]:
    settings = get_settings()
    conn = psycopg.connect(settings.database_url, row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def db_available() -> bool:
    if get_settings().use_demo_store:
        return False
    conn = try_connect()
    if conn is None:
        return False
    conn.close()
    return True


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
