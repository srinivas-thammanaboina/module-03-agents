"""Stage 4, step 1: the reusable ANALYST.

Wraps our whole Stage 1-3 graph as a self-contained specialist that answers ONE
company's question and returns a grounded result with citations. The orchestrator
(Prompt 4.2) treats this as a black box — A2A-style task handoff — reading only the
AGENT_CARD to know what it can do, never reaching inside the graph.

Statelessness (the 4.1 acceptance check): every call builds FRESH initial state and
invokes the compiled graph; our module-level globals (bound retriever, retrieval
singleton) are read-only. So two analyst calls for different companies cannot bleed
into each other — which is what makes parallel delegation safe later.
"""

from typing import Any

from filing_agent.graph import app
from filing_agent.nodes import _CITATION_RE, _assistant_text
from filing_agent.retrieval import _to_ticker, bind_real_retriever

SUPPORTED = ("TSLA", "AAPL", "NVDA")
_NAMES = {"TSLA": "Tesla", "AAPL": "Apple", "NVDA": "Nvidia"}

# The A2A "Agent Card" — what this analyst advertises to an orchestrator. Plain
# data; the orchestrator coordinates from this without touching the analyst's graph.
AGENT_CARD: dict[str, Any] = {
    "name": "filing-analyst",
    "description": (
        "Answers grounded questions about ONE company's latest SEC 10-K. Retrieves "
        "and cites filing chunks (chunk ids), fetches live stock prices (cited as "
        "MKT- ids), computes deterministic comparisons, and self-checks that every "
        "claim is grounded before answering."
    ),
    "supported_companies": list(SUPPORTED),
    "input": {
        "company": "ticker or name (TSLA / AAPL / NVDA)",
        "question": "a single-company question",
    },
    "output": {
        "answer": "grounded text with [citation] ids",
        "citations": "list of cited ids (chunk + MKT-)",
        "reflection_passed": "bool — did the grounding self-check pass",
    },
    "scope": "exactly one latest 10-K per supported company; no other companies, years, or 8-Ks",
}


def build_scoped_question(ticker: str, question: str) -> str:
    """Wrap a question so the analyst is scoped to one company's filing/ticker."""
    name = _NAMES.get(ticker, ticker)
    return (
        f"You are analyzing ONLY {name} ({ticker}). Whenever you call search_filings "
        f"or get_stock_price, use company/ticker = {ticker}. Do not reference any other "
        f"company.\n\nQuestion: {question}"
    )


def run_analyst(company: str, question: str) -> dict[str, Any]:
    """Answer a single company's question with the full Stage 1-3 agent.

    Returns a dict: {company, ticker, question, answer, citations, retrieved_ids,
    reflection_passed}. For an unsupported company, returns an error result without
    invoking the graph (the orchestrator should never delegate one of these).
    """
    ticker = _to_ticker(company)
    if ticker not in SUPPORTED:
        return {
            "company": company,
            "ticker": None,
            "question": question,
            "answer": None,
            "citations": [],
            "retrieved_ids": [],
            "reflection_passed": False,
            "error": f"Unsupported company {company!r}. Covered: {', '.join(SUPPORTED)}.",
        }

    bind_real_retriever()  # idempotent — ensures search/describe hit the real corpus

    # FRESH state per call → no shared mutable state between invocations.
    initial_state = {
        "messages": [{"role": "user", "content": build_scoped_question(ticker, question)}],
        "turn_count": 0,
        "retrieved_ids": [],
        "draft_answer": "",
        "reflection_passed": False,
        "revision_count": 0,
    }
    final = app.invoke(initial_state)

    answer = final.get("draft_answer") or _assistant_text(final["messages"][-1])
    citations = sorted(set(_CITATION_RE.findall(answer or "")))
    return {
        "company": _NAMES.get(ticker, ticker),
        "ticker": ticker,
        "question": question,
        "answer": answer,
        "citations": citations,
        # de-duped, order-preserved — the orchestrator audits the union of these.
        "retrieved_ids": list(dict.fromkeys(final.get("retrieved_ids", []))),
        "reflection_passed": bool(final.get("reflection_passed")),
    }
