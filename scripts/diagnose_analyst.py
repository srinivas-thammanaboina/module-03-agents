"""Diagnose why an analyst's answer failed reflection.

Runs ONE analyst loop and surfaces the reflection CRITIQUE(s) — the exact claims
the groundedness check rejected — plus the final answer, pass/fail, revision count,
and the cited-vs-retrieved id check. Defaults to AAPL with the AI-risk +
revenue-growth ask (mirrors the orchestrator sub-task that failed).

NOTE: reflection is an LLM judgment, so a single run is not perfectly
reproducible — it may pass this time. That's itself a finding (the answer is
borderline). If it fails, the critiques show exactly what tripped it.

Run:
    .venv/bin/python scripts/diagnose_analyst.py            # AAPL, default question
    .venv/bin/python scripts/diagnose_analyst.py AAPL "your question"
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from filing_agent.analyst import build_scoped_question  # noqa: E402
from filing_agent.graph import app  # noqa: E402
from filing_agent.nodes import _CITATION_RE, _assistant_text  # noqa: E402
from filing_agent.retrieval import _to_ticker, bind_real_retriever  # noqa: E402

DEFAULT_COMPANY = "AAPL"
DEFAULT_QUESTION = (
    "Describe the AI-related risks in the latest 10-K, and report the latest "
    "year-over-year total revenue growth with figures. Cite chunks."
)


def _critiques(messages: list) -> list[str]:
    """Reflect appends critiques as plain-string user messages; tool results are
    lists. So a str-content user message starting with the critique header is one."""
    found = []
    for m in messages:
        content = m.get("content")
        if (
            m.get("role") == "user"
            and isinstance(content, str)
            and content.startswith("Your draft did not pass")
        ):
            found.append(content)
    return found


def main() -> None:
    args = sys.argv[1:]
    company = args[0] if args else DEFAULT_COMPANY
    question = " ".join(args[1:]) if len(args) > 1 else DEFAULT_QUESTION

    ticker = _to_ticker(company)
    bind_real_retriever()
    state = {
        "messages": [{"role": "user", "content": build_scoped_question(ticker, question)}],
        "turn_count": 0,
        "retrieved_ids": [],
        "draft_answer": "",
        "reflection_passed": False,
        "revision_count": 0,
    }
    final = app.invoke(state)

    answer = final.get("draft_answer") or _assistant_text(final["messages"][-1])
    cited = sorted(set(_CITATION_RE.findall(answer or "")))
    retrieved = list(dict.fromkeys(final.get("retrieved_ids", [])))

    print(
        f"COMPANY: {ticker} | reflection_passed={final.get('reflection_passed')} "
        f"| revisions={final.get('revision_count', 0)}"
    )
    print(f"cited ids ({len(cited)}): {cited}")
    print(
        f"retrieved ids: {len(retrieved)} | "
        f"cited-not-retrieved (hallucinated): {sorted(set(cited) - set(retrieved)) or 'none'}"
    )

    crits = _critiques(final["messages"])
    print(f"\n=== REFLECTION CRITIQUES ({len(crits)}) — what the groundedness check rejected ===")
    for i, critique in enumerate(crits, 1):
        print(f"\n--- attempt {i} ---\n{critique}")
    if not crits:
        print("(none — it passed this run; the answer is borderline, not consistently ungrounded)")

    print("\n=== FINAL ANSWER ===")
    print(answer)


if __name__ == "__main__":
    main()
