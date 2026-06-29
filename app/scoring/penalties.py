from __future__ import annotations

import re
from collections.abc import Iterable

from .config import LONG_POST_LIMIT, OPENING_WINDOW
from .models import ContentScoreInput, PenaltyFactors

CLICKBAIT_PATTERNS = (
    r"\bshocking\b",
    r"\byou won't believe\b",
    r"\bguaranteed\b",
    r"\bmust read\b",
    r"\b100%\b",
    r"!!!+",
)
PROMO_PATTERNS = (
    r"\bbuy now\b",
    r"\bsubscribe now\b",
    r"\blimited offer\b",
    r"\bdiscount\b",
    r"\bpromo\b",
    r"\bact now\b",
)
UNSUPPORTED_CLAIM_PATTERNS = (
    r"\bproven\b",
    r"\bscientifically\b",
    r"\beveryone knows\b",
    r"\balways\b",
    r"\bnever\b",
    r"\bguarantees?\b",
)
VAGUE_PATTERNS = (
    r"\bmany people\b",
    r"\bsome experts\b",
    r"\bin many cases\b",
    r"\bit is important\b",
    r"\binteresting\b",
)


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, round(value, 4)))


def extract_opening(text: str, limit: int = OPENING_WINDOW) -> str:
    return (text or "").strip()[:limit]


def opening_strength(text: str) -> float:
    opening = extract_opening(text).lower()
    if not opening:
        return 0.0

    score = 0.15
    if "?" in opening:
        score += 0.18
    if any(token in opening for token in ("how", "why", "what changed", "mistake", "problem", "risk")):
        score += 0.18
    if re.search(r"\b\d+(?:[%x]|[kmb])?\b", opening):
        score += 0.15
    if any(token in opening for token in ("instead", "but", "not", "losing", "fail", "waste")):
        score += 0.12
    if len(opening.split()) >= 6:
        score += 0.08
    if opening.endswith(":"):
        score += 0.06
    if opening.startswith(("in this post", "it is interesting", "today we", "let's talk", "let us")):
        score -= 0.12
    return clamp01(score)


def weak_opening_penalty(text: str) -> float:
    return clamp01(1.0 - opening_strength(text))


def _pattern_density(text: str, patterns: Iterable[str]) -> float:
    lowered = (text or "").lower()
    pattern_list = tuple(patterns)
    hits = sum(1 for pattern in pattern_list if re.search(pattern, lowered))
    if hits == 0:
        return 0.0
    return clamp01(min(1.0, hits / max(1, len(pattern_list))))


def score_penalties(input_data: ContentScoreInput, comparison_texts: list[str] | None = None) -> PenaltyFactors:
    text = input_data.text.strip()
    words = [word for word in re.split(r"\s+", text) if word]
    sentences = [part.strip() for part in re.split(r"[.!?]+", text) if part.strip()]
    avg_sentence_length = len(words) / max(1, len(sentences))
    emoji_count = len(re.findall(r"[\U0001F300-\U0001FAFF]", text))
    bullet_count = text.count("\n- ") + text.count("\n* ") + text.count("\n1.")

    duplicate_penalty = 0.0
    for candidate in comparison_texts or []:
        if not candidate.strip():
            continue
        if candidate.strip().lower() == text.lower():
            duplicate_penalty = max(duplicate_penalty, 1.0)
        elif candidate.strip() and _token_overlap(candidate, text) >= 0.82:
            duplicate_penalty = max(duplicate_penalty, 0.75)

    too_long = 0.0
    if len(text) > LONG_POST_LIMIT:
        too_long = clamp01((len(text) - LONG_POST_LIMIT) / 1200)

    weak_telegram_fit = 0.0
    if len(text) < 80 or (bullet_count == 0 and len(text) > 1000):
        weak_telegram_fit += 0.35
    if emoji_count > 10:
        weak_telegram_fit += 0.25
    if input_data.has_poll and "?" not in text:
        weak_telegram_fit += 0.15

    cognitive_overload = 0.0
    if avg_sentence_length > 28:
        cognitive_overload += min(0.7, (avg_sentence_length - 28) / 25)
    if bullet_count >= 8:
        cognitive_overload += 0.2
    if text.count("(") + text.count("[") >= 6:
        cognitive_overload += 0.15

    return PenaltyFactors(
        clickbait=_pattern_density(text, CLICKBAIT_PATTERNS),
        vague_text=_pattern_density(text, VAGUE_PATTERNS),
        too_long=too_long,
        too_promotional=_pattern_density(text, PROMO_PATTERNS),
        unsupported_claims=_pattern_density(text, UNSUPPORTED_CLAIM_PATTERNS),
        duplicate_or_rewritten_low_value=duplicate_penalty,
        cognitive_overload=clamp01(cognitive_overload),
        weak_opening=weak_opening_penalty(text),
        weak_telegram_fit=clamp01(weak_telegram_fit),
    )


def _token_overlap(left: str, right: str) -> float:
    left_tokens = set(re.findall(r"\w+", left.lower()))
    right_tokens = set(re.findall(r"\w+", right.lower()))
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = len(left_tokens & right_tokens)
    return intersection / max(1, min(len(left_tokens), len(right_tokens)))
