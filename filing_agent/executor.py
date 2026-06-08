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
from typing import Any, NamedTuple

from filing_agent import tools


class ToolResult(NamedTuple):
    """What a tool call produces.

    content      — the model-readable string fed back into the transcript.
    retrieved_ids — chunk ids this call returned (empty for non-search tools).
                    Stage 2's reflect node uses these as the authoritative set
                    of "ids we actually retrieved" for its citation audit.
    """

    content: str
    retrieved_ids: list[str]

# Explicit name → function map. Readable over clever: you can see every tool the
# agent can reach in one place. (Stage 3 adds the MCP tool here.)
_DISPATCH = {
    "search_filings": tools.search_filings,
    "describe_filing": tools.describe_filing,
    "compare_numbers": tools.compare_numbers,
}


def run_tool(name: str, args: dict[str, Any]) -> ToolResult:
    """Dispatch a tool call and return its result for the transcript.

    Args:
        name: The tool the model asked for.
        args: The keyword arguments the model supplied.

    Returns:
        A ToolResult (content string + any retrieved chunk ids). On an unknown
        tool or a tool that raises, content is a readable "ERROR: ..." string and
        retrieved_ids is empty — never propagates an exception.
    """
    fn = _DISPATCH.get(name)
    if fn is None:
        return ToolResult(
            f"ERROR: unknown tool {name!r}. "
            f"Available tools: {', '.join(sorted(_DISPATCH))}.",
            [],
        )
    try:
        result = fn(**args)
    except Exception as exc:  # noqa: BLE001 — deliberately broad: never crash the run
        return ToolResult(f"ERROR running {name}: {type(exc).__name__}: {exc}", [])
    return _to_result(result)


def _to_result(result: Any) -> ToolResult:
    """Serialize a tool result for the model, capturing chunk ids as we go.

    A list of chunk dicts (each with an `id`) is rendered as labeled blocks so
    the ids lead each line and the model can cite them — and those ids are
    returned alongside for Stage 2's audit. Everything else (describe_filing's
    dict, compare_numbers' dict) is JSON, with no ids.
    """
    if isinstance(result, list) and all(isinstance(x, dict) and "id" in x for x in result):
        if not result:
            return ToolResult("No chunks found.", [])
        content = "\n".join(_format_chunk(ch) for ch in result)
        return ToolResult(content, [ch["id"] for ch in result])
    return ToolResult(json.dumps(result, ensure_ascii=False, indent=2, default=str), [])


def _format_chunk(ch: dict[str, Any]) -> str:
    """One chunk → one line, id first so it's unmissable as a citation token."""
    return (
        f"[{ch['id']}] {ch.get('company', '?')} / {ch.get('section', '?')} "
        f"(score={ch.get('score')}): {ch.get('text', '')}"
    )
