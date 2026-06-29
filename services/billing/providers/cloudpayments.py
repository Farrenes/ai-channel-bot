from __future__ import annotations

from services.billing.providers.base import BillingProvider


class CloudPaymentsProvider(BillingProvider):
    provider_name = "cloudpayments"

    async def create_payment(self, user, plan, return_url=None):
        raise NotImplementedError("TODO: CloudPayments payment link")

    async def create_subscription(self, user, plan):
        raise NotImplementedError("TODO: recurrent payments, trial, renew, payment_failed, retry failed payment")

    async def cancel_subscription(self, subscription):
        raise NotImplementedError("TODO: cancel recurrent subscription")

    async def handle_webhook(self, raw_body, headers):
        raise NotImplementedError("TODO: Check, Pay, Fail notifications and X-Content-HMAC verification")

    async def get_payment_status(self, provider_payment_id):
        raise NotImplementedError("TODO: transaction status lookup")

    async def sync_subscription(self, provider_subscription_id):
        raise NotImplementedError("TODO: current_period_end and recurrent status sync")
