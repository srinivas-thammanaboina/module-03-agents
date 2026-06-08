# Session State — module-03-agents-app

> Paste this file at the start of the next session to resume. Say: *"continue module-03-agents-app — read SESSION-STATE.md"*.

## ⏱ Catch-up recap — READ THIS FIRST (per CLAUDE.md Rule 7)

> On resume, summarize the per-task list below (1–2 sentences each), then state the single next step.

**Session 3 (ended 2026-06-07) — what we did, per task:**
1. **Stage 2 — Reflection (✅)** — whiteboarded then built the `reflect` node + revision loop (two-loop graph): a deterministic citation audit (mirrors M02 `_audit_citations`) AND an LLM groundedness check, pass only if both. New state fields + `executor` now returns `ToolResult(content, retrieved_ids)`. Verified: normal Q passes (0 revisions); a forced fake citation is caught by BOTH checks. `docs/graph-stage2.mmd` exported.
2. **Rule 8 — "I run it, not you" (✅)** — added to CLAUDE.md + strengthened memory: after code changes I hand over exact commands, the USER runs and pastes output, we analyze together; nothing marked verified until the user's output is in. User then re-ran Stage 2 themselves to confirm.
3. **Stage 3 — MCP live market data (✅, extension)** — whiteboarded (4 decisions), then built `prices.py` (Yahoo source; Stooq was JS-anti-bot-walled) → `mcp_server.py` (FastMCP/stdio) → `market.py` (our MCP client) → registered `get_stock_price` in the toolset (lazy dispatch). Verified real cross-source run: `describe_filing → search_filings → get_stock_price×2 → compare_numbers`, answer grounded with BOTH chunk-ids and `MKT-` ids, reflection passed. Graph shape unchanged (tool, not node).
4. **Mid-session phone reminders (✅)** — user confirmed they want phone nudges mid-session too; added `breakReminder` (every 30 min) to `~/.claude/settings.json` alongside the existing `SessionStart` hook; updated the phone-focus memory.

**Single next step:** Two small things: (a) **confirm `pytest`** — user to run `.venv/bin/python -m pytest -q` (expect 4 passed) to sign off that Stage 3's lazy dispatch didn't break unit tests (was not pasted yet). Then (b) **decide Stage 4 (Multi-agent / A2A)** — the last, most ambitious extension (orchestrator decomposes a cross-company question → delegates to reusable analyst copies → synthesizes/ranks). Per Rule 1, whiteboard Stage 4 before any code. Prompts 4.1 → 4.2 in `project-build-prompts-v2.md`. Stopping after Stage 3 is also a clean milestone.

> _Earlier: Session 1 (2026-06-05) scaffolded docs + Stage 0 + Stage 1 whiteboard; Session 2 (2026-06-06) adopted the v2 build prompts and built all of Stage 1 against the real Module 02 corpus._

## Where we are

Building a **"Filing Analyst Agent"** over SEC 10-K filings as an explicit **LangGraph state machine** (per `project-build-prompts-v2.md`). It evolves the Module 02 RAG pipeline from a single-pass retriever into a multi-step agent. Sequential, stage-by-stage build with a 🛑 pause for review after each step.

**Win condition:** I can diagram the agent's control flow from memory — every node, every edge, the condition on each edge.

## Confirmed decisions (durable)

