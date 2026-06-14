"""Stage 1, Prompt 1.6: bind the REAL Module 02 retrieval pipeline.

We import and call Module 02's *composed production stack* — the same one
app/generate.py uses — rather than forking its logic, so there is one source of
truth for retrieval:

    Expand( Decomposition( Hybrid( Retriever(store) ) ) )

Key correctness points (see project-build-prompts-v2.md + the user's 1.6 notes):
  - The Chroma index was embedded with BAAI/bge-small-en-v1.5. We let Module 02
    build its own embedder (get_vector_store) so queries are embedded with the
    IDENTICAL model that built the index — mismatch would silently degrade recall.
  - The embedder/store/stack are built ONCE (module-level singletons) and reused
    across the whole agent loop. Building per call would reload ~130 MB each time.
  - We bind ONLY the default ask stack (no cross-encoder reranker), so torch's
    cross-encoder is never pulled in.
  - Every returned row keeps its chunk `id` — it's the citation token Stage 2
    audits. We never drop it.

Binding is explicit (`bind_real_retriever()`), so tests that only import tools /
executor stay on the stubs (the "keep the stub behind a fallback" requirement).
"""

import os
import pathlib
import sys
import warnings
from typing import Any, Optional

# Quiet two cosmetic warnings that fire when Module 02's embedder loads (the bge
# model is cached locally, and the FutureWarning lives in Module 02's code, which
# we don't edit). Set BEFORE sentence-transformers is first imported (in _ensure).
os.environ.setdefault("HF_HUB_OFFLINE", "1")  # model cached → skip hub checks
warnings.filterwarnings("ignore", message=r".*get_sentence_embedding_dimension.*")

# Module 02 lives in a sibling repo. Its config resolves all paths (including the
# Chroma dir) relative to its own package location, so importing it from here
# points at the real, already-built index regardless of our cwd.
MODULE_02_PATH = pathlib.Path(
    os.getenv("MODULE_02_PATH", "/Users/srinivasthammanaboina/Projects/module-02-rag-app")
)

# Put Module 02 on the path at import time (cheap) so `from app...` works in any
# helper. The HEAVY work (embedder + stack) stays lazy, in _ensure().
if str(MODULE_02_PATH) not in sys.path:
    sys.path.insert(0, str(MODULE_02_PATH))

# Built once, on first use, by _ensure().
_store: Any = None
_stack: Any = None


def _ensure() -> None:
    """Build the store + composed retriever stack once (embedder loads here)."""
    global _store, _stack
    if _stack is not None:
        return

    from app.decompose import DecompositionRetriever
    from app.expand import ExpandRetriever
    from app.hybrid import HybridRetriever
    from app.retrieve import Retriever
    from app.store import get_vector_store

    # get_vector_store() constructs Module 02's production embedder (bge-small) —
    # the same model that built the index. Done exactly once.
    _store = get_vector_store()
    _stack = ExpandRetriever(
        DecompositionRetriever(
            HybridRetriever(Retriever(_store), fusion="interleave", gated=True)
        )
    )


def _to_ticker(company: Optional[str]) -> Optional[str]:
    """Normalize a company ticker OR name to a known ticker, else None.

    Reuses Module 02's _COMPANY_PATTERNS so there's one mapping. Returns None for
    an unknown company (the caller turns that into a clear note, not a silent
    empty filter — Module 02 would otherwise build {"ticker": "FOO"} → 0 chunks).
    """
    if not company or not company.strip():
        return None
    from app.retrieve import _COMPANY_PATTERNS

    text = company.strip()
    upper = text.upper()
    if upper in _COMPANY_PATTERNS:  # already a ticker
        return upper
    lower = text.lower()
    for ticker, name_patterns in _COMPANY_PATTERNS.items():
        if any(pat in lower for pat in name_patterns):
            return ticker
    return None


def _map_row(row: dict[str, Any]) -> dict[str, Any]:
    """Map a Module 02 retrieval row to our tool's chunk shape, preserving `id`.

    Module 02 row: {id, document, similarity, metadata{ticker, company_name,
    section, filing_date, source_url, ...}}.
    """
    meta = row.get("metadata", {}) or {}
    return {
        "id": row["id"],  # NEVER drop — the citation token
        "text": row.get("document", ""),
        "company": meta.get("company_name") or meta.get("ticker"),
        "section": meta.get("section"),
        "filing_date": meta.get("filing_date"),
        "source_url": meta.get("source_url"),
        "score": row.get("similarity"),
    }


def _search(query: str, company: Optional[str] = None, k: int = 6) -> list[dict[str, Any]]:
    """Real search_filings: run the composed stack, map rows, preserve ids."""
    ticker = _to_ticker(company)
    if company and ticker is None:
        # Company given but unknown — return a clear, citable-as-non-fact note
        # rather than silently filtering to nothing.
        return [
            {
                "id": "NO-MATCH-COMPANY",
                "text": (
                    f"No known company matched {company!r}. The corpus covers only "
                    f"TSLA, AAPL, NVDA — no search was run."
                ),
                "company": company,
                "section": "-",
                "filing_date": "-",
                "source_url": "-",
                "score": 0.0,
            }
        ]
    _ensure()
    rows = _stack.retrieve(question=query, k=k, company=ticker)
    return [_map_row(r) for r in rows]


def _describe(company: str) -> dict[str, Any]:
    """Real describe_filing: identity + distinct sections for the one 10-K.

    Reads metadata directly from the collection (a where-filtered get, no
    embedding) so it does NOT trigger a second embedder load.
    """
    ticker = _to_ticker(company)
    if ticker is None:
        return {
            "company_name": None,
            "ticker": None,
            "filing_date": None,
            "source_url": None,
            "sections": [],
            "note": f"Unknown company {company!r}. Corpus is TSLA/AAPL/NVDA only.",
        }
    _ensure()
    # Metadata-only read for this ticker — no query vector needed.
    raw = _store._collection.get(where={"ticker": ticker}, include=["metadatas"])
    metas = raw.get("metadatas") or []
    if not metas:
        return {
            "company_name": None,
            "ticker": ticker,
            "filing_date": None,
            "source_url": None,
            "sections": [],
            "note": f"No filing indexed for {ticker}.",
        }
    first = metas[0]
    sections = sorted({m.get("section") for m in metas if m.get("section")})
    return {
        "company_name": first.get("company_name"),
        "ticker": ticker,
        "filing_date": first.get("filing_date"),
        "source_url": first.get("source_url"),
        "sections": sections,
    }


def bind_real_retriever() -> None:
    """Wire the real search/describe callables into tools.py.

    Call this before running the agent against the real corpus. Tests that don't
    call it keep using the stubs in tools.py.
    """
    _ensure()
    from filing_agent import tools

    tools.bind_retriever(_search, _describe)
