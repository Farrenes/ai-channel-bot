from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from pydantic import BaseModel, Field

import database
from app.scoring.models import ContentScoreInput
from app.scoring.scorer import score_content


class ScoringInputItem(BaseModel):
    title: str = Field(min_length=1)
    description: str = ""
    source: str = ""
    link: str = ""
    category: str = ""


class ScoringContext(BaseModel):
    content_strategy: str = ""
    topic_profile: dict[str, Any] = Field(default_factory=dict)
    topic_type: list[str] = Field(default_factory=list)
    save_to_db: bool = True


class ScoringItemResult(BaseModel):
    title: str
    source: str = ""
    link: str = ""
    category: str = ""
    relevance_score: int = 0
    quality_score: int = 0
    novelty_score: int = 0
    authority_score: int = 0
    risk_score: int = 0
    virality_score: int = 0
    evergreen_score: int = 0
    commercial_score: int = 0
    final_score: int = 0
    score_b2c: int = 0
    score_utility: int = 0
    score_savability: int = 0
    score_repostability: int = 0
    score_practical: int = 0
    total_score: int = 0
    raw_description: str = ""
    status: str = "pending"
    content_hash: str = ""
    base_score: float = 0.0
    penalty_score: float = 0.0
    decision: str = ""
    factor_breakdown: dict[str, float] = Field(default_factory=dict)
    penalty_breakdown: dict[str, float] = Field(default_factory=dict)
    strongest_points: list[str] = Field(default_factory=list)
    weakest_points: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)
    recommended_format: str = ""


class ScoringResponse(BaseModel):
    status: str
    total_items: int
    filtered_items: int
    scored_items: int
    items: list[ScoringItemResult]


class ScoringEnvelope(BaseModel):
    status: str
    module: str
    run_id: str
    duration_ms: int
    data: ScoringResponse | dict[str, Any]
    errors: list[str] = Field(default_factory=list)


class ScoringRequest(BaseModel):
    user_id: int | None = None
    items: list[ScoringInputItem]
    content_strategy: str = ""
    topic_profile: dict[str, Any] = Field(default_factory=dict)
    save_to_db: bool = True


DbWriter = Callable[[dict[str, Any]], Awaitable[None]]
ScoreRunner = Callable[[list[dict[str, Any]], ScoringContext], Awaitable[dict[str, dict[str, Any]]]]


def _normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _dedupe_key(item: dict[str, Any]) -> str:
    title = _normalize_text(item.get("title", ""))
    link = _normalize_text(item.get("link", ""))
    return f"{title}|{link}" if link else title


