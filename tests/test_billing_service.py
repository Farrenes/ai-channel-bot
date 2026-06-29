from __future__ import annotations

import asyncio

from services.billing.service import BillingService


class FakeBillingProvider:
    def __init__(self, provider_name: str = "fakepay") -> None:
        self.provider_name = provider_name
        self.create_payment_calls: list[dict[str, object]] = []

    async def create_payment(self, user: dict[str, object], plan: dict[str, object], return_url: str | None = None) -> dict[str, object]:
        self.create_payment_calls.append({"user": user, "plan": plan, "return_url": return_url})
        return {
            "provider": self.provider_name,
            "provider_payment_id": "fake-payment-001",
            "amount_rub": plan["price_rub"],
            "currency": "RUB",
            "status": "pending",
            "confirmation_url": "https://pay.example/confirm",
            "raw_payload": {"provider": self.provider_name},
        }


class FakeBillingRepo:
    def __init__(self) -> None:
        self.plan = {"id": 1, "code": "pro", "price_rub": 990, "period_days": 30, "post_limit": 5}
        self.customers: dict[int, dict[str, object]] = {}
        self.payments: list[dict[str, object]] = []
        self.subscription_events: list[dict[str, object]] = []
        self.event_logs: list[tuple[str, str, dict[str, object]]] = []
        self.promocodes = {"PROMO10": {"id": 10, "code": "PROMO10", "discount_percent": 10}}
        self.used_promocodes: set[tuple[int, int]] = set()

    async def fetch_plan_by_code(self, plan_code: str) -> dict[str, object] | None:
        return self.plan if plan_code == self.plan["code"] else None

    async def fetch_plans(self) -> list[dict[str, object]]:
        return [self.plan]

    async def upsert_customer(self, user_id: int) -> dict[str, object]:
        customer = self.customers.setdefault(user_id, {"id": user_id, "user_id": user_id, "is_banned": False})
        return customer

    async def create_payment(self, payload: dict[str, object]) -> dict[str, object]:
        payment = {"id": len(self.payments) + 1, **payload}
        self.payments.append(payment)
        return payment

    async def insert_event_log(self, event_type: str, status: str, payload: dict[str, object]) -> None:
        self.event_logs.append((event_type, status, payload))

    async def fetch_promocode(self, code: str) -> dict[str, object] | None:
        return self.promocodes.get(code)

    async def mark_promocode_used(self, promocode_id: int, user_id: int) -> bool:
        key = (promocode_id, user_id)
        if key in self.used_promocodes:
            return False
        self.used_promocodes.add(key)
        return True


def test_create_payment_uses_provider_abstraction_and_persists_payment():
    repo = FakeBillingRepo()
    provider = FakeBillingProvider()
    service = BillingService(repo=repo, providers={"fakepay": provider}, billing_enabled=True)

    result = asyncio.run(
        service.create_payment_for_plan(
            user_id=42,
            plan_code="pro",
            provider_name="fakepay",
            return_url="https://app.example/return",
            idempotency_key="idem-001",
        )
    )

    assert len(provider.create_payment_calls) == 1
    assert provider.create_payment_calls[0]["return_url"] == "https://app.example/return"
    assert len(repo.payments) == 1
    assert repo.payments[0]["provider"] == "fakepay"
    assert repo.payments[0]["provider_payment_id"] == "fake-payment-001"
    assert result["payment"]["id"] == 1
    assert result["plan"]["code"] == "pro"
    assert repo.event_logs[0][0] == "payment_created"


def test_billing_service_supports_fake_provider_without_direct_yookassa_usage():
    repo = FakeBillingRepo()
    provider = FakeBillingProvider(provider_name="custom-provider")
    service = BillingService(repo=repo, providers={"custom": provider}, billing_enabled=True)

    result = asyncio.run(
        service.create_payment_for_plan(
            user_id=7,
            plan_code="pro",
            provider_name="custom",
            idempotency_key="idem-002",
        )
    )

    assert provider.create_payment_calls
    assert result["payment"]["provider"] == "custom"
    assert repo.payments[0]["raw_provider_payload"] == {"provider": "custom-provider"}


def test_promocode_applies_only_once_per_user():
    repo = FakeBillingRepo()
    service = BillingService(repo=repo, providers={"manual": FakeBillingProvider("manual")}, billing_enabled=True)

    first = asyncio.run(service.apply_promocode(user_id=5, code="PROMO10"))
    second = asyncio.run(service.apply_promocode(user_id=5, code="PROMO10"))

    assert first["applied"] is True
    assert first["promocode"]["code"] == "PROMO10"
    assert second == {"applied": False, "reason": "already_used"}
