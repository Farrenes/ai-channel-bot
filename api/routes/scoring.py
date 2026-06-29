from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, Depends

from services.billing.guards import extract_user_id
from services.billing.service import BillingService
from services.scoring import ScoringEnvelope, ScoringRequest, ScoringService

router = APIRouter(prefix="/score", tags=["scoring"])
scoring_service = ScoringService()
billing_service = BillingService()


def get_scoring_service() -> ScoringService:
    return scoring_service


def get_billing_service() -> BillingService:
    return billing_service


@router.post("", response_model=ScoringEnvelope)
async def score_items(
    request: ScoringRequest,
    service: ScoringService = Depends(get_scoring_service),
    billing: BillingService = Depends(get_billing_service),
):
    started_at = perf_counter()
    run_id = uuid4().hex
    payload = request.model_dump()
    user_id = extract_user_id(payload)
    guard_result = await billing.check_limit(user_id, "score")
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

    data = await service.score_items(
        items=request.items,
        content_strategy=request.content_strategy,
        topic_profile=request.topic_profile,
        save_to_db=request.save_to_db,
    )
    await billing.record_usage(user_id, "score")
    duration_ms = int((perf_counter() - started_at) * 1000)
    return {
        "status": "ok",
        "module": "scoring",
        "run_id": run_id,
        "duration_ms": duration_ms,
        "data": data,
        "errors": [],
    }
