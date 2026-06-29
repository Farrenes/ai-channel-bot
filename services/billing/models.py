from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class BillingEnvelope(BaseModel):
    status: str
    module: str
    run_id: str
    duration_ms: int
    data: dict[str, Any]
    errors: list[str] = Field(default_factory=list)


class BillingPlan(BaseModel):
    id: int
    code: str
    name: str
    description: str = ""
    price_rub: Decimal
    period_days: int
    post_limit: int
    source_limit: int
    channel_limit: int
    llm_limit: int = 0
    rewrite_limit: int = 0
    source_check_limit: int = 0
    candidate_limit: int = 0
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreatePaymentRequest(BaseModel):
    user_id: int
    plan_code: str
    return_url: str | None = None
    provider: str | None = None
    idempotency_key: str | None = None


class ApplyPromocodeRequest(BaseModel):
    user_id: int
    code: str


class ManualGrantRequest(BaseModel):
    admin_id: int
    plan_code: str
    days: int = Field(default=30, ge=1)
    reason: str = ""


class ManualBanRequest(BaseModel):
    admin_id: int
    reason: str = ""


class ManualResetLimitsRequest(BaseModel):
    admin_id: int
    reason: str = ""


class GuardRequest(BaseModel):
    user_id: int | None = None
    action: str
    amount: int = Field(default=1, ge=1)


class ProviderPayment(BaseModel):
    provider: str
    provider_payment_id: str
    status: str
    amount_rub: Decimal
    currency: str = "RUB"
    confirmation_url: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class ProviderWebhookResult(BaseModel):
    provider: str
    event_id: str
    event_type: str
    provider_payment_id: str | None = None
    status: str
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class AccessResult(BaseModel):
    allowed: bool
    reason: str
    message: str
    plan_code: str | None = None
    subscription_id: int | None = None
    current_period_end: datetime | None = None


class LimitResult(BaseModel):
    allowed: bool
    action: str
    reason: str
    message: str
    used: int = 0
    limit: int = 0
    plan_code: str | None = None
