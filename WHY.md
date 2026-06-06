# WHY — the design rationale behind module-03-agents-app

**Takeaway:** This document explains *why* the agent is shaped the way it is. The per-stage `notes/*.md` files go deep on one stage each (how it works, what we learned building it). This one is horizontal — the handful of design ideas that cut across stages and the reasoning that ties them together.

It's written to be *reasoned from*, not memorized. Each principle ends with a couple of **self-test questions** — if you can answer them from scratch, you understand the choice; if you can only recognize the answer, you don't yet.

> **Status: skeleton.** Module 02's WHY.md was written *after* the build, with real numbers. This one is seeded with the design commitments the Project Brief locks in up front; the per-stage rationale (marked _TBD_) gets filled as each stage is built and run.

---

## The system in one paragraph

Given a question about a company's SEC filings, the agent runs a loop: a **model** node (Claude, holding the tools) decides what to do; a **tools** node executes whatever it asked for and feeds the result back; a **conditional edge** loops them until the model stops asking for tools and emits an answer. Later stages add a **reflect** node (does every claim trace to a retrieved chunk?), an **MCP** tool (live market data the filings can't contain), and an **orchestrator** that delegates per-company sub-tasks to reusable copies of the analyst. The whole thing is an explicit LangGraph state machine — every node and edge visible, nothing hidden in a prebuilt executor.

---

## The cross-cutting principles

### 1. The control flow is explicit — nodes and edges, not a prebuilt loop

The single most important decision: we build the `StateGraph` by hand — `model` node, `tools` node, a conditional edge with a named routing function — and we do **not** use `create_react_agent` / `AgentExecutor`. A prebuilt agent loop would be fewer lines and would *work*, but it hides exactly the thing this module exists to teach: *when does the agent decide to call a tool vs. answer, and what makes it loop?* The win condition — diagram the graph from memory — is only meaningful if the graph is something I wrote, not something a framework generated.

This is the Module 02 "mechanism stays visible" principle, moved up a level: there, we refused to hide the retrieval math; here, we refuse to hide the control flow.

*Check yourself:* What exactly does `create_react_agent` hide that building the graph by hand exposes? — If the agent loops forever, where in *our* graph is the thing that stops it, and why would a prebuilt executor make that harder to find?

### 2. Tools add capability; nodes add control flow

A **tool** is something the model can *choose* to call (search filings, compare numbers, fetch a live price). A **node** is a step in the graph that *always* runs when control reaches it (the model step, the tools step, the reflection step). The distinction decides how every new feature lands: Stage 3 (MCP market data) adds a **tool** and the graph shape does **not** change — the model just has one more option. Stage 2 (reflection) adds a **node + edge** because it changes the *control flow* — answers now route through a checker before they can exit.

Blurring these is the classic way an agent project turns into spaghetti: people bolt control-flow decisions into tools, or wrap capabilities as nodes, and then can't reason about either.

*Check yourself:* Reflection is a node, but "check groundedness" could have been written as a tool the model calls. Why is making it a node (mandatory) the right call for *this* guarantee? — When Stage 3 adds market data, why is the graph diagram unchanged?

### 3. The Module 02 pipeline is a bound dependency behind a thin tool wrapper

The retrieval stack is done, eval-validated, and lives in another repo. This agent does not rewrite it, import its internals, or re-litigate its design — it calls it through one thin wrapper (`search_filings`) that maps Module 02's output into the chunk+metadata shape the tools expect. Until the real import is bound, the tool returns clearly-marked stub data so the whole agent is testable without the corpus.

This is Module 02's "interfaces at every swap point" principle applied across the module boundary: the agent depends on the *contract* (a query in, chunks+sources out), not the implementation.

*Check yourself:* Why keep the stub behind a flag even after the real retriever is bound? — If Module 02's retrieve signature changed, how many files in *this* repo should have to change, and which ones?

### 4. Grounded-by-construction: reflection is a gate, not a vibe _(TBD — fill after Stage 2)_

The copilot's whole promise is grounded answers. The reasoning for making that a structural guarantee (a node every answer must pass) rather than a prompt instruction gets written here once Stage 2 is built and we've seen it catch a real ungrounded claim.

### 5. Multi-agent only when sub-tasks differ in kind _(TBD — fill after Stage 4)_

Why an orchestrator + analyst specialists beats one bigger agent for cross-company questions — and why the Stage 1–3 agent becomes a reusable A2A-style specialist rather than being copy-pasted. Filled after Stage 4.

---

## Decision log

| Decision | Choice | Alternative | Why |
|---|---|---|---|
| Orchestration | hand-built LangGraph `StateGraph` | `create_react_agent` / `AgentExecutor` | Control flow must be visible and diagrammable from memory (Principle 1) |
| Retrieval | Module 02 pipeline via thin tool wrapper | rewrite retrieval here | It's done and eval-validated; this module is about the agent, not retrieval (Principle 3) |
| Reflection | a mandatory node + revision loop | a prompt instruction / optional tool | Groundedness is the product promise; structure it, don't suggest it (Principle 4, TBD) |
| Market data | external tool via MCP | bake a price API into a normal tool | MCP is the lesson — a real external connection across a private + public source (Stage 3) |
| _more as we build_ | | | |
