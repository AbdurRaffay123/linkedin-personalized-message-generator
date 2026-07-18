"""Observability + security middleware (blueprint §7).

- RequestContextMiddleware: assigns a request id, logs method/path/status/latency
  (never bodies or secrets), and echoes the id back as `X-Request-ID`.
- SecurityHeadersMiddleware: conservative headers suitable for a JSON API.
"""
from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed = (time.perf_counter() - start) * 1000
            logger.exception(
                "request_failed id=%s %s %s (%.1fms)",
                request_id, request.method, request.url.path, elapsed,
            )
            raise
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(
            "id=%s %s %s -> %s (%.1fms)",
            request_id, request.method, request.url.path, response.status_code, elapsed,
        )
        response.headers["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response
