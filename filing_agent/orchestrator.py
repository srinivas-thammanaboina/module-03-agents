"""Stage 4, step 2: the ORCHESTRATOR — a small linear LangGraph over analysts.

    decompose  → split a multi-company question into per-company tasks
                 (restricted to TSLA/AAPL/NVDA; others are flagged, not delegated)
    delegate   → run one analyst per task (sequential for now; parallel later)
    synthesize → combine the grounded answers, rank, PRESERVE citations,
                 then run a union citation audit so the merged answer stays grounded

This is a DIFFERENT decomposition from Module 02's DecompositionRetriever: that
balances retrieval inside one analyst; this splits TASKS across whole analysts.
"""

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from filing_agent.analyst import SUPPORTED, run_analyst
from filing_agent.llm import call_model
from filing_agent.nodes import _CITATION_RE, _assistant_text, _parse_verdict


class OrchestratorState(TypedDict):
    question: str
    tasks: list[dict[str, Any]]     # [{company(ticker), subquestion}]
    flagged: list[str]              # requested companies not in the corpus
    results: list[dict[str, Any]]   # analyst result dicts
    final: str                      # synthesized, ranked answer
    audit: dict[str, Any]           # {hallucinated, cited} from the union audit
    unverified: list[str]           # tickers whose analyst answer failed reflection


_DECOMPOSE_SYSTEM = (
    "You split a multi-company question into per-company sub-tasks for a "
    "filing-analyst that covers ONLY TSLA, AAPL, and NVDA (one latest 10-K each).\n"
    "Identify which of those three the question asks about. For each, write a focused "
    "SINGLE-company sub-question capturing what to find for that company. Any company "
    "mentioned that is NOT TSLA/AAPL/NVDA goes in 'flagged' (we cannot analyze it). "
    "If the question implies all covered companies, include all three.\n"
    "Respond with ONLY JSON, no prose:\n"
    '{"tasks": [{"company": "TSLA", "subquestion": "..."}, ...], "flagged": ["GOOG", ...]}\n'
    "Use tickers (TSLA/AAPL/NVDA) for company."
)

_SYNTHESIZE_SYSTEM = (
    "You combine per-company grounded answers into ONE synthesis that answers the "
    "user's original question, including any requested ranking or comparison.\n"
    "CRITICAL: preserve the citation ids EXACTLY as they appear in the per-company "
    "answers (e.g. [TSLA-2026-01-29-0061], [MKT-NVDA-2026-02-25]). Do NOT invent, "
    "alter, or drop ids; only use ids that appear in the provided answers.\n"
    "If some requested companies were flagged as not in the corpus, say so plainly.\n"
    "If a per-company answer is marked reflection_passed=False, it is UNVERIFIED — its "
    "analyst could not fully ground it. Explicitly flag that company's contribution as "
    "'⚠ unverified' and treat its figures/claims with caution; do not present them as "
    "confidently as the verified ones.\n"
    "Lead with the ranking/answer, then support each point with its citation."
)

# Groundedness check on the SYNTHESIS itself — closes the gap the union audit can't
# see (an UNcited assertion). Evidence = the per-company analyst answers.
_SYNTHESIS_CHECK_SYSTEM = (
    "You are a strict groundedness checker for a multi-company synthesis. You are given a "
    "SYNTHESIS answer and the PER-COMPANY ANALYST ANSWERS it was built from (each already "
    "grounded + cited).\n"
    "For EACH factual claim in the synthesis — INCLUDING every ranking claim and figure — "
    "decide whether it is supported by the analyst answers. A claim is UNSUPPORTED if no "
    "analyst answer states it, including any ranking or number asserted WITHOUT a citation "
    "or filled in from outside knowledge to cover a gap.\n"
    "Respond with ONLY JSON: {\"passed\": <true|false>, \"unsupported_claims\": [\"...\"]}."
)