def cheap_prefilter(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        title = (item.get("title") or "").strip()
        description = (item.get("description") or "").strip()
        if not title or len(title) < 8:
            continue
        if len(title.split()) < 2:
            continue
        if title.lower() in {"[ removed by reddit ]", "plz help me", "soon at your local school"}:
            continue
        key = _dedupe_key(item)
        if key in seen:
            continue
        seen.add(key)
        filtered.append({**item, "title": title, "description": description})
    return filtered


def _normalize_topic_types(topic_type: Iterable[str] | str | None) -> list[str]:
    if topic_type is None:
        return []
    if isinstance(topic_type, str):
        values = [topic_type]
    else:
        values = [str(item) for item in topic_type if str(item).strip()]
    cleaned: list[str] = []
    for value in values:
        normalized = value.strip().lower().replace(" ", "_")
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned


def build_scoring_weights(
    content_strategy: str = "",
    topic_profile: dict[str, Any] | None = None,
    topic_type: Iterable[str] | str | None = None,
) -> dict[str, float]:
    profile = topic_profile or {}
    strategy = (content_strategy or profile.get("content_strategy") or "").strip().lower()
    types = set(_normalize_topic_types(topic_type or profile.get("topic_type") or []))
    domain = str(profile.get("domain") or "").strip().lower()
    risk_level = str(profile.get("risk_level") or "").strip().lower()

    weights = {
        "relevance_score": 0.18,
        "quality_score": 0.16,
        "novelty_score": 0.12,
        "authority_score": 0.12,
        "risk_score": 0.10,
        "virality_score": 0.12,
        "evergreen_score": 0.10,
        "commercial_score": 0.10,
    }

    def bump(name: str, delta: float) -> None:
        weights[name] = max(0.01, weights[name] + delta)

    if any(token in strategy for token in ("practical path", "steps and examples", "tutorial")) or "tutorial" in types:
        bump("relevance_score", 0.04)
        bump("quality_score", 0.05)
        bump("evergreen_score", 0.05)
        bump("commercial_score", 0.02)
        bump("virality_score", -0.03)
        bump("novelty_score", -0.02)
    elif any(token in strategy for token in ("compare options", "trade-offs")) or "comparison" in types:
        bump("authority_score", 0.05)
        bump("novelty_score", 0.04)
        bump("commercial_score", 0.03)
        bump("virality_score", 0.02)
        bump("evergreen_score", -0.02)
    elif "what changed" in strategy or "news" in types:
        bump("relevance_score", 0.05)
        bump("novelty_score", 0.05)
        bump("virality_score", 0.05)
        bump("quality_score", -0.02)
        bump("evergreen_score", -0.02)
    elif "research" in types or "evidence" in strategy:
        bump("authority_score", 0.06)
        bump("quality_score", 0.05)
        bump("evergreen_score", 0.03)
        bump("virality_score", -0.02)

    if domain in {"legal", "finance", "health", "security"} or risk_level == "high" or "policy" in types or "safety" in types:
        bump("risk_score", 0.06)
        bump("authority_score", 0.03)
        bump("virality_score", -0.03)

    total = sum(weights.values())
    return {name: value / total for name, value in weights.items()}


def _estimate_risk_score(item: dict[str, Any], context: ScoringContext) -> int:
    profile = context.topic_profile
    risk_level = str(profile.get("risk_level") or "").strip().lower()
    topic_type = set(_normalize_topic_types(context.topic_type or profile.get("topic_type") or []))
    content = f"{item.get('title', '')} {item.get('description', '')}".lower()
    score = 15
    if risk_level == "high":
        score += 50
    elif risk_level == "medium":
        score += 20
    if topic_type & {"policy", "safety"}:
        score += 15
    if any(marker in content for marker in ("scam", "fraud", "warning", "critical", "risk", "unsafe")):
        score += 10
    return max(0, min(100, score))


def _content_hash(item: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    digest.update(_normalize_text(item.get("title", "")).encode("utf-8"))
    digest.update(b"|")
    digest.update(_normalize_text(item.get("description", "")).encode("utf-8"))
    digest.update(b"|")
    digest.update(_normalize_text(item.get("source", "")).encode("utf-8"))
    digest.update(b"|")
    digest.update(_normalize_text(item.get("link", "")).encode("utf-8"))
    return digest.hexdigest()


def _content_score_idempotency_key(item: dict[str, Any], context: ScoringContext) -> str:
    digest = hashlib.sha256()
    digest.update(_content_hash(item).encode("utf-8"))
    digest.update(b"|")
    digest.update(str(context.topic_profile.get("id") or context.topic_profile.get("topic_profile_id") or "").encode("utf-8"))
    digest.update(b"|")
    digest.update(str(context.content_strategy or "").encode("utf-8"))
    return digest.hexdigest()


def _map_result(
    item: dict[str, Any],
    context: ScoringContext,
    legacy_scores: dict[str, Any] | None = None,
) -> ScoringItemResult:
    scoring_input = ContentScoreInput(
        text=f"{item.get('title', '').strip()}\n\n{item.get('description', '').strip()}".strip(),
        title=item.get("title", ""),
        source_url=item.get("link", "") or None,
        source_channel=item.get("source", "") or None,
        niche=context.topic_profile.get("normalized_topic") or context.topic_profile.get("raw_topic") or None,
        target_audience=context.topic_profile.get("target_audience") or None,
        post_type="news" if "news" in context.topic_type else "unknown",
    )
    scored = score_content(scoring_input)
    if legacy_scores:
        return ScoringItemResult(
            title=item.get("title", ""),
            source=item.get("source", ""),
            link=item.get("link", ""),
            category=item.get("category", ""),
            relevance_score=int(legacy_scores.get("relevance_score", 0)),
            quality_score=int(legacy_scores.get("quality_score", 0)),
            novelty_score=int(legacy_scores.get("novelty_score", 0)),
            authority_score=int(legacy_scores.get("authority_score", 0)),
            risk_score=int(legacy_scores.get("risk_score", _estimate_risk_score(item, context))),
            virality_score=int(legacy_scores.get("virality_score", 0)),
            evergreen_score=int(legacy_scores.get("evergreen_score", 0)),
            commercial_score=int(legacy_scores.get("commercial_score", 0)),
            final_score=int(legacy_scores.get("final_score", legacy_scores.get("total_score", 0))),
            score_b2c=int(legacy_scores.get("score_b2c", legacy_scores.get("virality_score", 0))),
            score_utility=int(legacy_scores.get("score_utility", legacy_scores.get("quality_score", 0))),
            score_savability=int(legacy_scores.get("score_savability", legacy_scores.get("evergreen_score", 0))),
            score_repostability=int(legacy_scores.get("score_repostability", legacy_scores.get("virality_score", 0))),
            score_practical=int(legacy_scores.get("score_practical", legacy_scores.get("quality_score", 0))),
            total_score=int(legacy_scores.get("total_score", legacy_scores.get("final_score", 0))),
            raw_description=item.get("description", ""),
            status=legacy_scores.get("status", "pending"),
            content_hash=_content_hash(item),
            decision="pending",
        )

    factors = scored.factors
    penalties = scored.penalties

    relevance = round((factors.utility * 0.45 + factors.audience_fit * 0.35 + factors.hook_strength * 0.20) * 100)
    quality = round((factors.readability * 0.30 + factors.credibility * 0.35 + factors.specificity * 0.35) * 100)
    novelty = round((factors.novelty * 0.70 + factors.curiosity_gap * 0.30) * 100)
    authority = round((factors.credibility * 0.70 + factors.utility * 0.30) * 100)
    risk = max(_estimate_risk_score(item, context), round((penalties.unsupported_claims * 0.5 + penalties.clickbait * 0.25 + penalties.too_promotional * 0.25) * 100))
    virality = round((factors.shareability * 0.45 + factors.emotional_energy * 0.30 + factors.hook_strength * 0.25) * 100)
    evergreen = round((factors.utility * 0.45 + factors.specificity * 0.25 + factors.readability * 0.30) * 100)
    commercial = round((factors.actionability * 0.45 + factors.utility * 0.35 + (1.0 - penalties.too_promotional) * 0.20) * 100)
    final_score = int(round(scored.total_score))

    return ScoringItemResult(
        title=item.get("title", ""),
        source=item.get("source", ""),
        link=item.get("link", ""),
        category=item.get("category", ""),
        relevance_score=max(0, min(100, relevance)),
        quality_score=max(0, min(100, quality)),
        novelty_score=max(0, min(100, novelty)),
        authority_score=max(0, min(100, authority)),
        risk_score=max(0, min(100, risk)),
        virality_score=max(0, min(100, virality)),
        evergreen_score=max(0, min(100, evergreen)),
        commercial_score=max(0, min(100, commercial)),
        final_score=max(0, min(100, final_score)),
        score_b2c=max(0, min(100, virality)),
        score_utility=max(0, min(100, round(factors.utility * 100))),
        score_savability=max(0, min(100, round((factors.utility * 0.4 + factors.specificity * 0.3 + factors.readability * 0.3) * 100))),
        score_repostability=max(0, min(100, round((factors.shareability * 0.6 + factors.novelty * 0.4) * 100))),
        score_practical=max(0, min(100, round((factors.actionability * 0.5 + factors.utility * 0.5) * 100))),
        total_score=max(0, min(100, final_score)),
        raw_description=item.get("description", ""),
        status="pending" if final_score >= 30 else "rejected",
        content_hash=_content_hash(item),
        base_score=scored.base_score,
        penalty_score=scored.penalty_score,
        decision=scored.decision,
        factor_breakdown=scored.factors.model_dump(),
        penalty_breakdown=scored.penalties.model_dump(),
        strongest_points=scored.strongest_points,
        weakest_points=scored.weakest_points,
        improvement_suggestions=scored.improvement_suggestions,
        recommended_format=scored.recommended_format,
    )


def _build_content_score_payload(
    item: dict[str, Any],
    scored_item: ScoringItemResult,
    context: ScoringContext,
) -> dict[str, Any]:
    profile = context.topic_profile
    text = f"{item.get('title', '').strip()}\n\n{item.get('description', '').strip()}".strip()
    topic_profile_id = profile.get("id") or profile.get("topic_profile_id")
    topic_config_id = profile.get("topic_config_id")
    return {
        "topic_profile_id": topic_profile_id,
        "topic_config_id": topic_config_id,
        "source_id": item.get("source_id"),
        "candidate_id": item.get("candidate_id"),
        "generated_post_id": item.get("generated_post_id"),
        "idea_id": item.get("idea_id"),
        "published_post_id": item.get("published_post_id"),
        "content_kind": item.get("content_kind", "candidate"),
        "scoring_stage": item.get("scoring_stage", "pre_generation"),
        "content_hash": scored_item.content_hash,
        "title": scored_item.title,
        "content_text": text,
        "source_name": scored_item.source,
        "niche": profile.get("normalized_topic") or profile.get("raw_topic") or scored_item.category,
        "audience": profile.get("target_audience", ""),
        "format": profile.get("default_post_format", "telegram_html"),
        "post_type": "news" if "news" in context.topic_type else "unknown",
        "model_name": "heuristic",
        "score_version": 1,
        "base_score": scored_item.base_score,
        "penalty_score": scored_item.penalty_score,
        "total_score": scored_item.total_score,
        "decision": scored_item.decision if scored_item.decision in {"publish", "improve", "reject"} else "improve",
        "factor_breakdown": scored_item.factor_breakdown,
        "penalty_breakdown": scored_item.penalty_breakdown,
        "strong_sides": scored_item.strongest_points,
        "weak_sides": scored_item.weakest_points,
        "recommendations": scored_item.improvement_suggestions,
        "recommended_format": scored_item.recommended_format or "short_post",
        "idempotency_key": _content_score_idempotency_key(item, context),
        "metadata": {
            "content_strategy": context.content_strategy,
            "source_url": scored_item.link,
            "category": scored_item.category,
            "legacy_scores": {
                "relevance_score": scored_item.relevance_score,
                "quality_score": scored_item.quality_score,
                "novelty_score": scored_item.novelty_score,
                "authority_score": scored_item.authority_score,
                "risk_score": scored_item.risk_score,
                "virality_score": scored_item.virality_score,
                "evergreen_score": scored_item.evergreen_score,
                "commercial_score": scored_item.commercial_score,
            },
        },
    }


async def save_content_score(payload: dict[str, Any]) -> None:
    if database.db_pool is None:
        return

    sql = """
        INSERT INTO content_scores (
            topic_profile_id, topic_config_id, source_id, candidate_id, generated_post_id,
            idea_id, published_post_id, content_kind, scoring_stage, content_hash,
            title, content_text, source_name, niche, audience, format, post_type,
            model_name, score_version, base_score, penalty_score, total_score,
            decision, factor_breakdown, penalty_breakdown, strong_sides, weak_sides,
            recommendations, recommended_format, idempotency_key, metadata
        ) VALUES (
            $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,
            $11,$12,$13,$14,$15,$16,$17,$18,$19,$20,
            $21,$22,$23,$24::jsonb,$25::jsonb,$26::jsonb,$27::jsonb,$28::jsonb,
            $29,$30,$31::jsonb
        )
        ON CONFLICT (idempotency_key)
        WHERE idempotency_key IS NOT NULL
        DO UPDATE SET
            base_score = EXCLUDED.base_score,
            penalty_score = EXCLUDED.penalty_score,
            total_score = EXCLUDED.total_score,
            decision = EXCLUDED.decision,
            factor_breakdown = EXCLUDED.factor_breakdown,
            penalty_breakdown = EXCLUDED.penalty_breakdown,
            strong_sides = EXCLUDED.strong_sides,
            weak_sides = EXCLUDED.weak_sides,
            recommendations = EXCLUDED.recommendations,
            recommended_format = EXCLUDED.recommended_format,
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
    """
    async with database.db_pool.acquire() as conn:
        await conn.execute(
            sql,
            payload.get("topic_profile_id"),
            payload.get("topic_config_id"),
            payload.get("source_id"),
            payload.get("candidate_id"),
            payload.get("generated_post_id"),
            payload.get("idea_id"),
            payload.get("published_post_id"),
            payload.get("content_kind", "candidate"),
            payload.get("scoring_stage", "pre_generation"),
            payload.get("content_hash", ""),
            payload.get("title", ""),
            payload.get("content_text", ""),
            payload.get("source_name", ""),
            payload.get("niche", ""),
            payload.get("audience", ""),
            payload.get("format", "telegram_html"),
            payload.get("post_type", "unknown"),
            payload.get("model_name", "heuristic"),
            payload.get("score_version", 1),
            payload.get("base_score", 0),
            payload.get("penalty_score", 0),
            payload.get("total_score", 0),
            payload.get("decision", "improve"),
            json.dumps(payload.get("factor_breakdown", {})),
            json.dumps(payload.get("penalty_breakdown", {})),
            json.dumps(payload.get("strong_sides", [])),
            json.dumps(payload.get("weak_sides", [])),
            json.dumps(payload.get("recommendations", [])),
            payload.get("recommended_format", "short_post"),
            payload.get("idempotency_key"),
            json.dumps(payload.get("metadata", {})),
        )


async def score_items_universal(
    items: Iterable[ScoringInputItem | dict[str, Any]],
    *,
    content_strategy: str = "",
    topic_profile: dict[str, Any] | None = None,
    topic_type: Iterable[str] | str | None = None,
    save_to_db: bool = True,
    db_writer: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    score_runner: ScoreRunner | None = None,
) -> ScoringResponse:
    prepared = [item.model_dump() if isinstance(item, ScoringInputItem) else dict(item) for item in items]
    total_input = len(prepared)
    if not prepared:
        return ScoringResponse(status="ok", total_items=0, filtered_items=0, scored_items=0, items=[])

    cheap = cheap_prefilter(prepared)
    if not cheap:
        return ScoringResponse(status="ok", total_items=total_input, filtered_items=0, scored_items=0, items=[])

    context = ScoringContext(
        content_strategy=content_strategy or (topic_profile or {}).get("content_strategy", ""),
        topic_profile=dict(topic_profile or {}),
        topic_type=_normalize_topic_types(topic_type or (topic_profile or {}).get("topic_type") or []),
        save_to_db=save_to_db,
    )
    legacy_map: dict[str, dict[str, Any]] = {}
    if score_runner is not None:
        legacy_map = await score_runner(cheap, context)
    scored_items: list[ScoringItemResult] = []
    for item in cheap:
        legacy = legacy_map.get(_normalize_text(item.get("title", ""))[:80]) or legacy_map.get(item.get("title", ""))
        scored_item = _map_result(item, context, legacy_scores=legacy)
        scored_items.append(scored_item)
        if save_to_db:
            if db_writer is not None:
                await db_writer(scored_item.model_dump())
            elif scored_item.factor_breakdown:
                await save_content_score(_build_content_score_payload(item, scored_item, context))

    return ScoringResponse(
        status="ok",
        total_items=total_input,
        filtered_items=len(cheap),
        scored_items=len(scored_items),
        items=scored_items,
    )


class ScoringService:
    async def score_items(
        self,
        *,
        items: list[ScoringInputItem | dict[str, Any]],
        content_strategy: str = "",
        topic_profile: dict[str, Any] | None = None,
        save_to_db: bool = True,
        db_writer: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
        score_runner: ScoreRunner | None = None,
    ) -> ScoringResponse:
        return await score_items_universal(
            items,
            content_strategy=content_strategy,
            topic_profile=topic_profile,
            save_to_db=save_to_db,
            db_writer=db_writer,
            score_runner=score_runner,
        )
