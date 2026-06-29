from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from services.topic_profile import TopicProfile


class ReviewRequest(BaseModel):
    user_id: int | None = None
    post: str
    topic_profile: TopicProfile
    context: str = Field(default="")
    feedback: str = Field(default="")


class ReviewVerdict(BaseModel):
    approved: bool
    can_autopublish: bool
    risk_blocked: bool
    issues: list[str]
    summary: str


class ReviewRewriteResult(BaseModel):
    post: str
    changed: bool
    can_autopublish: bool
    risk_blocked: bool
    issues: list[str]
    summary: str


class ReviewEnvelope(BaseModel):
    status: str
    module: str
    run_id: str
    duration_ms: int
    data: ReviewVerdict | dict[str, Any]
    errors: list[str] = Field(default_factory=list)


class ReviewRewriteEnvelope(BaseModel):
    status: str
    module: str
    run_id: str
    duration_ms: int
    data: ReviewRewriteResult | dict[str, Any]
    errors: list[str] = Field(default_factory=list)


class ReviewService:
    def __init__(self, llm_client: Callable[[str], Any] | None = None):
        self.llm_client = llm_client

    def review_post(self, post: str, topic_profile: TopicProfile | dict[str, Any], context: str = "") -> dict[str, Any]:
        profile = self._coerce_profile(topic_profile)
        issues: list[str] = []
        approved = True
        can_autopublish = True
        risk_blocked = False

        if not post or not post.strip():
            issues.append("Post is empty.")
            approved = False
            can_autopublish = False

        if profile.get("risk_level") == "high":
            issues.append("High-risk topic blocked from unsafe autopublish.")
            approved = False
            can_autopublish = False
            risk_blocked = True

        if profile.get("requires_human_approval"):
            can_autopublish = False

        summary = "approved" if approved else "rejected"
        if risk_blocked:
            summary = "rejected: high-risk topic requires human review"
        elif not approved:
            summary = "rejected: post failed review checks"

        return {
            "approved": approved,
            "can_autopublish": can_autopublish,
            "risk_blocked": risk_blocked,
            "issues": issues,
            "summary": summary,
        }

    def rewrite_post(
        self,
        post: str,
        topic_profile: TopicProfile | dict[str, Any],
        context: str = "",
        feedback: str = "",
    ) -> dict[str, Any]:
        verdict = self.review_post(post, topic_profile, context)
        profile = self._coerce_profile(topic_profile)
        if verdict["approved"]:
            return {
                "post": post.strip(),
                "changed": False,
                "can_autopublish": verdict["can_autopublish"],
                "risk_blocked": verdict["risk_blocked"],
                "issues": verdict["issues"],
                "summary": "No rewrite needed.",
            }

        rewritten = self._safe_rewrite(post, profile, context, feedback)
        return {
            "post": rewritten,
            "changed": rewritten.strip() != post.strip(),
            "can_autopublish": False,
            "risk_blocked": verdict["risk_blocked"],
            "issues": verdict["issues"],
            "summary": "Rewritten for safety and clarity." if rewritten else "Rewrite unavailable.",
        }

    def _coerce_profile(self, topic_profile: TopicProfile | dict[str, Any]) -> dict[str, Any]:
        if isinstance(topic_profile, TopicProfile):
            return topic_profile.model_dump()
        return dict(topic_profile)

    def _safe_rewrite(
        self,
        post: str,
        profile: dict[str, Any],
        context: str,
        feedback: str,
    ) -> str:
        subject = context.strip() or profile.get("normalized_topic", profile.get("raw_topic", "")).strip()
        if profile.get("risk_level") == "high":
            return "\n".join(
                part
                for part in [
                    subject,
                    "Caution: verify facts against primary sources before taking action.",
                    "This post needs human approval.",
                ]
                if part
            )

        if not post or not post.strip():
            return "\n".join(
                part
                for part in [
                    subject,
                    f"Strategy: {profile.get('content_strategy', '')}",
                    "Rewritten after review feedback.",
                ]
                if part
            )

        return "\n".join(
            part
            for part in [
                post.strip(),
                f"Revision note: {feedback.strip()}" if feedback.strip() else "",
            ]
            if part
        )
