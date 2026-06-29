from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request

from services.billing.models import (
    ApplyPromocodeRequest,
    BillingEnvelope,
    CreatePaymentRequest,
    GuardRequest,
    ManualBanRequest,
    ManualGrantRequest,
    ManualResetLimitsRequest,
)
from services.billing.service import BillingService


router = APIRouter(tags=["billing"])
billing_service = BillingService()


def get_billing_service() -> BillingService:
    return billing_service


def _build_envelope(started_at: float, data: dict, errors: list[str] | None = None, status: str = "ok") -> BillingEnvelope:
    duration_ms = int((perf_counter() - started_at) * 1000)
    return BillingEnvelope(
        status=status,
        module="billing",
        run_id=uuid4().hex,
        duration_ms=duration_ms,
        data=data,
        errors=errors or [],
    )


def _bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/billing/plans", response_model=BillingEnvelope)
async def get_billing_plans(service: BillingService = Depends(get_billing_service)):
    started_at = perf_counter()
    plans = await service.get_available_plans()
    return _build_envelope(started_at, {"plans": plans})


@router.post("/billing/payments/create", response_model=BillingEnvelope)
async def create_billing_payment(
    request: CreatePaymentRequest,
    service: BillingService = Depends(get_billing_service),
):
    started_at = perf_counter()
    try:
        data = await service.create_payment_for_plan(
            user_id=request.user_id,
            plan_code=request.plan_code,
            return_url=request.return_url,
            provider_name=request.provider,
            idempotency_key=request.idempotency_key,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return _build_envelope(started_at, data)


@router.get("/billing/payments/{payment_id}/status", response_model=BillingEnvelope)
async def get_billing_payment_status(
    payment_id: int,
    service: BillingService = Depends(get_billing_service),
):
    started_at = perf_counter()
    payment = await service.repo.fetch_payment(payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail=f"Payment not found: {payment_id}")
    return _build_envelope(started_at, {"payment": payment})


@router.post("/billing/webhooks/yookassa", response_model=BillingEnvelope)
async def handle_yookassa_webhook(
    request: Request,
    service: BillingService = Depends(get_billing_service),
):
    started_at = perf_counter()
    raw_body = await request.body()
    data = await service.process_yookassa_webhook(raw_body, dict(request.headers))
    return _build_envelope(started_at, data)


@router.post("/billing/promocode/apply", response_model=BillingEnvelope)
async def apply_billing_promocode(
    request: ApplyPromocodeRequest,
    service: BillingService = Depends(get_billing_service),
):
    started_at = perf_counter()
    data = await service.apply_promocode(request.user_id, request.code)
    return _build_envelope(started_at, data)


@router.get("/billing/me/subscription", response_model=BillingEnvelope)
async def get_my_billing_subscription(
    user_id: int,
    service: BillingService = Depends(get_billing_service),
):
    started_at = perf_counter()
    access = await service.check_user_access(user_id)
    subscription = await service.repo.fetch_active_subscription(user_id)
    return _build_envelope(started_at, {"access": access, "subscription": subscription})


@router.get("/billing/me/limits", response_model=BillingEnvelope)
async def get_my_billing_limits(
    user_id: int,
    service: BillingService = Depends(get_billing_service),
):
    started_at = perf_counter()
    data = await service.get_user_limits(user_id)
    return _build_envelope(started_at, data)


@router.post("/billing/guard", response_model=BillingEnvelope)
async def check_billing_guard(
    request: GuardRequest,
    service: BillingService = Depends(get_billing_service),
):
    started_at = perf_counter()
    data = await service.check_limit(request.user_id, request.action, request.amount)
    return _build_envelope(started_at, data)


@router.post("/admin/billing/users/{user_id}/grant-access", response_model=BillingEnvelope)
async def grant_billing_access(
    user_id: int,
    request: ManualGrantRequest,
    service: BillingService = Depends(get_billing_service),
):
    started_at = perf_counter()
    try:
        subscription = await service.manual_grant_access_by_code(
            admin_id=request.admin_id,
            user_id=user_id,
            plan_code=request.plan_code,
            days=request.days,
            reason=request.reason,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return _build_envelope(started_at, {"subscription": subscription})


@router.post("/admin/billing/users/{user_id}/ban", response_model=BillingEnvelope)
async def ban_billing_user(
    user_id: int,
    request: ManualBanRequest,
    service: BillingService = Depends(get_billing_service),
):
    started_at = perf_counter()
    customer = await service.manual_ban_user(request.admin_id, user_id, request.reason)
    return _build_envelope(started_at, {"customer": customer})


@router.post("/admin/billing/users/{user_id}/reset-limits", response_model=BillingEnvelope)
async def reset_billing_limits(
    user_id: int,
    request: ManualResetLimitsRequest,
    service: BillingService = Depends(get_billing_service),
):
    started_at = perf_counter()
    data = await service.reset_user_limits(request.admin_id, user_id, request.reason)
    return _build_envelope(started_at, data)


@router.post("/admin/billing/subscriptions/{subscription_id}/cancel", response_model=BillingEnvelope)
async def cancel_billing_subscription(
    subscription_id: int,
    service: BillingService = Depends(get_billing_service),
):
    started_at = perf_counter()
    data = await service.cancel_subscription_by_id(subscription_id)
    if not data.get("canceled"):
        raise HTTPException(status_code=404, detail=f"Subscription not found: {subscription_id}")
    return _build_envelope(started_at, data)
