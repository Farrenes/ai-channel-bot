from __future__ import annotations

import re
from typing import Protocol

from .models import ContentScoreInput, PsychologicalFactors
from .penalties import opening_strength


class LLMAnalyzerAdapter(Protocol):
    def analyze(
        self,
        input_data: ContentScoreInput,
        comparison_texts: list[str] | None = None,
    ) -> dict[str, float]:
        ...


def analyze_with_fallback(
    input_data: ContentScoreInput,
    llm_adapter: LLMAnalyzerAdapter | None = None,
    comparison_texts: list[str] | None = None,
) -> PsychologicalFactors:
    if llm_adapter is not None:
        try:
            try:
                payload = llm_adapter.analyze(input_data, comparison_texts=comparison_texts)
            except TypeError:
                payload = llm_adapter.analyze(input_data)
            return PsychologicalFactors(**payload)
        except Exception:
            pass
    return heuristic_analyze(input_data)


def heuristic_analyze(input_data: ContentScoreInput) -> PsychologicalFactors:
    text = input_data.text.strip()
    lowered = text.lower()
    words = [word for word in re.split(r"\s+", text) if word]
    sentences = [part.strip() for part in re.split(r"[.!?]+", text) if part.strip()]
    avg_sentence_length = len(words) / max(1, len(sentences))
    number_hits = len(re.findall(r"\b\d+(?:[%x]|[kmb])?\b", lowered))
    question_hits = lowered.count("?")
    bullet_count = text.count("\n- ") + text.count("\n* ") + text.count("\n1.")

    utility_hits = _count_hits(
        lowered,
        ("how", "step", "guide", "checklist", "save", "reduce", "avoid", "use this", "here is"),
    )
    action_hits = _count_hits(
        lowered,
        ("do this", "try", "start", "use", "compare", "measure", "cut", "add", "remove"),
    )
    credibility_hits = _count_hits(
        lowered,
        ("according to", "source", "study", "report", "data", "official", "benchmark"),
    ) + min(2, number_hits)
    novelty_hits = _count_hits(
        lowered,
        ("new", "unexpected", "instead", "counterintuitive", "changed", "different", "underused"),
    )
    emotional_hits = _count_hits(
        lowered,
        ("mistake", "risk", "problem", "pain", "surprising", "wins", "fails", "waste"),
    )
    discussion_hits = _count_hits(
        lowered,
        ("agree", "disagree", "what do you think", "question", "debate", "should"),
    ) + question_hits

    readability = 0.9
    if avg_sentence_length > 24:
        readability -= min(0.45, (avg_sentence_length - 24) / 40)
    if len(text) > 1600:
        readability -= 0.15
    if len(text) < 60:
        readability -= 0.12

    specificity = min(1.0, 0.18 + (number_hits * 0.14) + (_count_hits(lowered, ("for example", "case", "before", "after")) * 0.12))
    utility = min(1.0, 0.22 + utility_hits * 0.16 + action_hits * 0.09)
    hook = opening_strength(text)
    curiosity_gap = min(1.0, 0.12 + question_hits * 0.15 + _count_hits(lowered, ("why", "what changed", "but", "however", "turns out")) * 0.12)
    novelty = min(1.0, 0.1 + novelty_hits * 0.18)
    emotional_energy = min(1.0, 0.12 + emotional_hits * 0.14)
    credibility = min(1.0, 0.14 + credibility_hits * 0.12)
    audience_fit = _audience_fit(input_data, lowered)
    narrative = min(1.0, 0.18 + _count_hits(lowered, ("first", "then", "finally", "because", "so")) * 0.12)
    actionability = min(1.0, 0.16 + action_hits * 0.18)
    discussion_potential = min(1.0, 0.08 + discussion_hits * 0.12)
    shareability = min(1.0, 0.08 + novelty_hits * 0.1 + emotional_hits * 0.08 + question_hits * 0.08)
    telegram_fit = _telegram_fit(text, bullet_count, input_data)

    return PsychologicalFactors(
        utility=utility,
        hook_strength=hook,
        curiosity_gap=curiosity_gap,
        novelty=novelty,
        emotional_energy=emotional_energy,
        specificity=specificity,
        credibility=credibility,
        audience_fit=audience_fit,
        readability=max(0.0, min(1.0, readability)),
        narrative=narrative,
        actionability=actionability,
        discussion_potential=discussion_potential,
        shareability=shareability,
        telegram_format_fit=telegram_fit,
    )


def _count_hits(text: str, patterns: tuple[str, ...]) -> int:
    return sum(1 for pattern in patterns if pattern in text)


def _audience_fit(input_data: ContentScoreInput, lowered: str) -> float:
    score = 0.35
    for field in (input_data.niche, input_data.target_audience, input_data.title):
        if not field:
            continue
        tokens = [token for token in re.findall(r"\w+", field.lower()) if len(token) > 3]
        if not tokens:
            continue
        overlap = sum(1 for token in tokens if token in lowered)
        score += min(0.35, overlap * 0.08)
    if input_data.post_type in {"guide", "review", "educational", "news"}:
        score += 0.08
    return max(0.0, min(1.0, score))


def _telegram_fit(text: str, bullet_count: int, input_data: ContentScoreInput) -> float:
    score = 0.35
    length = len(text)
    if 180 <= length <= 900:
        score += 0.3
    elif length <= 1400:
        score += 0.15
    if bullet_count > 0:
        score += 0.15
    if "\n\n" in text:
        score += 0.08
    if input_data.has_image or input_data.has_video or input_data.has_buttons:
        score += 0.05
    return max(0.0, min(1.0, score))


# Backward-compatible alias for earlier callers.
ScoringModelAdapter = LLMAnalyzerAdapter
