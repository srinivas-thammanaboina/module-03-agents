"""Stage 1: the two node functions — the per-turn logic of the loop.

  - model_node: ask Claude (with the tools) what to do; append its reply.
  - tools_node: run whatever tool Claude asked for; append the result.

Neither builds the graph (that's Prompt 1.4). Each returns a partial state update
that LangGraph merges via the reducers in state.py — so they return only the NEW
messages, not the whole transcript.
"""

import json
import re
from typing import Any

from filing_agent.executor import run_tool
from filing_agent.llm import call_model
from filing_agent.tools import TOOL_SCHEMAS

# The turn cap is a SAFETY RAIL, not a normal exit. The agent should stop on its
# own by emitting an answer with no tool call; this only catches a runaway loop.
TURN_CAP = 6

# Up to this many revision loops before we give up and flag the answer unverified.
REVISION_CAP = 2

# Matches an inline citation tag like [TSLA-2026-01-29-0224]. Same scheme as
# Module 02's app/generate.py — one citation token across both modules.
_CITATION_RE = re.compile(r"\[([A-Za-z0-9][A-Za-z0-9\-_.]*)\]")

# The groundedness check is deliberately strict about "supported by the cited
# chunk's TEXT" rather than "sounds plausible" — that distinction is the value of
# the node. JSON-only output so we can parse it.
REFLECT_SYSTEM_PROMPT = (
    "You are a strict groundedness checker for answers about SEC 10-K filings.\n"
    "You are given a DRAFT ANSWER and the RETRIEVED CHUNKS it was supposed to use "
    "(each chunk is labeled with its id in square brackets).\n"
    "For EACH factual claim in the draft, decide whether it is directly supported by "
    "the TEXT of a retrieved chunk. A claim is UNSUPPORTED if no chunk's text states "
    "it, even if it sounds plausible or is generally true — being correct in the world "
    "is not enough; it must be in the chunks. A number or comparison is unsupported "
    "unless the figures appear in the chunk text.\n"
    "Respond with ONLY a JSON object, no prose:\n"
    '{"passed": <true|false>, "unsupported_claims": ["<claim>", ...]}\n'
    "passed is true only if every factual claim is supported. List each unsupported "
    "claim briefly in unsupported_claims (empty list if all supported)."
)

# Minimal system prompt. It states the single-filing reality so the model doesn't
# invent a `year` arg or try to fetch a second filing, and it demands grounding +
# chunk-id citations (which Stage 2 will audit).
SYSTEM_PROMPT = (
    "You are a financial filing analyst answering questions about SEC 10-K filings.\n"
    "The corpus is exactly ONE latest 10-K each for three companies: TSLA, AAPL, NVDA. "
    "There are no other companies, no 8-Ks, and no other years.\n"
    "Ground EVERY factual claim by retrieving chunks with the tools and citing the "
    "chunk id in square brackets, e.g. [TSLA-1A-0007]. Do not state a fact you did not "
    "retrieve.\n"
    "Year-over-year comparisons are made WITHIN a single 10-K (it reports current- and "
    "prior-year figures side by side) — there is no second filing to compare against.\n"
    "Use the compare_numbers tool for any numeric comparison instead of doing arithmetic "
    "yourself.\n"
    "Never guess or rely on outside knowledge. If the filings don't support an answer, "
    "say so plainly."
)


def _tool_uses(message: dict[str, Any]) -> list[tuple[str, str, dict]]:
    """Return (id, name, input) for each tool_use block in a message.

    Handles content blocks whether they're SDK objects (from a fresh response) or
    plain dicts. Shared by tools_node here and should_continue in graph.py.
    """
    uses: list[tuple[str, str, dict]] = []
    for block in message.get("content", []) or []:
        btype = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
        if btype != "tool_use":
            continue
        if isinstance(block, dict):
            uses.append((block["id"], block["name"], block.get("input", {}) or {}))
        else:
            uses.append((block.id, block.name, dict(block.input or {})))
    return uses


def model_node(state: dict[str, Any]) -> dict[str, Any]:
    """Call Claude with the tools; append its response; bump the turn count."""
    response = call_model(state["messages"], tools=TOOL_SCHEMAS, system=SYSTEM_PROMPT)
    # Store the raw content blocks as an Anthropic-native assistant message; the
    # SDK accepts these blocks back on the next call, and tools_node can read the
    # tool_use blocks out of them.
    assistant_message = {"role": "assistant", "content": response.content}
    return {"messages": [assistant_message], "turn_count": state["turn_count"] + 1}


