"""Rate limiting on the expensive analyze endpoint."""
from __future__ import annotations

from app.config import settings


def test_analyze_rate_limited(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_analyze_per_hour", 3)

    pid = client.post(
        "/api/v1/prospects/capture", json={"full_name": "RL Target"}
    ).json()["id"]

    codes = [client.post(f"/api/v1/prospects/{pid}/analyze").status_code for _ in range(4)]
    assert codes[:3] == [202, 202, 202]
    assert codes[3] == 429  # 4th within the window is rejected
