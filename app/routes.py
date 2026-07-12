"""HTTP route definitions for the FAQ assistant."""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator

from app.ai import AIConfigError, AIRequestError, answer
from app.config import TEMPLATES_DIR, settings
from app.rate_limit import limiter

logger = logging.getLogger("faq_assistant")

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

MAX_MESSAGE_LENGTH = 2000
MAX_HISTORY_MESSAGES = 30


class ChatMessage(BaseModel):
    """A single turn in the conversation history."""

    role: str
    content: str

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, value: str) -> str:
        if value not in ("user", "assistant"):
            raise ValueError('role must be "user" or "assistant"')
        return value


class ChatRequest(BaseModel):
    """Payload expected by POST /chat."""

    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    history: list[ChatMessage] = Field(default_factory=list)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message must not be empty")
        return stripped


class ChatResponse(BaseModel):
    """Payload returned by POST /chat on success."""

    reply: str


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Serve the standalone chat page."""
    return templates.TemplateResponse(request, "index.html")


@router.get("/widget", response_class=HTMLResponse)
async def widget(request: Request) -> HTMLResponse:
    """Serve the embeddable widget (launcher button + chat panel) for iframing."""
    return templates.TemplateResponse(request, "widget.html")


@router.get("/health")
async def health() -> dict[str, str]:
    """Simple liveness check."""
    return {"status": "ok"}


@router.post("/chat")
@limiter.limit(settings.chat_rate_limit)
async def chat(request: Request, payload: ChatRequest) -> JSONResponse:
    """Answer a customer question using the local knowledge base."""
    trimmed_history = [
        {"role": item.role, "content": item.content}
        for item in payload.history[-MAX_HISTORY_MESSAGES:]
    ]

    try:
        reply = answer(payload.message, trimmed_history)
    except AIConfigError as exc:
        logger.error("AI configuration error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": "Asistentas sukonfigūruotas netinkamai. Susisiekite su palaikymo komanda."},
        )
    except AIRequestError as exc:
        logger.error("AI request error: %s", exc)
        return JSONResponse(
            status_code=502,
            content={"error": str(exc)},
        )
    except Exception:
        logger.exception("Unexpected error while generating an answer")
        return JSONResponse(
            status_code=500,
            content={"error": "Įvyko netikėta klaida. Bandykite dar kartą."},
        )

    return JSONResponse(status_code=200, content=ChatResponse(reply=reply).model_dump())
