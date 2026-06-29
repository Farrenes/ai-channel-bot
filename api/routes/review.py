from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, Depends

from services.billing.guards import extract_user_id
from services.billing.service import BillingService
from services.review import (
    ReviewEnvelope,
    ReviewRewriteEnvelope,
    ReviewRequest,
    ReviewService,
)

router = APIRouter(prefix="/review", tags=["review"])
review_service = ReviewService()
billing_service = BillingService()


def get_review_service() -> ReviewService:
    return review_service


def get_billing_service() -> BillingService:
    return billing_service


@router.post("/post", response_model=ReviewEnvelope)
async def review_post(
    request: ReviewRequest,
    service: ReviewService = Depends(get_review_service),
):
    started_at = perf_counter()
    data = service.review_post(request.post, request.topic_profile, request.context)
    duration_ms = int((perf_counter() - started_at) * 1000)
    return {
        "status": "ok",
        "module": "review",
        "run_id": uuid4().hex,
        "duration_ms": duration_ms,
        "data": data,
        "errors": [],
    }


@router.post("/rewrite", response_model=ReviewRewriteEnvelope)
async def rewrite_post(
    request: ReviewRequest,
    service: ReviewService = Depends(get_review_service),
    billing: BillingService = Depends(get_billing_service),
):
    started_at = perf_counter()
    run_id = uuid4().hex
    payload = request.model_dump()
    user_id = extract_user_id(payload)
    guard_result = await billing.check_limit(user_id, "rewrite")
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

    data = service.rewrite_post(request.post, request.topic_profile, request.context, request.feedback)
    await billing.record_usage(user_id, "rewrite")
    duration_ms = int((perf_counter() - started_at) * 1000)
    return {
        "status": "ok",
        "module": "review",
        "run_id": run_id,
        "duration_ms": duration_ms,
        "data": data,
        "errors": [],
    }
