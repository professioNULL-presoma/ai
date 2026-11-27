import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.routers import health, ocr

settings = get_settings()
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.ocr_preload:
        from app.services.ocr import get_engine

        get_engine()
    yield


app = FastAPI(
    title="집사 AI",
    description="원룸 임대차 계약서 OCR·분석 서버 (backend 내부 호출용)",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(health.router)
app.include_router(ocr.router)
