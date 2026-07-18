"""Retention purge (GDPR/CCPA): delete prospects past their retention window.

Usage (cron this, e.g. daily):
    python -m app.purge

Deletes every prospect whose `retention_expires_at` is in the past, cascading to
its posts, analyses, crawled_pages, and messages. Prints how many were removed.
"""
from __future__ import annotations

import sys

from sqlalchemy import select

from app.db.base import SessionLocal
from app.db.models import Prospect, utcnow


def purge_expired() -> int:
    db = SessionLocal()
    try:
        now = utcnow()
        expired = list(
            db.scalars(
                select(Prospect).where(
                    Prospect.retention_expires_at.is_not(None),
                    Prospect.retention_expires_at < now,
                )
            )
        )
        for prospect in expired:
            db.delete(prospect)
        db.commit()
        return len(expired)
    finally:
        db.close()


if __name__ == "__main__":
    count = purge_expired()
    print(f"purged {count} expired prospect(s)")
    sys.exit(0)
