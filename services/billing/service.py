from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from services.billing.repository import BillingRepository
from services.billing.providers.base import BillingProvider
from services.billing.providers.manual import ManualProvider
from services.billing.providers.yookassa import YooKassaProvider


ACCESS_INACTIVE_MESSAGE = "Подписка не активна. Выберите тариф, чтобы продолжить."
LIMIT_POSTS_MESSAGE = "У вас закончился лимит постов на этом тарифе."
LIMIT_SOURCE_MESSAGE = "Этот тариф позволяет добавить только ограниченное число источников."
BAN_MESSAGE = "Доступ временно ограничен. Напишите в поддержку."


class BillingService:
    def __init__(
        self,
        repo: BillingRepository | None = None,
        providers: dict[str, BillingProvider] | None = None,
        billing_enabled: bool | None = None,
    ) -> None:
        self.repo = repo or BillingRepository()
        self.providers = providers or {
            "manual": ManualProvider(),
            "yookassa": YooKassaProvider(),
        }
        self.billing_enabled = (
            billing_enabled
            if billing_enabled is not None
            else os.getenv("BILLING_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
        )
        self.default_provider = os.getenv("BILLING_DEFAULT_PROVIDER", "yookassa")

    async def get_available_plans(self) -> list[dict[str, Any]]:
        return await self.repo.fetch_plans()

    async def create_payment_for_plan(
        self,
        user_id: int,
        plan_code: str,
        return_url: str | None = None,
        provider_name: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        plan = await self._require_plan(plan_code)
        user = await self.repo.upsert_customer(user_id)
        provider_name = provider_name or self.default_provider
        provider = self._provider(provider_name)
        idempotency_key = idempotency_key or f"{user_id}:{plan_code}:{uuid4().hex}"

        provider_payment = await provider.create_payment(user, plan, return_url=return_url)
        payment = await self.repo.create_payment(
            {
                "user_id": user_id,
                "plan_id": plan["id"],
                "provider": provider_name,
                "provider_payment_id": provider_payment.get("provider_payment_id"),
                "amount_rub": provider_payment.get("amount_rub", plan["price_rub"]),
                "currency": provider_payment.get("currency", "RUB"),
                "status": provider_payment.get("status", "pending"),
                "confirmation_url": provider_payment.get("confirmation_url"),
                "idempotency_key": idempotency_key,
                "raw_provider_payload": provider_payment.get("raw_payload", {}),
            }
        )
        await self.repo.insert_event_log(
            "payment_created",
            "ok",
            {"user_id": user_id, "plan_code": plan_code, "provider": provider_name, "payment_id": payment["id"]},
        )
        return {"payment": payment, "plan": plan}

    async def activate_subscription(self, user_id: int, plan_id: int, provider: str, payment_id: int | None = None) -> dict[str, Any]:
        plan = await self._require_plan_by_id(plan_id)
        subscription = await self.repo.activate_subscription(
            {
                "user_id": user_id,
                "plan_id": plan_id,
                "provider": provider,
                "days": plan["period_days"],
                "metadata": {"payment_id": payment_id} if payment_id else {},
            }
        )
        await self.repo.insert_subscription_event(
            {
                "user_id": user_id,
                "subscription_id": subscription["id"],
                "event_type": "subscription_activated",
                "new_status": "active",
                "reason": f"provider={provider}; payment_id={payment_id}",
            }
        )
        await self.repo.insert_event_log(
            "subscription_activated",
            "ok",
            {"user_id": user_id, "subscription_id": subscription["id"], "plan_code": plan["code"]},
        )
        return subscription

    async def extend_subscription(self, user_id: int, plan_id: int, days: int) -> dict[str, Any]:
        return await self.repo.activate_subscription(
            {"user_id": user_id, "plan_id": plan_id, "provider": "manual", "days": days, "metadata": {"extend": True}}
        )

    async def cancel_subscription(self, user_id: int) -> dict[str, Any]:
        subscription = await self.repo.fetch_active_subscription(user_id)
        if not subscription:
            return {"canceled": False, "reason": "active_subscription_not_found"}
        canceled = await self.repo.cancel_subscription(subscription["id"])
        await self.repo.insert_subscription_event(
            {
                "user_id": user_id,
                "subscription_id": subscription["id"],
                "event_type": "subscription_canceled",
                "old_status": subscription["status"],
                "new_status": "canceled",
                "reason": "manual_or_admin_cancel",
            }
        )
        return {"canceled": True, "subscription": canceled}

    async def cancel_subscription_by_id(self, subscription_id: int, reason: str = "admin_cancel") -> dict[str, Any]:
        subscription = await self.repo.fetch_subscription(subscription_id)
        if not subscription:
            return {"canceled": False, "reason": "subscription_not_found"}
        canceled = await self.repo.cancel_subscription(subscription_id)
        await self.repo.insert_subscription_event(
            {
                "user_id": subscription["user_id"],
                "subscription_id": subscription_id,
                "event_type": "subscription_canceled",
                "old_status": subscription["status"],
                "new_status": "canceled",
                "reason": reason,
            }
        )
        return {"canceled": True, "subscription": canceled}

    async def expire_subscription(self, user_id: int) -> dict[str, Any]:
        return await self.cancel_subscription(user_id)

    async def check_user_access(self, user_id: int | None) -> dict[str, Any]:
        if not self.billing_enabled:
            return {"allowed": True, "reason": "billing_disabled", "message": "", "plan_code": "dev"}
        if user_id is None:
            return {"allowed": False, "reason": "missing_user_id", "message": ACCESS_INACTIVE_MESSAGE}
        customer = await self.repo.fetch_customer(user_id)
        if customer and customer.get("is_banned"):
            return {"allowed": False, "reason": "banned", "message": BAN_MESSAGE}
        subscription = await self.repo.fetch_active_subscription(user_id)
        if not subscription:
            return {"allowed": False, "reason": "inactive_subscription", "message": ACCESS_INACTIVE_MESSAGE}
        return {
            "allowed": True,
            "reason": "active_subscription",
            "message": "",
            "plan_code": subscription.get("plan_code"),
            "subscription_id": subscription.get("id"),
            "current_period_end": subscription.get("current_period_end"),
        }

    async def get_user_limits(self, user_id: int) -> dict[str, Any]:
        access = await self.check_user_access(user_id)
        subscription = await self.repo.fetch_active_subscription(user_id) if access.get("allowed") else None
        usage = await self.repo.fetch_usage(user_id)
        return {"access": access, "subscription": subscription, "usage": usage}

    async def check_limit(self, user_id: int | None, action: str, amount: int = 1) -> dict[str, Any]:
        if not self.billing_enabled:
            return {"allowed": True, "action": action, "reason": "billing_disabled", "message": "", "used": 0, "limit": 0}
        access = await self.check_user_access(user_id)
        if not access.get("allowed"):
            return {"allowed": False, "action": action, "reason": access["reason"], "message": access["message"], "used": 0, "limit": 0}
        assert user_id is not None
        subscription = await self.repo.fetch_active_subscription(user_id)
        usage = await self.repo.fetch_usage(user_id)
        limit_map = {
            "publish": ("posts_published", "post_limit", LIMIT_POSTS_MESSAGE),
            "source_check": ("source_checks", "source_check_limit", LIMIT_SOURCE_MESSAGE),
            "fetch": ("fetch_runs", "candidate_limit", "Лимит сбора материалов на сегодня исчерпан."),
            "score": ("scoring_runs", "candidate_limit", "Лимит скоринга на сегодня исчерпан."),
            "generate": ("generation_runs", "candidate_limit", "Лимит генераций на сегодня исчерпан."),
            "rewrite": ("rewrites", "rewrite_limit", "Лимит переписываний на сегодня исчерпан."),
        }
        usage_field, limit_field, message = limit_map.get(action, ("posts_published", "post_limit", "Лимит тарифа исчерпан."))
        limit = int(subscription.get(limit_field) or 0)
        used = int(usage.get(usage_field) or 0)
        allowed = limit == 0 or used + amount <= limit
        return {
            "allowed": allowed,
            "action": action,
            "reason": "ok" if allowed else "plan_limit_exceeded",
            "message": "" if allowed else message,
            "used": used,
            "limit": limit,
            "plan_code": subscription.get("plan_code"),
        }

    async def record_usage(self, user_id: int | None, action: str, amount: int = 1) -> None:
        if not self.billing_enabled or user_id is None:
            return
        await self.repo.increment_usage(user_id, action, amount)

    async def apply_promocode(self, user_id: int, code: str) -> dict[str, Any]:
        promo = await self.repo.fetch_promocode(code)
        if not promo:
            return {"applied": False, "reason": "invalid_or_expired"}
        used = await self.repo.mark_promocode_used(promo["id"], user_id)
        if not used:
            return {"applied": False, "reason": "already_used"}
        return {"applied": True, "promocode": promo}

    async def manual_grant_access(self, admin_id: int, user_id: int, plan_id: int, days: int, reason: str) -> dict[str, Any]:
        await self.repo.upsert_customer(user_id)
        subscription = await self.repo.activate_subscription(
            {"user_id": user_id, "plan_id": plan_id, "provider": "manual", "days": days, "metadata": {"admin_id": admin_id, "reason": reason}}
        )
        await self.repo.insert_manual_override({"user_id": user_id, "admin_id": admin_id, "action": "grant_access", "reason": reason})
        await self.repo.insert_subscription_event(
            {
                "user_id": user_id,
                "subscription_id": subscription["id"],
                "event_type": "manual_grant_access",
                "new_status": "active",
                "reason": reason,
            }
        )
        return subscription

    async def manual_grant_access_by_code(self, admin_id: int, user_id: int, plan_code: str, days: int, reason: str) -> dict[str, Any]:
        plan = await self._require_plan(plan_code)
        return await self.manual_grant_access(admin_id, user_id, plan["id"], days, reason)

    async def manual_ban_user(self, admin_id: int, user_id: int, reason: str) -> dict[str, Any]:
        customer = await self.repo.set_customer_ban(user_id, True, reason)
        await self.repo.insert_manual_override({"user_id": user_id, "admin_id": admin_id, "action": "ban", "reason": reason})
        return customer

    async def reset_user_limits(self, admin_id: int, user_id: int, reason: str) -> dict[str, Any]:
        await self.repo.reset_usage(user_id)
        await self.repo.insert_manual_override({"user_id": user_id, "admin_id": admin_id, "action": "reset_limits", "reason": reason})
        return {"reset": True, "user_id": user_id}

    async def process_yookassa_webhook(self, raw_body: bytes, headers: dict[str, str]) -> dict[str, Any]:
        provider = self._provider("yookassa")
        event = await provider.handle_webhook(raw_body, headers)
        webhook_row, inserted = await self.repo.insert_webhook_event(
            {
                "provider": event["provider"],
                "event_id": event["event_id"],
                "event_type": event["event_type"],
                "payload_json": event.get("raw_payload", {}),
            }
        )
        if not inserted:
            await self.repo.mark_webhook_event(webhook_row["id"], "duplicate")
            return {"processed": False, "duplicate": True, "event": event}

        try:
            result = await self._apply_payment_event(event)
        except Exception as exc:
            await self.repo.mark_webhook_event(webhook_row["id"], "failed", str(exc))
            raise
        await self.repo.mark_webhook_event(webhook_row["id"], "processed")
        return {"processed": True, "duplicate": False, "event": event, "result": result}

    async def _apply_payment_event(self, event: dict[str, Any]) -> dict[str, Any]:
        provider_payment_id = event.get("provider_payment_id")
        if not provider_payment_id:
            return {"applied": False, "reason": "missing_provider_payment_id"}
        payment = await self.repo.fetch_payment_by_provider_id(event["provider"], provider_payment_id)
        if not payment:
            return {"applied": False, "reason": "payment_not_found"}
        if Decimal(str(payment["amount_rub"])) != Decimal(str(event.get("amount_rub", payment["amount_rub"]))):
            await self.repo.update_payment_status(payment["id"], "amount_mismatch", event.get("raw_payload", {}), "amount mismatch")
            return {"applied": False, "reason": "amount_mismatch"}
        if event["event_type"] == "payment.succeeded" or event.get("status") == "succeeded":
            updated_payment = await self.repo.update_payment_status(payment["id"], "succeeded", event.get("raw_payload", {}))
            subscription = await self.activate_subscription(payment["user_id"], payment["plan_id"], event["provider"], payment["id"])
            return {"applied": True, "payment": updated_payment, "subscription": subscription}
        if event["event_type"] == "payment.canceled" or event.get("status") == "canceled":
            updated_payment = await self.repo.update_payment_status(payment["id"], "canceled", event.get("raw_payload", {}), "provider canceled")
            return {"applied": True, "payment": updated_payment}
        return {"applied": False, "reason": "ignored_event_type"}

    async def _require_plan(self, plan_code: str) -> dict[str, Any]:
        plan = await self.repo.fetch_plan_by_code(plan_code)
        if not plan:
            raise ValueError(f"Unknown or inactive billing plan: {plan_code}")
        return plan

    async def _require_plan_by_id(self, plan_id: int) -> dict[str, Any]:
        for plan in await self.repo.fetch_plans():
            if int(plan["id"]) == int(plan_id):
                return plan
        raise ValueError(f"Unknown or inactive billing plan id: {plan_id}")

    def _provider(self, provider_name: str) -> BillingProvider:
        provider = self.providers.get(provider_name)
        if not provider:
            raise ValueError(f"Unsupported billing provider: {provider_name}")
        return provider
