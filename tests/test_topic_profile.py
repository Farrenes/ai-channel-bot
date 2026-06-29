from fastapi.testclient import TestClient

from api.main import app
from api.routes.topics import get_topic_profile_service
from services.topic_profile import TopicProfileService


def test_topic_profile_success_with_llm_stub():
    def llm_stub(raw_topic: str):
        assert raw_topic == "OpenAI policy update for dev teams"
        return {
            "raw_topic": raw_topic,
            "normalized_topic": "openai policy update for dev teams",
            "topic_type": ["policy", "news"],
            "domain": "ai",
            "risk_level": "medium",
            "content_strategy": "explain the update and its operational impact",
            "default_post_format": "brief_explainer",
            "language": "en",
            "tone": "analytical",
            "depth": "standard",
            "allowed_source_types": ["official_docs", "primary_news"],
            "blocked_source_types": ["speculation"],
            "requires_human_approval": True,
        }

    service = TopicProfileService(llm_client=llm_stub)
    app.dependency_overrides[get_topic_profile_service] = lambda: service
    client = TestClient(app)
    try:
        response = client.post("/topics/profile", json={"raw_topic": "OpenAI policy update for dev teams"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["module"] == "topic_profile"
    assert payload["run_id"]
    assert payload["duration_ms"] >= 0
    assert payload["errors"] == []
    assert payload["data"]["topic_type"] == ["policy", "news"]
    assert payload["data"]["requires_human_approval"] is True


def test_topic_profile_fallback_when_llm_unavailable():
    def failing_llm(_raw_topic: str):
        raise RuntimeError("LLM unavailable")

    service = TopicProfileService(llm_client=failing_llm)
    app.dependency_overrides[get_topic_profile_service] = lambda: service
    client = TestClient(app)
    try:
        response = client.post("/topics/profile", json={"raw_topic": "How to evaluate a new AI coding tool"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data"]["raw_topic"] == "How to evaluate a new AI coding tool"
    assert payload["data"]["topic_type"]
    assert payload["data"]["default_post_format"] == "how_to"
    assert payload["data"]["requires_human_approval"] is False
    assert payload["errors"]
