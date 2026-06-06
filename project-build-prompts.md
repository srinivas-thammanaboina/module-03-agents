# Filing Analyst Agent — Build Prompts

These are copy-paste prompts for building the Module 3 project with **Claude Code**, one small step at a time. Read the **Project Brief** first and paste it at the start of each new Claude Code session so it has the full picture. Then work through the stages in order. Each prompt is a single, reviewable step — build it, run it, read the code, then move on.

**How to use this file:**
- Paste the **Project Brief** once per session (it's the shared context).
- Within a stage, run the prompts in order. Don't skip ahead — each assumes the previous step works.
- After each step, actually read the diff and run the acceptance check before continuing. The point is to understand the agent, not to generate it.
- The 🛑 markers are review gates: stop, run, confirm, then proceed.

---

## Project Brief (paste this first, every session)

```
We are building a "Filing Analyst Agent" — an agent over SEC 10-K and 8-K filings,
built as a LangGraph state machine. This is Module 3 of a self-directed AI engineering
curriculum; it evolves a Module 2 RAG pipeline (the "Filing Analyst Copilot") from a
single-pass retriever into a multi-step agent.

CONTEXT AND CONSTRAINTS:
- LLM provider: Anthropic Claude API (the `anthropic` Python SDK). Model via env var
  ANTHROPIC_MODEL, default to a current Claude model string I will set.
- Orchestration: LangGraph (StateGraph). I want the control flow EXPLICIT as nodes and
  conditional edges — not hidden inside a prebuilt agent executor. Do not use
  langchain's create_react_agent / AgentExecutor; build the graph by hand.
- Retrieval: a Module 2 RAG pipeline already exists as importable code. It needs a CLEAN
  TOOL WRAPPER, not a rewrite. Assume a function exists that takes a query string (and
  optional filters) and returns retrieved chunks with source metadata. I will point you
  at the exact import path; until then, code against a thin interface I can bind later.
- This is a LEARNING project. Keep scope small and code readable over clever. Favor
  explicit, well-named functions over abstractions. Comment the WHY, not the what.
- Python 3.11+. Use a venv. Pin dependencies in requirements.txt or pyproject.toml.

THE STAGED PLAN (we build incrementally; do not jump ahead):
- Stage 1: Comparison Agent — the loop + tools (model node, tools node, conditional edge).
- Stage 2: Add a reflection node (self-check that every claim is grounded in a chunk).
- Stage 3: Add an EXTERNAL tool via MCP (live market data — something the filings can't
  contain), so the agent reasons across a private corpus and a public live source.
- Stage 4: Multi-agent — an orchestrator delegates per-company sub-tasks to copies of the
  Stage 1-3 agent (A2A-style), then synthesizes and ranks.

WORKING STYLE:
- Small steps. Do ONE thing per request. After each, stop and let me review and run it.
- When you need a design decision I haven't specified, ask rather than assume.
- Always show me how to run/test what you just built.

The win condition for the project: I can diagram the agent's control flow from memory —
naming every node, every edge, and the condition on each edge. Keep the graph small
enough that this stays true.
```

---

## Stage 0 — Scaffold

**Intention:** A clean repo and a working Claude API call before any agent logic. If the
plumbing is broken you want to find out now, not while debugging a graph.

### Prompt 0.1 — repo skeleton
```
Set up the project skeleton. Create:
- a venv and a requirements file pinning: anthropic, langgraph, python-dotenv (and
  nothing else yet — we add deps per stage)
- a package directory `filing_agent/` with empty __init__.py
- a `.env.example` with ANTHROPIC_API_KEY= and ANTHROPIC_MODEL=
- a `.gitignore` for Python (venv, .env, __pycache__)
- a README.md stub describing the project in two sentences and the staged plan as a list

Do not write any agent code yet. Show me the tree and the requirements file.
```
🛑 Review the tree. Create your `.env` from the example with a real key.

### Prompt 0.2 — smoke-test the Claude client
```
Create `filing_agent/llm.py` with a single function `get_client()` that loads env vars
and returns a configured Anthropic client, plus a thin `call_model(messages, tools=None)`
wrapper that sends a request and returns the raw response. Then create a tiny script
`scripts/smoke_test.py` that sends one "reply with OK" message and prints the result.
Show me how to run it.
```
🛑 Run the smoke test. Confirm you get a response back. **Do not proceed until this works.**

---

## Stage 1 — Comparison Agent (the loop + tools)

**Intention:** This is the core of the whole module — a model in a loop with tools, where
*the model* decides the order of operations. By the end you should be able to draw the
graph: a `model` node, a `tools` node, and a conditional edge that loops until the model
stops asking for tools. Everything in later stages hangs off this graph.

**Precondition:** Stage 0 smoke test passes.

**The spec to hand Claude Code (so it builds YOUR design):**
- **State** (a TypedDict): `messages` (the running transcript, with an add-reducer so it
  accumulates), `turn_count` (int, for the cap).
- **Tools (3):**
  - `search_filings(query: str, company: str | None, year: int | None, form_type: str | None)` → returns retrieved chunks + source metadata. Thin wrapper over the Module 2 pipeline.
  - `lookup_filing(company: str, year: int, form_type: str)` → resolves to a specific filing's identity/metadata (so the agent can target the right document).
  - `compare_numbers(a: float, b: float, label_a: str, label_b: str)` → returns the difference, percent change, and direction. Deterministic; no LLM.
- **Nodes:** `model` (calls Claude with the tools; appends its response to messages),
  `tools` (executes whatever tool the model requested; appends the result to messages).
- **Edges:** entry → `model`; conditional edge out of `model`: if the response contains a
  tool-use request → `tools`, else → END; normal edge `tools` → `model` (loop back).
- **Stop conditions:** model emits a final answer (no tool call), OR `turn_count` exceeds
  a cap (e.g. 6) — the cap is a hard safety rail, not a normal exit.

### Prompt 1.1 — define the tools (no agent yet)
```
Stage 1, step 1: define the three tools as plain Python functions with full type hints
and docstrings, in `filing_agent/tools.py`:
- search_filings(query, company=None, year=None, form_type=None)
- lookup_filing(company, year, form_type)
- compare_numbers(a, b, label_a, label_b)

For search_filings and lookup_filing, DO NOT implement real retrieval yet. Write them
against a thin interface: import a `retriever` object/function I will bind later, and for
now have them return clearly-marked STUB data (e.g. one fake chunk with a note that it's a
stub) so the rest of the agent is testable. compare_numbers should be fully real (it's
deterministic). Also produce the Anthropic tool schemas (name, description, input_schema)
for all three in the same file, as a list called TOOL_SCHEMAS. Show me the file.
```
🛑 Read the schemas. Are the descriptions clear enough that a model would know *when* to
call each? That description quality is what makes the agent pick the right tool.

### Prompt 1.2 — the tool executor
```
Stage 1, step 2: create `filing_agent/executor.py` with `run_tool(name, args) -> str`
that dispatches to the right function in tools.py, handles an unknown tool name and a
tool that raises (return an error string the model can read, don't crash), and returns
the result as a string suitable for feeding back to the model. Add a couple of direct
unit tests in `tests/test_executor.py` (real compare_numbers, a stub search, an unknown
tool, a raising tool). Show me the file and the test output.
```
🛑 Run the tests. Confirm errors come back as readable strings, not exceptions.

### Prompt 1.3 — the state and the two nodes
```
Stage 1, step 3: create `filing_agent/state.py` defining the AgentState TypedDict
(messages with an add-reducer, turn_count: int). Then create `filing_agent/nodes.py` with
two node functions: `model_node(state)` — calls call_model with TOOL_SCHEMAS, appends the
assistant response to messages, increments turn_count, returns the state update; and
`tools_node(state)` — finds the tool-use request in the last assistant message, runs it
via run_tool, appends a tool-result message, returns the state update. Do NOT build the
graph yet. Show me both files.
```
🛑 Read `nodes.py` carefully — this is where the loop's per-turn logic lives. Make sure
`model_node` appends and `tools_node` reads the right message.

### Prompt 1.4 — wire the graph
```
Stage 1, step 4: create `filing_agent/graph.py` that builds the StateGraph:
- nodes: "model" -> model_node, "tools" -> tools_node
- entry point: "model"
- a routing function should_continue(state) that returns "tools" if the last assistant
  message requested a tool AND turn_count < cap, else END
- add_conditional_edges from "model" using should_continue, mapping {"tools": "tools",
  END: END}
- a normal edge from "tools" back to "model"
- compile and expose `app`
Then add `scripts/run_agent.py` that takes a question on the command line, invokes the
graph, and prints the final answer plus the sequence of tools that were called. Show me
both files and how to run it.
```
🛑 Run it with a multi-step question (e.g. *"Did revenue grow between the 2022 and 2023
10-K for [company]?"*). With stubs, confirm the agent **loops**: calls a tool, gets a
result, calls another, then answers. Watch the tool sequence print out — that sequence
*is* the loop working.

### Prompt 1.5 — visualize the graph
```
Stage 1, step 5: add a small script `scripts/draw_graph.py` that uses LangGraph's built-in
mermaid export to print the graph's structure, and save the mermaid text to
`docs/graph-stage1.mmd`. Show me the output.
```
🛑 **This is your win-condition check.** Look at the diagram. Can you now redraw it from
memory — model node, tools node, the conditional edge with its condition, the loop-back?
If not, re-read `graph.py` until you can. Don't start Stage 2 until you can draw Stage 1.

### Prompt 1.6 — bind the real retriever
```
Stage 1, step 6: I'm now pointing you at the real Module 2 retrieval pipeline. Its import
path and call signature are: [PASTE YOUR ACTUAL IMPORT AND SIGNATURE HERE]. Replace the
stub in search_filings and lookup_filing with a thin wrapper that calls this real code and
maps its output into the chunk+metadata shape our tools already return. Do not change the
tool signatures or schemas. Keep the stub behind a flag or fallback so tests still run
without the corpus. Show me the wrapper and run the agent against a real question.
```
🛑 Run a real question end to end. **Stage 1 done when:** the agent answers a question that
needs ≥2 tool calls, against real filings, and you can diagram the control flow from memory.

---

## Stage 2 — Reflection (the self-check node)

**Intention:** Your copilot's whole promise is *grounded* answers. Reflection is where the
agent checks its own work before returning it — does every claim trace to a retrieved
chunk? This teaches you that reflection is a NODE with a conditional edge, not a prompt
trick. You're adding to the Stage 1 graph, not rebuilding it.

**Precondition:** Stage 1 works against real filings.

**The spec:**
- Add to state: `draft_answer` (str), `reflection_passed` (bool), `revision_count` (int).
- New node `reflect`: given the draft answer and the retrieved chunks in messages, ask the
  model to check whether every factual claim is supported by a chunk. It returns a verdict
  (pass / needs-revision) and, if needs-revision, what's unsupported.
- New edges: model's "I'm done" path now goes to `reflect` instead of END. Conditional
  edge out of `reflect`: pass → END; needs-revision AND revision_count < cap → back to
  `model` (with the critique added to messages so it can fix or retrieve more); else → END
  (give up gracefully, flag the answer as unverified).

### Prompt 2.1 — the reflection node
```
Stage 2, step 1: add a `reflect_node(state)` to nodes.py. It takes the draft answer (the
last assistant message when no tool was called) and the retrieved chunks from the
transcript, and calls the model with a focused prompt: "Check each factual claim in the
answer against the provided chunks. Respond in JSON: {passed: bool, unsupported_claims:
[...]}". Parse the JSON robustly (handle the model wrapping it in prose). Update state
with reflection_passed and, if failed, append the critique to messages. Add the new state
fields to state.py. Do NOT change the graph yet. Show me the node and the prompt.
```
🛑 Read the reflection prompt. Is it specific about *grounded in the chunks* vs. just
"sounds right"? That distinction is the whole value of the node.

### Prompt 2.2 — rewire the graph
```
Stage 2, step 2: update graph.py. Add the "reflect" node. Change should_continue so the
model's no-tool path routes to "reflect" instead of END. Add a routing function
should_revise(state): "model" if not reflection_passed and revision_count < cap, else END
(increment revision_count when looping back). Add_conditional_edges from "reflect" using
should_revise. Re-export the mermaid diagram to docs/graph-stage2.mmd. Show me the diff
and the new diagram.
```
🛑 Diagram check again. The graph now has a loop-back from `reflect` → `model`. Can you draw
the whole thing — two loops now (tool loop and revision loop)? **Stage 2 done when:** a
question with a deliberately hard-to-ground part gets caught by reflection and either fixed
or flagged, and you can diagram both loops from memory.

---

## Stage 3 — External tool via MCP (live market data)

**Intention:** So far every tool reads your own corpus. MCP earns its place when the agent
needs something it genuinely *can't* hold — live data. A question like *"the 2023 10-K
flagged margin pressure; how has the stock moved since that filing?"* needs current prices.
This teaches you MCP as a real external connection and forces the agent to reason across a
private source (filings) and a public live one (market data).

**Precondition:** Stages 1-2 work. Treat this as a green-lit extension, not part of the
committed build — only start once 1-2 are solid.

**The spec (lighter — flesh out as you build):**
- Connect to an MCP server that exposes a market-data / stock-price tool. Decide first
  whether to use an existing public MCP server or write a tiny one wrapping a free price
  API — ask Claude Code to lay out both options before committing.
- The MCP tool joins the existing tool set; the model chooses it like any other tool. The
  graph does NOT change shape — you're adding a tool, not a node.

### Prompt 3.1 — scope the MCP integration
```
Stage 3, step 1: I want to add a LIVE market-data tool to the agent via MCP, so it can
answer questions that combine filing content with current stock prices. Before writing
code, lay out my options: (a) connect to an existing public MCP server for market/stock
data, vs (b) write a minimal local MCP server wrapping a free stock-price API. For each,
note setup cost, reliability, and what I'd learn. Recommend one for a learning project and
explain why. Do not write code yet.
```
🛑 Pick an approach based on the tradeoffs. Confirm the data source before building.

### Prompt 3.2 — wire the MCP tool
```
Stage 3, step 2: implement the approach we chose. Add the market-data tool so it appears
in the agent's tool set alongside search_filings etc., with a clear schema describing when
to use it (current/recent prices, NOT historical filing content). Make sure run_tool can
dispatch to it. The graph shape must not change. Show me the integration and run a question
that needs BOTH a filing lookup and a live price.
```
🛑 Run a cross-source question. Confirm the agent calls *both* a filing tool and the market
tool, and reasons across them. **Stage 3 done when:** the agent answers a question no single
source could, and you can explain how MCP connects the external tool (host/client/server).

---

## Stage 4 — Multi-agent (orchestrator + analyst specialists)

**Intention:** Multi-agent is only worth it when sub-tasks need genuinely different work.
A cross-company question — *"Compare how [A], [B], [C] each described AI-related risks in
their latest 10-Ks, and rank them by revenue growth"* — splits cleanly: an **orchestrator**
decomposes and ranks (different job), while a **filing-analyst** (your Stage 1-3 agent,
reused) grounds one company's answer. This teaches A2A-style delegation and why your earlier
agent becomes a reusable specialist.

**Precondition:** Stages 1-2 (ideally 3) solid. This is the most ambitious stage — treat the
spec as a starting sketch and expect to refine it as you build.

**The spec (sketch — refine during build):**
- The Stage 1-3 graph becomes a callable "analyst" that answers ONE company's question.
- An `orchestrator` decomposes a multi-company question into per-company sub-tasks, invokes
  an analyst per company (in parallel where possible), collects the grounded answers, then
  does a final synthesis/ranking step.
- Keep the A2A concepts visible even if you don't use the full protocol: each analyst should
  expose a small "capability description" (what it can answer) and accept a well-defined
  task; the orchestrator coordinates without reaching into the analyst's internals.

### Prompt 4.1 — make the analyst reusable
```
Stage 4, step 1: refactor so the Stage 1-3 graph can be invoked as a self-contained
"analyst" for a single company's question — a clean function/class that takes (company,
question) and returns a grounded answer with sources, with no shared mutable state between
invocations. Add a small capability descriptor (name + what kinds of questions it answers),
in the spirit of an A2A Agent Card. Don't build the orchestrator yet. Show me the interface.
```
🛑 Confirm two analyst invocations for different companies don't interfere (no shared state
bleed). This isolation is what makes parallel delegation safe.

### Prompt 4.2 — the orchestrator
```
Stage 4, step 2: build an orchestrator as its own small LangGraph: a `decompose` node
(split a multi-company question into per-company tasks), a `delegate` node (invoke the
analyst per company; run them concurrently if straightforward), and a `synthesize` node
(combine the grounded answers and produce the requested ranking). Show me the orchestrator
graph, export its mermaid diagram to docs/graph-stage4.mmd, and run the cross-company
question end to end.
```
🛑 Run the full multi-company question. **Stage 4 done when:** the orchestrator delegates to
analysts, aggregates grounded per-company answers, and ranks them — and you can diagram BOTH
graphs (orchestrator and analyst) and explain the delegation as an A2A-style task handoff.

---

## A note on scope and sequencing

Stages 1-2 are the committed project — they fully satisfy the README's "done when" (a
working agent that plans and uses tools, diagrammable from memory). Stages 3 and 4 are
real extensions that each add a substantial concept (MCP, then multi-agent/A2A). Build them
only after the earlier stage genuinely works, and re-export the diagram at every stage — if
you ever can't draw the current graph from memory, that's the signal to stop adding and
consolidate before continuing. Coverage of concepts matters less than being able to reason
about the ones you've built.
