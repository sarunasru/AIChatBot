"""HTTP route definitions for the FAQ assistant."""

import logging
import re

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator

from app.ai import AIConfigError, AIRequestError, answer
from app.chat_log import log_exchange
from app.config import TEMPLATES_DIR, settings
from app.email_sender import EmailConfigError, EmailSendError, send_contact_email
from app.rate_limit import limiter

logger = logging.getLogger("faq_assistant")

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

MAX_MESSAGE_LENGTH = 2000
MAX_HISTORY_MESSAGES = 30

MAX_CONTACT_MESSAGE_LENGTH = 4000
MAX_NAME_LENGTH = 120
# Deliberately loose sanity check — real validation is that the address works.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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
    session_id: str = Field(default="", max_length=64)

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


class ContactRequest(BaseModel):
    """Payload expected by POST /contact."""

    email: str = Field(min_length=3, max_length=254)
    name: str = Field(default="", max_length=MAX_NAME_LENGTH)
    message: str = Field(min_length=1, max_length=MAX_CONTACT_MESSAGE_LENGTH)
    history: list[ChatMessage] = Field(default_factory=list)
    consent: bool = False

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, value: str) -> str:
        stripped = value.strip()
        if not EMAIL_RE.match(stripped):
            raise ValueError("invalid email address")
        return stripped

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message must not be empty")
        return stripped

    @field_validator("consent")
    @classmethod
    def consent_must_be_given(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("consent is required")
        return value


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

    log_exchange(payload.session_id, payload.message, reply)
    return JSONResponse(status_code=200, content=ChatResponse(reply=reply).model_dump())


def _format_transcript(history: list[ChatMessage]) -> str:
    """Render the chat history as a readable plain-text transcript."""
    if not history:
        return "(pokalbio istorija tuščia)"
    lines = []
    for item in history[-MAX_HISTORY_MESSAGES:]:
        speaker = "Lankytojas" if item.role == "user" else "Asistentas"
        lines.append(f"{speaker}: {item.content}")
    return "\n".join(lines)


@router.post("/contact")
@limiter.limit(settings.contact_rate_limit)
async def contact(request: Request, payload: ContactRequest) -> JSONResponse:
    """Forward a visitor's message plus the chat transcript to library staff."""
    name = payload.name.strip()
    subject = f"Nauja žinutė iš Simas asistento{f' – {name}' if name else ''}"
    body = (
        f"Vardas: {name or '(nenurodyta)'}\n"
        f"El. paštas: {payload.email}\n\n"
        f"Žinutė:\n{payload.message}\n\n"
        f"--- Pokalbio istorija ---\n{_format_transcript(payload.history)}\n"
    )

    try:
        send_contact_email(subject=subject, body=body, reply_to=payload.email)
    except EmailConfigError as exc:
        logger.error("Email configuration error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": "Kontaktų forma sukonfigūruota netinkamai. Susisiekite su palaikymo komanda."},
        )
    except EmailSendError as exc:
        logger.error("Email send error: %s", exc)
        return JSONResponse(
            status_code=502,
            content={"error": "Nepavyko išsiųsti žinutės. Bandykite dar kartą vėliau."},
        )
    except Exception:
        logger.exception("Unexpected error while sending a contact email")
        return JSONResponse(
            status_code=500,
            content={"error": "Įvyko netikėta klaida. Bandykite dar kartą."},
        )

    return JSONResponse(status_code=200, content={"status": "sent"})
