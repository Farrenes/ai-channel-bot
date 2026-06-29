from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .config import (
    DECISION_THRESHOLDS,
    DEFAULT_VARIANT_COUNT,
    MAX_IMPROVEMENT_PASSES,
    PENALTY_WEIGHTS,
    SCORING_WEIGHTS,
)
from .explanations import improvement_suggestions, recommend_format, strongest_points, weakest_points
from .llm_analyzer import LLMAnalyzerAdapter, analyze_with_fallback
from .models import ContentScoreInput, ContentScoreResult
from .penalties import score_penalties


class ContentGeneratorAdapter(Protocol):
    def generate_variants(
        self,
        source_material: str,
        niche: str | None = None,
        target_audience: str | None = None,
        count: int = DEFAULT_VARIANT_COUNT,
    ) -> list[str]:
        ...

    def rewrite(
        self,
        text: str,
        suggestions: list[str],
        source_material: str,
        niche: str | None = None,
        target_audience: str | None = None,
    ) -> str:
        ...


@dataclass
class GenerateSelectResult:
    best_text: str
    best_result: ContentScoreResult
    candidates: list[tuple[str, ContentScoreResult]]


def score_content(
    input_data: ContentScoreInput,
    llm_adapter: LLMAnalyzerAdapter | None = None,
    comparison_texts: list[str] | None = None,
) -> ContentScoreResult:
    factors = analyze_with_fallback(input_data, llm_adapter=llm_adapter, comparison_texts=comparison_texts)
    penalties = score_penalties(input_data, comparison_texts=comparison_texts)

    base_score = sum(getattr(factors, factor_name) * weight for factor_name, weight in SCORING_WEIGHTS.items()) * 100
    penalty_score = sum(getattr(penalties, penalty_name) * weight for penalty_name, weight in PENALTY_WEIGHTS.items()) * 100
    total_score = max(0.0, min(100.0, base_score - penalty_score))

    if total_score >= DECISION_THRESHOLDS["publish"]:
        decision = "publish"
    elif total_score >= DECISION_THRESHOLDS["improve"]:
        decision = "improve"
    else:
        decision = "reject"

    return ContentScoreResult(
        total_score=round(total_score, 2),
        base_score=round(base_score, 2),
        penalty_score=round(penalty_score, 2),
        decision=decision,
        factors=factors,
        penalties=penalties,
        strongest_points=strongest_points(factors),
        weakest_points=weakest_points(factors, penalties),
        improvement_suggestions=improvement_suggestions(input_data, factors, penalties),
        recommended_format=recommend_format(input_data, total_score),
    )


def generate_and_select_best_post(
    source_material: str,
    niche: str | None,
    target_audience: str | None,
    generator: ContentGeneratorAdapter,
    llm_adapter: LLMAnalyzerAdapter | None = None,
    variant_count: int = DEFAULT_VARIANT_COUNT,
) -> GenerateSelectResult:
    variants = generator.generate_variants(
        source_material=source_material,
        niche=niche,
        target_audience=target_audience,
        count=max(3, variant_count),
    )
    if not variants:
        raise ValueError("generator returned no variants")

    scored_candidates: list[tuple[str, ContentScoreResult]] = []
    normalized_variants = [variant.strip() for variant in variants if variant and variant.strip()]
    for variant in normalized_variants:
        result = _score_variant(
            variant=variant,
            source_material=source_material,
            niche=niche,
            target_audience=target_audience,
            llm_adapter=llm_adapter,
            comparison_texts=normalized_variants,
        )
        if result.decision == "improve":
            improved_text = _improve_variant(
                generator=generator,
                text=variant,
                result=result,
                source_material=source_material,
                niche=niche,
                target_audience=target_audience,
                llm_adapter=llm_adapter,
                comparison_texts=normalized_variants,
            )
            improved_result = _score_variant(
                variant=improved_text,
                source_material=source_material,
                niche=niche,
                target_audience=target_audience,
                llm_adapter=llm_adapter,
                comparison_texts=normalized_variants,
            )
            if improved_result.total_score >= result.total_score:
                variant, result = improved_text, improved_result
        scored_candidates.append((variant, result))

    best_text, best_result = max(scored_candidates, key=lambda item: item[1].total_score)
    return GenerateSelectResult(
        best_text=best_text,
        best_result=best_result,
        candidates=scored_candidates,
    )


def _score_variant(
    *,
    variant: str,
    source_material: str,
    niche: str | None,
    target_audience: str | None,
    llm_adapter: LLMAnalyzerAdapter | None,
    comparison_texts: list[str],
) -> ContentScoreResult:
    return score_content(
        ContentScoreInput(
            text=variant,
            title=_derive_title(source_material),
            niche=niche,
            target_audience=target_audience,
            post_type="unknown",
        ),
        llm_adapter=llm_adapter,
        comparison_texts=[text for text in comparison_texts if text != variant],
    )


def _improve_variant(
    *,
    generator: ContentGeneratorAdapter,
    text: str,
    result: ContentScoreResult,
    source_material: str,
    niche: str | None,
    target_audience: str | None,
    llm_adapter: LLMAnalyzerAdapter | None,
    comparison_texts: list[str],
) -> str:
    rewritten = text
    current_result = result
    for _ in range(MAX_IMPROVEMENT_PASSES):
        candidate = generator.rewrite(
            text=rewritten,
            suggestions=current_result.improvement_suggestions,
            source_material=source_material,
            niche=niche,
            target_audience=target_audience,
        )
        if not candidate or candidate.strip() == rewritten.strip():
            break
        candidate_result = _score_variant(
            variant=candidate,
            source_material=source_material,
            niche=niche,
            target_audience=target_audience,
            llm_adapter=llm_adapter,
            comparison_texts=comparison_texts,
        )
        rewritten, current_result = candidate, candidate_result
        if current_result.decision == "publish":
            break
    return rewritten


def _derive_title(source_material: str) -> str:
    first_line = next((line.strip() for line in source_material.splitlines() if line.strip()), "")
    if not first_line:
        return "Generated Telegram post"
    return first_line[:120]
