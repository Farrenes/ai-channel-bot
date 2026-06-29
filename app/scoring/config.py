from __future__ import annotations

SCORING_WEIGHTS = {
    "utility": 0.16,
    "hook_strength": 0.12,
    "curiosity_gap": 0.10,
    "novelty": 0.09,
    "emotional_energy": 0.08,
    "specificity": 0.08,
    "credibility": 0.08,
    "audience_fit": 0.08,
    "readability": 0.06,
    "narrative": 0.05,
    "actionability": 0.04,
    "discussion_potential": 0.03,
    "shareability": 0.02,
    "telegram_format_fit": 0.01,
}

PENALTY_WEIGHTS = {
    "clickbait": 0.18,
    "vague_text": 0.14,
    "too_long": 0.10,
    "too_promotional": 0.14,
    "unsupported_claims": 0.16,
    "duplicate_or_rewritten_low_value": 0.12,
    "cognitive_overload": 0.08,
    "weak_opening": 0.06,
    "weak_telegram_fit": 0.02,
}

DECISION_THRESHOLDS = {
    "publish": 78.0,
    "improve": 58.0,
}

MAX_IMPROVEMENT_PASSES = 2
DEFAULT_VARIANT_COUNT = 5
SHORT_POST_LIMIT = 700
LONG_POST_LIMIT = 1400
OPENING_WINDOW = 140
