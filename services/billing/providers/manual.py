from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from services.billing.providers.base import BillingProvider


class ManualProvider(BillingProvider):
    provider_name = "manual"

    async def create_payment(self, user, plan, return_url=None):
        payment_id = f"manual_{uuid4().hex}"
        return {
            "provider": self.provider_name,
            "provider_payment_id": payment_id,
            "status": "succeeded",
            "amount_rub": Decimal(str(plan["price_rub"])),
            "currency": "RUB",
            "confirmation_url": None,
            "raw_payload": {"manual": True, "user_id": user["user_id"], "plan_code": plan["code"]},
        }

    async def handle_webhook(self, raw_body, headers):
        raise NotImplementedError("ManualProvider does not receive webhooks")

    async def get_payment_status(self, provider_payment_id):
        return {
            "provider": self.provider_name,
            "provider_payment_id": provider_payment_id,
            "status": "succeeded",
            "raw_payload": {"manual": True},
        }
