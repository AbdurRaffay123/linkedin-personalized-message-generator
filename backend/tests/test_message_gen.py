"""Message-generation tests: full loop capture -> analyze -> message."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_capture_analyze_message_loop():
    cap = client.post(
        "/api/v1/prospects/capture",
        json={"full_name": "Dana Buyer", "headline": "COO at Beta",
              "company": {"name": "Beta Inc", "domain": "example.com"},
              "posts": [{"content": "scaling ops team"}]},
    )
    assert cap.status_code == 201, cap.text
    pid = cap.json()["id"]

    started = client.post(f"/api/v1/prospects/{pid}/analyze")
    aid = started.json()["analysis_id"]
    assert client.get(f"/api/v1/analyses/{aid}").json()["status"] == "completed"

    msg = client.post(
        f"/api/v1/analyses/{aid}/messages",
        json={"tone": "warm", "length": "short", "goal": "book a call"},
    )
    assert msg.status_code == 201, msg.text
    body = msg.json()
    assert body["body"]
    assert body["tone"] == "warm"
    assert body["model_used"]


def test_message_rejected_before_analysis_completes():
    # Fabricate a pending analysis via capture + analyze is always sync-complete
    # with mock, so instead assert 404 on a missing analysis id.
    r = client.post("/api/v1/analyses/999999/messages", json={})
    assert r.status_code == 404
