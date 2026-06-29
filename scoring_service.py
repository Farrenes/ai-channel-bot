from __future__ import annotations

import gc
from contextlib import asynccontextmanager
from typing import Any

import asyncpg
from fastapi import FastAPI
from loguru import logger
from pydantic import BaseModel, Field

from config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER, ROUTERAI_API_KEY, validate_required_env
from services.scoring import ScoringInputItem, ScoringResponse, score_items_universal

db_pool = None


async def init_db() -> None:
    global db_pool
    if not all([DB_HOST, DB_NAME, DB_USER, DB_PASSWORD]):
        db_pool = None
        return
    db_pool = await asyncpg.create_pool(
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        min_size=1,
        max_size=3,
        command_timeout=60,
    )


async def close_db() -> None:
    global db_pool
    if db_pool:
        await db_pool.close()
        db_pool = None


async def add_idea_to_pool(idea: dict[str, Any]) -> None:
    if not db_pool or not idea.get("title"):
        return
    async with db_pool.acquire() as conn:
        try:
            await conn.execute(
                """
                INSERT INTO ideas_pool (
                    title, source, link, category, score_b2c, score_utility,
                    score_savability, score_repostability, score_practical,
                    total_score, raw_description, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                ON CONFLICT (title) DO UPDATE SET
                    source = COALESCE(NULLIF(EXCLUDED.source, ''), ideas_pool.source),
                    link = COALESCE(NULLIF(EXCLUDED.link, ''), ideas_pool.link),
                    category = COALESCE(NULLIF(EXCLUDED.category, ''), ideas_pool.category),
                    score_b2c = COALESCE(EXCLUDED.score_b2c, ideas_pool.score_b2c),
                    score_utility = COALESCE(EXCLUDED.score_utility, ideas_pool.score_utility),
                    score_savability = COALESCE(EXCLUDED.score_savability, ideas_pool.score_savability),
                    score_repostability = COALESCE(EXCLUDED.score_repostability, ideas_pool.score_repostability),
                    score_practical = COALESCE(EXCLUDED.score_practical, ideas_pool.score_practical),
                    total_score = COALESCE(EXCLUDED.total_score, ideas_pool.total_score),
                    raw_description = COALESCE(NULLIF(EXCLUDED.raw_description, ''), ideas_pool.raw_description),
                    status = COALESCE(NULLIF(EXCLUDED.status, ''), ideas_pool.status)
                """,
                idea["title"],
                idea.get("source"),
                idea.get("link"),
                idea.get("category"),
                idea.get("score_b2c"),
                idea.get("score_utility"),
                idea.get("score_savability"),
                idea.get("score_repostability"),
                idea.get("score_practical"),
                idea.get("total_score"),
                idea.get("raw_description"),
                idea.get("status", "pending"),
            )
        except Exception as exc:
            logger.error(f"Failed to write idea to DB: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_required_env(("ROUTERAI_API_KEY",))
    try:
        await init_db()
    except Exception as exc:
        logger.warning(f"DB unavailable for scoring service, continuing without persistence: {exc}")
    logger.info("Scoring service started")
    yield
    await close_db()
    gc.collect()
    logger.info("Scoring service stopped")


app = FastAPI(title="Scoring Service", lifespan=lifespan)


class ScoringRequest(BaseModel):
    items: list[ScoringInputItem]
    content_strategy: str = ""
    topic_profile: dict[str, Any] = Field(default_factory=dict)
    topic_type: list[str] = Field(default_factory=list)
    save_to_db: bool = True


@app.get("/health")
async def health():
    return {"status": "ok", "db": db_pool is not None}


@app.post("/score", response_model=ScoringResponse)
async def score_items(request: ScoringRequest):
    result = await score_items_universal(
        request.items,
        content_strategy=request.content_strategy,
        topic_profile=request.topic_profile,
        topic_type=request.topic_type,
        save_to_db=request.save_to_db,
        db_writer=add_idea_to_pool,
    )
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
