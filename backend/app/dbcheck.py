"""Connectivity + schema check for the configured DATABASE_URL.

Usage:
    python -m app.dbcheck

Pings the database, confirms every expected table exists, and reports the
Alembic head it's stamped at. Works for both SQLite (local) and Supabase Postgres.
Exit code 0 = healthy, 1 = problem — so it doubles as a deploy/CI gate.
"""
from __future__ import annotations

import sys

from sqlalchemy import inspect, text

from app.config import settings
from app.db.base import Base, engine
from app.db import models  # noqa: F401 — register tables on Base.metadata


def _redact(url: str) -> str:
    """Hide the password when echoing the connection target."""
    if "@" not in url or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    if "@" in rest and ":" in rest.split("@", 1)[0]:
        creds, host = rest.split("@", 1)
        user = creds.split(":", 1)[0]
        return f"{scheme}://{user}:***@{host}"
    return url


def main() -> int:
    print(f"→ target: {_redact(settings.database_url)}")

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        print(f"✗ cannot connect: {exc}")
        return 1
    print("✓ connection OK")

    expected = set(Base.metadata.tables)
    actual = set(inspect(engine).get_table_names())
    missing = expected - actual
    if missing:
        print(f"✗ missing tables: {', '.join(sorted(missing))}")
        print("  run: alembic upgrade head")
        return 1
    print(f"✓ all {len(expected)} tables present")

    if "alembic_version" in actual:
        with engine.connect() as conn:
            head = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        print(f"✓ alembic head: {head}")
    else:
        print("! alembic_version not found (schema not managed by Alembic yet)")

    print("✓ database healthy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
