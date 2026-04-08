"""Thin wrapper around the Anthropic client."""

import os
import anthropic

_client: anthropic.Anthropic | None = None

MODEL = "claude-opus-4-6"
MAX_TOKENS = 8096


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def call(system: str, user: str, max_tokens: int = MAX_TOKENS) -> str:
    """Make a single LLM call and return the text response."""
    response = get_client().messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text
