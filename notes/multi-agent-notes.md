# Multi-agent notes — module-03-agents-app (Stage 4, A2A)

**Takeaway:** Multi-agent earns its keep only when sub-tasks differ in KIND. A cross-company question splits into N identical "ground one company" tasks (each needs the full Stage 1–3 machinery) plus one different "synthesize & rank" task (coordination, not grounding). So: an **orchestrator** splits + ranks; a reusable **analyst** (our whole Stage 1–3 agent, as a black box) answers each company. The earlier agent becomes a tool for a higher-level agent — that's A2A.

## Intuition / mental model — A2A

A2A = Agent-to-Agent: one agent calls *other agents* instead of just functions. Two concepts kept visible (without the full A2A wire protocol):
- **Agent Card** — a small capability description the analyst advertises ("I answer grounded questions about ONE company's latest 10-K, TSLA/AAPL/NVDA, citing chunk ids + live prices"). The orchestrator reads it to know what the analyst can do.
- **Task handoff** — the orchestrator hands the analyst a well-defined task `(company, question)` and gets back a grounded result, WITHOUT reaching inside the analyst's graph. Black box in, grounded answer out.

## Two graphs

```
  ORCHESTRATOR (new, linear)                 ANALYST (Stage 1–3 graph, reused)
  decompose → delegate → synthesize → END    model ↔ tools ↔ reflect
     │ split Q       │ run_analyst()             (unchanged; made callable)
     │ per company   │ per company  ─────────────────► one full run per company
                     ▼
              collect grounded answers → rank, preserve citations
```

The analyst graph is unchanged — we just make it callable as `run_analyst(company, question)`. The orchestrator is a NEW small linear LangGraph (no loops).

## The name-collision to keep straight (v2 flagged it)

Module 02's `DecompositionRetriever` splits a question for **balanced retrieval inside one analyst**. The orchestrator's `decompose` splits into per-company **tasks delegated to whole analysts** — a different layer. Each analyst is scoped to one company, so the inner retrieval-decomposition is effectively a no-op within an analyst. Two "decompositions": retrieval-balancing (inside) vs task-delegation (across). Don't conflate.

## Why "reusable analyst" requires statelessness (the 4.1 🛑)

For the orchestrator to run analysts safely (especially in parallel), two invocations must not share mutable state — TSLA's run can't leak into NVDA's. `app.invoke(fresh_initial_state)` is already stateless per call (the compiled graph holds no per-run state; our module-level globals — bound retriever, retrieval singleton — are read-only). The 4.1 check: run two analysts for different companies, confirm each cites only its own company's chunks (zero bleed).

## Chosen design + tradeoffs

- **`run_analyst(company, question)`** reuses the existing compiled graph with FRESH per-call state; scopes to the company by injecting the ticker into the analyst's prompt so it filters retrieval. Returns `{company, ticker, answer, citations, reflection_passed}`. Plus an **AGENT_CARD** capability descriptor (A2A spirit).
- **Orchestrator = its own LangGraph** (`decompose → delegate → synthesize`), separate from the analyst graph — teaches graph composition.
- **Delegation: sequential first** (watch each analyst run in order — clearer for learning), parallel (thread pool) a noted upgrade.
- **Citation integrity in synthesis:** reuse Stage 2's deterministic audit at the orchestrator level — every id in the final ranking must be one some analyst actually retrieved (audit against the UNION of all analysts' retrieved_ids). Keeps the multi-agent answer provably grounded.
- **Out-of-corpus:** `decompose` restricts to TSLA/AAPL/NVDA and flags any other company rather than delegating an analyst that returns nothing.

**Tradeoffs:** N companies × (full tool loop + reflection) = many model calls; parallel cuts wall-clock. Synthesis can drop/invent citations → the union audit is the backstop. One analyst failing must degrade gracefully (note the gap), not crash.

## Design decisions baked into the code (confirmed with user — all 5)

