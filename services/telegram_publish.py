from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

import database
from pydantic import BaseModel, Field


class TelegramPublishRequest(BaseModel):
    user_id: int | None = None
    generated_post_id: int
    idempotency_key: str
    title: str
    post_text: str
    target_channel: str
    topic_profile_id: int | None = None
    topic_config_id: int | None = None
    source_id: int | None = None
    candidate_id: int | None = None
    mock_publish: bool = True


class TelegramPublishResult(BaseModel):
    published: bool
    deduplicated: bool
    status: str
    generated_post_id: int
    published_post_id: int | None
    telegram_message_id: str
    idempotency_key: str
    target_channel: str
    event_log_id: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class TelegramPublishEnvelope(BaseModel):
    status: str
    module: str
    run_id: str
    duration_ms: int
    data: TelegramPublishResult | dict[str, Any]
    errors: list[str] = Field(default_factory=list)


class TelegramPublishRepository:
    async def fetch_existing_publish(self, *, generated_post_id: int, idempotency_key: str) -> dict[str, Any] | None:
        if database.db_pool is None:
            raise RuntimeError("database pool is not initialized")

        sql = """
            SELECT id, generated_post_id, publish_idempotency_key, telegram_message_id, title, post_text
            FROM published_posts
            WHERE generated_post_id = $1 OR publish_idempotency_key = $2
            ORDER BY published_at DESC
            LIMIT 1
        """
        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow(sql, generated_post_id, idempotency_key)
            return dict(row) if row else None

    async def insert_published_post(self, payload: dict[str, Any]) -> dict[str, Any]:
        if database.db_pool is None:
            raise RuntimeError("database pool is not initialized")

        sql = """
            INSERT INTO published_posts (
                title,
                post_text,
                source_info,
                category,
                topic_profile_id,
                topic_config_id,
                source_id,
                candidate_id,
                generated_post_id,
                publish_idempotency_key,
                telegram_message_id,
                content_hash
            ) VALUES (
                $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12
            )
            RETURNING id
        """
        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                sql,
                payload["title"],
                payload["post_text"],
                payload.get("source_info", ""),
                payload.get("category", ""),
                payload.get("topic_profile_id"),
                payload.get("topic_config_id"),
                payload.get("source_id"),
                payload.get("candidate_id"),
                payload["generated_post_id"],
                payload["idempotency_key"],
                payload["telegram_message_id"],
                payload["content_hash"],
            )
            return dict(row) if row else {}

    async def update_generated_post(self, payload: dict[str, Any]) -> None:
        if database.db_pool is None:
            raise RuntimeError("database pool is not initialized")

        sql = """
            UPDATE generated_posts
            SET status = 'published',
                published_post_id = $2,
                publish_idempotency_key = $3,
                telegram_message_id = $4,
                updated_at = NOW()
            WHERE id = $1
        """
        async with database.db_pool.acquire() as conn:
            await conn.execute(
                sql,
                payload["generated_post_id"],
                payload["published_post_id"],
                payload["idempotency_key"],
                payload["telegram_message_id"],
            )

    async def insert_event_log(self, payload: dict[str, Any]) -> dict[str, Any]:
        if database.db_pool is None:
            raise RuntimeError("database pool is not initialized")

        sql = """
            INSERT INTO event_log (
                event_type,
                workflow_run_id,
                topic_profile_id,
                topic_config_id,
                source_id,
                candidate_id,
                generated_post_id,
                published_post_id,
                status,
                payload
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            RETURNING id
        """
        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                sql,
                payload["event_type"],
                payload.get("workflow_run_id", ""),
                payload.get("topic_profile_id"),
                payload.get("topic_config_id"),
                payload.get("source_id"),
                payload.get("candidate_id"),
                payload.get("generated_post_id"),
                payload.get("published_post_id"),
                payload.get("status", "ok"),
                payload.get("payload", {}),
            )
            return dict(row) if row else {}


