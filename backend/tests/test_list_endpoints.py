"""Dashboard read endpoints."""
from __future__ import annotations


def test_list_prospects_analyses_messages(client):
    cap = client.post(
        "/api/v1/prospects/capture",
        json={"full_name": "List Target", "company": {"name": "ListCo"},
              "posts": [{"content": "x"}]},
    )
    pid = cap.json()["id"]

    prospects = client.get("/api/v1/prospects")
    assert prospects.status_code == 200
    assert any(p["id"] == pid for p in prospects.json())
    # Company is embedded for the list view.
    row = next(p for p in prospects.json() if p["id"] == pid)
    assert row["company"]["name"] == "ListCo"

    aid = client.post(f"/api/v1/prospects/{pid}/analyze").json()["analysis_id"]
    analyses = client.get(f"/api/v1/prospects/{pid}/analyses")
    assert analyses.status_code == 200
    assert analyses.json()[0]["id"] == aid

    client.post(f"/api/v1/analyses/{aid}/messages", json={})
    messages = client.get(f"/api/v1/analyses/{aid}/messages")
    assert messages.status_code == 200
    assert len(messages.json()) == 1


def test_list_analyses_404_for_missing_prospect(client):
    assert client.get("/api/v1/prospects/999999/analyses").status_code == 404
