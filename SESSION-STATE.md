# Session State — module-03-agents-app

> Paste this file at the start of the next session to resume. Say: *"continue module-03-agents-app — read SESSION-STATE.md"*.

## ⏱ Catch-up recap — READ THIS FIRST (per CLAUDE.md Rule 7)

> On resume, summarize the per-task list below (1–2 sentences each), then state the single next step.

**Session 1 (ended 2026-06-05) — what we did, per task:**
1. **Docs scaffold** — created `CLAUDE.md`, `SESSION-STATE.md`, `WHY.md` (skeleton), `notes/README.md`, all adapted from Module 02's conventions and the agent project's needs.
2. **Progress tracker** — added a per-stage *concepts → tasks → status* tracker to `SESSION-STATE.md` (legend: ⬜ todo · 🔄 in-progress · ✅ done · 🚧 blocked), each task tied to a prompt in `project-build-prompts.md`.
3. **Stage 0 — Scaffold (✅ done)** — repo skeleton (venv, pinned deps `anthropic 0.106`/`langgraph 1.2.4`/`python-dotenv 1.2.2`, `filing_agent/`, `.env.example`, `.gitignore`, README); built `filing_agent/llm.py` (`get_client` + raw-response `call_model`) and `scripts/smoke_test.py`; smoke test passed — Sonnet 4.6 replied "OK".
4. **Stage 1 whiteboard (✅ done)** — designed the model↔tools loop on paper and captured it in `notes/agent-loop-notes.md`; locked two decisions: Anthropic-native message dicts (no LangChain message objects) + a minimal system prompt in `model_node`.

**Single next step:** Begin **Stage 1, Prompt 1.1** — write `filing_agent/tools.py`: the 3 tools (`search_filings`, `lookup_filing`, `compare_numbers`) + `TOOL_SCHEMAS`, with retrieval *stubbed* and `compare_numbers` fully real. The 🛑 there is about tool-*description* quality (the model picks tools from descriptions alone).

## Where we are

Building a **"Filing Analyst Agent"** over SEC 10-K / 8-K filings as an explicit **LangGraph state machine** (per `project-build-prompts.md`). It evolves the Module 02 RAG pipeline from a single-pass retriever into a multi-step agent. Sequential, stage-by-stage build with a 🛑 pause for review after each step.

**Win condition:** I can diagram the agent's control flow from memory — every node, every edge, the condition on each edge.

## Confirmed decisions (durable)

- **Orchestration:** LangGraph `StateGraph`, control flow EXPLICIT as hand-built nodes + conditional edges. **No `create_react_agent` / `AgentExecutor`.**
- **LLM provider:** Anthropic Claude API (`anthropic` SDK). Model via env var `ANTHROPIC_MODEL`, default to a current Claude string (TBD at Stage 0).
- **Package name:** `filing_agent/`.
- **Module 02 retrieval:** a **bound dependency**, called through a thin tool wrapper (`search_filings` / `lookup_filing`) — not rewritten. Stubbed behind a thin interface until the real import path is bound (Prompt 1.6).
- **Python:** 3.11+, venv, deps pinned, added per stage (not all up front).
- **Scope:** Stages 1–2 committed; Stages 3 (MCP) and 4 (multi-agent) are extensions, built only after earlier stages are solid.
- **Message format (Stage 1):** store raw **Anthropic-format message dicts** (`{role, content}`) with an add-reducer — NOT LangChain message objects. Avoids hidden conversions; keeps the transcript legible.
- **System prompt (Stage 1):** `model_node` includes a minimal system prompt ("analyze SEC filings; always ground via tools; don't guess") to make the agent loop rather than free-associate.

## Stage tracker (concepts → tasks → status)

**Status legend:** ⬜ todo · 🔄 in-progress · ✅ done · 🚧 blocked (note why)

Each task maps to a prompt in `project-build-prompts.md`. Mark blocked tasks with a one-line reason so we don't lose anything we couldn't solve.

| Stage | Status |
|---|---|
| Docs scaffold (`CLAUDE.md`, `SESSION-STATE.md`, `WHY.md`, `notes/`) | ✅ done |
| Stage 0 — Scaffold | ✅ done (smoke test passed: Sonnet 4.6 replied "OK") |
| Stage 1 — Comparison Agent | 🔄 next |
| Stage 2 — Reflection | ⬜ todo |
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
| Define 3 tools (`search_filings`, `lookup_filing`, `compare_numbers`) + `TOOL_SCHEMAS`; retrieval stubbed | 1.1 | ⬜ |
| `executor.py` `run_tool` (unknown tool + raising tool handled) + `tests/test_executor.py` | 1.2 | ⬜ |
| `state.py` (`AgentState`) + `nodes.py` (`model_node`, `tools_node`) | 1.3 | ⬜ |
| `graph.py` StateGraph + `should_continue` + `scripts/run_agent.py` | 1.4 | ⬜ |
| `scripts/draw_graph.py` → `docs/graph-stage1.mmd` (win-condition diagram check) | 1.5 | ⬜ |
| Bind real Module 02 retriever (replace stub; keep stub behind a flag) | 1.6 | ⬜ |

### Stage 2 — Reflection (the self-check node)
**Concepts:** reflection as a *node*, not a prompt trick; the revision loop; groundedness (claim → chunk); graceful give-up (flag-as-unverified).
| Task | Prompt | Status |
|---|---|---|
| `reflect_node` + JSON verdict parsing; new state fields | 2.1 | ⬜ |
| Rewire graph: model→reflect, `should_revise`, `docs/graph-stage2.mmd` | 2.2 | ⬜ |

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
