from app.scoring.models import ContentScoreInput
from app.scoring.penalties import score_penalties


def test_penalties_detect_clickbait_and_promo():
    penalties = score_penalties(
        ContentScoreInput(
            title="Shocking result",
            text="You won't believe this shocking result!!! Buy now and subscribe now before it is gone.",
            source="blog",
            niche="marketing",
            target_audience="founders",
            format="telegram_html",
            post_type="unknown",
        )
    )

    assert penalties.clickbait > 0
    assert penalties.too_promotional > 0


def test_duplicate_penalty_uses_comparison_texts():
    text = "Use one metric, one owner, and one workflow to start AI automation."
    penalties = score_penalties(
        ContentScoreInput(
            title="Operational workflow",
            text=text,
            source="official",
            niche="ai ops",
            target_audience="operators",
            format="telegram_html",
            post_type="guide",
        ),
        comparison_texts=[text],
    )

    assert penalties.duplicate_or_rewritten_low_value >= 0.99
