"""Auth, ownership isolation, and GDPR deletion."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.auth import issue_key
from app.db.base import SessionLocal
from app.main import app


def _client_for(email: str) -> TestClient:
    db = SessionLocal()
    try:
        key = issue_key(db, email)
    finally:
        db.close()
    return TestClient(app, headers={"X-API-Key": key})


def test_capture_requires_auth(anon_client):
    r = anon_client.post("/api/v1/prospects/capture", json={"full_name": "X"})
    assert r.status_code == 401


def test_invalid_key_rejected(anon_client):
    r = anon_client.post(
        "/api/v1/prospects/capture",
        json={"full_name": "X"},
        headers={"X-API-Key": "sk_live_notarealkey"},
    )
    assert r.status_code == 401


def test_ownership_isolation():
    alice = _client_for("alice@test")
    bob = _client_for("bob@test")

    pid = alice.post(
        "/api/v1/prospects/capture", json={"full_name": "Alice Lead"}
    ).json()["id"]

    # Bob cannot see Alice's prospect — 404, not 403 (no id leakage).
    assert bob.get(f"/api/v1/prospects/{pid}").status_code == 404
    assert bob.post(f"/api/v1/prospects/{pid}/analyze").status_code == 404
    # Bob's own list is empty.
    assert bob.get("/api/v1/prospects").json() == []
    # Alice still sees it.
    assert alice.get(f"/api/v1/prospects/{pid}").status_code == 200


def test_delete_prospect_and_erase_all():
    user = _client_for("eraser@test")
    p1 = user.post("/api/v1/prospects/capture", json={"full_name": "One"}).json()["id"]
    user.post("/api/v1/prospects/capture", json={"full_name": "Two"})

    assert user.delete(f"/api/v1/prospects/{p1}").status_code == 204
    assert user.get(f"/api/v1/prospects/{p1}").status_code == 404

    # Right-to-erasure wipes the rest.
    assert user.delete("/api/v1/me/data").status_code == 204
    assert user.get("/api/v1/prospects").json() == []
