"""Run the Stage 1 agent on a question and show what it did.

Prints the final answer AND the sequence of tools the agent chose to call — that
sequence IS the loop working: watch it call a tool, get a result, decide again.

Run from the repo root:
    .venv/bin/python scripts/run_agent.py "In Tesla's latest 10-K, did automotive revenue grow versus the prior year it reports?"

(With stubs bound, the answers are placeholder text — we're watching the control
flow, not answer quality, until the real retriever binds at Prompt 1.6.)
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from filing_agent.graph import app  # noqa: E402
from filing_agent.nodes import _tool_uses  # noqa: E402

DEFAULT_QUESTION = (
    "In Tesla's latest 10-K, did automotive revenue grow versus the prior year it reports?"
)


def _maybe_bind_real() -> str:
    """Bind the real Module 02 retriever unless --stub was passed.

    Returns a short label for the run header. Removes --stub from argv so it
    isn't treated as part of the question.
    """
    if "--stub" in sys.argv:
        sys.argv.remove("--stub")
        return "STUB retrieval"
    from filing_agent.retrieval import bind_real_retriever

    bind_real_retriever()
    return "REAL Module 02 retrieval"


def _final_text(message: dict) -> str:
    """Concatenate the text blocks of an assistant message (objects or dicts)."""
    parts = []
    for block in message.get("content", []) or []:
        btype = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
        if btype == "text":
            parts.append(block["text"] if isinstance(block, dict) else block.text)
    return "".join(parts).strip()


def main() -> None:
    mode = _maybe_bind_real()  # do this BEFORE reading the question (strips --stub)
    question = " ".join(sys.argv[1:]).strip() or DEFAULT_QUESTION
    print(f"[mode: {mode}]")

    initial_state = {
        "messages": [{"role": "user", "content": question}],
        "turn_count": 0,
        "retrieved_ids": [],
        "draft_answer": "",
        "reflection_passed": False,
        "revision_count": 0,
    }
    final_state = app.invoke(initial_state)

    # The tool sequence, in order, across the whole run.
    tool_sequence = [
        name
        for message in final_state["messages"]
        if (message.get("role") if isinstance(message, dict) else None) == "assistant"
        for _id, name, _args in _tool_uses(message)
    ]

    print(f"QUESTION: {question}\n")
    print(f"TOOLS CALLED ({len(tool_sequence)}): {' -> '.join(tool_sequence) or '(none)'}")
    print(f"TURNS: {final_state['turn_count']} | REVISIONS: {final_state.get('revision_count', 0)}")

    # On a pass, draft_answer IS the shipped answer. On give-up, the last message
    # is the critique, so use draft_answer and flag it unverified.
    passed = final_state.get("reflection_passed")
    answer = final_state.get("draft_answer") or _final_text(final_state["messages"][-1])
    print(f"REFLECTION: {'passed ✓' if passed else 'NOT passed ⚠'}\n")
    if passed is False:
        print("⚠ UNVERIFIED — reflection did not pass after revisions. Treat with caution.\n")
    print("ANSWER:")
    print(answer or "(no text answer)")


if __name__ == "__main__":
    main()
