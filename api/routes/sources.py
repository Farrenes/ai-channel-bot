from __future__ import annotations

from time import perf_counter
from uuid import uuid4
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from services.billing.guards import extract_user_id
from services.billing.service import BillingService
from services.source_validation import SourceValidationService

router = APIRouter(prefix="/sources", tags=["sources"])
source_validation_service = SourceValidationService()
billing_service = BillingService()


class SourceValidationRequest(BaseModel):
    url: str = Field(min_length=1)
    user_id: int | None = None
    topic_profile_id: int | None = None
    topic_config_id: int | None = None
    name: str | None = None
    topic: str | None = None
    is_user_added: bool = True
    is_active: bool = True
    priority: int = 100
    request_source: str = "api"
    idempotency_key: str | None = None


class SourceEnvelope(BaseModel):
    status: str
    module: str
    run_id: str
    duration_ms: int
    data: dict[str, Any]
    errors: list[str] = Field(default_factory=list)


def get_source_validation_service() -> SourceValidationService:
    return source_validation_service


def get_billing_service() -> BillingService:
    return billing_service


def _build_blocked_envelope(*, run_id: str, duration_ms: int, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "blocked",
        "module": "billing_guard",
        "run_id": run_id,
        "duration_ms": duration_ms,
        "data": result,
        "errors": [result.get("message", "Action is blocked by billing limits.")],
    }


@router.post("/validate", response_model=SourceEnvelope)
async def validate_source(
    request: SourceValidationRequest,
    service: SourceValidationService = Depends(get_source_validation_service),
    billing: BillingService = Depends(get_billing_service),
):
    started_at = perf_counter()
    run_id = uuid4().hex
    payload = request.model_dump()
    user_id = extract_user_id(payload)
    guard_result = await billing.check_limit(user_id, "source_check")
    if not guard_result.get("allowed"):
        duration_ms = int((perf_counter() - started_at) * 1000)
        return _build_blocked_envelope(run_id=run_id, duration_ms=duration_ms, result=guard_result)

    data = await service.validate_source(payload)
    await billing.record_usage(user_id, "source_check")
    duration_ms = int((perf_counter() - started_at) * 1000)
    return {
        "status": "ok",
        "module": "source_validation",
        "run_id": run_id,
        "duration_ms": duration_ms,
        "data": data,
        "errors": [],
    }


@router.post("/fetch", response_model=SourceEnvelope)
async def fetch_source(
    request: SourceValidationRequest,
    service: SourceValidationService = Depends(get_source_validation_service),
    billing: BillingService = Depends(get_billing_service),
):
    started_at = perf_counter()
    run_id = uuid4().hex
    payload = request.model_dump()
    user_id = extract_user_id(payload)
    guard_result = await billing.check_limit(user_id, "fetch")
    if not guard_result.get("allowed"):
        duration_ms = int((perf_counter() - started_at) * 1000)
        return _build_blocked_envelope(run_id=run_id, duration_ms=duration_ms, result=guard_result)

    data = await service.fetch_source(payload)
    await billing.record_usage(user_id, "fetch")
    duration_ms = int((perf_counter() - started_at) * 1000)
    return {
        "status": "ok",
        "module": "source_validation",
        "run_id": run_id,
        "duration_ms": duration_ms,
        "data": data,
        "errors": [],
    }
