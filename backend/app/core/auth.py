"""API-key authentication (blueprint §7 hardening).

Keys look like `sk_live_<48 hex>`. Only the SHA-256 hash is stored; the plaintext
is shown once at issue time. Requests authenticate via `Authorization: Bearer <key>`
or the `X-API-Key` header.
"""
from __future__ import annotations

import hashlib
import secrets

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.base import get_db
from app.db.models import ApiKey, User, utcnow

_KEY_PREFIX = "sk_live_"


def generate_key() -> tuple[str, str, str]:
    """Return (plaintext_key, sha256_hash, display_prefix)."""
    raw = _KEY_PREFIX + secrets.token_hex(24)
    return raw, hash_key(raw), raw[: len(_KEY_PREFIX) + 6]


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def issue_key(db: Session, email: str, name: str | None = None) -> str:
    """Create the user if needed, issue a key, return the plaintext (once)."""
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email)
        db.add(user)
        db.flush()
    raw, key_hash, prefix = generate_key()
    db.add(ApiKey(user_id=user.id, key_hash=key_hash, prefix=prefix, name=name))
    db.commit()
    return raw


def _extract_key(authorization: str | None, x_api_key: str | None) -> str | None:
    if x_api_key:
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def get_current_user(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: resolve the authenticated user or 401."""
    if not settings.auth_required:
        # Dev-only escape hatch. Never enabled in a deployed environment.
        user = db.scalar(select(User).where(User.email == "dev@local"))
        if user is None:
            user = User(email="dev@local")
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    raw = _extract_key(authorization, x_api_key)
    if not raw:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Missing API key (send 'Authorization: Bearer <key>' or 'X-API-Key').",
            headers={"WWW-Authenticate": "Bearer"},
        )
    record = db.scalar(select(ApiKey).where(ApiKey.key_hash == hash_key(raw)))
    if record is None or record.revoked:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or revoked API key.")

    record.last_used_at = utcnow()
    db.commit()
    return record.user
