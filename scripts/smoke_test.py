from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.generation import GenerationService
from services.review import ReviewService
from services.scoring import ScoringInputItem, ScoringService
from services.source_validation import SourceValidationService
from services.telegram_publish import TelegramPublishRequest, TelegramPublishService
from services.topic_profile import TopicProfileService


@dataclass
class FakeResponse:
    status_code: int
    headers: dict[str, str]
    text: str
    url: str


class FakeSourceRepo:
    async def upsert_source(self, payload):
        return {"id": 101}

    async def insert_validation_run(self, payload):
        return {"id": 201}

    async def insert_fetch_run(self, payload):
        return {"id": 301}


class FakeFetcher:
    async def get(self, url: str) -> FakeResponse:
        return FakeResponse(
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            text="""
            <html>
              <head><title>Example Article</title></head>
              <body><article><h1>Example Article</h1><p>Useful source text.</p></article></body>
            </html>
            """,
            url=url,
        )


class FakePublishRepo:
    def __init__(self):
        self.published = None
        self.events = []

    async def fetch_existing_publish(self, *, generated_post_id: int, idempotency_key: str):
        return None

    async def insert_published_post(self, payload):
        self.published = payload
        return {"id": 401}

    async def update_generated_post(self, payload):
        self.events.append(("update_generated_post", payload))

    async def insert_event_log(self, payload):
        self.events.append(("insert_event_log", payload))
        return {"id": 501 + len(self.events)}


async def main() -> int:
    topic_service = TopicProfileService()
    profile, topic_errors = topic_service.build_profile("ИИ для малого бизнеса")

    source_service = SourceValidationService(repo=FakeSourceRepo(), fetcher=FakeFetcher())
    source_result = await source_service.validate_source({"url": "https://example.com/article", "topic_profile_id": 1})

    scoring_service = ScoringService()
    score_result = await scoring_service.score_items(
        items=[ScoringInputItem(title="Useful article", description="Useful source text.")],
        content_strategy=profile["content_strategy"],
        topic_profile=profile,
        save_to_db=False,
    )

    generation_service = GenerationService()
    generated_post, generation_errors = generation_service.generate_post(profile, "Useful source text.")

    review_service = ReviewService()
    review_result = review_service.review_post(generated_post["post"], profile, "Useful source text.")

    publish_service = TelegramPublishService(repo=FakePublishRepo())
    publish_result = await publish_service.publish(
        TelegramPublishRequest(
            generated_post_id=777,
            idempotency_key="smoke-test-777",
            title="Smoke Test",
            post_text=generated_post["post"],
            target_channel="@smoke-test",
            mock_publish=True,
        )
    )

    result = {
        "topic_errors": topic_errors,
        "source_classification": source_result["classification"],
        "score_count": score_result.scored_items,
        "generation_used_llm": generated_post["used_llm"],
        "generation_errors": generation_errors,
        "review_approved": review_result["approved"],
        "publish_status": publish_result.status,
        "publish_deduplicated": publish_result.deduplicated,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if source_result["classification"] not in {"supported", "partially_supported"}:
        raise SystemExit("source validation failed")
    if score_result.scored_items != 1:
        raise SystemExit("scoring failed")
    if review_result["risk_blocked"]:
        raise SystemExit("review blocked smoke test topic unexpectedly")
    if not publish_result.published:
        raise SystemExit("publish failed")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
