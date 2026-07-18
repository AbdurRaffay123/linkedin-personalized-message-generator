"""FastAPI application entrypoint."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Decision-grade prospect research & intelligence engine.",
)

# Observability + security headers (outermost first).
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestContextMiddleware)

# CORS: explicit allowlist in prod; "*" only when debugging locally.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/")
def root() -> dict:
    return {"service": settings.app_name, "docs": "/docs", "health": "/api/v1/health"}
