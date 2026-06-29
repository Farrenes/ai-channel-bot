from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, Depends

from services.topic_profile import (
    TopicProfileEnvelope,
    TopicProfileRequest,
    TopicProfileService,
)

router = APIRouter(prefix="/topics", tags=["topics"])
topic_profile_service = TopicProfileService()


def get_topic_profile_service() -> TopicProfileService:
    return topic_profile_service


@router.post("/profile", response_model=TopicProfileEnvelope)
async def profile_topic(
    request: TopicProfileRequest,
    service: TopicProfileService = Depends(get_topic_profile_service),
):
    started_at = perf_counter()
    profile, errors = service.build_profile(request.raw_topic)
    duration_ms = int((perf_counter() - started_at) * 1000)
    return {
        "status": "ok",
        "module": "topic_profile",
        "run_id": uuid4().hex,
        "duration_ms": duration_ms,
        "data": profile,
        "errors": errors,
    }

