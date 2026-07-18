"""Message-generation tests: full loop capture -> analyze -> message."""
from __future__ import annotations


def test_capture_analyze_message_loop(client):
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


def test_message_404_for_missing_analysis(client):
    r = client.post("/api/v1/analyses/999999/messages", json={})
    assert r.status_code == 404
