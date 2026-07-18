"""Test fixtures: throwaway SQLite schema + authenticated/anonymous clients.

The suite runs with auth ENABLED (production-like). The `client` fixture carries
a valid API key; `anon_client` carries none.
"""
from __future__ import annotations

import os
import tempfile

import pytest

# Point the app at an isolated DB *before* app modules import settings/engine.
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ["AUTH_REQUIRED"] = "true"
# Force the keyless deterministic provider so tests never hit a real LLM API,
# overriding any MODEL_* set in a developer's .env.
os.environ["MODEL_EXTRACTION"] = "mock:extraction"
os.environ["MODEL_REASONING"] = "mock:reasoning"
os.environ["MODEL_MESSAGE_GEN"] = "mock:message"


@pytest.fixture(scope="session", autouse=True)
def _schema():
    from app.db.base import Base, engine
    from app.db import models  # noqa: F401 — register tables on Base.metadata

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    os.unlink(_tmp.name)


def _make_client(email: str):
    from fastapi.testclient import TestClient
    from app.core.auth import issue_key
    from app.db.base import SessionLocal
    from app.main import app

    db = SessionLocal()
    try:
        key = issue_key(db, email)
    finally:
        db.close()
    return TestClient(app, headers={"X-API-Key": key})


@pytest.fixture
def client(_schema):
    """Authenticated client for the default test user."""
    return _make_client("tester@local")


@pytest.fixture
def anon_client(_schema):
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    from app.core.ratelimit import reset

    reset()
    yield
