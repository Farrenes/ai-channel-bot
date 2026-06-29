from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, Depends

from services.billing.guards import extract_user_id
from services.billing.service import BillingService
from services.generation import (
    GenerationEnvelope,
    GenerationRequest,
    GenerationService,
)

router = APIRouter(prefix="/generation", tags=["generation"])
generation_service = GenerationService()
billing_service = BillingService()


def get_generation_service() -> GenerationService:
    return generation_service


def get_billing_service() -> BillingService:
    return billing_service


@router.post("/post", response_model=GenerationEnvelope)
async def generate_post(
    request: GenerationRequest,
    service: GenerationService = Depends(get_generation_service),
    billing: BillingService = Depends(get_billing_service),
):
    started_at = perf_counter()
    run_id = uuid4().hex
    payload = request.model_dump()
    user_id = extract_user_id(payload)
    guard_result = await billing.check_limit(user_id, "generate")
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

    data, errors = service.generate_post(request.topic_profile, request.context)
    await billing.record_usage(user_id, "generate")
    duration_ms = int((perf_counter() - started_at) * 1000)
    return {
        "status": "ok",
        "module": "generation",
        "run_id": run_id,
        "duration_ms": duration_ms,
        "data": data,
        "errors": errors,
    }
