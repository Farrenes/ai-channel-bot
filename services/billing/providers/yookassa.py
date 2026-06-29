from __future__ import annotations

import json
import os
from decimal import Decimal
from typing import Any
from uuid import uuid4

from services.billing.providers.base import BillingProvider


class YooKassaProvider(BillingProvider):
    provider_name = "yookassa"

    def __init__(
        self,
        shop_id: str | None = None,
        secret_key: str | None = None,
        return_url: str | None = None,
    ) -> None:
        self.shop_id = shop_id or os.getenv("YOOKASSA_SHOP_ID", "")
        self.secret_key = secret_key or os.getenv("YOOKASSA_SECRET_KEY", "")
        self.return_url = return_url or os.getenv("YOOKASSA_RETURN_URL", "")

    async def create_payment(self, user: dict[str, Any], plan: dict[str, Any], return_url: str | None = None) -> dict[str, Any]:
        try:
            from yookassa import Configuration, Payment  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on optional SDK
            raise RuntimeError("YooKassa SDK is not installed. Install yookassa to create real payments.") from exc

        if not self.shop_id or not self.secret_key:
            raise RuntimeError("YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY are required")

        Configuration.account_id = self.shop_id
        Configuration.secret_key = self.secret_key

        payment = Payment.create(
            {
                "amount": {
                    "value": f"{Decimal(str(plan['price_rub'])):.2f}",
                    "currency": "RUB",
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": return_url or self.return_url,
                },
                "capture": True,
                "description": f"BotTG тариф {plan['name']}",
                "metadata": {
                    "user_id": str(user["user_id"]),
                    "plan_code": plan["code"],
                },
                "receipt": self._receipt_stub(user, plan),
            },
            uuid4().hex,
        )
        raw = payment.json() if hasattr(payment, "json") else payment
        payload = json.loads(raw) if isinstance(raw, str) else dict(raw)
        confirmation = payload.get("confirmation") or {}
        return {
            "provider": self.provider_name,
            "provider_payment_id": payload["id"],
            "status": payload.get("status", "pending"),
            "amount_rub": Decimal(str(plan["price_rub"])),
            "currency": "RUB",
            "confirmation_url": confirmation.get("confirmation_url"),
            "raw_payload": payload,
        }

    async def handle_webhook(self, raw_body: bytes, headers: dict[str, str]) -> dict[str, Any]:
        payload = json.loads(raw_body.decode("utf-8"))
        event_type = str(payload.get("event") or payload.get("type") or "unknown")
        obj = payload.get("object") or {}
        provider_payment_id = obj.get("id")
        event_id = str(payload.get("id") or f"{event_type}:{provider_payment_id}")
        return {
            "provider": self.provider_name,
            "event_id": event_id,
            "event_type": event_type,
            "provider_payment_id": provider_payment_id,
            "status": obj.get("status", "unknown"),
            "amount_rub": Decimal(str((obj.get("amount") or {}).get("value") or "0")),
            "currency": (obj.get("amount") or {}).get("currency", "RUB"),
            "raw_payload": payload,
        }

    async def get_payment_status(self, provider_payment_id: str) -> dict[str, Any]:
        try:
            from yookassa import Configuration, Payment  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on optional SDK
            raise RuntimeError("YooKassa SDK is not installed. Install yookassa to check real payments.") from exc

        if not self.shop_id or not self.secret_key:
            raise RuntimeError("YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY are required")

        Configuration.account_id = self.shop_id
        Configuration.secret_key = self.secret_key
        payment = Payment.find_one(provider_payment_id)
        raw = payment.json() if hasattr(payment, "json") else payment
        payload = json.loads(raw) if isinstance(raw, str) else dict(raw)
        return {
            "provider": self.provider_name,
            "provider_payment_id": payload["id"],
            "status": payload.get("status", "unknown"),
            "raw_payload": payload,
        }

    def _receipt_stub(self, user: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
        customer: dict[str, Any] = {}
        if user.get("email"):
            customer["email"] = user["email"]
        if user.get("phone"):
            customer["phone"] = user["phone"]
        return {
            "customer": customer or {"email": "billing@example.local"},
            "items": [
                {
                    "description": f"BotTG тариф {plan['name']}",
                    "quantity": "1.00",
                    "amount": {"value": f"{Decimal(str(plan['price_rub'])):.2f}", "currency": "RUB"},
                    "vat_code": 1,
                    "payment_mode": "full_payment",
                    "payment_subject": "service",
                }
            ],
        }
