from app.scoring.models import ContentScoreInput
from app.scoring.scorer import score_content


def _field(result, *names):
    for name in names:
        if isinstance(result, dict) and name in result:
            return result[name]
        if hasattr(result, name):
            return getattr(result, name)
    raise AssertionError(f"Missing expected field. Tried: {names}")


def test_score_content_returns_structured_result():
    result = score_content(
        ContentScoreInput(
            text=(
                "If your channel loses readers in the first 5 seconds, fix the opening first.\n\n"
                "Use one concrete pain point, one practical takeaway, and one next step."
            ),
            title="How to improve Telegram post openings",
            source="official",
            niche="telegram growth",
            target_audience="channel owners",
            format="telegram_html",
            post_type="guide",
        )
    )

    assert _field(result, "total_score") > 0
    assert _field(result, "base_score") >= _field(result, "penalty_score")
    assert _field(result, "decision") in {"publish", "improve", "reject"}
    assert isinstance(_field(result, "strong_sides", "strongest_points", "strengths"), list)
    assert isinstance(_field(result, "weak_sides", "weakest_points", "weaknesses"), list)
    assert isinstance(_field(result, "recommendations", "improvement_suggestions"), list)


def test_score_content_penalizes_empty_value_props():
    weak = score_content(
        ContentScoreInput(
            text="Today we will talk about some important things in content.",
            title="General thoughts",
            source="blog",
            niche="content",
            target_audience="editors",
            format="telegram_html",
        )
    )
    strong = score_content(
        ContentScoreInput(
            text=(
                "Most channels lose retention in the first 120 characters.\n\n"
                "Fix it with a pain-first opening, one number, and one clear reader benefit."
            ),
            title="Retention fix",
            source="official",
            niche="telegram",
            target_audience="channel owners",
            format="telegram_html",
            post_type="guide",
        )
    )

    assert _field(strong, "total_score") > _field(weak, "total_score")
