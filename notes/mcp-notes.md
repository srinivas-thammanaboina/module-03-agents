# MCP notes — module-03-agents-app (Stage 3)

**Takeaway:** MCP (Model Context Protocol) is the standard "plug" for giving an agent external capabilities. Stage 3 adds a *live market-data* tool over MCP so the agent can answer questions the filings physically cannot contain (current/recent stock prices) — reasoning across a private source (10-Ks) and a public live one (the market). Crucially, this adds a **tool, not a node**: the graph shape is unchanged; the model just gets one more option.

## Intuition / mental model — host / client / server

A filing is a frozen snapshot (Tesla's 10-K is dated 2026-01-29 and will never know today's price). Any question needing live data must reach outside. MCP is the standard way to do that. Three roles, restaurant analogy:

- **MCP server** = the kitchen — a separate program exposing tools (here: "get a stock price"); knows nothing about our agent.
- **MCP client** = the waiter — code in our app that connects to the server, discovers its tools, relays calls + results.
- **MCP host** = the restaurant — our agent app, holding the client(s) + the LLM.

Host contains client(s); each client talks to one server. Transport here is **stdio** (our app launches the server as a subprocess, talks over stdin/stdout). The payoff vs. a hand-coded `requests` call: once you've built one MCP tool, any MCP server (GitHub, Slack, a DB…) plugs in the same way.

## Why the naive approach fails

You *could* just `import requests` and add a normal local tool. That works, but it skips the lesson: MCP is the interoperable standard the ecosystem is converging on, and it forces a clean client/server boundary. Building both halves once teaches the protocol you'll reuse everywhere.

## Chosen design + tradeoffs

```
   host (our agent)                         server (kitchen)
   graph: model ↔ tools ↔ reflect  (same!)  ┌──────────────────┐
   TOOL_SCHEMAS: search_filings,            │ get_stock_price  │→ free price API
     describe_filing, compare_numbers,      │ (FastMCP, stdio) │  (Stooq, no key)
     get_stock_price ──(MCP client)────────►└──────────────────┘
   run_tool dispatch ──┘
```

**The synergy:** a "how has the stock moved since the filing?" question chains existing pieces —
`describe_filing(TSLA)`→ filing_date (the "since" anchor) → `get_stock_price(TSLA, filing_date)` + `get_stock_price(TSLA)` → `compare_numbers(then, now)` → answer. Two sources + our deterministic tool, reused.

**Layering (separation of concerns):**
- `prices.py` — pure data source (Stooq CSV via stdlib urllib, no key, no MCP). Verifiable on its own.
- `mcp_server.py` — FastMCP server wrapping `prices.fetch_price` as the `get_stock_price` tool.
- `market.py` — our MCP *client* wrapper: connects over stdio, calls the tool, and maps the result into our unified chunk shape (with a citation id).
- register `get_stock_price` in `TOOL_SCHEMAS` + `run_tool` dispatch — flows through the same graph/executor/reflect as every other tool.

**Tradeoffs:** live data isn't local+static like the index — calls can fail (handled as readable errors). Per-call stdio connect is simpler than a persistent session (a documented simplification; production would hold one session). The model could confuse filing content with live price — the schema description must be crisp about "market prices ONLY."

## Design decisions baked into the code (confirmed with user)

1. **Our own in-process MCP client + dispatch via `run_tool`** (not Anthropic's server-side MCP connector). Keeps control flow explicit and visible — the MCP call still goes through our graph/executor and gets reflected like any other tool.
2. **Build a minimal local MCP server** wrapping a **free, no-key** price source (Stooq CSV) — not an existing public server. You build BOTH halves and see the whole protocol; no key, no third-party flakiness.
3. **Tool shape `get_stock_price(ticker, date=None)`** → latest close, or the close on `date`. One shape enables the "since filing" chain (two calls + `compare_numbers`).
4. **Unified citation across sources.** The market tool returns its result in our chunk shape with a non-chunk id like `MKT-TSLA-2026-01-29` (hyphens only, so it matches `_CITATION_RE`). `run_tool` records that id into `retrieved_ids`, so Stage 2's deterministic audit treats live data as a legitimate cited source — and the LLM groundedness check already sees the market tool's result (it reads all `tool_result` blocks). **Reflect needs no change**; live-data claims are grounded just like filing claims.

## Sanity-check experiment (fill in after build)

**(a) data source — done.** Stooq turned out to be JS-anti-bot-walled (returned a browser-challenge HTML page, not CSV), so we switched `prices.py` to Yahoo Finance's v8 chart endpoint (no key, needs a browser User-Agent). `fetch_price('TSLA')` → $391.0 (2026-06-05); `fetch_price('TSLA','2026-01-29')` → $416.56. Both latest and historical-by-date paths confirmed.

**(b) MCP round-trip — done.** `market.get_stock_price_tool('TSLA')` spawned the server over stdio and returned our unified chunk with id `MKT-TSLA-2026-06-05`; `...,'2026-01-29')` → `MKT-TSLA-2026-01-29` ($416.56). Server logs `Processing request of type CallToolRequest/ListToolsRequest` to **stderr** (harmless; stdout stays clean for the protocol).

**(c) cross-source agent run — done.** *"How has Tesla's stock moved since the 10-K was filed? … cite sources."* → tool chain **`describe_filing → search_filings → get_stock_price → get_stock_price → compare_numbers`** (5 calls, 4 turns, 0 revisions). Answer combined filing risks cited with chunk ids `[TSLA-2026-01-29-00xx]` AND the market move cited with `[MKT-TSLA-2026-01-29] [MKT-TSLA-2026-06-05]` (−$25.56 / −6.14%, computed by compare_numbers). **REFLECTION passed ✓** — confirming live-data claims pass the citation audit via their `MKT-` ids with no change to reflect (Decision 4 validated).

## Future experiments queue

- Persistent MCP session (vs per-call connect) and measure latency difference.
- Swap the local server for an existing public market MCP server — learn the client-only path.
- A question where live data and the filing *disagree* — does the agent attribute each to the right source?

## Lessons to carry forward

External capability = a tool, not a node (graph shape stays put). When you add a second evidence source, the grounding model must accommodate it — here, by giving live data a citation id and folding it into the same audit, so "grounded" means *traceable to a source*, chunk or live, not specifically "in a chunk."
