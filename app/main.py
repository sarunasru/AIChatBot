"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import STATIC_DIR, settings
from app.knowledge_loader import load_knowledge_base
from app.rate_limit import limiter
from app.routes import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("faq_assistant")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Load the company knowledge base into memory once, at startup."""
    knowledge = load_knowledge_base()
    logger.info("Loaded knowledge base (%d characters).", len(knowledge))
    yield


app = FastAPI(title="Virtualus DI asistentas Simas", lifespan=lifespan)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(router)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return a clean JSON 429 instead of slowapi's default plain-text response."""
    return JSONResponse(
        status_code=429,
        content={"error": "Per daug užklausų. Palaukite akimirką ir bandykite dar kartą."},
    )


@app.middleware("http")
async def add_widget_frame_ancestors(request: Request, call_next):
    """Restrict who may <iframe> the embeddable widget via CSP frame-ancestors."""
    response = await call_next(request)
    if request.url.path == "/widget":
        response.headers["Content-Security-Policy"] = (
            f"frame-ancestors {settings.widget_frame_ancestors}"
        )
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return a clean JSON error for malformed or invalid requests."""
    return JSONResponse(
        status_code=422,
        content={"error": "Neteisinga užklausa.", "details": exc.errors()},
    )
