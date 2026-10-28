"""Lazy PostgreSQL connection pool; no connection is opened at import time."""

import os
from typing import Any

from psycopg2 import pool as pg_pool

_pool: pg_pool.ThreadedConnectionPool | None = None


def get_pool() -> pg_pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        dsn = os.environ.get("JAMP_DATABASE_URL")
        if not dsn:
            raise RuntimeError("JAMP_DATABASE_URL is not set")
        _pool = pg_pool.ThreadedConnectionPool(minconn=2, maxconn=10, dsn=dsn)
    return _pool


def get_connection() -> Any:
    return get_pool().getconn()


def release_connection(conn: Any) -> None:
    get_pool().putconn(conn)
