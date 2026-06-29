from __future__ import annotations

from services.billing.providers.base import BillingProvider


class TelegramStarsProvider(BillingProvider):
    provider_name = "telegram_stars"

    async def create_payment(self, user, plan, return_url=None):
        raise NotImplementedError("TODO: sendInvoice/createInvoiceLink with XTR currency")

    async def create_subscription(self, user, plan):
        raise NotImplementedError("TODO: 30-day Telegram Stars subscriptions or access packages")

    async def cancel_subscription(self, subscription):
        raise NotImplementedError("TODO: Stars subscription cancellation/refund handling")

    async def handle_webhook(self, raw_body, headers):
        raise NotImplementedError("TODO: successful_payment payload, stars_amount, 7/30 day access packages")

    async def get_payment_status(self, provider_payment_id):
        raise NotImplementedError("TODO: reconcile telegram_payment_charge_id")
