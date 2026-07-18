"""In-process sliding-window rate limiter (blueprint §7).

Keyed by (bucket, user_id). Adequate for a single-worker MVP; for multiple
workers/instances, back this with Redis (same interface). It fails-closed on the
protected endpoints: exceeding the window returns HTTP 429.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, status

from app.config import settings
from app.core.auth import get_current_user
from app.db.models import User

_lock = threading.Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)


def _check(bucket: str, user_id: int, limit: int, window_s: int = 3600) -> None:
    key = f"{bucket}:{user_id}"
    now = time.monotonic()
    cutoff = now - window_s
    with _lock:
        dq = _hits[key]
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= limit:
            retry = int(dq[0] + window_s - now) + 1
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Rate limit exceeded for '{bucket}' ({limit}/hour).",
                headers={"Retry-After": str(max(1, retry))},
            )
        dq.append(now)


def limit_analyze(user: User = Depends(get_current_user)) -> User:
    _check("analyze", user.id, settings.rate_limit_analyze_per_hour)
    return user


def limit_capture(user: User = Depends(get_current_user)) -> User:
    _check("capture", user.id, settings.rate_limit_capture_per_hour)
    return user


def reset() -> None:
    """Test helper: clear all counters."""
    with _lock:
        _hits.clear()