- **Orchestration:** LangGraph `StateGraph`, control flow EXPLICIT as hand-built nodes + conditional edges. **No `create_react_agent` / `AgentExecutor`.**
- **LLM provider:** Anthropic Claude API (`anthropic` SDK). Model via env var `ANTHROPIC_MODEL`, default to a current Claude string (TBD at Stage 0).
- **Package name:** `filing_agent/`.
- **Module 02 retrieval:** a **bound dependency**, called through a thin tool wrapper (`search_filings` / `describe_filing`) — not rewritten. Bind the **composed production stack** `Expand(Decomposition(Hybrid(Retriever(store))))` (each layer exposes `.retrieve(question, k, company)`), not a bare `Retriever`. Stubbed behind `bind_retriever` until the real import is wired (Prompt 1.6).
- **Corpus ground truth (from v2):** latest **10-K only**, **TSLA/AAPL/NVDA only**, **one year** each (~678 chunks). No 8-Ks, no multi-year. YoY is **within one 10-K**. Retrieval filters by **ticker only** (names→tickers). Each chunk's **`id`** is the citation token and must flow end to end. **Never send `temperature`** (Opus 4.x rejects it).
- **Python:** 3.11+, venv, deps pinned, added per stage (not all up front).
- **Scope:** Stages 1–2 committed; Stages 3 (MCP) and 4 (multi-agent) are extensions, built only after earlier stages are solid.
- **Message format (Stage 1):** store raw **Anthropic-format message dicts** (`{role, content}`) with an add-reducer — NOT LangChain message objects. Avoids hidden conversions; keeps the transcript legible.
- **System prompt (Stage 1):** `model_node` includes a minimal system prompt ("analyze SEC filings; always ground via tools; don't guess") to make the agent loop rather than free-associate.

## Stage tracker (concepts → tasks → status)

**Status legend:** ⬜ todo · 🔄 in-progress · ✅ done · 🚧 blocked (note why)

Each task maps to a prompt in `project-build-prompts-v2.md`. Mark blocked tasks with a one-line reason so we don't lose anything we couldn't solve.

| Stage | Status |
|---|---|
| Docs scaffold (`CLAUDE.md`, `SESSION-STATE.md`, `WHY.md`, `notes/`) | ✅ done |
| Stage 0 — Scaffold | ✅ done (smoke test passed: Sonnet 4.6 replied "OK") |
| Stage 1 — Comparison Agent | ✅ done (real run: `search_filings → compare_numbers`, grounded answer with chunk-id citations; TSLA revenue −2.93% computed by the tool) |
| Stage 2 — Reflection | ✅ done (reflect node + revision loop; deterministic citation audit + LLM groundedness; verified normal-pass and forced-hallucination-caught) |
| Stage 3 — MCP external tool | ✅ done (live market data via local MCP server+client; cross-source reasoning verified, both citation schemes grounded, reflection passed) |
| Stage 4 — Multi-agent | ⬜ todo (extension) |

### Stage 0 — Scaffold
**Concepts:** project plumbing; Anthropic client config; env loading; "prove the pipe works before any graph logic."
| Task | Prompt | Status |
|---|---|---|
| Repo skeleton — venv, pinned deps, `filing_agent/`, `.env.example`, `.gitignore`, README stub | 0.1 | ✅ (anthropic 0.106, langgraph 1.2.4, python-dotenv 1.2.2; imports verified) |
| `llm.py` (`get_client`, `call_model`) + `scripts/smoke_test.py` (one real Claude call) | 0.2 | ✅ (reply "OK", stop_reason end_turn) |

### Stage 1 — Comparison Agent (the loop + tools)
**Concepts:** model-in-a-loop (the model owns the order of operations); tool schemas & *description quality*; tool dispatch + error handling; TypedDict state + add-reducer; conditional edges; the turn cap as a safety rail; binding a real dependency.
| Task | Prompt | Status |
|---|---|---|
| Define 3 tools (`search_filings`, `describe_filing`, `compare_numbers`) + `TOOL_SCHEMAS`; retrieval stubbed | 1.1 | ✅ (`tools.py`, **v2**: no year/form_type, stub chunks carry `id`, `describe_filing` returns identity+sections; `compare_numbers` real) — at 🛑: review schema descriptions |
| `executor.py` `run_tool` (unknown tool + raising tool handled) + `tests/test_executor.py` | 1.2 | ✅ (4/4 tests pass; chunk `id` leads each serialized line; unknown/raising tools return readable ERROR strings, never crash; pytest pinned, root `conftest.py` added) |
| `state.py` (`AgentState`) + `nodes.py` (`model_node`, `tools_node`) | 1.3 | ✅ (add-reducer = `operator.add`; system prompt states single-filing reality; `_tool_uses` helper shared; `call_model` gained `system=`) |
| `graph.py` StateGraph + `should_continue` + `scripts/run_agent.py` | 1.4 | ✅ (loop verified live: `describe_filing → search_filings → answer`, 2 turns, exited on its own; agent correctly refused to fabricate on stub data) |
| `scripts/draw_graph.py` → `docs/graph-stage1.mmd` (win-condition diagram check) | 1.5 | ✅ (mermaid matches hand-drawn graph: `model` dotted→`tools`/`END`, `tools`→`model` solid loop-back) |
| Bind real Module 02 retriever (replace stub; keep stub behind a flag) | 1.6 | ✅ (`filing_agent/retrieval.py`: imports M02 composed stack via `MODULE_02_PATH`+sys.path; embedder/store/stack built once; names→tickers; chunk `id` preserved; `run_agent.py --stub` keeps tests on stubs. Deps pinned to M02: torch 2.12.0 / s-t 5.5.1 / chromadb 1.5.9 / numpy 2.4.6) |

