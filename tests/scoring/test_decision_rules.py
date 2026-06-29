from app.scoring.models import ContentScoreInput
from app.scoring.scorer import score_content


class FixedAdapter:
    def __init__(self, payload):
        self.payload = payload

    def analyze(self, input_data):
        return self.payload


def test_decision_publish_threshold():
    result = score_content(
        ContentScoreInput(
            text="Concrete post with value.",
            title="Concrete post with value",
            source="official",
            niche="ai ops",
            target_audience="operators",
            format="telegram_html",
            post_type="guide",
        ),
        llm_adapter=FixedAdapter(
            {
                "utility": 0.95,
                "hook_strength": 0.90,
                "curiosity_gap": 0.85,
                "novelty": 0.80,
                "emotional_energy": 0.70,
                "specificity": 0.85,
                "credibility": 0.90,
                "audience_fit": 0.88,
                "readability": 0.85,
                "narrative": 0.72,
                "actionability": 0.92,
                "discussion_potential": 0.55,
                "shareability": 0.60,
                "telegram_format_fit": 0.70,
            }
        ),
    )
    assert result.decision == "publish"


def test_decision_reject_threshold():
    result = score_content(
        ContentScoreInput(
            text="Interesting thoughts.",
            title="Interesting thoughts",
            source="blog",
            niche="general",
            target_audience="readers",
            format="telegram_html",
            post_type="unknown",
        ),
        llm_adapter=FixedAdapter(
            {
                "utility": 0.10,
                "hook_strength": 0.08,
                "curiosity_gap": 0.10,
                "novelty": 0.08,
                "emotional_energy": 0.05,
                "specificity": 0.08,
                "credibility": 0.10,
                "audience_fit": 0.12,
                "readability": 0.20,
                "narrative": 0.10,
                "actionability": 0.05,
                "discussion_potential": 0.08,
                "shareability": 0.06,
                "telegram_format_fit": 0.10,
            }
        ),
    )
    assert result.decision == "reject"
