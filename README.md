# Filing Analyst Agent (module-03-agents-app)

A multi-step agent over SEC 10-K filings, built as an **explicit LangGraph state machine** that plans, calls tools, checks its own grounding, reaches a live external source over MCP, and delegates cross-company work to reusable sub-agents. It evolves the Module 02 RAG pipeline (the "Filing Analyst Copilot") from a single-pass retriever into an agent whose control flow you can diagram from memory.

**Corpus:** the latest 10-K for exactly three companies — **TSLA, AAPL, NVDA** (one filing each; no 8-Ks, no other years). Year-over-year comparisons are made *within* a single 10-K. See `project-build-prompts-v2.md` for the full ground truth.

## What it does (the four stages)

| Stage | Capability | Key idea |
|---|---|---|
| **1 — Comparison Agent** | a `model ↔ tools` loop: `search_filings`, `describe_filing`, `compare_numbers`, bound to Module 02's real retriever | the *model* decides the order of operations |
| **2 — Reflection** | a `reflect` node + revision loop: deterministic citation audit **and** LLM groundedness check | grounding is a *gate*, not a prompt wish |
| **3 — MCP market data** | `get_stock_price` via a local MCP server/client (live Yahoo prices) | external capability = a *tool*, not a node; reason across private filings + public live data |
| **4 — Multi-agent (A2A)** | an orchestrator (`decompose → delegate → synthesize`) delegating per-company tasks to reusable **analyst** copies, then ranking | multi-agent only when sub-tasks differ in kind |

Every claim the agent makes carries a citation id — filing chunks (`TSLA-2026-01-29-0061`) or live data (`MKT-TSLA-2026-01-29`) — and those are audited.

## Architecture — two graphs

```
  ANALYST (Stages 1–3)                 ORCHESTRATOR (Stage 4)
  model ↔ tools ↔ reflect              decompose → delegate → synthesize → END
  (two loops: tool + revision)         (linear; delegate runs one analyst per company)
```

Diagrams: `docs/graph-stage1.mmd`, `graph-stage2.mmd`, `graph-stage4.mmd` (regenerate with the `scripts/draw_*.py`).

Design rationale lives in `WHY.md`; per-stage notes in `notes/*.md`; current status in `SESSION-STATE.md`.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in ANTHROPIC_API_KEY (ANTHROPIC_MODEL defaults to claude-sonnet-4-6)
```

**Dependency on Module 02:** retrieval imports Module 02's composed stack from `../module-02-rag-app` (override with `MODULE_02_PATH`). That repo must have its Chroma index built and its deps available. The retrieval deps here are pinned to match Module 02's exact versions so query embeddings match the index.

## Run it

```bash
# unit tests (tool executor)
.venv/bin/python -m pytest -q

# single-company agent (Stages 1–3) — prints the tool sequence + reflection verdict
.venv/bin/python scripts/run_agent.py "In Tesla's latest 10-K, did total revenue grow vs the prior year? Cite chunks."

# cross-company orchestrator (Stage 4) — decompose → delegate → synthesize, with rankings
.venv/bin/python scripts/run_orchestrator.py "Compare AI risks across TSLA, AAPL, NVDA and rank by revenue growth. Cite chunks."

# export the graph diagrams
.venv/bin/python scripts/draw_graph.py          # analyst → docs/graph-stage2.mmd
.venv/bin/python scripts/draw_orchestrator.py   # orchestrator → docs/graph-stage4.mmd
```

Pass `--stub` to `run_agent.py` to use stub retrieval (no corpus needed).

## Layout

```
filing_agent/
  llm.py          Anthropic client + call_model
  tools.py        the 4 tool functions + TOOL_SCHEMAS
  executor.py     run_tool dispatch (returns content + retrieved ids)
  state.py        AgentState (messages, turn_count, reflection fields)
  nodes.py        model_node, tools_node, reflect_node + system prompt
  graph.py        the analyst StateGraph (Stages 1–2)
  retrieval.py    binds Module 02's composed retriever
  prices.py       live price source (Yahoo, no key)
  mcp_server.py   FastMCP server exposing get_stock_price
  market.py       our MCP client → unified chunk shape with MKT- ids
  analyst.py      run_analyst() + AGENT_CARD (Stage 4 specialist)
  orchestrator.py decompose/delegate/synthesize graph (Stage 4)
scripts/          run_agent, run_orchestrator, draw_graph, draw_orchestrator, diagnose_analyst, smoke_test
tests/            test_executor.py
```