def decompose_node(state: OrchestratorState) -> dict[str, Any]:
    """LLM splits the question into per-company tasks; flags out-of-corpus names."""
    response = call_model(
        [{"role": "user", "content": f"Question: {state['question']}\n"
          f"Supported companies: {', '.join(SUPPORTED)}."}],
        system=_DECOMPOSE_SYSTEM,
    )
    data = _parse_verdict(_assistant_text({"content": response.content}))

    tasks, flagged = [], list(data.get("flagged", []) or [])
    for task in data.get("tasks", []) or []:
        company = (task.get("company") or "").upper()
        if company in SUPPORTED:
            tasks.append({"company": company, "subquestion": task.get("subquestion") or state["question"]})
        else:
            flagged.append(task.get("company"))
    return {"tasks": tasks, "flagged": flagged}


def delegate_node(state: OrchestratorState) -> dict[str, Any]:
    """Run one analyst per task. Sequential (readable/observable) for now."""
    results = [run_analyst(t["company"], t["subquestion"]) for t in state["tasks"]]
    return {"results": results}


def synthesize_node(state: OrchestratorState) -> dict[str, Any]:
    """Combine grounded answers + rank, then audit citations against the union."""
    results = state["results"]
    blocks = []
    for r in results:
        blocks.append(
            f"### {r['company']} ({r['ticker']}) — reflection_passed={r['reflection_passed']}\n"
            f"{r['answer']}\nCitations: {', '.join(r['citations']) or '(none)'}"
        )
    user = (
        f"Original question: {state['question']}\n\n"
        f"Per-company grounded answers:\n\n" + "\n\n".join(blocks)
    )
    if state.get("flagged"):
        user += (
            f"\n\nNOTE: these requested companies are NOT in the corpus and were not "
            f"analyzed: {', '.join(str(c) for c in state['flagged'])}."
        )
    # Surface unverified analysts explicitly (option 1) — deterministic, not just
    # relying on the synthesizer to notice the reflection_passed flags.
    unverified = [r["ticker"] for r in results if not r.get("reflection_passed")]
    if unverified:
        user += (
            f"\n\nUNVERIFIED companies (their analyst's reflection did NOT pass — flag "
            f"clearly and treat with caution): {', '.join(unverified)}."
        )
    response = call_model([{"role": "user", "content": user}], system=_SYNTHESIZE_SYSTEM)
    final = _assistant_text({"content": response.content})

    # Union citation audit (Decision 4): every id cited in the final synthesis must
    # be one some analyst actually retrieved — reuse Stage 2's regex at the top level.
    provided: set[str] = set()
    for r in results:
        provided |= set(r.get("retrieved_ids", []))
        provided |= set(r.get("citations", []))
    cited = set(_CITATION_RE.findall(final or ""))
    hallucinated = sorted(cited - provided)

    # Reflect the synthesis itself: does every claim (esp. rankings) trace to an
    # analyst answer? Catches uncited assertions the citation audit cannot.
    evidence = "\n\n".join(f"{r['company']} ({r['ticker']}):\n{r['answer']}" for r in results)
    check = call_model(
        [{"role": "user", "content": f"SYNTHESIS:\n{final}\n\nPER-COMPANY ANALYST ANSWERS:\n{evidence}"}],
        system=_SYNTHESIS_CHECK_SYSTEM,
    )
    verdict = _parse_verdict(_assistant_text({"content": check.content}))
    synthesis_passed = (not hallucinated) and bool(verdict.get("passed"))

    return {
        "final": final,
        "audit": {
            "hallucinated": hallucinated,
            "cited": sorted(cited),
            "synthesis_passed": synthesis_passed,
            "unsupported_claims": verdict.get("unsupported_claims", []) or [],
        },
        "unverified": unverified,
    }


def build_orchestrator():
    graph = StateGraph(OrchestratorState)
    graph.add_node("decompose", decompose_node)
    graph.add_node("delegate", delegate_node)
    graph.add_node("synthesize", synthesize_node)
    graph.set_entry_point("decompose")
    graph.add_edge("decompose", "delegate")
    graph.add_edge("delegate", "synthesize")
    graph.add_edge("synthesize", END)
    return graph.compile()


orchestrator = build_orchestrator()
