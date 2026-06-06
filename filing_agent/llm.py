"""Stage 0: the LLM plumbing.

One job: load config and make a Claude call work, so every later stage can
`from filing_agent.llm import call_model` and never think about clients or env
vars again. Kept deliberately thin — the transport lives here and nowhere else.
"""

import os

from anthropic import Anthropic
from dotenv import load_dotenv

# Read .env once, at import. Later stages just call the functions below.
load_dotenv()

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 1024

# The agent loop calls the model many times per question, so we build the
# client once and reuse it rather than re-reading the key on every call.
_client: Anthropic | None = None


def get_client() -> Anthropic:
    """Return a configured Anthropic client, building it on first use.

    Fails loudly (not silently) if the key is missing — a clear error now
    beats a confusing 401 deep inside a graph run later.
    """
    global _client
    if _client is None:
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in."
            )
        _client = Anthropic(api_key=key)
    return _client


def call_model(messages, tools=None, max_tokens=DEFAULT_MAX_TOKENS):
    """Send one request to Claude and return the RAW response object.

    Thin on purpose. We return the raw Message (not just text) so callers can
    inspect `stop_reason` and any `tool_use` blocks — which is exactly what the
    Stage 1 agent loop needs to decide whether to call a tool or stop.

    Model comes from ANTHROPIC_MODEL (env), falling back to DEFAULT_MODEL.
    """
    model = os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL)
    kwargs = {"model": model, "max_tokens": max_tokens, "messages": messages}
    if tools:
        kwargs["tools"] = tools
    return get_client().messages.create(**kwargs)
