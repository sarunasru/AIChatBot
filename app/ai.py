"""All LLM API interaction lives in this module.

The rest of the application must never call the LLM client SDK directly -
it should only ever call `answer()`. This keeps future model or provider
changes isolated to a single file.

Uses the `openai` package as a client, since its chat-completions format is
the de facto standard implemented by OpenAI, OpenRouter, and most other
providers - swap LLM_BASE_URL in .env to point at a different one.
"""

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
)

from app.config import settings
from app.knowledge_loader import get_cached_knowledge
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

    return reply.strip()
