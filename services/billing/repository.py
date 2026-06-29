from __future__ import annotations

from datetime import date
from typing import Any

import database


class BillingRepository:
    def _ensure_pool(self) -> None:
        if database.db_pool is None:
            raise RuntimeError("database pool is not initialized")

    async def fetch_plans(self) -> list[dict[str, Any]]:
        self._ensure_pool()
        sql = """
            SELECT *
            FROM billing_plans
            WHERE is_active = TRUE
            ORDER BY price_rub ASC, id ASC
        """
        async with database.db_pool.acquire() as conn:
            rows = await conn.fetch(sql)
            return [dict(row) for row in rows]

    async def fetch_plan_by_code(self, code: str) -> dict[str, Any] | None:
        self._ensure_pool()
        sql = "SELECT * FROM billing_plans WHERE code = $1 AND is_active = TRUE"
        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow(sql, code)
            return dict(row) if row else None

    async def upsert_customer(self, user_id: int, **fields: Any) -> dict[str, Any]:
        self._ensure_pool()
        sql = """
            INSERT INTO billing_customers (user_id, provider, provider_customer_id, email, phone, metadata)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (user_id) DO UPDATE SET
                provider = COALESCE(EXCLUDED.provider, billing_customers.provider),
                provider_customer_id = COALESCE(EXCLUDED.provider_customer_id, billing_customers.provider_customer_id),
                email = COALESCE(EXCLUDED.email, billing_customers.email),
                phone = COALESCE(EXCLUDED.phone, billing_customers.phone),
                updated_at = NOW()
            RETURNING *
        """
        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                sql,
                user_id,
                fields.get("provider", "internal"),
                fields.get("provider_customer_id"),
                fields.get("email"),
                fields.get("phone"),
                fields.get("metadata", {}),
            )
            return dict(row)

    async def fetch_customer(self, user_id: int) -> dict[str, Any] | None:
        self._ensure_pool()
        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM billing_customers WHERE user_id = $1", user_id)
            return dict(row) if row else None

    async def create_payment(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_pool()
        sql = """
            INSERT INTO billing_payments (
                user_id, plan_id, provider, provider_payment_id, amount_rub, currency,
                status, confirmation_url, idempotency_key, raw_provider_payload
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            ON CONFLICT (provider, idempotency_key) DO UPDATE SET
                updated_at = NOW()
            RETURNING *
        """
        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                sql,
                payload["user_id"],
                payload["plan_id"],
                payload["provider"],
                payload.get("provider_payment_id"),
                payload["amount_rub"],
                payload.get("currency", "RUB"),
                payload.get("status", "pending"),
                payload.get("confirmation_url"),
                payload["idempotency_key"],
                payload.get("raw_provider_payload", {}),
            )
            return dict(row)

    async def fetch_payment(self, payment_id: int) -> dict[str, Any] | None:
        self._ensure_pool()
        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM billing_payments WHERE id = $1", payment_id)
            return dict(row) if row else None

    async def fetch_payment_by_provider_id(self, provider: str, provider_payment_id: str) -> dict[str, Any] | None:
        self._ensure_pool()
        sql = "SELECT * FROM billing_payments WHERE provider = $1 AND provider_payment_id = $2"
        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow(sql, provider, provider_payment_id)
            return dict(row) if row else None

    async def update_payment_status(self, payment_id: int, status: str, raw_payload: dict[str, Any], failed_reason: str | None = None) -> dict[str, Any]:
        self._ensure_pool()
        sql = """
            UPDATE billing_payments
            SET status = $2,
                raw_provider_payload = $3,
                failed_reason = $4,
                paid_at = CASE WHEN $2 = 'succeeded' THEN COALESCE(paid_at, NOW()) ELSE paid_at END,
                updated_at = NOW()
            WHERE id = $1
            RETURNING *
        """
        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow(sql, payment_id, status, raw_payload, failed_reason)
            return dict(row)

    async def fetch_active_subscription(self, user_id: int) -> dict[str, Any] | None:
        self._ensure_pool()
        sql = """
            SELECT s.*, p.code AS plan_code, p.name AS plan_name, p.post_limit, p.source_limit,
                   p.channel_limit, p.llm_limit, p.rewrite_limit, p.source_check_limit,
                   p.candidate_limit, p.metadata AS plan_metadata
            FROM billing_subscriptions s
            JOIN billing_plans p ON p.id = s.plan_id
            WHERE s.user_id = $1
              AND s.status IN ('active', 'trialing')
              AND s.current_period_end > NOW()
            ORDER BY s.current_period_end DESC
            LIMIT 1
        """
        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow(sql, user_id)
            return dict(row) if row else None

    async def activate_subscription(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_pool()
        sql = """
            INSERT INTO billing_subscriptions (
                user_id, plan_id, provider, provider_subscription_id, status,
                starts_at, current_period_start, current_period_end, metadata
            ) VALUES ($1,$2,$3,$4,'active',NOW(),NOW(),NOW() + ($5::text || ' days')::interval,$6)
            RETURNING *
        """
        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                sql,
                payload["user_id"],
                payload["plan_id"],
                payload.get("provider", "manual"),
                payload.get("provider_subscription_id"),
                payload["days"],
                payload.get("metadata", {}),
            )
            return dict(row)

    async def cancel_subscription(self, subscription_id: int) -> dict[str, Any] | None:
        self._ensure_pool()
        sql = """
            UPDATE billing_subscriptions
            SET status = 'canceled', canceled_at = NOW(), updated_at = NOW()
            WHERE id = $1
            RETURNING *
        """
        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow(sql, subscription_id)
            return dict(row) if row else None

    async def fetch_subscription(self, subscription_id: int) -> dict[str, Any] | None:
        self._ensure_pool()
        sql = """
            SELECT s.*, p.code AS plan_code, p.name AS plan_name
            FROM billing_subscriptions s
            JOIN billing_plans p ON p.id = s.plan_id
            WHERE s.id = $1
        """
        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow(sql, subscription_id)
            return dict(row) if row else None

    async def insert_subscription_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_pool()
        sql = """
            INSERT INTO billing_subscription_events (
                user_id, subscription_id, event_type, old_status, new_status, reason
            ) VALUES ($1,$2,$3,$4,$5,$6)
            RETURNING *
        """
        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                sql,
                payload["user_id"],
                payload.get("subscription_id"),
                payload["event_type"],
                payload.get("old_status"),
                payload.get("new_status"),
                payload.get("reason", ""),
            )
            return dict(row)

    async def insert_webhook_event(self, payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        self._ensure_pool()
        sql = """
            INSERT INTO billing_webhook_events (
                provider, event_id, event_type, payload_json, processing_status
            ) VALUES ($1,$2,$3,$4,'received')
            ON CONFLICT (provider, event_id) DO NOTHING
            RETURNING *
        """
        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                sql,
                payload["provider"],
                payload["event_id"],
                payload["event_type"],
                payload.get("payload_json", {}),
            )
            if row:
                return dict(row), True
            existing = await conn.fetchrow(
                "SELECT * FROM billing_webhook_events WHERE provider = $1 AND event_id = $2",
                payload["provider"],
                payload["event_id"],
            )
            return dict(existing), False

    async def mark_webhook_event(self, event_id: int, status: str, error_text: str | None = None) -> None:
        self._ensure_pool()
        sql = """
            UPDATE billing_webhook_events
            SET processing_status = $2,
                processed_at = CASE WHEN $2 IN ('processed', 'failed', 'duplicate') THEN NOW() ELSE processed_at END,
                error_text = $3
            WHERE id = $1
        """
        async with database.db_pool.acquire() as conn:
            await conn.execute(sql, event_id, status, error_text)

    async def fetch_promocode(self, code: str) -> dict[str, Any] | None:
        self._ensure_pool()
        sql = """
            SELECT *
            FROM billing_promocodes
            WHERE lower(code) = lower($1)
              AND is_active = TRUE
              AND (valid_until IS NULL OR valid_until > NOW())
              AND (max_uses = 0 OR used_count < max_uses)
        """
        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow(sql, code)
            return dict(row) if row else None

    async def mark_promocode_used(self, promocode_id: int, user_id: int) -> bool:
        self._ensure_pool()
        sql = """
            INSERT INTO billing_promocode_uses (promocode_id, user_id)
            VALUES ($1, $2)
            ON CONFLICT (promocode_id, user_id) DO NOTHING
            RETURNING id
        """
        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow(sql, promocode_id, user_id)
            if not row:
                return False
            await conn.execute(
                "UPDATE billing_promocodes SET used_count = used_count + 1 WHERE id = $1",
                promocode_id,
            )
            return True

    async def insert_manual_override(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_pool()
        sql = """
            INSERT INTO billing_manual_overrides (user_id, admin_id, action, reason, expires_at)
            VALUES ($1,$2,$3,$4,$5)
            RETURNING *
        """
        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                sql,
                payload["user_id"],
                payload["admin_id"],
                payload["action"],
                payload.get("reason", ""),
                payload.get("expires_at"),
            )
            return dict(row)

    async def set_customer_ban(self, user_id: int, banned: bool, reason: str = "") -> dict[str, Any]:
        self._ensure_pool()
        await self.upsert_customer(user_id)
        sql = """
            UPDATE billing_customers
            SET is_banned = $2, ban_reason = $3, updated_at = NOW()
            WHERE user_id = $1
            RETURNING *
        """
        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow(sql, user_id, banned, reason)
            return dict(row)

    async def fetch_usage(self, user_id: int, period: str = "day", counter_date: date | None = None) -> dict[str, Any]:
        self._ensure_pool()
        counter_date = counter_date or date.today()
        sql = """
            INSERT INTO billing_usage_counters (user_id, period, counter_date)
            VALUES ($1,$2,$3)
            ON CONFLICT (user_id, period, counter_date) DO UPDATE SET updated_at = NOW()
            RETURNING *
        """
        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow(sql, user_id, period, counter_date)
            return dict(row)

    async def increment_usage(self, user_id: int, action: str, amount: int = 1) -> dict[str, Any]:
        self._ensure_pool()
        allowed_columns = {
            "publish": "posts_published",
            "source_check": "source_checks",
            "fetch": "fetch_runs",
            "score": "scoring_runs",
            "generate": "generation_runs",
            "rewrite": "rewrites",
            "llm_tokens": "llm_tokens",
        }
        column = allowed_columns.get(action)
        if column is None:
            raise ValueError(f"Unsupported usage action: {action}")
        sql = f"""
            INSERT INTO billing_usage_counters (user_id, period, counter_date, {column})
            VALUES ($1,'day',CURRENT_DATE,$2)
            ON CONFLICT (user_id, period, counter_date) DO UPDATE SET
                {column} = billing_usage_counters.{column} + EXCLUDED.{column},
                updated_at = NOW()
            RETURNING *
        """
        async with database.db_pool.acquire() as conn:
            row = await conn.fetchrow(sql, user_id, amount)
            return dict(row)

    async def reset_usage(self, user_id: int) -> None:
        self._ensure_pool()
        async with database.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE billing_usage_counters
                SET posts_published = 0,
                    source_checks = 0,
                    fetch_runs = 0,
                    scoring_runs = 0,
                    generation_runs = 0,
                    rewrites = 0,
                    llm_tokens = 0,
                    updated_at = NOW()
                WHERE user_id = $1
                """,
                user_id,
            )

    async def insert_event_log(self, event_type: str, status: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        self._ensure_pool()
        sql = """
            INSERT INTO event_log (event_type, workflow_run_id, status, payload)
            VALUES ($1,$2,$3,$4)
            RETURNING id
        """
        try:
            async with database.db_pool.acquire() as conn:
                row = await conn.fetchrow(sql, event_type, payload.get("workflow_run_id", ""), status, payload)
                return dict(row) if row else None
        except Exception:
            return None