### Stage 2 — Reflection (the self-check node)
**Concepts:** reflection as a *node*, not a prompt trick; the revision loop; groundedness (claim → chunk); graceful give-up (flag-as-unverified).
| Task | Prompt | Status |
|---|---|---|
| `reflect_node` + JSON verdict parsing; new state fields | 2.1 | ✅ (state +`retrieved_ids`/`draft_answer`/`reflection_passed`/`revision_count`; `executor` now returns `ToolResult(content, retrieved_ids)`; reflect = deterministic citation audit (mirrors M02 `_CITATION_RE`/`_audit_citations`) AND LLM groundedness check, pass only if both; fail→critique+`revision_count`+1; `REVISION_CAP=2`. Deterministic half verified offline; tests 4/4) |
| Rewire graph: model→reflect, `should_revise`, `docs/graph-stage2.mmd` | 2.2 | ✅ (two-loop graph: `should_continue` no-tool→`reflect`; `should_revise` pass→END / fail&under cap→model / else→END flagged unverified; diagram exported. Verified: normal Q passes reflection (0 revisions); forced fake citation caught by BOTH deterministic audit + LLM check → revision loop) |

### Stage 3 — External tool via MCP (extension)
**Concepts:** MCP host/client/server; a tool adds capability without changing graph shape; reasoning across a private corpus + a public live source.
| Task | Prompt | Status |
|---|---|---|
| Scope MCP: existing public server vs. minimal local one (decide source) | 3.1 | ✅ (4 decisions: own client+dispatch; local server; `get_stock_price(ticker,date)`; unified `MKT-` citation id. Captured in `notes/mcp-notes.md`) |
| Wire the market-data MCP tool into the tool set (graph shape unchanged) | 3.2 | ✅ (`prices.py` Yahoo source [Stooq was JS-walled] → `mcp_server.py` FastMCP/stdio → `market.py` client → registered in `TOOL_SCHEMAS`+`run_tool` (lazy). Real cross-source run: `describe_filing→search_filings→get_stock_price×2→compare_numbers`, both chunk-id + `MKT-` citations, reflection passed ✓) |

### Stage 4 — Multi-agent (extension)
**Concepts:** A2A-style delegation; why the analyst must be stateless to parallelize; decompose → delegate → synthesize.
| Task | Prompt | Status |
|---|---|---|
| Make the Stage 1–3 graph a reusable, stateless `analyst` + capability descriptor | 4.1 | ⬜ |
| Orchestrator graph (`decompose`/`delegate`/`synthesize`) + `docs/graph-stage4.mmd` | 4.2 | ⬜ |

## Open questions / to decide

- **`ANTHROPIC_MODEL` default** — which Claude string to pin for Stage 0.
- **Prompts development plan** — how to sequence/adapt the build prompts into our working cadence (the user's stated next task).
- **MCP data source** (Stage 3) — existing public MCP server vs. a minimal local one over a free price API (decided at Prompt 3.1).

## Notes / docs status

- `CLAUDE.md` — working agreement, adapted from Module 02. **done.**
- `WHY.md` — skeleton; cross-cutting principles seeded, per-stage rationale fills in as we build.
- `notes/` — convention guide in place; per-stage notes created during each stage's whiteboard.
