"""Stage 1: the graph — two nodes, one conditional edge, one loop-back.

This is the whole agent's control flow, and it's small on purpose (the win
condition is being able to draw it from memory):

    START → model → (should_continue?) → tools → model → ... → END

  - entry is `model`.
  - `should_continue` is the conditional edge out of `model`: if the model asked
    for a tool AND we're under the turn cap → "tools"; otherwise → END.
  - `tools` always loops back to `model`.

That single branch is what makes this an agent rather than a one-shot call.
"""

from langgraph.graph import END, StateGraph

from filing_agent.nodes import TURN_CAP, _tool_uses, model_node, tools_node
from filing_agent.state import AgentState


def should_continue(state: AgentState) -> str:
    """Route out of the model node.

    -> "tools" if the last assistant message requested a tool AND we're still
       under the turn cap.
    -> END otherwise (the normal exit: the model answered with no tool call; or
       the safety exit: we hit the cap).
    """
    last_message = state["messages"][-1]
    if _tool_uses(last_message) and state["turn_count"] < TURN_CAP:
        return "tools"
    return END


def build_graph():
    """Assemble and compile the StateGraph."""
    graph = StateGraph(AgentState)
    graph.add_node("model", model_node)
    graph.add_node("tools", tools_node)

    graph.set_entry_point("model")
    graph.add_conditional_edges("model", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "model")  # loop back

    return graph.compile()


# The compiled, runnable agent. Import this and call `app.invoke(initial_state)`.
app = build_graph()
