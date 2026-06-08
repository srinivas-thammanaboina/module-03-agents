# Session State — module-03-agents-app

> Paste this file at the start of the next session to resume. Say: *"continue module-03-agents-app — read SESSION-STATE.md"*.

## ⏱ Catch-up recap — READ THIS FIRST (per CLAUDE.md Rule 7)

> On resume, summarize the per-task list below (1–2 sentences each), then state the single next step.

**Session 2 (ended 2026-06-06) — what we did, per task:**
1. **Phone-focus reminder hook** — added a global `SessionStart` hook in `~/.claude/settings.json` so every Claude session opens with "📵 Step 0: Keep your mobile far away." Saved the preference to memory too, so it carries across modules.
2. **Adopted v2 build prompts** — switched the source of truth to `project-build-prompts-v2.md` (v1 assumed a corpus that doesn't exist) and swept every project doc for stale v1 references (10-K only; `describe_filing`; chunk-`id`; never send `temperature`).
3. **Stage 1 Prompts 1.1–1.5 (✅)** — built `tools.py` (3 tools + schemas, v2 shapes), `executor.py` + 4 passing tests (chunk `id` survives, errors return strings), `state.py`/`nodes.py` (add-reducer + system prompt), `graph.py` + `run_agent.py` (loop verified live), and `draw_graph.py` → `docs/graph-stage1.mmd` (matches the hand-drawn graph).
4. **Stage 1 Prompt 1.6 — real retriever bound (✅)** — `filing_agent/retrieval.py` imports Module 02's composed stack via `MODULE_02_PATH`, builds the embedder/store/stack once, normalizes names→tickers, preserves chunk `id`. Pinned retrieval deps to M02's exact versions. End-to-end real run worked: `search_filings → compare_numbers`, grounded answer citing chunk ids, TSLA revenue −2.93%.
5. **Stage 1 COMPLETE** — captured notes (`agent-loop-notes.md`, `tools-notes.md` sanity-checks filled with the real runs); the committed core of the module is done.

**Single next step:** **Stage 2 — Reflection.** Per Rule 1, **whiteboard first** (don't write code): design the `reflect` node + the *revision loop* (a second loop atop the tool loop) — a deterministic citation audit (mirror Module 02's `_audit_citations`: every cited id must be one actually retrieved) PLUS an LLM groundedness check; then capture it in `notes/reflection-notes.md` before any code. Prompts 2.1 → 2.2 in `project-build-prompts-v2.md`.

> _Session 1 (ended 2026-06-05): scaffolded the docs/working-agreement layer, the progress tracker, Stage 0 (smoke test passed), and the Stage 1 whiteboard. Full Stage-1 build happened in Session 2 above._

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
| Stage 3 — MCP external tool | ⬜ todo (extension) |
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
| Scope MCP: existing public server vs. minimal local one (decide source) | 3.1 | ⬜ |
| Wire the market-data MCP tool into the tool set (graph shape unchanged) | 3.2 | ⬜ |

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