def tools_node(state: dict[str, Any]) -> dict[str, Any]:
    """Run every tool the last assistant message requested; append the results.

    All tool results for one assistant turn go back as a SINGLE user message (one
    tool_result block per call) — that's the shape the Anthropic API expects.
    """
    last_message = state["messages"][-1]
    results = []
    retrieved_ids: list[str] = []
    for tool_use_id, name, args in _tool_uses(last_message):
        tool_result = run_tool(name, args)
        results.append(
            {"type": "tool_result", "tool_use_id": tool_use_id, "content": tool_result.content}
        )
        # Record ids at the source — the authoritative set Stage 2's audit uses.
        retrieved_ids.extend(tool_result.retrieved_ids)
    tool_message = {"role": "user", "content": results}
    return {"messages": [tool_message], "retrieved_ids": retrieved_ids}


# ---------------------------------------------------------------------------
# Stage 2 — reflection
# ---------------------------------------------------------------------------
def _assistant_text(message: dict[str, Any]) -> str:
    """Concatenate the text blocks of a message (blocks may be objects or dicts)."""
    parts = []
    for block in message.get("content", []) or []:
        btype = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
        if btype == "text":
            parts.append(block["text"] if isinstance(block, dict) else block.text)
    return "".join(parts).strip()


def _gather_evidence(messages: list[dict[str, Any]]) -> str:
    """Pull the retrieved-chunk text out of the transcript's tool_result messages.

    The deterministic audit uses `retrieved_ids` from state, but the LLM check
    needs the chunk TEXT to judge support — and that lives in the tool_result
    blocks we fed back during the run. Each block already labels chunks with
    their [id], so the checker sees id + text together.
    """
    evidence = []
    for message in messages:
        for block in message.get("content", []) or []:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                evidence.append(str(block.get("content", "")))
    return "\n\n".join(evidence)


def _parse_verdict(text: str) -> dict[str, Any]:
    """Parse the checker's JSON verdict, tolerating prose around it.

    Falls back to 'needs revision' if we can't parse — failing safe means a
    malformed verdict triggers a review, never a silent pass.
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {"passed": False, "unsupported_claims": ["(could not parse reflection verdict)"]}


def reflect_node(state: dict[str, Any]) -> dict[str, Any]:
    """Check the draft answer two ways; pass only if BOTH agree.

    (a) deterministic citation audit — every [id] cited must be one actually
        retrieved this run (mirrors Module 02's _audit_citations). A cited id we
        never retrieved is a hallucinated citation = automatic fail.
    (b) LLM groundedness check — each factual claim must be supported by the text
        of a retrieved chunk, not just sound plausible.

    On failure, append a critique to the transcript (so the model can fix it or
    retrieve more) and bump revision_count. Graph rewiring happens in Prompt 2.2.
    """
    draft = _assistant_text(state["messages"][-1])
    provided_ids = set(state.get("retrieved_ids", []))

    # (a) deterministic citation audit
    cited_ids = set(_CITATION_RE.findall(draft))
    hallucinated = sorted(cited_ids - provided_ids)

    # (b) LLM groundedness check — give the checker the draft + the chunk text.
    evidence = _gather_evidence(state["messages"])
    check_prompt = [
        {"role": "user", "content": f"DRAFT ANSWER:\n{draft}\n\nRETRIEVED CHUNKS:\n{evidence}"}
    ]
    response = call_model(check_prompt, system=REFLECT_SYSTEM_PROMPT)
    verdict = _parse_verdict(_assistant_text({"content": response.content}))
    llm_passed = bool(verdict.get("passed"))
    unsupported = verdict.get("unsupported_claims", []) or []

    passed = (not hallucinated) and llm_passed

    update: dict[str, Any] = {"draft_answer": draft, "reflection_passed": passed}
    if not passed:
        update["messages"] = [{"role": "user", "content": _format_critique(hallucinated, unsupported)}]
        update["revision_count"] = state.get("revision_count", 0) + 1
    return update


def _format_critique(hallucinated: list[str], unsupported: list[str]) -> str:
    """A clear, actionable critique for the model to fix on the next loop."""
    lines = ["Your draft did not pass the grounding check. Fix these and re-answer:"]
    if hallucinated:
        lines.append(
            "- Hallucinated citations (these ids were NOT retrieved — remove them or "
            f"retrieve real support): {', '.join(hallucinated)}"
        )
    for claim in unsupported:
        lines.append(f"- Unsupported claim (not backed by a retrieved chunk): {claim}")
    lines.append(
        "Either retrieve chunks that support each claim and cite their real ids, or "
        "remove/qualify the unsupported parts."
    )
    return "\n".join(lines)
