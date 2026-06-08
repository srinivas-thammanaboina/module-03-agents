"""Stage 1: the agent's state.

The state IS the agent's memory. LangGraph passes it from node to node; each node
returns a partial update, and LangGraph merges it using each field's *reducer*.

Two fields:
  - messages: the running transcript (Anthropic-native message dicts — see the
    Stage 1 whiteboard decision). Its reducer is `operator.add`, which means a
    node returns only the NEW messages and LangGraph CONCATENATES them onto the
    list. So history accumulates instead of being overwritten — the model re-reads
    the whole conversation each turn to decide its next move.
  - turn_count: how many times the model node has run. No reducer, so returning it
    overwrites. Used only by the turn-cap safety rail.

Note we use `operator.add`, NOT langgraph's `add_messages` — that helper assumes
LangChain message objects and would coerce ours. We store raw Anthropic dicts and
just concatenate.
"""

import operator
from typing import Annotated, Any, TypedDict


class AgentState(TypedDict):
    messages: Annotated[list[dict[str, Any]], operator.add]
    turn_count: int

    # --- Stage 2 (reflection) ---
    # Ids of chunks actually retrieved this run. add-reducer so they accumulate
    # across every search call. This is the AUTHORITATIVE "provided" set the
    # deterministic citation audit checks against (don't scrape it from text).
    retrieved_ids: Annotated[list[str], operator.add]
    # The answer being checked, the verdict, and how many times we've looped back
    # to fix it (feeds the revision cap). No reducer → each write overwrites.
    draft_answer: str
    reflection_passed: bool
    revision_count: int
