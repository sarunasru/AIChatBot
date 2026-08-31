"""All LLM API interaction lives in this module.

The rest of the application must never call the LLM client SDK directly -
it should only ever call `answer()`. This keeps future model or provider
changes isolated to a single file.

The `openai` package below is used purely as a generic client for OpenRouter's
chat-completions API; point it at a different compatible endpoint by changing
LLM_BASE_URL in .env.
"""

import re

# The `openai` package is just the client library for the OpenRouter API here;
# `OpenAI` is the client class, pointed at LLM_BASE_URL (OpenRouter) in _get_client.
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
)

from app.config import settings
from app.knowledge_loader import get_cached_knowledge
from app.retrieval import search
from app.prompts import build_system_prompt

Message = dict[str, str]


class AIConfigError(Exception):
    """Raised when the AI module is misconfigured (e.g. missing API key)."""


class AIRequestError(Exception):
    """Raised when the call to the LLM API fails or times out."""


_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Lazily create and cache the LLM client."""
    global _client

    if not settings.api_key:
        raise AIConfigError(
            "LLM_API_KEY nenustatytas. Sukonfigūruokite jį .env faile."
        )

    if _client is None:
        _client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout=settings.request_timeout,
        )
    return _client


def _build_messages(question: str, history: list[Message]) -> list[Message]:
    """Assemble the full message list: system prompt, history, then the question."""
    knowledge = get_cached_knowledge()

    # Hybrid retrieval: add the website chunks most relevant to this question on
    # top of the always-on curated knowledge. Each chunk carries its source URL
    # so the assistant can link straight to the relevant page.
    # Pass the recent user turns as separate context so follow-ups ("what are
    # his contacts?") work, while a fresh new-topic question still matches on its
    # own (search() takes the best match against either - see retrieval.search).
    recent_user = [e.get("content", "") for e in history if e.get("role") == "user"][-2:]
    context = " ".join(recent_user).strip() or None
    chunks = search(question, context)
    if chunks:
        parts = []
        for c in chunks:
            src = f"(Šaltinis: {c['url']})\n" if c.get("url") else ""
            parts.append(f"{src}{c['text']}")
        extra = "\n\n---\n\n".join(parts)
        knowledge = (
            f"{knowledge}\n\n"
            "Papildoma informacija iš bibliotekos svetainės (aktuali šiam klausimui). "
            "Kur tinka, atsakyme gali nurodyti šaltinio adresą:\n"
            f"\"\"\"\n{extra}\n\"\"\""
        )

    system_prompt = build_system_prompt(knowledge)

    messages: list[Message] = [{"role": "system", "content": system_prompt}]

    for entry in history:
        role = entry.get("role")
        content = entry.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": question})
    return messages


def answer(question: str, history: list[Message]) -> str:
    """Generate an AI answer to `question`, given prior conversation `history`.

    Raises:
        AIConfigError: if the LLM API key is missing.
        AIRequestError: if the request to the LLM API fails, times out, or the
            response is otherwise invalid.
    """
    client = _get_client()
    messages = _build_messages(question, history)

    try:
        completion = client.chat.completions.create(
            model=settings.model,
            messages=messages,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
        )
    except AuthenticationError as exc:
        raise AIConfigError("Nurodytas API raktas buvo atmestas.") from exc
    except APITimeoutError as exc:
        raise AIRequestError("Užklausa AI paslaugai pasibaigė laiku. Bandykite dar kartą.") from exc
    except APIConnectionError as exc:
        raise AIRequestError("Nepavyko prisijungti prie AI paslaugos. Bandykite vėliau.") from exc
    except APIStatusError as exc:
        raise AIRequestError(f"AI paslauga grąžino klaidą: {exc.message}") from exc

    if not completion.choices:
        raise AIRequestError("AI paslauga grąžino tuščią atsakymą.")

    reply = completion.choices[0].message.content
    if not reply:
        raise AIRequestError("AI paslauga grąžino tuščią atsakymą.")

    return _strip_markdown(reply.strip())


def _strip_markdown(text: str) -> str:
    """Remove Markdown formatting so replies are shown as clean plain text.

    The system prompt already asks for plain text, but models occasionally slip in
    emphasis/headers anyway - this guarantees no stray "*", "#" or backticks reach
    the user, whose chat UI renders replies as literal text.
    """
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"^\s*#{1,6}\s*", "", line)      # "# Heading" -> "Heading"
        line = re.sub(r"^(\s*)\*\s+", r"\1- ", line)   # "* item" bullet -> "- item"
        lines.append(line)
    text = "\n".join(lines)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = text.replace("*", "")  # any remaining emphasis asterisks
    return text
