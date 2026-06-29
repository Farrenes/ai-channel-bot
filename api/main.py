from fastapi import FastAPI

from api.routes.billing import router as billing_router
from api.routes.generation import router as generation_router
from api.routes.review import router as review_router
from api.routes.scoring import router as scoring_router
from api.routes.sources import router as sources_router
from api.routes.topics import router as topics_router
from api.routes.telegram import router as telegram_router

app = FastAPI()
app.include_router(topics_router)
app.include_router(generation_router)
app.include_router(review_router)
app.include_router(scoring_router)
app.include_router(telegram_router)
app.include_router(sources_router)
app.include_router(billing_router)
