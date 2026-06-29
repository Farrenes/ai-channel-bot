from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from app.scoring.scorer import ContentGeneratorAdapter, generate_and_select_best_post
from services.topic_profile import TopicProfile


class GenerationRequest(BaseModel):
    user_id: int | None = None
    topic_profile: TopicProfile
    context: str = Field(default="")


class GeneratedPost(BaseModel):
    post: str
    content_strategy: str
    tone: str
    depth: str
    default_post_format: str
    risk_level: str
    used_llm: bool
    score: float | None = None
    decision: str | None = None
    candidate_count: int = 1


class GenerationEnvelope(BaseModel):
    status: str
    module: str
    run_id: str
    duration_ms: int
    data: GeneratedPost | dict[str, Any]
    errors: list[str] = Field(default_factory=list)


class GenerationService:
    def __init__(self, llm_client: Callable[[str], Any] | None = None):
        self.llm_client = llm_client

    def generate_post(self, topic_profile: TopicProfile | dict[str, Any], context: str = "") -> tuple[dict[str, Any], list[str]]:
        profile = self._coerce_profile(topic_profile)
        prompt = self._build_prompt(profile, context)
        subject = context.strip() or profile.get("normalized_topic", profile.get("raw_topic", "")).strip()

        generator = _GenerationAdapter(
            profile=profile,
            subject=subject,
            prompt_builder=self._build_prompt,
            post_extractor=self._extract_post,
            llm_client=self.llm_client,
            deterministic_builder=self._deterministic_post,
        )

        best = generate_and_select_best_post(
            source_material=subject,
            niche=profile.get("normalized_topic") or profile.get("raw_topic"),
            target_audience=profile.get("target_audience"),
            generator=generator,
            variant_count=5,
        )
        used_llm = bool(self.llm_client) and generator.used_llm

        errors = list(generator.errors)
        if not used_llm and self.llm_client is not None and not errors:
            errors.append("LLM returned no usable variants; used deterministic fallback")
        return self._build_result(
            profile,
            best.best_text,
            used_llm,
            score=best.best_result.total_score,
            decision=best.best_result.decision,
            candidate_count=len(best.candidates),
        ), errors

    def _coerce_profile(self, topic_profile: TopicProfile | dict[str, Any]) -> dict[str, Any]:
        if isinstance(topic_profile, TopicProfile):
            return topic_profile.model_dump()
        return dict(topic_profile)

    def _build_prompt(self, profile: dict[str, Any], context: str) -> str:
        subject = context.strip() or profile.get("normalized_topic", profile.get("raw_topic", "")).strip()
        return "\n".join(
            [
                "Generate a Telegram post using the topic profile only.",
                f"content_strategy: {profile.get('content_strategy', '')}",
                f"tone: {profile.get('tone', '')}",
                f"depth: {profile.get('depth', '')}",
                f"default_post_format: {profile.get('default_post_format', '')}",
                f"risk_level: {profile.get('risk_level', '')}",
                f"context: {subject}",
            ]
        )

    def _extract_post(self, generated: Any) -> str:
        if isinstance(generated, dict):
            value = generated.get("post") or generated.get("text") or generated.get("content")
            return str(value).strip() if value else ""
        if isinstance(generated, str):
            return generated.strip()
        return ""

    def _deterministic_post(self, profile: dict[str, Any], context: str) -> str:
        subject = context.strip() or profile.get("normalized_topic", profile.get("raw_topic", "")).strip()
        parts = [
            subject,
            f"Strategy: {profile.get('content_strategy', '')}",
            f"Tone: {profile.get('tone', '')}",
            f"Depth: {profile.get('depth', '')}",
            f"Format: {profile.get('default_post_format', '')}",
        ]
        if profile.get("risk_level") == "high":
            parts.append("Caveat: verify with primary sources before acting.")
        return "\n".join(part for part in parts if part)

    def _build_result(
        self,
        profile: dict[str, Any],
        post: str,
        used_llm: bool,
        *,
        score: float | None = None,
        decision: str | None = None,
        candidate_count: int = 1,
    ) -> dict[str, Any]:
        return {
            "post": post,
            "content_strategy": profile.get("content_strategy", ""),
            "tone": profile.get("tone", ""),
            "depth": profile.get("depth", ""),
            "default_post_format": profile.get("default_post_format", ""),
            "risk_level": profile.get("risk_level", ""),
            "used_llm": used_llm,
            "score": score,
            "decision": decision,
            "candidate_count": candidate_count,
        }


