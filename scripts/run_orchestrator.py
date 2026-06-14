"""Run the Stage 4 orchestrator on a cross-company question and show what it did.

Prints the per-company task split, each analyst's pass/citation summary, the final
synthesized + ranked answer, and the union citation audit (should find no
fabricated ids).

Run from the repo root:
    .venv/bin/python scripts/run_orchestrator.py "Compare AI risks across TSLA, AAPL, NVDA and rank by revenue growth. Cite chunks."
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from filing_agent.orchestrator import orchestrator  # noqa: E402

DEFAULT_QUESTION = (
    "Compare how TSLA, AAPL, and NVDA each described AI-related risks in their latest "
    "10-Ks, and rank the three by their latest reported year-over-year total revenue "
    "growth. Cite chunks."
)


def main() -> None:
    question = " ".join(sys.argv[1:]).strip() or DEFAULT_QUESTION

    final_state = orchestrator.invoke(
        {
            "question": question,
            "tasks": [],
            "flagged": [],
            "results": [],
            "final": "",
            "audit": {},
            "unverified": [],
        }
    )

    print(f"QUESTION: {question}\n")
    tasks = final_state.get("tasks", [])
    print(f"DECOMPOSED INTO {len(tasks)} TASK(S): {', '.join(t['company'] for t in tasks) or '(none)'}")
    if final_state.get("flagged"):
        print(f"FLAGGED (not in corpus): {', '.join(str(c) for c in final_state['flagged'])}")
    print()
    for r in final_state.get("results", []):
        print(f"  {r['ticker']}: reflection={'pass' if r['reflection_passed'] else 'FAIL'} "
              f"| {len(r['citations'])} citations")
    unverified = final_state.get("unverified") or []
    print(f"\nUNVERIFIED ANALYSTS (surfaced in synthesis): {', '.join(unverified) if unverified else 'none ✓'}")
    audit = final_state.get("audit", {})
    print(f"UNION CITATION AUDIT: hallucinated={audit.get('hallucinated') or 'none ✓'}")
    print(f"SYNTHESIS GROUNDEDNESS: {'passed ✓' if audit.get('synthesis_passed') else 'NOT passed ⚠'}")
    for claim in audit.get("unsupported_claims", []) or []:
        print(f"    ⚠ unsupported in synthesis: {claim}")
    print()
    print("=== SYNTHESIZED ANSWER ===")
    print(final_state.get("final") or "(no answer)")


if __name__ == "__main__":
    main()
