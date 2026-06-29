from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, Depends

from services.billing.guards import extract_user_id
from services.billing.service import BillingService
from services.telegram_publish import TelegramPublishEnvelope, TelegramPublishRequest, TelegramPublishService

router = APIRouter(prefix="/telegram", tags=["telegram"])
telegram_publish_service = TelegramPublishService()
billing_service = BillingService()


def get_telegram_publish_service() -> TelegramPublishService:
    return telegram_publish_service


def get_billing_service() -> BillingService:
    return billing_service


@router.post("/publish", response_model=TelegramPublishEnvelope)
async def publish_post(
    request: TelegramPublishRequest,
    service: TelegramPublishService = Depends(get_telegram_publish_service),
    billing: BillingService = Depends(get_billing_service),
):
    started_at = perf_counter()
    run_id = uuid4().hex
    payload = request.model_dump()
    user_id = extract_user_id(payload)
    guard_result = await billing.check_limit(user_id, "publish")
    if not guard_result.get("allowed"):
        duration_ms = int((perf_counter() - started_at) * 1000)
        return {
            "status": "blocked",
            "module": "billing_guard",
            "run_id": run_id,
            "duration_ms": duration_ms,
            "data": guard_result,
            "errors": [guard_result.get("message", "Action is blocked by billing limits.")],
        }

    data = await service.publish(request)
    await billing.record_usage(user_id, "publish")
    duration_ms = int((perf_counter() - started_at) * 1000)
    return {
        "status": "ok",
        "module": "telegram_publish",
        "run_id": run_id,
        "duration_ms": duration_ms,
        "data": data,
        "errors": [],
    }
