"""Stage 1: the two node functions — the per-turn logic of the loop.

  - model_node: ask Claude (with the tools) what to do; append its reply.
  - tools_node: run whatever tool Claude asked for; append the result.

Neither builds the graph (that's Prompt 1.4). Each returns a partial state update
that LangGraph merges via the reducers in state.py — so they return only the NEW
messages, not the whole transcript.
"""

from typing import Any

from filing_agent.executor import run_tool
from filing_agent.llm import call_model
from filing_agent.tools import TOOL_SCHEMAS

# The turn cap is a SAFETY RAIL, not a normal exit. The agent should stop on its
# own by emitting an answer with no tool call; this only catches a runaway loop.
TURN_CAP = 6

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
    for tool_use_id, name, args in _tool_uses(last_message):
        result_str = run_tool(name, args)
        results.append(
            {"type": "tool_result", "tool_use_id": tool_use_id, "content": result_str}
        )
    tool_message = {"role": "user", "content": results}
    return {"messages": [tool_message]}
