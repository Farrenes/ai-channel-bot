from __future__ import annotations

import asyncio

from services.billing.service import BillingService


class FakeWebhookProvider:
    def __init__(self, event: dict[str, object]) -> None:
        self.event = event
        self.webhook_calls: list[tuple[bytes, dict[str, str]]] = []

    async def handle_webhook(self, raw_body: bytes, headers: dict[str, str]) -> dict[str, object]:
        self.webhook_calls.append((raw_body, headers))
        return dict(self.event)


class FakeWebhookRepo:
    def __init__(self) -> None:
        self.plan = {
            "id": 1,
            "code": "pro",
            "price_rub": 990,
            "period_days": 30,
            "post_limit": 5,
            "source_check_limit": 5,
            "candidate_limit": 5,
            "rewrite_limit": 5,
        }
        self.payments_by_provider_id = {
            ("yookassa", "pay-001"): {
                "id": 11,
                "user_id": 42,
                "plan_id": 1,
                "amount_rub": 990,
                "provider": "yookassa",
                "provider_payment_id": "pay-001",
                "status": "pending",
            }
        }
        self.webhook_events: dict[tuple[str, str], dict[str, object]] = {}
        self.marked_webhooks: list[tuple[int, str, str | None]] = []
        self.updated_payments: list[tuple[int, str, dict[str, object], str | None]] = []
        self.activated_subscriptions: list[dict[str, object]] = []
        self.subscription_events: list[dict[str, object]] = []
        self.event_logs: list[tuple[str, str, dict[str, object]]] = []

    async def insert_webhook_event(self, payload: dict[str, object]) -> tuple[dict[str, object], bool]:
        key = (str(payload["provider"]), str(payload["event_id"]))
        if key in self.webhook_events:
            return self.webhook_events[key], False
        row = {"id": len(self.webhook_events) + 1, **payload}
        self.webhook_events[key] = row
        return row, True

    async def mark_webhook_event(self, event_id: int, status: str, error_text: str | None = None) -> None:
        self.marked_webhooks.append((event_id, status, error_text))

    async def fetch_payment_by_provider_id(self, provider: str, provider_payment_id: str) -> dict[str, object] | None:
        return self.payments_by_provider_id.get((provider, provider_payment_id))

    async def update_payment_status(
        self,
        payment_id: int,
        status: str,
        raw_provider_payload: dict[str, object],
        reason: str | None = None,
    ) -> dict[str, object]:
        for payment in self.payments_by_provider_id.values():
            if payment["id"] == payment_id:
                payment["status"] = status
                payment["raw_provider_payload"] = raw_provider_payload
                if reason is not None:
                    payment["reason"] = reason
                self.updated_payments.append((payment_id, status, raw_provider_payload, reason))
                return dict(payment)
        raise AssertionError(f"Unknown payment id: {payment_id}")

    async def fetch_plans(self) -> list[dict[str, object]]:
        return [self.plan]

    async def activate_subscription(self, payload: dict[str, object]) -> dict[str, object]:
        subscription = {
            "id": len(self.activated_subscriptions) + 100,
            "status": "active",
            "plan_code": self.plan["code"],
            **payload,
        }
        self.activated_subscriptions.append(subscription)
        return subscription

    async def insert_subscription_event(self, payload: dict[str, object]) -> None:
        self.subscription_events.append(payload)

    async def insert_event_log(self, event_type: str, status: str, payload: dict[str, object]) -> None:
        self.event_logs.append((event_type, status, payload))


def test_repeated_webhook_does_not_activate_subscription_twice():
    event = {
        "provider": "yookassa",
        "event_id": "evt-001",
        "event_type": "payment.succeeded",
        "provider_payment_id": "pay-001",
        "amount_rub": 990,
        "status": "succeeded",
        "raw_payload": {"object": {"id": "pay-001"}},
    }
    repo = FakeWebhookRepo()
    provider = FakeWebhookProvider(event)
    service = BillingService(repo=repo, providers={"yookassa": provider}, billing_enabled=True)

    first = asyncio.run(service.process_yookassa_webhook(b"{}", {"X-Test": "1"}))
    second = asyncio.run(service.process_yookassa_webhook(b"{}", {"X-Test": "1"}))

    assert first["processed"] is True
    assert first["duplicate"] is False
    assert second["processed"] is False
    assert second["duplicate"] is True
    assert len(repo.activated_subscriptions) == 1
    assert repo.marked_webhooks[-1][1] == "duplicate"


def test_payment_succeeded_activates_subscription():
    event = {
        "provider": "yookassa",
        "event_id": "evt-002",
        "event_type": "payment.succeeded",
        "provider_payment_id": "pay-001",
        "amount_rub": 990,
        "status": "succeeded",
        "raw_payload": {"status": "succeeded"},
    }
    repo = FakeWebhookRepo()
    service = BillingService(repo=repo, providers={"yookassa": FakeWebhookProvider(event)}, billing_enabled=True)

    result = asyncio.run(service.process_yookassa_webhook(b"{}", {}))

    assert result["result"]["applied"] is True
    assert repo.updated_payments[0][1] == "succeeded"
    assert len(repo.activated_subscriptions) == 1
    assert repo.subscription_events[0]["event_type"] == "subscription_activated"


def test_payment_canceled_does_not_activate_subscription():
    event = {
        "provider": "yookassa",
        "event_id": "evt-003",
        "event_type": "payment.canceled",
        "provider_payment_id": "pay-001",
        "amount_rub": 990,
        "status": "canceled",
        "raw_payload": {"status": "canceled"},
    }
    repo = FakeWebhookRepo()
    service = BillingService(repo=repo, providers={"yookassa": FakeWebhookProvider(event)}, billing_enabled=True)

    result = asyncio.run(service.process_yookassa_webhook(b"{}", {}))

    assert result["result"]["applied"] is True
    assert repo.updated_payments[0][1] == "canceled"
    assert repo.activated_subscriptions == []
