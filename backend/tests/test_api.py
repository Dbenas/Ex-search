import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from curator.api.app import create_app
from curator.config import Settings
from curator.service import CurationService
from tests.conftest import CTO_JOB

pytestmark = pytest.mark.slow

KEY = "test-key-123"


@pytest.fixture
def client(settings: Settings, service: CurationService) -> Iterator[TestClient]:
    secured = settings.model_copy(update={"api_keys": [SecretStr(KEY)], "rate_limit_per_minute": 3})
    with TestClient(create_app(secured, service_factory=lambda _: service)) as c:
        yield c


def test_health_is_public(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["candidates"] == 4
    assert response.headers["x-content-type-options"] == "nosniff"


def test_requires_api_key(client: TestClient) -> None:
    assert client.get("/v1/candidates").status_code == 401
    assert client.get("/v1/candidates", headers={"X-API-Key": "wrong"}).status_code == 401


def test_candidates_hide_contact_data(client: TestClient) -> None:
    response = client.get("/v1/candidates", headers={"X-API-Key": KEY})
    assert response.status_code == 200
    body = response.text
    assert "Carolina Mendes" in body
    assert "@example.com" not in body and "90000-" not in body


def test_rejects_short_job_description(client: TestClient) -> None:
    response = client.post("/v1/match", json={"job_description": "CTO"}, headers={"X-API-Key": KEY})
    assert response.status_code == 422


def test_match_and_rate_limit(client: TestClient) -> None:
    headers = {"X-API-Key": KEY}
    for _ in range(3):
        ok = client.post("/v1/match", json={"job_description": CTO_JOB}, headers=headers)
        assert ok.status_code == 200
    assert ok.json()["top_candidates"][0]["name"] == "Carolina Mendes"

    blocked = client.post("/v1/match", json={"job_description": CTO_JOB}, headers=headers)
    assert blocked.status_code == 429
    assert "retry-after" in blocked.headers


def test_stream_returns_sse_events(client: TestClient) -> None:
    with client.stream(
        "POST", "/v1/match/stream", json={"job_description": CTO_JOB}, headers={"X-API-Key": KEY}
    ) as response:
        assert response.status_code == 200
        payloads = [
            json.loads(line.removeprefix("data: "))
            for line in response.iter_lines()
            if line.startswith("data: ")
        ]
    assert payloads[0]["stage"] == "sanitize"
    assert payloads[-1]["type"] == "report"


def test_feedback_is_stored_without_pii(client: TestClient, settings: Settings) -> None:
    response = client.post(
        "/v1/feedback",
        json={
            "run_id": "abcdef123456",
            "candidate_id": "cand-ana-silva",
            "verdict": "agree",
            "comment": "Ligar em 11 91234-5678",
        },
        headers={"X-API-Key": KEY},
    )
    assert response.status_code == 204
    stored = settings.feedback_path.read_text(encoding="utf-8")
    assert "91234-5678" not in stored and "[PHONE]" in stored
