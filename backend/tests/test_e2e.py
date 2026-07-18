"""End-to-end spine test: capture -> analyze -> poll -> evidence-linked brief.

Runs entirely on the keyless mock provider, so it proves the orchestration,
persistence, structured-output validation, and API layers work without secrets.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_full_pipeline():
    # 1. Passive capture (derived fields only).
    capture = client.post(
        "/api/v1/prospects/capture",
        json={
            "full_name": "Jane Founder",
            "headline": "CEO at Acme Robotics",
            "about": "Scaling warehouse automation.",
            "company": {"name": "Acme Robotics", "domain": "acme.example"},
            "posts": [{"content": "We just opened 12 automation-engineer roles."}],
        },
    )
    assert capture.status_code == 201, capture.text
    prospect_id = capture.json()["id"]

    # 2. Kick off async analysis (BackgroundTasks runs it before the poll).
    started = client.post(f"/api/v1/prospects/{prospect_id}/analyze")
    assert started.status_code == 202, started.text
    analysis_id = started.json()["analysis_id"]

    # 3. Poll -> completed, structured, evidence-linked result.
    got = client.get(f"/api/v1/analyses/{analysis_id}")
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["status"] == "completed", body
    assert body["result"] is not None
    assert "should_reach_out" in body["result"]
    assert isinstance(body["opportunity_score"], int)
