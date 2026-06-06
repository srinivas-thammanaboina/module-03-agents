# Agent loop notes — module-03-agents-app (Stage 1)

**Takeaway:** An agent is a straight-line pipeline replaced by a *loop where the model decides what to do next*. We hand Claude a question and a toolbox; it chooses a tool, reads the result, and chooses again, until it has enough to answer. The intelligence is in that sequence of choices — our code only runs the loop and executes whatever tool the model picks. The entire control flow reduces to two nodes (`model`, `tools`) and one conditional edge ("did the model ask for a tool? loop : stop").

## Intuition / mental model

Module 02 was a straight line: question → retrieve → answer. One pass, fixed order, no decisions. Stage 1 turns that line into a loop. Instead of *us* hardcoding "search, then compare, then answer," we give the model a toolbox and let *it* order the operations. The same graph answers different questions with different tool sequences, because the model — not the code — picks the path.

The agent's working memory is the **transcript** (`messages`): the question, the model's replies, and the tool results, all appended in order. Every time control returns to the `model` node, Claude re-reads that whole transcript to decide its next move. That re-reading is why the loop works without us threading any state by hand — the conversation *is* the state.

Two plain-English terms used throughout: a **node** is one step in the graph that always runs when control reaches it; an **edge** is the arrow to the next step; a **conditional edge** is an arrow with an if-statement on it.

## Why the naive (single-pass) approach fails

Take *"Did revenue grow between the 2022 and 2023 10-K for Tesla?"* A single retrieve-then-answer pass can't do this: it needs two *separate* facts (2022 revenue, 2023 revenue) and then an arithmetic comparison. There's no one query that returns "the growth"; the answer has to be *assembled* across steps. That assembly — fetch, fetch, compute, conclude — is precisely what the loop provides and the straight line cannot.

Traced through the loop:

| Turn | `model` decides | `tools` runs | transcript after |
|---|---|---|---|
| 1 | need 2022 revenue → `search_filings(…2022)` | → `$81,462M` | question + result |
| 2 | need 2023 revenue → `search_filings(…2023)` | → `$96,773M` | + result |
| 3 | compare them → `compare_numbers(81462, 96773)` | → `+15,311 / +18.8% / up` | + result |
| 4 | have everything → writes answer, **no tool** | — | + final answer |

The sequence search → search → compare → answer is the model reasoning. Nobody hardcoded it; a different question yields a different sequence through the same two nodes.

## Chosen design + tradeoffs

**State (`AgentState`, a TypedDict, two fields):**
- `messages` — the running transcript, carrying an **add-reducer**. Plain English: each node *appends* to the list rather than overwriting it, so history accumulates and the model never loses what it already retrieved. (Without the reducer, each node clobbers the transcript and the agent forgets mid-task.)
- `turn_count` — how many times the `model` node has run; consumed only by the safety cap.

**Tools (3):**
- `search_filings(query, company, year, form_type)` — *semantic* retrieval ("find chunks about X"). Thin wrapper over the Module 02 pipeline; stubbed until Prompt 1.6.
- `lookup_filing(company, year, form_type)` — *identity* resolution ("which exact document is Tesla's 2023 10-K?"). Separate from search because targeting the right document is a different job from searching inside it; resolving identity first keeps the semantic search scoped and prevents cross-company/cross-year bleed.
- `compare_numbers(a, b, label_a, label_b)` — deterministic arithmetic (difference, % change, direction). **No LLM.** Language models are unreliable at arithmetic, so we hand that to real Python and *guarantee* correctness. General lesson: give the agent deterministic tools for anything code does better than a model.

**Nodes (2):**
- `model` — calls Claude with the toolbox, appends the reply to `messages`, increments `turn_count`.
- `tools` — finds the tool the model asked for in its last message, runs it, appends the result.

**Edges:** entry → `model`; a conditional edge out of `model` (routing function `should_continue`): asked for a tool **and** `turn_count < cap` → `tools`, else → `END`; a plain edge `tools` → `model` (loop back).

**Stop conditions:** the normal exit is the model emitting a final answer with no tool call. The turn cap (≈6) is a *circuit breaker*, not a normal exit — it only fires if the model gets stuck asking for tools forever, so a confused agent can't loop and burn API budget.

### The graph (draw this from memory — it's the win condition)

```
            ┌──────────────────────────────────────┐
            │                                       │  (loop back)
            ▼                                       │
  START ─► ┌─────────┐   should_continue(state)?    │
           │  model  │ ───────────────┬──────────►  │
           └─────────┘                │             │
                 ▲          asked for a tool        │
                 │          AND turn_count < cap     │
                 │                    │             │
                 │                    ▼             │
                 │              ┌──────────┐        │
                 │              │  tools   │ ───────┘
                 │              └──────────┘
                 │
            (no tool asked, OR turn_count ≥ cap)
                 │
                 ▼
               (END)
```

Two nodes, one conditional edge, one loop-back. **That conditional edge *is* the agent** — the single branch "tool requested? loop : stop" is the whole difference between an agent and a one-shot call, and everything in Stages 2–4 hangs off it.

### Tradeoffs / what can break

- **Model answers without using tools** (hallucinates from memory). Defended by clear tool descriptions + a light system prompt ("ground every claim via tools; don't guess"). This is why Prompt 1.1's review gate is about *description quality* — the model picks tools from their name + description alone.
- **Model calls `compare_numbers` with made-up numbers** instead of retrieved ones. Stage 1 can't fully catch this; it's exactly the hole Stage 2 (reflection) plugs.
- **Infinite loop** → the turn cap.
- **Stubbed retrieval (1.1–1.5).** Tools return clearly-marked fake chunks until Prompt 1.6. Deliberate: we're testing the *control flow* (does it loop correctly?), not answer quality, until the real retriever binds in.

## Design decisions baked into the code

1. **Message format = raw Anthropic dicts, not LangChain message objects.** LangGraph is provider-agnostic, but we store the same `{role, content}` shape `call_model` already takes, with a simple add-reducer — no LangChain message layer, no hidden conversions. Keeps the data flow legible (the "control flow stays visible" ethos). *(Decided with the user during the Stage 1 whiteboard.)*
2. **A minimal system prompt in `model_node`.** A one-liner: "you analyze SEC filings; always ground answers using the tools; don't guess." Markedly improves whether the agent actually loops vs. free-associates. *(Decided with the user during the Stage 1 whiteboard.)*
3. **Turn cap ≈ 6**, treated as a safety rail, not a normal exit.
4. **`compare_numbers` is deterministic** — no model call inside it.

## Sanity-check experiment (fill in after running)

_TBD — after Prompt 1.4/1.6._ Target: run a question needing ≥2 tool calls and confirm the printed tool sequence shows a genuine loop (e.g. `search → search → compare → answer`), first against stubs, then against the real Module 02 retriever. Record the actual sequence and whether the model exited on its own (vs. hitting the cap).

## Future experiments queue

- Tool-description A/B: does sharpening `search_filings` vs. `lookup_filing` descriptions change which the model picks? (Schema-quality lessons land in `tools-notes.md` after Prompt 1.1.)
- Turn-cap probing: craft a question that *almost* loops forever; see where the cap fires.
- Whether a stronger model (Opus) changes the tool sequence on the same question.

## Lessons to carry forward

The agent is not the tools and not the model — it's the **loop and its exit condition**. When an agent misbehaves, read the *transcript and the tool sequence* first (Rule 4's "look at the real output," moved up to the control-flow level): the bug is almost always in *what the model decided*, visible in the sequence, not in a tool's internals. Keep the graph small enough to draw from memory; the moment you can't, stop adding and consolidate.
