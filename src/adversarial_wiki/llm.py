"""LLM client wrapper.

Centralizes interaction with Anthropic and exposes a minimal `call()` helper.
This module does not configure global logging; the CLI sets verbosity.
"""

from __future__ import annotations

import os
import logging
import anthropic
import click

_client: anthropic.Anthropic | None = None

MODEL = "claude-opus-4-6"
MAX_TOKENS = 8096

logger = logging.getLogger(__name__)


def get_client() -> anthropic.Anthropic:
    """Return a singleton Anthropic client using `ANTHROPIC_API_KEY`.

    Raises a ClickException if the env var is missing, so CLI surfaces a
    friendly message without a traceback.
    """
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise click.ClickException(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        logger.debug("Initializing Anthropic client")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def call(system: str, user: str, max_tokens: int = MAX_TOKENS) -> str:
    """Make a single LLM call and return the text response.

    Args:
        system: System prompt string.
        user: User content string.
        max_tokens: Max tokens for the response.

    Returns:
        The first text block from the response.
    """
    logger.debug(
        "LLM call model=%s max_tokens=%s system_len=%d user_len=%d",
        MODEL, max_tokens, len(system or ""), len(user or ""),
    )
    response = get_client().messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = response.content[0].text
    logger.debug("LLM response chars=%d", len(text or ""))
    return text