class _GenerationAdapter(ContentGeneratorAdapter):
    def __init__(
        self,
        *,
        profile: dict[str, Any],
        subject: str,
        prompt_builder: Callable[[dict[str, Any], str], str],
        post_extractor: Callable[[Any], str],
        llm_client: Callable[[str], Any] | None,
        deterministic_builder: Callable[[dict[str, Any], str], str],
    ) -> None:
        self.profile = profile
        self.subject = subject
        self.prompt_builder = prompt_builder
        self.post_extractor = post_extractor
        self.llm_client = llm_client
        self.deterministic_builder = deterministic_builder
        self.used_llm = False
        self.errors: list[str] = []

    def generate_variants(
        self,
        source_material: str,
        niche: str | None = None,
        target_audience: str | None = None,
        count: int = 5,
    ) -> list[str]:
        variants: list[str] = []
        if self.llm_client is not None:
            for index in range(count):
                prompt = self.prompt_builder(self.profile, source_material)
                prompt = "\n".join(
                    [
                        prompt,
                        f"variation_index: {index + 1}",
                        f"opening_mode: {['fact', 'question', 'contrast', 'checklist', 'insight'][index % 5]}",
                        "Return only the post body.",
                    ]
                )
                try:
                    generated = self.llm_client(prompt)
                    post = self.post_extractor(generated)
                    if post:
                        variants.append(post)
                        self.used_llm = True
                except Exception as exc:
                    self.errors.append(f"LLM generation failed on variant {index + 1}: {exc}")
                    break
        if variants:
            return variants
        return [self._fallback_variant(index, source_material) for index in range(count)]

    def rewrite(
        self,
        text: str,
        suggestions: list[str],
        source_material: str,
        niche: str | None = None,
        target_audience: str | None = None,
    ) -> str:
        if self.llm_client is not None:
            prompt = "\n".join(
                [
                    "Rewrite the Telegram post using the requested improvements.",
                    f"context: {source_material}",
                    "improvements:",
                    *[f"- {item}" for item in suggestions],
                    "original_post:",
                    text,
                ]
            )
            try:
                generated = self.llm_client(prompt)
                rewritten = self.post_extractor(generated)
                if rewritten:
                    self.used_llm = True
                    return rewritten
            except Exception as exc:
                self.errors.append(f"LLM rewrite failed: {exc}")
        return self._fallback_rewrite(text, suggestions)

    def _fallback_variant(self, index: int, source_material: str) -> str:
        base = self.deterministic_builder(self.profile, source_material)
        templates = [
            "{subject}\nWhy it matters: {strategy}\nNext step: apply one concrete action today.",
            "Question: what changes for the reader here?\n{subject}\nTakeaway: {strategy}.",
            "{subject}\n3 quick points:\n- main shift\n- practical impact\n- what to do next",
            "Most teams miss this:\n{subject}\nUse this angle: {strategy}.",
            "{subject}\nShort version:\n- what happened\n- why it matters\n- what to do",
        ]
        template = templates[index % len(templates)]
        rendered = template.format(
            subject=source_material or base,
            strategy=self.profile.get("content_strategy", "make it practical"),
        )
        return rendered.strip()

    def _fallback_rewrite(self, text: str, suggestions: list[str]) -> str:
        addition = suggestions[0] if suggestions else "Tighten the opening and add a practical takeaway."
        if addition.lower() in text.lower():
            return text
        return f"{text.strip()}\n\nRevision: {addition}"
