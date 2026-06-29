from __future__ import annotations

from typing import Any

from services.billing.service import BillingService


def extract_user_id(payload: dict[str, Any]) -> int | None:
    for key in ("user_id", "telegram_user_id", "owner_user_id"):
        value = payload.get(key)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
    topic_profile = payload.get("topic_profile")
    if isinstance(topic_profile, dict):
        return extract_user_id(topic_profile)
    return None


async def guard_or_error(service: BillingService, payload: dict[str, Any], action: str) -> dict[str, Any] | None:
    user_id = extract_user_id(payload)
    result = await service.check_limit(user_id, action)
    if result.get("allowed"):
        return None
    return {
        "status": "blocked",
        "module": "billing_guard",
        "data": result,
        "errors": [result.get("message", "Действие недоступно по тарифу.")],
    }
