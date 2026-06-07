"""Stage 1: the tool executor.

`run_tool(name, args)` is the bridge between the model's request and our Python:
the model emits "call tool X with args {...}"; this dispatches to the right
function in tools.py and returns a STRING to feed back into the transcript.

Two robustness rules, because the model reads whatever we return:
  - An unknown tool name returns a readable error string (never raises) — the
    model can see it and recover (e.g. pick a real tool).
  - A tool that raises (bad/missing args, etc.) is caught and returned as an
    error string — one bad tool call must not crash the whole graph run.

Serialization keeps each search_filings chunk's `id` visible in the string, since
the model needs to see ids in order to cite them (Stage 2 audits those citations).
"""

import json
from typing import Any

from filing_agent import tools

# Explicit name → function map. Readable over clever: you can see every tool the
# agent can reach in one place. (Stage 3 adds the MCP tool here.)
_DISPATCH = {
    "search_filings": tools.search_filings,
    "describe_filing": tools.describe_filing,
    "compare_numbers": tools.compare_numbers,
}


def run_tool(name: str, args: dict[str, Any]) -> str:
    """Dispatch a tool call and return its result as a model-readable string.

    Args:
        name: The tool the model asked for.
        args: The keyword arguments the model supplied.

    Returns:
        The tool's result serialized to a string, or a readable "ERROR: ..."
        string if the tool is unknown or raised. Never propagates an exception.
    """
    fn = _DISPATCH.get(name)
    if fn is None:
        return (
            f"ERROR: unknown tool {name!r}. "
            f"Available tools: {', '.join(sorted(_DISPATCH))}."
        )
    try:
        result = fn(**args)
    except Exception as exc:  # noqa: BLE001 — deliberately broad: never crash the run
        return f"ERROR running {name}: {type(exc).__name__}: {exc}"
    return _to_string(result)


def _to_string(result: Any) -> str:
    """Serialize a tool result for the model, keeping chunk ids prominent.

    A list of chunk dicts (each with an `id`) is rendered as labeled blocks so
    the ids lead each line and the model can cite them. Everything else
    (describe_filing's dict, compare_numbers' dict) is JSON for legibility.
    """
    if isinstance(result, list) and all(isinstance(x, dict) and "id" in x for x in result):
        if not result:
            return "No chunks found."
        return "\n".join(_format_chunk(ch) for ch in result)
    return json.dumps(result, ensure_ascii=False, indent=2, default=str)


def _format_chunk(ch: dict[str, Any]) -> str:
    """One chunk → one line, id first so it's unmissable as a citation token."""
    return (
        f"[{ch['id']}] {ch.get('company', '?')} / {ch.get('section', '?')} "
        f"(score={ch.get('score')}): {ch.get('text', '')}"
    )
