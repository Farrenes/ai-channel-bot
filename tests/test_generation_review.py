from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.generation import get_generation_service, router as generation_router
from api.routes.review import get_review_service, router as review_router
from services.generation import GenerationService
from services.review import ReviewService


def build_topic_profile(**overrides):
    base = {
        "raw_topic": "OpenAI policy update for dev teams",
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
    base.update(overrides)
    return base


def make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(generation_router)
    app.include_router(review_router)
    return app


def test_generation_uses_topic_profile_fields_only():
    seen_prompt: dict[str, str] = {}

    def llm_stub(prompt: str) -> dict[str, str]:
        seen_prompt["prompt"] = prompt
        return {"post": "Generated from prompt"}

    service = GenerationService(llm_client=llm_stub)
    app = make_app()
    app.dependency_overrides[get_generation_service] = lambda: service
    client = TestClient(app)

    try:
        response = client.post(
            "/generation/post",
            json={
                "topic_profile": build_topic_profile(),
                "context": "Release notes and operator guidance.",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["module"] == "generation"
    assert payload["run_id"]
    assert payload["duration_ms"] >= 0
    assert payload["errors"] == []
    assert payload["data"]["post"] == "Generated from prompt"
    assert "explain the update and its operational impact" in seen_prompt["prompt"]
    assert "analytical" in seen_prompt["prompt"]
    assert "standard" in seen_prompt["prompt"]
    assert "brief_explainer" in seen_prompt["prompt"]
    assert "medium" in seen_prompt["prompt"]
    assert "favorite_words" not in seen_prompt["prompt"]
    assert "opening_style" not in seen_prompt["prompt"]


def test_review_approves_normal_post():
    service = ReviewService()
    app = make_app()
    app.dependency_overrides[get_review_service] = lambda: service
    client = TestClient(app)

    try:
        response = client.post(
            "/review/post",
            json={
                "post": "Clear post with useful guidance for readers.",
                "topic_profile": build_topic_profile(risk_level="low", requires_human_approval=False),
                "context": "A normal product update.",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["module"] == "review"
    assert payload["data"]["approved"] is True
    assert payload["data"]["can_autopublish"] is True
    assert payload["data"]["risk_blocked"] is False
    assert payload["data"]["issues"] == []


def test_review_rejects_empty_post():
    service = ReviewService()
    verdict = service.review_post("", build_topic_profile(risk_level="low", requires_human_approval=False), "")

    assert verdict["approved"] is False
    assert verdict["can_autopublish"] is False
    assert any("empty" in issue.lower() for issue in verdict["issues"])


def test_review_blocks_high_risk_autopublish():
    app = make_app()
    app.dependency_overrides[get_review_service] = lambda: ReviewService()
    client = TestClient(app)

    try:
        response = client.post(
            "/review/post",
            json={
                "post": "Important update with confident recommendations.",
                "topic_profile": build_topic_profile(
                    risk_level="high",
                    requires_human_approval=True,
                    content_strategy="summarize carefully, cite primary sources, and call out caveats",
                ),
                "context": "High-risk legal or medical adjacent topic.",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data"]["approved"] is False
    assert payload["data"]["can_autopublish"] is False
    assert payload["data"]["risk_blocked"] is True
    assert any("high-risk" in issue.lower() for issue in payload["data"]["issues"])

    rewrite_response = client.post(
        "/review/rewrite",
        json={
            "post": "Important update with confident recommendations.",
            "topic_profile": build_topic_profile(
                risk_level="high",
                requires_human_approval=True,
                content_strategy="summarize carefully, cite primary sources, and call out caveats",
            ),
            "context": "High-risk legal or medical adjacent topic.",
            "feedback": "Add caution and human approval notice.",
        },
    )

    assert rewrite_response.status_code == 200
    rewrite_payload = rewrite_response.json()
    assert rewrite_payload["status"] == "ok"
    assert rewrite_payload["data"]["changed"] is True
    assert rewrite_payload["data"]["can_autopublish"] is False
    assert "human approval" in rewrite_payload["data"]["post"].lower()
