# Reflection notes — module-03-agents-app (Stage 2)

**Takeaway:** Reflection makes the agent grade its own homework before handing it in. After the model writes a draft answer, a `reflect` node checks that every factual claim traces to a chunk we actually retrieved; if not, it loops back so the model can fix it or retrieve more. The key idea: reflection is a **node (a gate), not a prompt instruction (a wish)** — the answer physically cannot leave the graph without passing the check.

## Intuition / mental model

Stage 1's agent answers and we *hope* it grounded every claim — the system prompt asks for grounding, but a prompt has no teeth. Stage 2 adds a structural guarantee: the model's "I'm done" path no longer exits to END; it routes through `reflect` first. Reflect either lets the answer out (grounded) or sends it back with a critique (a second loop, on top of the tool loop). Same "tool adds capability, node adds control flow" principle from WHY.md — reflection changes the *control flow*, so it's a node, not a tool.

## Why the naive approach fails — two failure modes need two checks

1. **Fabricated citation:** the model writes `[TSLA-2026-01-29-0999]` but no such chunk was retrieved. Cheap and certain to catch — compare cited ids against retrieved ids (plain set math, no LLM).
2. **Real id, wrong content:** the model cites a *real* chunk but the chunk doesn't say what the claim says (e.g. "revenue grew" citing a chunk that says it fell). The id check passes; only *reading the chunk* catches this — needs an LLM judgment.

So reflect runs BOTH and passes only if BOTH pass:

```
reflect = deterministic citation audit  AND  LLM groundedness check
          (every cited id was retrieved)     (each claim follows from its cited chunk's text)
          free · certain · backstop          one model call · judgment
```

The deterministic audit is the backstop: even if the LLM check is lenient or flaky, a fabricated id is *always* caught by set math. That's why we keep both, not the LLM alone. We mirror Module 02's `app/generate.py` `_audit_citations` and reuse its exact citation regex `\[([A-Za-z0-9][A-Za-z0-9\-_.]*)\]` and chunk-id scheme — one citation token across both modules, no parallel invention.

## Chosen design + tradeoffs

**State — new fields:**
- `draft_answer` (str), `reflection_passed` (bool), `revision_count` (int)
- `retrieved_ids` (list, add-reducer) — the authoritative set of ids actually retrieved this run, so the deterministic audit has a robust "provided" set.

**New node `reflect`:** reads the draft (last assistant message, no tool call) + `retrieved_ids`; runs both checks; sets `reflection_passed`; on failure appends a **critique** message (unsupported claims + any hallucinated ids) and bumps `revision_count`.

**Routing (rewired in Prompt 2.2):**
- model's no-tool path → `reflect` (instead of END)
- `should_revise` out of reflect: pass → END; fail & `revision_count < cap` → back to `model`; else → END but flag the answer **"⚠ unverified"** (graceful give-up).

**The two-loop graph:**
```
START → model ──tool & turn<cap──► tools ──► model      (TOOL LOOP: gather evidence)
           │ no tool (draft)
           ▼
        reflect ──not grounded & revisions<cap──► model  (REVISION LOOP: fix claims)
           │ grounded  (or gave up → "⚠ unverified")
           ▼
         END
```

**Tradeoffs:** reflection costs one extra model call per answer (and per revision) — bounded by the revision cap. The LLM check can be imperfect, but the deterministic audit covers the worst case (fabrication). Graceful give-up means we never loop forever and never silently ship an ungrounded answer.

## Design decisions baked into the code (confirmed with user)

1. **`retrieved_ids` lives in state** (not scraped from transcript text). Scraping is fragile — chunk body text can contain `[...]` tokens that would pollute the "provided" set and let a real hallucination slip through. `tools_node` records ids at the source instead. *(The LLM groundedness check still reads chunk TEXT from the transcript's tool_result messages — only the deterministic id set comes from state.)*
2. **Revision cap = 2** (up to two fix attempts), a second safety rail alongside the turn cap.
3. **Groundedness check uses the default model (Sonnet)** for quality/simplicity now; Haiku is a noted later cost optimization (the check is a narrow "is this claim supported by this text" judgment).
4. **Give-up UX:** on cap-exhaustion, return the draft flagged **"⚠ unverified"** with the unsupported claims/citations named — never spin, never lie.

## Sanity-check experiment (fill in after running)

**Normal question (real run):** *"…did total revenue grow vs the prior year? Give figures and cite chunks."* → `search_filings → compare_numbers`, **reflection passed ✓, 0 revisions**. The grounded, cited answer (TSLA revenue −2.93%) exited cleanly through the reflect node.

**Forced hallucinated citation:** crafted a draft citing one real id `[…-0223]` and one fake `[…-9999]` (never retrieved), with `retrieved_ids=[…-0223]`. → **reflection_passed: False, revision_count: 1.** BOTH checks fired: the deterministic audit flagged `…-9999` as a hallucinated citation, AND the LLM check independently flagged "Net income tripled to \$99,999M" as unsupported. Critique appended naming both. Confirms the core claim: even a lenient LLM can't let a fabricated id through — set math catches it.

_Not yet exercised:_ the full revision loop fixing a real run (model retrieving more after a critique) and the cap-exhaustion "⚠ unverified" give-up path — both wired and reachable; worth a live trigger later.

## Future experiments queue

- Swap the groundedness check to Haiku and compare verdicts vs Sonnet (cost vs reliability).
- Tighten the reflect prompt: does "quote the supporting span" reduce lenient passes?
- Measure how often revision actually fixes vs gives up, across question types.

## Lessons to carry forward

A guarantee you want to *hold* must be a structure, not a sentence — encode it as a node/gate, not a prompt request. And pair a cheap deterministic check with an LLM judgment whenever you can: the deterministic part bounds the worst case so the LLM only has to handle the subtle cases.