1. `run_analyst(company, question)` reusing the compiled graph, fresh state, ticker-scoped; + AGENT_CARD.
2. Orchestrator as its own small LangGraph (decompose → delegate → synthesize).
3. Delegation sequential first; parallelize later.
4. Citation integrity via the deterministic audit at orchestrator level (union of analysts' retrieved_ids).
5. decompose restricts to TSLA/AAPL/NVDA; flags out-of-corpus companies.

## Sanity-check experiment (fill in after build, user-run per Rule 8)

**(4.1) Isolation — done.** Ran TSLA + NVDA analysts; TSLA cited only `TSLA-2026-01-29-*`, NVDA only `NVDA-2026-02-25-*` (different filing dates → each hit the right 10-K), both `reflection_passed`. Zero cross-bleed → fresh-state-per-call confirmed.

**(4.2) Orchestrator — done.** Cross-company question (*"compare AI risks across TSLA/AAPL/NVDA, rank by YoY revenue growth"*) ran `decompose → delegate → synthesize`, split into 3 tasks, ranked NVDA +65.5% › AAPL +6.4% › TSLA, union citation audit clean. Graph is linear (no loops) — `docs/graph-stage4.mmd`.

**AAPL FAIL diagnosis (the rich finding).** On one run AAPL failed reflection on 3 *legitimate* over-claims (invented "five categories" taxonomy; selectively-incomplete growth framing; a real citation `[…-0098]` attached to the wrong claim) — see Future experiments. This validated **surfacing unverified sub-answers**: implemented (option 1) — orchestrator computes an `unverified` list from analyst `reflection_passed` flags AND the synthesis prompt flags those contributions "⚠ unverified." A later run had all three pass (`UNVERIFIED: none ✓`), confirming the surfacing is correct either way.

**Bug caught by Rule 8.** The 4.1 scoping refactor (extracting `build_scoped_question`) left an orphaned `name` in `run_analyst`'s return → `NameError`, surfaced only when the user ran the orchestrator (not in the 4.1 check, which predated the refactor). Fixed to `_NAMES.get(ticker, ticker)`.

**Polish + the reflect-the-synthesis fix (verified).** Implemented (option 3) a groundedness check on the SYNTHESIS itself — caught a real fabrication on its first run: the synthesizer invented NVDA's revenue (`~+114%`) to fill a gap left by a truncated analyst answer; the citation audit missed it (real id), the groundedness check flagged it. Root cause of the truncation: `DEFAULT_MAX_TOKENS=1024` in `llm.py` cut off rich answers (quotes + tables). **Fixed: 1024 → 4096.** Re-run after the bump: answers complete, TSLA's spurious FAIL gone (pass, 15 citations), NVDA's figures back to the grounded `+65%`, and `SYNTHESIS GROUNDEDNESS: passed ✓`. Also quieted the HF-hub + FutureWarning noise (in `retrieval.py`) and rewrote `README.md` for the finished 4-stage agent.

## Future experiments queue

- Parallelize delegation (thread pool) and measure wall-clock vs sequential.
- A 4-company question including an out-of-corpus name (e.g. GOOG) — confirm decompose flags it.
- Optionally reflect the final synthesis itself (not just the per-company answers). **Concrete motivation observed:** in one run TSLA's analyst answer was cut off before its revenue figures, and the synthesizer filled the gap with an UNCITED "well-documented as negative" claim to still rank TSLA third. The union citation audit did NOT catch it — that audit only checks that *cited* ids are real, not that every *claim* carries a citation. So the synthesis layer's grounding is weaker than the analyst's `reflect`. Fix idea: run the full groundedness check (or at least a "every ranking claim must cite") on the synthesis.
- **Analyst over-claiming (from the AAPL FAIL diagnosis).** AAPL failed reflection on 3 *legitimate* issues, none of them fake ids: (1) invented structure — claimed the 10-K "discloses five distinct categories" of AI risk, a taxonomy the filing never states; (2) selectively-incomplete framing — characterized revenue growth drivers while omitting Rest-of-Asia-Pacific (+10%) that IS in the cited chunk; (3) citation misattribution — pinned a "materially adversely affect…" phrase to `[AAPL-…-0086]` when it actually lives in `[…-0098]`, a different topic. Lesson: the more an answer editorializes/adds structure, the more ungrounded surface area (TSLA/NVDA stayed closer to the chunks and passed). Experiment: tighten the analyst system prompt to discourage imposing structure/framing not in the filing; measure pass-rate vs answer richness.
- **Loop/cap interaction (partially resolved).** The "cut off / pre-revision draft" symptom was largely `DEFAULT_MAX_TOKENS=1024` truncating answers — fixed by the bump to 4096. A separate, still-open question: when the revision loop re-retrieves and hits `TURN_CAP`, can `reflect` fail to re-run on the latest draft, leaving a stale verdict? Confirm by instrumenting; consider giving the revision loop its own budget or guaranteeing `reflect` runs on the final draft before END.
- **Reflection is strict on rich answers.** Even post-bump, the most elaborate per-company answer (lots of quotes/structure) is the one most likely to fail reflection (NVDA in the final run). Reinforces the over-claiming experiment: richer answer = more ungrounded surface area. Consider a "quote-or-qualify" instruction in the analyst prompt.

## Lessons to carry forward

Reach for multi-agent only when sub-tasks differ in kind; otherwise it's just cost. A well-built single agent becomes a reusable specialist — the Agent Card + task handoff is how you compose agents without coupling them. And grounding must survive composition: re-audit citations at the top level so the merged answer is as trustworthy as each piece.
