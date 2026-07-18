"""Test fixtures: build a fresh schema on a throwaway SQLite DB per session.

Keeps tests independent of Alembic state and of any dev database.
"""
from __future__ import annotations

import os
import tempfile

import pytest

# Point the app at an isolated DB *before* app modules import settings/engine.
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"


@pytest.fixture(scope="session", autouse=True)
def _schema():
    from app.db.base import Base, engine
    from app.db import models  # noqa: F401 — register tables on Base.metadata

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    os.unlink(_tmp.name)
