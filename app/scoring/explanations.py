from __future__ import annotations

from .models import ContentScoreInput, PenaltyFactors, PsychologicalFactors, RecommendedFormat

FACTOR_LABELS = {
    "utility": "practical value",
    "hook_strength": "opening hook",
    "curiosity_gap": "curiosity gap",
    "novelty": "novel angle",
    "emotional_energy": "emotional energy",
    "specificity": "specificity",
    "credibility": "credibility",
    "audience_fit": "audience fit",
    "readability": "readability",
    "narrative": "narrative flow",
    "actionability": "actionability",
    "discussion_potential": "discussion potential",
    "shareability": "shareability",
    "telegram_format_fit": "Telegram format fit",
}

PENALTY_LABELS = {
    "clickbait": "clickbait patterns",
    "vague_text": "vague wording",
    "too_long": "too long",
    "too_promotional": "promotional tone",
    "unsupported_claims": "unsupported claims",
    "duplicate_or_rewritten_low_value": "low-value rewrite",
    "cognitive_overload": "cognitive overload",
    "weak_opening": "weak opening",
    "weak_telegram_fit": "weak Telegram fit",
}


def strongest_points(factors: PsychologicalFactors, limit: int = 3) -> list[str]:
    items = sorted(factors.model_dump().items(), key=lambda item: item[1], reverse=True)
    return [FACTOR_LABELS[name] for name, value in items[:limit] if value >= 0.55]


def weakest_points(
    factors: PsychologicalFactors,
    penalties: PenaltyFactors,
    limit: int = 4,
) -> list[str]:
    factor_items = [(FACTOR_LABELS[name], 1.0 - value) for name, value in factors.model_dump().items()]
    penalty_items = [(PENALTY_LABELS[name], value) for name, value in penalties.model_dump().items()]
    items = sorted(factor_items + penalty_items, key=lambda item: item[1], reverse=True)
    return [name for name, value in items[:limit] if value >= 0.35]


def improvement_suggestions(
    input_data: ContentScoreInput,
    factors: PsychologicalFactors,
    penalties: PenaltyFactors,
) -> list[str]:
    suggestions: list[str] = []
    if factors.hook_strength < 0.45 or penalties.weak_opening > 0.45:
        suggestions.append("Rewrite the first 1-2 lines with a concrete pain point, question, or surprising fact.")
    if factors.utility < 0.55:
        suggestions.append("Add a clear takeaway, instruction, or practical benefit for the reader.")
    if factors.specificity < 0.5:
        suggestions.append("Add concrete numbers, examples, named tools, or before/after detail.")
    if penalties.unsupported_claims > 0.3:
        suggestions.append("Replace absolute claims with sourced facts or more precise wording.")
    if penalties.too_long > 0.3 or penalties.cognitive_overload > 0.3:
        suggestions.append("Shorten the text and break it into simpler paragraphs or bullets.")
    if penalties.too_promotional > 0.3:
        suggestions.append("Reduce sales language and focus on reader value first.")
    if factors.telegram_format_fit < 0.45 or penalties.weak_telegram_fit > 0.35:
        suggestions.append("Adapt the post to Telegram: shorter blocks, stronger opening, clearer structure.")
    if input_data.has_poll and "poll" not in " ".join(suggestions).lower():
        suggestions.append("If this is a poll post, end with a direct question that invites a quick response.")
    return suggestions[:5]


def recommend_format(input_data: ContentScoreInput, total_score: float) -> RecommendedFormat:
    if total_score < 58:
        return "do_not_publish"
    if input_data.has_poll:
        return "poll"
    if input_data.has_video:
        return "post_with_video"
    if input_data.has_image:
        return "post_with_image"
    if len(input_data.text) > 1400:
        return "thread_like_series"
    if len(input_data.text) > 900:
        return "long_post"
    return "short_post"
