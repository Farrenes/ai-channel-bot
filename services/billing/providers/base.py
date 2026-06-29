from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BillingProvider(ABC):
    provider_name: str

    @abstractmethod
    async def create_payment(self, user: dict[str, Any], plan: dict[str, Any], return_url: str | None = None) -> dict[str, Any]:
        raise NotImplementedError

    async def create_subscription(self, user: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(f"{self.provider_name} does not support subscriptions yet")

    async def cancel_subscription(self, subscription: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(f"{self.provider_name} does not support subscription cancellation yet")

    @abstractmethod
    async def handle_webhook(self, raw_body: bytes, headers: dict[str, str]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_payment_status(self, provider_payment_id: str) -> dict[str, Any]:
        raise NotImplementedError

    async def refund_payment(self, payment: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(f"{self.provider_name} refunds are not implemented yet")

    async def create_receipt(self, payment: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(f"{self.provider_name} receipts are not implemented yet")

    async def sync_subscription(self, provider_subscription_id: str) -> dict[str, Any]:
        raise NotImplementedError(f"{self.provider_name} subscription sync is not implemented yet")
