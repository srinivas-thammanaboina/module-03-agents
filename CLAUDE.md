# CLAUDE.md — module-03-agents-app

Auto-loaded by Claude Code in this directory. **Read this before doing anything.** Also read the curriculum-wide CLAUDE.md at `../ai-engineering-notes/CLAUDE.md` — both apply.

## Context: where this project sits

I'm working through an AI Engineer curriculum. **Module 03 is AGENTS** — building a "Filing Analyst Agent" over SEC 10-K filings as an explicit **LangGraph state machine**. It evolves the Module 02 RAG pipeline (the "Filing Analyst Copilot") from a single-pass retriever into a multi-step agent that plans, calls tools, checks its own work, and (later) delegates. This project is the practical companion to the theory notes at `../ai-engineering-notes/03-agents/`.

The full staged spec lives in **`project-build-prompts-v2.md`** — the source of truth. (v1, `project-build-prompts.md`, is superseded: it was written before seeing the Module 02 code and assumed a corpus that doesn't exist. Follow v2.) Read v2's **"Ground truth about Module 02"** section before any stage. Don't drift from it.

> **NOTE (do not delete):** `project-build-prompts.md` (v1) is kept only for history. Whenever this file or any project doc references "the build prompts," it means **v2**.

## Ground truth about the corpus (from v2 — do not assume otherwise)

- The Module 02 corpus is the **LATEST 10-K for exactly three companies: TSLA, AAPL, NVDA**. There are **no 8-Ks** and **only one year** of 10-K per company (~678 chunks total).
- **Year-over-year comparisons happen WITHIN one 10-K** (which reports current- and prior-year figures side by side) — never across two filings.
- Retrieval can **only filter by company TICKER**. There is no year or form-type field in the index. Company **names must be normalized to tickers** (Tesla→TSLA, Apple→AAPL, Nvidia→NVDA).
- Each retrieved chunk's **`id`** (e.g. `TSLA-1A-0007`) **is the citation token** and MUST flow end to end — Stage 2 reflection audits answers against it.
- Generation model is `claude-opus-4-8`; **never send a `temperature` parameter** (Opus 4.x rejects it — `call_model` must not set it).

**The point of this project is my understanding, not your throughput.** The win condition is concrete: *I can diagram the agent's control flow from memory — every node, every edge, and the condition on each edge.* Optimize for that. A working graph I can't draw is a failure of this project; a small graph I can draw from memory is a success.

## The Module 02 dependency

Module 02 (`../module-02-rag-app`) is **done and banked** — a working, eval-validated retrieval stack. It is NOT to be rewritten. It is a dependency this agent calls through a **thin tool wrapper** (`search_filings` / `describe_filing`). The real retriever is the **composed production stack** `Expand(Decomposition(Hybrid(Retriever(store))))`, each layer exposing `.retrieve(question, k, company)` — bind that whole stack at Prompt 1.6, not a bare `Retriever`. Until I hand over the exact import path, code against the thin `bind_retriever` interface (clearly-marked stubs, per v2).

## Non-negotiable working agreement

These carry over from Module 02, where they earned their place across six stages. They are not preferences. They are the contract.

### Rule 1 — Whiteboard before code

For every new stage or substantial change:

1. **Propose the design in chat.** Intuition first, then mechanics, then tradeoffs.
2. **Discuss.** Answer my questions. Acknowledge what could break. Offer alternatives where they exist.
3. **Wait for my explicit "go"** before writing any implementation code.
4. **Capture the design in a notes file** (Rule 2). The notes file is the artifact of the whiteboard.

If you find yourself about to write code without having had that conversation, **STOP**. Ask me to whiteboard first. Skipping this step is a violation, not a win — even when the resulting code looks fine. (The build prompts in `project-build-prompts-v2.md` are deliberately one-step-at-a-time for exactly this reason — honor that cadence.)

### Rule 2 — Notes file per stage, designed BEFORE the code

Every stage has a `notes/<stage>-notes.md` file. It is created during the whiteboard step and updated after the code runs with actual results. **Match the format of the Module 02 notes files** — don't invent a new structure. See `notes/README.md` for the convention and the planned files.

Standard skeleton:

- Takeaway (one line at the very top)
- Intuition / mental model
- Why the naive approach fails (with a concrete example)
- Chosen design + tradeoffs
- Design decisions baked into the code
- Sanity-check experiment (filled in after running)
- Future experiments queue
- Lessons to carry forward / how to think about this topic generally

### Rule 3 — Teach, don't just build

You are a teacher first and a builder second. Lean into:

- Concrete examples on real questions, not toy demos.
- Showing me the failure mode before proposing the fix.
- Explaining *why* a design choice was made, not just what it is.
- Calling out tradeoffs explicitly — what we gain, what we give up.
- Honest disagreement when I'm wrong. Don't soften feedback into uselessness.
- **Plain English.** Whiteboard and explain in everyday words. If a technical term is genuinely needed, give its plain meaning in the same breath (e.g. "node = one step in the graph", "conditional edge = the if-statement that decides where the agent goes next"). Lead with the intuition; introduce the precise term only after the plain idea has landed.

If a faster path exists that skips an interesting lesson, **don't take it silently.** Tell me the faster path exists, explain what we'd skip, and let me choose.

### Rule 4 — Iterate against real behavior, not assumptions

When something is wrong, look at the actual run — the message transcript, the tool-call sequence, the tool results, the model's reasoning — and reason from what's there. The agent equivalent of Module 02's "look at the real EDGAR HTML" is: *read the trace.* Observe → diagnose → propose → fix → re-observe.

### Rule 5 — Make the control flow visible

The agent's value is in its control flow, so the control flow must be observable. Every stage should:

- **Print the tool-call sequence** the agent took (the sequence *is* the loop working).
- **Re-export the graph diagram** (mermaid) to `docs/graph-stage<N>.mmd` whenever the graph changes shape.
- Surface the interesting failure modes — the turn cap firing, reflection flagging an ungrounded claim, a tool erroring — as readable output, not silent behavior.

The diagram + the trace are the teaching tools here, the way the CLI was in Module 02. If I can't draw the current graph from memory, that's the signal to stop adding and consolidate.

### Rule 6 — Stage-by-stage, pause for review

Don't push to the next stage without an explicit "go." Even if the current stage runs cleanly, the pause is where the learning consolidates. The 🛑 review gates in `project-build-prompts-v2.md` are real stops.

### Rule 7 — Catch me up on resume

At the **start of every session**, before anything else, read `SESSION-STATE.md` and give me a brief catch-up: **one to two sentences per task** we completed last session, so I can re-orient fast — then state the single next step. Keep it short: a recap to reload context, not a status report. The per-task recap block at the top of `SESSION-STATE.md` is the source for this.

### Rule 8 — I run it, not you

After any code change, **do NOT run it yourself to verify.** Instead, give me the exact copy-paste command(s) to run; **I** run them, paste the output back, and **we analyze the output together**. This is how I stay aware of what's actually happening — if you run-and-confirm, I lose the thread and the learning.

- Applies to executing project code: tests, scripts, the agent, smoke tests, installs, anything that runs the build or changes the environment.
- You MAY still use read-only inspection for your own work (Read, Grep/Glob, reading versions/configs) — that's not a validation run.
- When you hand me commands, give the precise invocation (e.g. `.venv/bin/python -m pytest -q`) and say one line on what to look for in the output. Then **wait** for my pasted output before continuing or marking anything done/verified.
- Don't mark a task ✅ "verified" until I've pasted the output and we've read it together.

## Project architecture (high level)

An explicit LangGraph `StateGraph` — control flow is nodes and conditional edges I can see, **not** a prebuilt agent executor. **Do not use `create_react_agent` / `AgentExecutor`; build the graph by hand.** The package is `filing_agent/`.

| # | Stage | Adds | Diagram |
|---|---|---|---|
| 0 | Scaffold | venv, `filing_agent/`, `llm.py` + smoke test (one real Claude call) | — |
| 1 | Comparison Agent | `state` (messages + turn_count), 3 tools (`search_filings`, `describe_filing`, `compare_numbers`), `model` + `tools` nodes, conditional edge that loops until the model stops asking for tools | `docs/graph-stage1.mmd` |
| 2 | Reflection | `reflect` node + revision loop — self-check that every claim is grounded in a chunk; model's "done" path routes through `reflect`, not straight to END | `docs/graph-stage2.mmd` |
| 3 | External tool via MCP | a live market-data tool added via MCP — reasons across the private corpus and a public live source. **Adds a tool, not a node — graph shape unchanged.** | (unchanged) |
| 4 | Multi-agent | orchestrator (`decompose` → `delegate` → `synthesize`) delegating per-company sub-tasks to reusable copies of the Stage 1–3 analyst (A2A-style) | `docs/graph-stage4.mmd` |

Stages 1–2 are the committed project. Stages 3–4 are real extensions — build them only after the earlier stage genuinely works.

**The tool-vs-node distinction is load-bearing:** adding a *capability* the model can choose = a new **tool** (Stage 3); changing the agent's *control flow* = a new **node + edge** (Stage 2 reflection). Don't blur them.

## Files to read at session start

- `project-build-prompts-v2.md` — the brief + staged build prompts + Module 02 ground truth; the source of truth for scope
- `SESSION-STATE.md` — where I am, what's done, what's next, durable decisions
- `WHY.md` — cross-cutting design rationale (fills in as we build)
- `notes/*.md` — design intent per stage
- `README.md` — entry point and run instructions (created in Stage 0)

## Things to NEVER do without asking

- Skip the whiteboard step (Rule 1)
- Use `create_react_agent` / `AgentExecutor` or any prebuilt loop that hides the control flow
- Change the graph's *shape* when the task only calls for a new tool (and vice versa)
- Rewrite or "improve" the Module 02 retrieval pipeline — it's a bound dependency, not part of this repo
- Invent new abstractions because they "feel right"
- Add features, nodes, or polish I didn't ask for
- Modify `.env`
- Commit or push on my behalf unless I explicitly asked
