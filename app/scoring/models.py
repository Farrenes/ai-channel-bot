from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


PostType = Literal[
    "news",
    "guide",
    "story",
    "opinion",
    "case",
    "review",
    "sale",
    "entertainment",
    "educational",
    "unknown",
]

RecommendedFormat = Literal[
    "short_post",
    "long_post",
    "post_with_image",
    "post_with_video",
    "poll",
    "thread_like_series",
    "do_not_publish",
]

DecisionType = Literal["publish", "improve", "reject"]


class ContentScoreInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    content: str = Field(min_length=1, alias="text")
    title: str | None = None
    source_url: str | None = None
    source_channel: str | None = None
    niche: str | None = None
    target_audience: str | None = None
    has_image: bool = False
    has_video: bool = False
    has_poll: bool = False
    has_buttons: bool = False
    post_type: PostType = "unknown"

    @property
    def text(self) -> str:
        return self.content


class _UnitFloatModel(BaseModel):
    @field_validator("*", mode="after")
    @classmethod
    def validate_unit_interval(cls, value: float) -> float:
        if value < 0.0 or value > 1.0:
            raise ValueError("factor must be between 0.0 and 1.0")
        return round(float(value), 4)


class PsychologicalFactors(_UnitFloatModel):
    utility: float = 0.0
    hook_strength: float = 0.0
    curiosity_gap: float = 0.0
    novelty: float = 0.0
    emotional_energy: float = 0.0
    specificity: float = 0.0
    credibility: float = 0.0
    audience_fit: float = 0.0
    readability: float = 0.0
    narrative: float = 0.0
    actionability: float = 0.0
    discussion_potential: float = 0.0
    shareability: float = 0.0
    telegram_format_fit: float = 0.0


class PenaltyFactors(_UnitFloatModel):
    clickbait: float = 0.0
    vague_text: float = 0.0
    too_long: float = 0.0
    too_promotional: float = 0.0
    unsupported_claims: float = 0.0
    duplicate_or_rewritten_low_value: float = 0.0
    cognitive_overload: float = 0.0
    weak_opening: float = 0.0
    weak_telegram_fit: float = 0.0


class ContentScoreResult(BaseModel):
    total_score: float
    base_score: float
    penalty_score: float
    decision: DecisionType
    factors: PsychologicalFactors
    penalties: PenaltyFactors
    strongest_points: list[str]
    weakest_points: list[str]
    improvement_suggestions: list[str]
    recommended_format: RecommendedFormat