class TelegramPublishService:
    def __init__(
        self,
        repo: TelegramPublishRepository | None = None,
        telegram_client: Callable[[str, str], Any] | None = None,
    ):
        self.repo = repo or TelegramPublishRepository()
        self.telegram_client = telegram_client

    async def publish(self, request: TelegramPublishRequest | dict[str, Any]) -> TelegramPublishResult:
        payload = request.model_dump() if isinstance(request, TelegramPublishRequest) else dict(request)
        payload["idempotency_key"] = payload.get("idempotency_key") or self._default_idempotency_key(payload)
        existing = await self.repo.fetch_existing_publish(
            generated_post_id=payload["generated_post_id"],
            idempotency_key=payload["idempotency_key"],
        )
        if existing:
            event_row = await self.repo.insert_event_log(
                self._event_payload(
                    "post_publish_skipped_duplicate",
                    payload,
                    published_post_id=existing.get("id"),
                    status="duplicate",
                    details={"reason": "existing_publish"},
                )
            )
            return TelegramPublishResult(
                published=True,
                deduplicated=True,
                status="duplicate",
                generated_post_id=payload["generated_post_id"],
                published_post_id=existing.get("id"),
                telegram_message_id=existing.get("telegram_message_id") or "",
                idempotency_key=payload["idempotency_key"],
                target_channel=payload["target_channel"],
                event_log_id=event_row.get("id"),
                details={"existing_publish_id": existing.get("id")},
            )

        telegram_message_id = await self._send_to_telegram(payload)
        published_row = await self.repo.insert_published_post(
            {
                **payload,
                "telegram_message_id": telegram_message_id,
                "content_hash": self._content_hash(payload["title"], payload["post_text"], payload["target_channel"]),
            }
        )
        published_post_id = published_row.get("id")
        await self.repo.update_generated_post(
            {
                "generated_post_id": payload["generated_post_id"],
                "published_post_id": published_post_id,
                "idempotency_key": payload["idempotency_key"],
                "telegram_message_id": telegram_message_id,
            }
        )
        event_row = await self.repo.insert_event_log(
            self._event_payload(
                "post_published",
                payload,
                published_post_id=published_post_id,
                status="ok",
                details={"telegram_message_id": telegram_message_id},
            )
        )
        return TelegramPublishResult(
            published=True,
            deduplicated=False,
            status="published",
            generated_post_id=payload["generated_post_id"],
            published_post_id=published_post_id,
            telegram_message_id=telegram_message_id,
            idempotency_key=payload["idempotency_key"],
            target_channel=payload["target_channel"],
            event_log_id=event_row.get("id"),
            details={"mock_publish": bool(payload.get("mock_publish", True))},
        )

    async def _send_to_telegram(self, payload: dict[str, Any]) -> str:
        if self.telegram_client is not None and not payload.get("mock_publish", True):
            result = self.telegram_client(payload["target_channel"], payload["post_text"])
            if hasattr(result, "__await__"):
                result = await result  # type: ignore[assignment]
            if isinstance(result, dict):
                telegram_message_id = result.get("message_id") or result.get("telegram_message_id") or ""
                if telegram_message_id:
                    return str(telegram_message_id)
            if isinstance(result, str) and result.strip():
                return result.strip()
        return f"mock_{payload['generated_post_id']}_{payload['idempotency_key'][:12]}"

    def _default_idempotency_key(self, payload: dict[str, Any]) -> str:
        digest = hashlib.sha256()
        digest.update(str(payload.get("generated_post_id", "")).encode("utf-8"))
        digest.update(b"|")
        digest.update(str(payload.get("target_channel", "")).encode("utf-8"))
        digest.update(b"|")
        digest.update(str(payload.get("title", "")).encode("utf-8"))
        digest.update(b"|")
        digest.update(str(payload.get("post_text", "")).encode("utf-8"))
        return digest.hexdigest()

    def _content_hash(self, title: str, post_text: str, target_channel: str) -> str:
        digest = hashlib.sha256()
        digest.update(title.encode("utf-8"))
        digest.update(b"|")
        digest.update(post_text.encode("utf-8"))
        digest.update(b"|")
        digest.update(target_channel.encode("utf-8"))
        return digest.hexdigest()

    def _event_payload(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        published_post_id: int | None,
        status: str,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "event_type": event_type,
            "workflow_run_id": payload.get("workflow_run_id", ""),
            "topic_profile_id": payload.get("topic_profile_id"),
            "topic_config_id": payload.get("topic_config_id"),
            "source_id": payload.get("source_id"),
            "candidate_id": payload.get("candidate_id"),
            "generated_post_id": payload.get("generated_post_id"),
            "published_post_id": published_post_id,
            "status": status,
            "payload": {
                "target_channel": payload.get("target_channel"),
                "idempotency_key": payload.get("idempotency_key"),
                "details": details,
            },
        }
