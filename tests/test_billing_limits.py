from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from services.billing.service import BillingService


class FakeLimitsRepo:
    def __init__(self) -> None:
        self.plan = {
            "id": 1,
            "code": "pro",
            "price_rub": 990,
            "period_days": 30,
            "post_limit": 3,
            "source_check_limit": 2,
            "candidate_limit": 4,
            "rewrite_limit": 1,
        }
        self.customers: dict[int, dict[str, object]] = {}
        self.active_subscription: dict[str, object] | None = None
        self.usage = {
            "posts_published": 0,
            "source_checks": 0,
            "fetch_runs": 0,
            "scoring_runs": 0,
            "generation_runs": 0,
            "rewrites": 0,
        }
        self.manual_overrides: list[dict[str, object]] = []
        self.subscription_events: list[dict[str, object]] = []

    async def fetch_customer(self, user_id: int) -> dict[str, object] | None:
        return self.customers.get(user_id)

    async def fetch_active_subscription(self, user_id: int) -> dict[str, object] | None:
        if self.active_subscription and self.active_subscription.get("user_id") == user_id:
            return self.active_subscription
        return None

    async def fetch_usage(self, user_id: int) -> dict[str, int]:
        return dict(self.usage)

    async def upsert_customer(self, user_id: int) -> dict[str, object]:
        customer = self.customers.setdefault(user_id, {"id": user_id, "user_id": user_id, "is_banned": False})
        return customer

    async def activate_subscription(self, payload: dict[str, object]) -> dict[str, object]:
        subscription = {
            "id": 100,
            "user_id": payload["user_id"],
            "status": "active",
            "plan_code": self.plan["code"],
            "current_period_end": datetime.now(timezone.utc) + timedelta(days=int(payload["days"])),
            "post_limit": self.plan["post_limit"],
            "source_check_limit": self.plan["source_check_limit"],
            "candidate_limit": self.plan["candidate_limit"],
            "rewrite_limit": self.plan["rewrite_limit"],
            **payload,
        }
        self.active_subscription = subscription
        return subscription

    async def insert_manual_override(self, payload: dict[str, object]) -> None:
        self.manual_overrides.append(payload)

    async def insert_subscription_event(self, payload: dict[str, object]) -> None:
        self.subscription_events.append(payload)

    async def fetch_plan_by_code(self, plan_code: str) -> dict[str, object] | None:
        return self.plan if plan_code == self.plan["code"] else None


def test_expired_or_inactive_subscription_blocks_access():
    repo = FakeLimitsRepo()
    service = BillingService(repo=repo, providers={}, billing_enabled=True)

    result = asyncio.run(service.check_user_access(user_id=10))

    assert result["allowed"] is False
    assert result["reason"] == "inactive_subscription"


def test_manual_grant_issues_access():
    repo = FakeLimitsRepo()
    service = BillingService(repo=repo, providers={}, billing_enabled=True)

    asyncio.run(service.manual_grant_access(admin_id=1, user_id=10, plan_id=1, days=14, reason="support"))
    result = asyncio.run(service.check_user_access(user_id=10))

    assert result["allowed"] is True
    assert result["plan_code"] == "pro"
    assert repo.manual_overrides[0]["action"] == "grant_access"


def test_ban_blocks_access():
    repo = FakeLimitsRepo()
    repo.customers[10] = {"id": 10, "user_id": 10, "is_banned": True}
    repo.active_subscription = {
        "id": 100,
        "user_id": 10,
        "status": "active",
        "plan_code": "pro",
        "current_period_end": datetime.now(timezone.utc) + timedelta(days=1),
        "post_limit": 3,
        "source_check_limit": 2,
        "candidate_limit": 4,
        "rewrite_limit": 1,
    }
    service = BillingService(repo=repo, providers={}, billing_enabled=True)

    result = asyncio.run(service.check_user_access(user_id=10))

    assert result["allowed"] is False
    assert result["reason"] == "banned"


def test_limit_exceeded_blocks_action():
    repo = FakeLimitsRepo()
    repo.active_subscription = {
        "id": 100,
        "user_id": 10,
        "status": "active",
        "plan_code": "pro",
        "current_period_end": datetime.now(timezone.utc) + timedelta(days=1),
        "post_limit": 3,
        "source_check_limit": 2,
        "candidate_limit": 4,
        "rewrite_limit": 1,
    }
    repo.usage["posts_published"] = 3
    service = BillingService(repo=repo, providers={}, billing_enabled=True)

    result = asyncio.run(service.check_limit(user_id=10, action="publish"))

    assert result["allowed"] is False
    assert result["reason"] == "plan_limit_exceeded"
