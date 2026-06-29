from __future__ import annotations

from services.billing.providers.base import BillingProvider


class RobokassaProvider(BillingProvider):
    provider_name = "robokassa"

    async def create_payment(self, user, plan, return_url=None):
        raise NotImplementedError("TODO: Robokassa payment link")

    async def create_subscription(self, user, plan):
        raise NotImplementedError("TODO: Robokassa recurring payments if enabled")

    async def cancel_subscription(self, subscription):
        raise NotImplementedError("TODO: recurring cancellation if enabled")

    async def handle_webhook(self, raw_body, headers):
        raise NotImplementedError("TODO: Result URL, Success URL, Fail URL and signature verification")

    async def get_payment_status(self, provider_payment_id):
        raise NotImplementedError("TODO: payment status lookup")

    def verify_signature(self, payload):
        raise NotImplementedError("TODO: SignatureValue verification and receipt/fiscalization details")
