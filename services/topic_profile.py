from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any, Callable

from pydantic import BaseModel, Field


class TopicProfileRequest(BaseModel):
    raw_topic: str = Field(min_length=1)


class TopicProfile(BaseModel):
    raw_topic: str
    normalized_topic: str
    topic_type: list[str]
    domain: str
    risk_level: str
    content_strategy: str
    default_post_format: str
    language: str
    tone: str
    depth: str
    allowed_source_types: list[str]
    blocked_source_types: list[str]
    requires_human_approval: bool


class TopicProfileEnvelope(BaseModel):
    status: str
    module: str
    run_id: str
    duration_ms: int
    data: TopicProfile
    errors: list[str] = Field(default_factory=list)


class TopicProfileService:
    def __init__(self, llm_client: Callable[[str], dict[str, Any]] | None = None):
        self.llm_client = llm_client

    def build_profile(self, raw_topic: str) -> tuple[dict[str, Any], list[str]]:
        fallback_profile = self._deterministic_profile(raw_topic)

        if self.llm_client is None:
            return fallback_profile, []

        try:
            llm_profile = self.llm_client(raw_topic)
            if not isinstance(llm_profile, dict):
                raise TypeError("LLM profile must be a mapping")
            merged = self._merge_profiles(fallback_profile, llm_profile)
            return merged, []
        except Exception as exc:  # pragma: no cover - exercised in fallback test
            return fallback_profile, [f"LLM unavailable, used deterministic fallback: {exc}"]

    def _merge_profiles(self, fallback_profile: dict[str, Any], llm_profile: dict[str, Any]) -> dict[str, Any]:
        merged = dict(fallback_profile)
        for key, value in llm_profile.items():
            if key == "topic_type":
                merged[key] = self._normalize_types(value) or merged[key]
            elif key in {"allowed_source_types", "blocked_source_types"}:
                merged[key] = self._normalize_types(value) or merged[key]
            elif key in merged and value not in (None, ""):
                merged[key] = value
        merged["topic_type"] = self._normalize_types(merged.get("topic_type")) or ["general"]
        merged["allowed_source_types"] = self._normalize_types(merged.get("allowed_source_types"))
        merged["blocked_source_types"] = self._normalize_types(merged.get("blocked_source_types"))
        return merged

    def _deterministic_profile(self, raw_topic: str) -> dict[str, Any]:
        normalized_topic = self._normalize_topic(raw_topic)
        topic_types = self._detect_topic_types(normalized_topic)
        domain = self._detect_domain(normalized_topic, topic_types)
        risk_level = self._detect_risk_level(normalized_topic, topic_types, domain)
        default_post_format = self._default_post_format(topic_types, risk_level)
        language = self._detect_language(raw_topic)
        tone = self._default_tone(topic_types, risk_level)
        depth = self._default_depth(topic_types, risk_level)
        allowed_source_types, blocked_source_types = self._default_source_policy(risk_level, topic_types)

        return {
            "raw_topic": raw_topic,
            "normalized_topic": normalized_topic,
            "topic_type": topic_types,
            "domain": domain,
            "risk_level": risk_level,
            "content_strategy": self._content_strategy(topic_types, domain, risk_level),
            "default_post_format": default_post_format,
            "language": language,
            "tone": tone,
            "depth": depth,
            "allowed_source_types": allowed_source_types,
            "blocked_source_types": blocked_source_types,
            "requires_human_approval": risk_level == "high",
        }

    def _normalize_topic(self, raw_topic: str) -> str:
        compact = re.sub(r"\s+", " ", raw_topic.strip())
        compact = re.sub(r"^[\W_]+|[\W_]+$", "", compact)
        return compact.lower()

    def _normalize_types(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            items = [value]
        elif isinstance(value, Iterable):
            items = [str(item) for item in value if str(item).strip()]
        else:
            items = [str(value)]
        cleaned: list[str] = []
        for item in items:
            normalized = item.strip().lower().replace(" ", "_")
            if normalized and normalized not in cleaned:
                cleaned.append(normalized)
        return cleaned

    def _detect_topic_types(self, normalized_topic: str) -> list[str]:
        topic_types: list[str] = []

        keyword_map = [
            ("policy", ("policy", "compliance", "regulation", "legal", "privacy", "governance")),
            ("news", ("news", "update", "announces", "announcement", "release", "launch", "breaking")),
            ("tutorial", ("how to", "guide", "tutorial", "step by step", "workflow", "walkthrough")),
            ("comparison", ("vs", "versus", "compare", "comparison", "alternatives", "best", "top")),
            ("research", ("research", "study", "paper", "benchmark", "analysis", "evaluation")),
            ("strategy", ("strategy", "roadmap", "plan", "market", "positioning", "pricing")),
            ("prompt", ("prompt", "prompts", "prompting")),
            ("tool", ("tool", "app", "platform", "plugin", "extension", "software", "product", "model")),
            ("safety", ("safety", "risk", "guardrail", "security", "abuse", "misuse")),
        ]

        for topic_type, keywords in keyword_map:
            if any(keyword in normalized_topic for keyword in keywords):
                topic_types.append(topic_type)

        return topic_types or ["general"]

    def _detect_domain(self, normalized_topic: str, topic_types: list[str]) -> str:
        domain_map = [
            ("ai", ("ai", "llm", "openai", "chatgpt", "model", "prompt", "agent", "copilot", "gpt")),
            ("security", ("security", "vulnerability", "threat", "exploit", "attack", "defense")),
            ("finance", ("finance", "market", "trading", "investment", "stocks", "crypto", "bank")),
            ("health", ("health", "medical", "clinical", "patient", "therapy")),
            ("legal", ("legal", "law", "policy", "compliance", "regulation")),
            ("marketing", ("marketing", "seo", "content", "campaign", "audience", "brand")),
            ("software", ("tool", "app", "platform", "plugin", "extension", "api", "software", "developer", "code")),
        ]

        for domain, keywords in domain_map:
            if any(keyword in normalized_topic for keyword in keywords):
                return domain

        if "policy" in topic_types:
            return "legal"
        return "general"

    def _detect_risk_level(self, normalized_topic: str, topic_types: list[str], domain: str) -> str:
        high_risk_markers = ("policy", "security", "legal", "finance", "health", "compliance", "regulation", "vulnerability")
        if domain in {"legal", "finance", "health", "security"} or any(marker in normalized_topic for marker in high_risk_markers):
            return "high"
        if "research" in topic_types or "comparison" in topic_types or "news" in topic_types:
            return "medium"
        return "low"

    def _default_post_format(self, topic_types: list[str], risk_level: str) -> str:
        if risk_level == "high":
            return "brief_explainer"
        if "tutorial" in topic_types:
            return "how_to"
        if "comparison" in topic_types or "research" in topic_types:
            return "analysis_note"
        if "news" in topic_types:
            return "brief_explainer"
        if "tool" in topic_types:
            return "how_to"
        return "brief_explainer"

    def _detect_language(self, raw_topic: str) -> str:
        return "ru" if re.search(r"[А-Яа-яЁё]", raw_topic) else "en"

    def _default_tone(self, topic_types: list[str], risk_level: str) -> str:
        if risk_level == "high":
            return "cautious"
        if "tutorial" in topic_types or "tool" in topic_types:
            return "practical"
        return "analytical"

    def _default_depth(self, topic_types: list[str], risk_level: str) -> str:
        if risk_level == "high" or "research" in topic_types:
            return "deep"
        return "standard"

    def _default_source_policy(self, risk_level: str, topic_types: list[str]) -> tuple[list[str], list[str]]:
        allowed = ["official_docs", "primary_news", "reputable_sources"]
        blocked = ["speculation", "unverified_social_posts", "anonymous_forums"]

        if "tutorial" in topic_types or "tool" in topic_types:
            allowed = ["official_docs", "product_docs", "primary_news", "reputable_sources"]
        if risk_level == "high":
            blocked.append("user_generated_opinion")
        return allowed, blocked

    def _content_strategy(self, topic_types: list[str], domain: str, risk_level: str) -> str:
        if risk_level == "high":
            return "summarize carefully, cite primary sources, and call out caveats"
        if "tutorial" in topic_types:
            return "show a practical path with steps and examples"
        if "comparison" in topic_types:
            return "compare options with clear trade-offs"
        if "research" in topic_types:
            return "summarize evidence, findings, and limitations"
        if "news" in topic_types or "policy" in topic_types:
            return "explain what changed and why it matters"
        if domain == "software":
            return "frame the topic around use cases and implementation details"
        return "explain the topic clearly with one actionable takeaway"
