"""
Utilities for interacting with the OpenAI Responses API to power the designer
assistant chat experience.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Dict, Iterable, List, Optional, Tuple

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from openai import OpenAI

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are AIOAK's Designer Studio Assistant. Provide thoughtful, practical, and"
    " encouraging guidance to fashion designers who are managing their design"
    " portfolio on designer.aioak.co. Offer step-by-step suggestions, highlight"
    " industry best practices, and, when helpful, recommend how they can leverage"
    " the platform's dashboard features. Keep answers concise, friendly, and focused"
    " on actionable next steps."
)


class ChatServiceError(Exception):
    """Raised when the AI assistant cannot complete a request."""


@lru_cache
def _get_client() -> OpenAI:
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        raise ImproperlyConfigured("OPENAI_API_KEY is required to use the AI assistant.")
    return OpenAI(api_key=api_key)


def _normalize_history(history: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Ensure the history only contains well-formed user/assistant messages without blank content.
    """
    normalized: List[Dict[str, str]] = []
    for item in history or []:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role not in {"user", "assistant"}:
            continue
        if not content:
            continue
        normalized.append({"role": role, "content": content})
    return normalized


def get_ai_reply(
    history: Iterable[Dict[str, str]],
    *,
    temperature: float = 0.7,
) -> Tuple[str, Optional[Dict[str, int]]]:
    """
    Generate a reply from the OpenAI chat model using the supplied conversation history.

    Parameters
    ----------
    history:
        An iterable of dicts in the OpenAI chat format (role/content).
    temperature:
        Sampling temperature to control creativity.

    Returns
    -------
    Tuple[str, Optional[Dict[str, int]]]
        The model's reply text, followed by optional token usage metadata.
    """
    client = _get_client()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(_normalize_history(history))

    try:
        response = client.chat.completions.create(
            model=getattr(settings, "OPENAI_CHAT_MODEL", "gpt-4.1-mini"),
            messages=messages,
            temperature=temperature,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("OpenAI chat completion failed")
        raise ChatServiceError("Failed to generate a reply from the AI assistant.") from exc

    if not response.choices:
        raise ChatServiceError("The AI assistant did not return any choices.")

    message = response.choices[0].message
    reply_text = (message.content or "").strip()

    usage = getattr(response, "usage", None)
    usage_payload: Optional[Dict[str, int]] = None
    if usage is not None:
        usage_payload = {
            key: getattr(usage, key, None)
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        }

    return reply_text, usage_payload
