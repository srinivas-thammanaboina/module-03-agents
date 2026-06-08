"""Stage 2: the graph — now TWO loops (tool loop + revision loop).

    START → model ──tool & turn<cap──► tools ──► model      (TOOL LOOP)
              │ no tool (a draft answer)
              ▼
           reflect ──not grounded & revisions<cap──► model  (REVISION LOOP)
              │ grounded (or gave up → flagged unverified)
              ▼
            END

  - entry is `model`.
  - `should_continue` (out of model): tool requested & under turn cap → "tools";
    a draft answer (no tool) → "reflect"; tool requested but cap hit → END (safety).
  - `tools` loops back to `model` (gather evidence).
  - `should_revise` (out of reflect): passed → END; failed & under revision cap →
    "model" (fix it); else → END (give up; answer is flagged unverified at output).

Stage 1's graph is untouched underneath — we only ADDED the reflect node and its
edge. (Reflection changes control flow, so it's a node, per WHY.md.)
"""

from langgraph.graph import END, StateGraph

from filing_agent.nodes import (
    REVISION_CAP,
    TURN_CAP,
    _tool_uses,
    model_node,
    reflect_node,
    tools_node,
)
from filing_agent.state import AgentState


def should_continue(state: AgentState) -> str:
    """Route out of the model node."""
    last_message = state["messages"][-1]
    has_tool = bool(_tool_uses(last_message))
    if has_tool and state["turn_count"] < TURN_CAP:
        return "tools"
    if has_tool:  # cap hit mid-tool-use → stop (safety rail)
        return END
    return "reflect"  # no tool requested = a draft answer → check it before exit


def should_revise(state: AgentState) -> str:
    """Route out of the reflect node."""
    if state.get("reflection_passed"):
        return END  # grounded → ship it
    if state.get("revision_count", 0) < REVISION_CAP:
        return "model"  # not grounded, still have attempts → loop back to fix
    return END  # out of attempts → give up; output flags the answer unverified


def build_graph():
    """Assemble and compile the StateGraph."""
    graph = StateGraph(AgentState)
    graph.add_node("model", model_node)
    graph.add_node("tools", tools_node)
    graph.add_node("reflect", reflect_node)

    graph.set_entry_point("model")
    graph.add_conditional_edges(
        "model", should_continue, {"tools": "tools", "reflect": "reflect", END: END}
    )
    graph.add_edge("tools", "model")  # tool loop
    graph.add_conditional_edges("reflect", should_revise, {"model": "model", END: END})

    return graph.compile()


# The compiled, runnable agent. Import this and call `app.invoke(initial_state)`.
app = build_graph()
