# Filing Analyst Agent (module-03-agents-app)

A multi-step agent over SEC 10-K filings, built as an explicit LangGraph state machine that plans, calls tools, and checks its own work. It evolves the Module 02 RAG pipeline (the "Filing Analyst Copilot") from a single-pass retriever into an agent whose control flow you can diagram from memory. The corpus is the latest 10-K for TSLA, AAPL, and NVDA (one filing each).

## Staged plan

- **Stage 0 — Scaffold:** clean repo + a working Claude API call (smoke test).
- **Stage 1 — Comparison Agent:** the loop + tools — a `model` node, a `tools` node, and a conditional edge that loops until the model stops asking for tools.
- **Stage 2 — Reflection:** a self-check node that verifies every claim is grounded in a retrieved chunk, with a revision loop.
- **Stage 3 — External tool via MCP:** a live market-data tool the filings can't contain, so the agent reasons across a private corpus and a public live source.
- **Stage 4 — Multi-agent:** an orchestrator delegates per-company sub-tasks to reusable copies of the Stage 1–3 analyst (A2A-style), then synthesizes and ranks.

See `project-build-prompts-v2.md` for the full brief and build prompts (the source of truth; v1 is superseded), and `SESSION-STATE.md` for current status.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # then fill in your ANTHROPIC_API_KEY
```
