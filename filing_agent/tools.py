"""Stage 1: the agent's toolbox.

Three tools the model can choose to call:
  - search_filings  — semantic retrieval: what a filing SAYS about a topic
  - describe_filing — identity + available sections of the one 10-K we have
  - compare_numbers — deterministic arithmetic (no LLM, always correct)

Ground truth about the corpus (from the real Module 02 code — see
project-build-prompts-v2.md):
  - It holds the LATEST 10-K for exactly three companies: TSLA, AAPL, NVDA.
    No 8-Ks, no second year. Year-over-year comparisons are done WITHIN one
    10-K (which reports current- and prior-year figures side by side).
  - Retrieval can only filter by company TICKER. There is no year or form-type
    field in the index, so those are not tool params. Company names are
    normalized to tickers (Tesla->TSLA, Apple->AAPL, Nvidia->NVDA) at bind time.
  - Each retrieved chunk has an `id` (e.g. "TSLA-1A-0007") that IS the citation
    token. It MUST flow end to end — Stage 2 reflection audits answers against it.

`search_filings` and `describe_filing` are STUBBED for now: they return clearly
marked fake data (the chunk stub still carries an `id`) so the whole agent loop
is testable before the real Module 02 retriever exists. The real composed stack
(Expand(Decomposition(Hybrid(Retriever(store))))) binds in at Prompt 1.6 via
`bind_retriever` — no caller or schema changes when it does.
"""

from typing import Any, Callable, Optional

# ---------------------------------------------------------------------------
# The retriever seam (bound for real at Prompt 1.6)
# ---------------------------------------------------------------------------
# A thin interface, deliberately not imported from Module 02 yet. Until something
# is bound, the search/describe tools return stub data so the loop is testable
# without the corpus. `bind_retriever` lets Prompt 1.6 inject the real pipeline.
_retriever: Optional[Callable[..., Any]] = None


def bind_retriever(fn: Callable[..., Any]) -> None:
    """Bind the real Module 02 retrieval callable (done at Prompt 1.6).

    Until called, search_filings / describe_filing return clearly-marked stubs.
    """
    global _retriever
    _retriever = fn


# ---------------------------------------------------------------------------
# Tool 1 — search_filings (semantic retrieval; STUB until 1.6)
# ---------------------------------------------------------------------------
def search_filings(query: str, company: Optional[str] = None) -> list[dict[str, Any]]:
    """Search the SEC 10-K corpus for passages relevant to a query.

    Use this to find what a filing *says* about a topic — revenue drivers, risk
    factors, segment performance, MD&A commentary, etc. Returns a list of text
    chunks; each carries its `id` (the citation token) plus source metadata.

    Args:
        query: Natural-language description of what to find.
        company: Optional company filter — a ticker (e.g. "TSLA") OR a name
            (e.g. "Tesla"). Names are normalized to tickers when the real
            retriever is bound. There is no year/form-type filter: the corpus is
            one latest 10-K per company.

    Returns:
        A list of chunk dicts, each:
        {id, text, company, section, filing_date, source_url, score}.
    """
    if _retriever is None:
        # STUB — clearly marked so it can never be mistaken for real data.
        # NOTE: the `id` is present even in the stub; Stage 2 depends on it.
        return [
            {
                "id": "STUB-0001",
                "text": (
                    f"[STUB CHUNK] Pretend this passage answers: {query!r} "
                    f"(company={company}). Real retrieval binds in at Prompt 1.6."
                ),
                "company": company or "STUB_CO",
                "section": "STUB_SECTION",
                "filing_date": "2025-01-30",
                "source_url": "https://example.com/stub-10k",
                "score": 0.0,
            }
        ]
    return _retriever(query=query, company=company)


# ---------------------------------------------------------------------------
# Tool 2 — describe_filing (identity + sections; STUB until 1.6)
# ---------------------------------------------------------------------------
def describe_filing(company: str) -> dict[str, Any]:
    """Describe the one 10-K we have for a company: identity + available sections.

    Use this to orient before searching — confirm which document exists for a
    company and see what sections are available to search within. We hold exactly
    one latest 10-K per company (TSLA, AAPL, NVDA), so there is nothing to
    disambiguate; this simply reports what IS there. Returns metadata only, not
    filing content — use search_filings to read what a filing says.

    Args:
        company: Ticker (e.g. "TSLA") OR name (e.g. "Tesla"). Normalized to a
            ticker when the real retriever is bound.

    Returns:
        A dict: {company_name, ticker, filing_date, source_url, sections}.
    """
    if _retriever is None:
        # STUB — clearly marked.
        return {
            "company_name": f"{company} (STUB)",
            "ticker": (company or "STUB").upper(),
            "filing_date": "2025-01-30",
            "source_url": "https://example.com/stub-10k",
            "sections": [
                "Item 1 - Business",
                "Item 1A - Risk Factors",
                "Item 7 - MD&A",
                "Item 8 - Financial Statements",
            ],
            "note": "[STUB] Real filing identity/sections bind in at Prompt 1.6.",
        }
    return _retriever(company=company, describe=True)


