# Session State — module-03-agents-app

> Paste this file at the start of the next session to resume. Say: *"continue module-03-agents-app — read SESSION-STATE.md"*.

## ⏱ Catch-up recap — READ THIS FIRST (per CLAUDE.md Rule 7)

> On resume, summarize the per-task list below (1–2 sentences each), then state the single next step.

**🏁 PROJECT COMPLETE — all stages 0–4 built and verified.**

**Session 4 (ended 2026-06-08) — what we did, per task:**
1. **Stage 4 whiteboard (A2A) (✅)** — designed orchestrator + reusable analyst; 5 decisions locked (own analyst fn + Agent Card; orchestrator as its own LangGraph; sequential delegation; union citation audit; restrict to TSLA/AAPL/NVDA). Captured in `notes/multi-agent-notes.md`.
2. **Prompt 4.1 — reusable analyst (✅)** — `analyst.py`: `run_analyst(company, question)` reuses the compiled graph with fresh state, ticker-scoped; `AGENT_CARD`. Isolation verified (TSLA cites only TSLA, NVDA only NVDA, both pass).
3. **Prompt 4.2 — orchestrator (✅)** — `orchestrator.py` linear graph `decompose → delegate → synthesize`; union citation audit; `docs/graph-stage4.mmd`. Cross-company run ranked NVDA>AAPL>TSLA, citations intact.
4. **AAPL-FAIL diagnosis (✅)** — `scripts/diagnose_analyst.py` revealed reflection caught 3 *legitimate* over-claims (invented taxonomy, selective framing, misattributed citation), not fake ids. Validated surfacing unverified answers.
5. **Polish + fixes (✅)** — (option 1) orchestrator surfaces unverified sub-answers; (option 3) reflect-the-synthesis groundedness check — caught a real fabrication; **root-cause fix `DEFAULT_MAX_TOKENS` 1024→4096** (answers were truncating → spurious FAILs + synthesis fabrication, both resolved); quieted HF/FutureWarning noise; rewrote `README.md` for the finished agent. Final run: all answers complete, synthesis groundedness ✓, union audit clean, weak analyst correctly flagged unverified.

**Single next step:** **None required — project is done.** Optional future experiments are logged in `notes/multi-agent-notes.md` (analyst over-claiming on rich answers; revision-loop/reflect-staleness; parallel delegation; quote-or-qualify analyst prompt). Module 03 is complete; next would be Module 04 (finetuning).

> _Earlier: S1 (2026-06-05) docs + Stage 0 + Stage 1 whiteboard; S2 (2026-06-06) adopted v2 prompts, built Stage 1 on the real corpus; S3 (2026-06-07) built Stage 2 (reflection) + Stage 3 (MCP), added Rule 8 + mid-session phone reminders._

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
| Stage 4 — Multi-agent | ✅ done (orchestrator delegates to reusable analyst specialists, ranks, audits citations, surfaces unverified answers) — **PROJECT COMPLETE: all stages 0–4 done** |

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
| Make the Stage 1–3 graph a reusable, stateless `analyst` + capability descriptor | 4.1 | ✅ (`analyst.py`: `run_analyst(company,question)` reuses the compiled graph, fresh state, ticker-scoped; `AGENT_CARD`. Isolation verified: TSLA cites only TSLA, NVDA only NVDA, both pass) |
| Orchestrator graph (`decompose`/`delegate`/`synthesize`) + `docs/graph-stage4.mmd` | 4.2 | ✅ (`orchestrator.py` linear graph; restricts to TSLA/AAPL/NVDA; sequential delegate; union citation audit; **surfaces unverified sub-answers** [option 1]. Real run: 3 tasks, ranked NVDA>AAPL>TSLA, audit clean. AAPL-FAIL diagnosed → 3 legit over-claims; logged as future experiments) |

## Open questions / to decide

- **`ANTHROPIC_MODEL` default** — which Claude string to pin for Stage 0.
- **Prompts development plan** — how to sequence/adapt the build prompts into our working cadence (the user's stated next task).
- **MCP data source** (Stage 3) — existing public MCP server vs. a minimal local one over a free price API (decided at Prompt 3.1).

## Notes / docs status

- `CLAUDE.md` — working agreement, adapted from Module 02. **done.**
- `WHY.md` — skeleton; cross-cutting principles seeded, per-stage rationale fills in as we build.
- `notes/` — convention guide in place; per-stage notes created during each stage's whiteboard.
