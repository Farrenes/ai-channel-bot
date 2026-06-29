import asyncio

import database
from services.scoring import (
    ScoringInputItem,
    build_scoring_weights,
    score_items_universal,
)


def test_score_items_is_pure_when_save_to_db_false():
    captured = []

    async def fake_score_runner(items, context):
        return {
            "ai tools in production": {
                "relevance_score": 88,
                "quality_score": 76,
                "novelty_score": 64,
                "authority_score": 52,
                "risk_score": 18,
                "virality_score": 70,
                "evergreen_score": 61,
                "commercial_score": 42,
                "final_score": 69,
                "status": "pending",
            }
        }

    async def fake_db_writer(payload):
        captured.append(payload)

    result = asyncio.run(
        score_items_universal(
            [ScoringInputItem(title="AI tools in production", description="A practical post about models.")],
            content_strategy="show a practical path with steps and examples",
            topic_profile={"content_strategy": "show a practical path with steps and examples", "topic_type": ["tutorial"]},
            save_to_db=False,
            db_writer=fake_db_writer,
            score_runner=fake_score_runner,
        )
    )

    assert result.status == "ok"
    assert result.scored_items == 1
    assert captured == []
    assert len(result.items) == 1
    item = result.items[0]
    assert item.relevance_score == 88
    assert item.final_score == 69
    assert item.total_score == 69
    assert item.score_utility == 76
    assert item.score_practical == 76


def test_build_scoring_weights_depend_on_strategy_and_topic_type():
    tutorial_weights = build_scoring_weights(
        content_strategy="show a practical path with steps and examples",
        topic_profile={"content_strategy": "show a practical path with steps and examples", "topic_type": ["tutorial"]},
        topic_type=["tutorial"],
    )
    news_weights = build_scoring_weights(
        content_strategy="explain what changed and why it matters",
        topic_profile={"content_strategy": "explain what changed and why it matters", "topic_type": ["news"]},
        topic_type=["news"],
    )

    assert tutorial_weights["quality_score"] > news_weights["quality_score"]
    assert tutorial_weights["evergreen_score"] > news_weights["evergreen_score"]
    assert news_weights["virality_score"] > tutorial_weights["virality_score"]
    assert news_weights["novelty_score"] > tutorial_weights["novelty_score"]


def test_cheap_prefilter_removes_duplicates_before_llm():
    seen_titles = []

    async def fake_score_runner(items, context):
        seen_titles.extend(item["title"] for item in items)
        return {
            "ai tools in production": {
                "relevance_score": 80,
                "quality_score": 70,
                "novelty_score": 55,
                "authority_score": 60,
                "risk_score": 15,
                "virality_score": 40,
                "evergreen_score": 66,
                "commercial_score": 50,
                "final_score": 63,
                "status": "pending",
            }
        }

    result = asyncio.run(
        score_items_universal(
            [
                ScoringInputItem(title="AI tools in production", description="First copy."),
                ScoringInputItem(title="AI tools in production", description="Duplicate copy."),
                ScoringInputItem(title="[ removed by reddit ]", description="Noise."),
            ],
            content_strategy="compare options with clear trade-offs",
            topic_profile={"content_strategy": "compare options with clear trade-offs", "topic_type": ["comparison"]},
            save_to_db=False,
            score_runner=fake_score_runner,
        )
    )

    assert seen_titles == ["AI tools in production"]
    assert result.total_items == 3
    assert result.filtered_items == 1
    assert result.scored_items == 1


def test_score_items_persists_content_score_when_db_pool_available():
    class FakeConnection:
        def __init__(self, calls):
            self.calls = calls

        async def execute(self, sql, *args):
            self.calls.append((sql, args))

    class FakeAcquire:
        def __init__(self, calls):
            self.calls = calls

        async def __aenter__(self):
            return FakeConnection(self.calls)

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakePool:
        def __init__(self):
            self.calls = []

        def acquire(self):
            return FakeAcquire(self.calls)

    original_pool = database.db_pool
    fake_pool = FakePool()
    database.db_pool = fake_pool
    try:
        result = asyncio.run(
            score_items_universal(
                [
                    ScoringInputItem(
                        title="AI automation checklist",
                        description="Use one owner, one workflow, and one metric to start safely.",
                        source="example",
                        link="https://example.com/ai",
                        category="technology",
                    )
                ],
                content_strategy="show a practical path with steps and examples",
                topic_profile={
                    "id": 1,
                    "normalized_topic": "AI automation for small business",
                    "content_strategy": "show a practical path with steps and examples",
                    "topic_type": ["tutorial"],
                },
                save_to_db=True,
            )
        )
    finally:
        database.db_pool = original_pool

    assert result.scored_items == 1
    assert fake_pool.calls
    sql, args = fake_pool.calls[0]
    assert "INSERT INTO content_scores" in sql
    assert args[0] == 1
    assert args[22] in {"publish", "improve", "reject"}