# ---------------------------------------------------------------------------
# Tool 3 — compare_numbers (fully real; deterministic, no LLM)
# ---------------------------------------------------------------------------
def compare_numbers(a: float, b: float, label_a: str, label_b: str) -> dict[str, Any]:
    """Compute the difference, percent change, and direction from a to b.

    Deterministic arithmetic — ALWAYS use this for a numeric comparison instead
    of computing in your head, so the math is guaranteed correct. Typically used
    to compare two figures pulled from the SAME 10-K (e.g. current-year vs
    prior-year revenue, which a 10-K reports side by side). Percent change is
    measured relative to `a` (the baseline / earlier value).

    Args:
        a: The baseline value (e.g. prior-year figure).
        b: The comparison value (e.g. current-year figure).
        label_a: Short label for `a` (e.g. "TSLA FY2023 automotive revenue").
        label_b: Short label for `b` (e.g. "TSLA FY2024 automotive revenue").

    Returns:
        A dict: {difference, percent_change, direction, summary}. percent_change
        is None when `a` is 0 (undefined), and direction is "up"/"down"/"flat".
    """
    difference = b - a
    if a == 0:
        percent_change = None
    else:
        percent_change = (difference / abs(a)) * 100.0

    if difference > 0:
        direction = "up"
    elif difference < 0:
        direction = "down"
    else:
        direction = "flat"

    pct_str = "undefined (baseline is 0)" if percent_change is None else f"{percent_change:+.2f}%"
    summary = (
        f"{label_b} ({b}) vs {label_a} ({a}): "
        f"difference {difference:+}, {pct_str}, direction {direction}."
    )

    return {
        "difference": difference,
        "percent_change": percent_change,
        "direction": direction,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Anthropic tool schemas — what the model reads to choose a tool
# ---------------------------------------------------------------------------
# The corpus reality is stated IN the descriptions on purpose: the model picks a
# tool from these strings alone, and it must not invent year/form-type filters or
# assume multiple filings exist.
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "search_filings",
        "description": (
            "Search the SEC 10-K corpus for passages relevant to a natural-language "
            "query. The corpus is ONE latest 10-K per company for TSLA, AAPL, and NVDA "
            "(no other companies, no 8-Ks, no other years). Use this when you need the "
            "CONTENT of a filing — what a company says about risks, revenue drivers, "
            "segments, or any topic — including pulling specific NUMBERS (a 10-K states "
            "current- and prior-year figures side by side; search for them, then pass the "
            "values to compare_numbers). Returns text chunks, each with an `id` you MUST "
            "cite. `company` is optional and may be a ticker ('TSLA') or a name ('Tesla'). "
            "There is no year or form-type filter. To see what document/sections exist "
            "before searching, use describe_filing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to find, in natural language.",
                },
                "company": {
                    "type": "string",
                    "description": "Optional company filter: ticker or name, e.g. 'TSLA' or 'Tesla'.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "describe_filing",
        "description": (
            "Describe the one 10-K we have for a company: its identity (company name, "
            "ticker, filing date, source URL) and the list of sections available to "
            "search. Use this to orient BEFORE searching — to confirm the document exists "
            "and see what's in it. We hold exactly one latest 10-K per company (TSLA, "
            "AAPL, NVDA), so there is nothing to disambiguate. This returns metadata only, "
            "NOT filing content — use search_filings to read what the filing says. "
            "`company` may be a ticker ('NVDA') or a name ('Nvidia')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {
                    "type": "string",
                    "description": "Company ticker or name, e.g. 'NVDA' or 'Nvidia'.",
                },
            },
            "required": ["company"],
        },
    },
    {
        "name": "compare_numbers",
        "description": (
            "Compute the difference, percent change, and direction between two numbers. "
            "ALWAYS use this for any numeric comparison (e.g. did revenue grow year over "
            "year) instead of doing the arithmetic yourself — it is deterministic and "
            "guaranteed correct. Year-over-year here means two figures from the SAME 10-K "
            "(current vs prior year, as the filing reports them) — there is no second "
            "filing to compare against. Provide both values plus a short label for each."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "Baseline / prior-year value."},
                "b": {"type": "number", "description": "Comparison / current-year value."},
                "label_a": {"type": "string", "description": "Short label for a."},
                "label_b": {"type": "string", "description": "Short label for b."},
            },
            "required": ["a", "b", "label_a", "label_b"],
        },
    },
]
