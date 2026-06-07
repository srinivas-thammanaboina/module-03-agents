# Tools notes — module-03-agents-app (Stage 1, Prompt 1.1)

**Takeaway:** The agent never sees the Python — it picks a tool from the `description` text in TOOL_SCHEMAS *alone*. So a tool's description is not documentation, it's **control logic**: it has to say what the tool is for, when to use it, when to use a *different* tool instead, and what the tool cannot do. Getting the descriptions right is the real work of this step; the function bodies are almost an afterthought.

## Intuition / mental model

A schema is the only thing the model knows about a tool at decision time: `name`, `description`, `input_schema`. When the model is mid-loop deciding "do I search, orient, compute, or answer?", it is pattern-matching the question against those description strings. Vague or overlapping descriptions → the model grabs the wrong tool or invents arguments that don't exist. Sharp, mutually-referential descriptions → it routes correctly. Treat each description as a tiny prompt aimed at the model's tool-choice.

## Why the naive approach fails

Two failure modes we designed against:

1. **Confusable siblings.** `search_filings` and `describe_filing` both touch "a filing." If their descriptions only say what each *does*, the model can't tell when to prefer one. Fix: each description says what it's for **and** points at the other for the opposite job — "to read what a filing says, use search_filings" / "to see what document/sections exist, use describe_filing." The cross-reference is what disambiguates.

2. **Inventing capability that isn't there.** The v1 schemas had `year` and `form_type` params and implied multiple filings. Against the real corpus (one latest 10-K per TSLA/AAPL/NVDA) that would make the model try to filter by a year that the index can't filter on, or fetch a second filing that doesn't exist — failing silently with zero chunks. Fix: the description states the corpus reality out loud ("ONE latest 10-K per company… no other years… there is no year or form-type filter") so the model never reaches for a capability we don't have.

## Chosen design + tradeoffs

- **Three tools, clearly partitioned by job:** `search_filings` (content), `describe_filing` (orientation/identity), `compare_numbers` (deterministic math). Each description names its job and the tool to use for the *other* jobs.
- **Corpus reality lives in the descriptions**, not just in code comments — because only the descriptions reach the model.
- **Stub-first, real-later.** `search_filings`/`describe_filing` return clearly-marked stub data behind a `bind_retriever` seam; the real Module 02 composed stack binds at Prompt 1.6 with no schema change. Tradeoff: the agent loop is fully testable now, at the cost of stub answers until 1.6 — acceptable because Stage 1 is about the *control flow*, not answer quality.
- **`compare_numbers` is deterministic** (no LLM) — arithmetic is something code does better than a model, so we offload it and guarantee correctness.

## Design decisions baked into the code

1. **Chunk `id` is carried even in stubs.** Each `search_filings` chunk includes `id` (e.g. `STUB-0001`, real ones like `TSLA-1A-0007`). The `id` is Module 02's citation token; Stage 2's grounding audit is impossible without it, so it must flow from the very first stub.
2. **No `year`/`form_type` anywhere** — params dropped from `search_filings`; the index can't filter them.
3. **`describe_filing(company)` replaces v1's `lookup_filing(company, year, form_type)`** — one filing per company means nothing to disambiguate; expose what's available instead.
4. **`company` is a ticker OR a name** in the schema; name→ticker normalization happens at bind time (1.6), not in the schema.

## Sanity-check experiment (fill in after running)

_Pending Prompt 1.4 (first live agent run)._ The real test of description quality is behavioral: pose a question and watch which tools the model picks and in what order. Target observations: (a) for a "what does X say" question it reaches for `search_filings`; (b) for "what filing/sections exist" it reaches for `describe_filing`; (c) it never emits a `year`/`form_type` argument; (d) for a YoY question it pulls two numbers then calls `compare_numbers`. Record the actual tool sequence here once we run it.

## Future experiments queue

- Description A/B: strip the cross-references ("use the other tool for…") and see whether the model starts confusing `search_filings` and `describe_filing`.
- Remove the "no year filter" sentence and check whether the model invents a `year` argument.
- Once real retrieval is bound (1.6): does `describe_filing` orientation *before* searching measurably improve the model's `company` targeting?

## Lessons to carry forward

Tool descriptions are part of the program. When an agent calls the wrong tool, fix the *description* before touching the code — the bug is usually in what the model was told, not in what the function does. And bake hard constraints of the world (here: one filing, ticker-only filtering) directly into the descriptions, because the model only knows what the schema tells it.
