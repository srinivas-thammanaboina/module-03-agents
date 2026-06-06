# notes/ — per-stage design notes

One markdown file per stage, **created during the whiteboard step (Rule 1) and updated after the code runs** with real results. Match the format of the Module 02 notes (`../../module-02-rag-app/notes/`) — don't invent a new structure.

## Standard skeleton (every notes file)

- **Takeaway** — one line at the very top
- **Intuition / mental model** — plain English first
- **Why the naive approach fails** — with a concrete example
- **Chosen design + tradeoffs** — what we gain, what we give up
- **Design decisions baked into the code**
- **Sanity-check experiment** — filled in *after* running
- **Future experiments queue**
- **Lessons to carry forward** — how to think about this topic generally

## Planned files (created as each stage is built)

| File | Stage | Covers |
|---|---|---|
| `agent-loop-notes.md` | 1 | the model↔tools loop, the conditional edge, why the model owns the order of operations, the turn cap |
| `tools-notes.md` | 1 | the 3 tools, schema/description quality (what makes the model pick the right one), stub→real retriever wrapper |
| `reflection-notes.md` | 2 | reflection as a node not a prompt trick, the revision loop, groundedness check, graceful give-up |
| `mcp-notes.md` | 3 | MCP host/client/server, why a tool not a node, reasoning across a private corpus + a public live source |
| `multi-agent-notes.md` | 4 | orchestrator/analyst split, A2A-style delegation, why the analyst must be stateless to parallelize |

Diagrams (mermaid) live alongside under `docs/graph-stage<N>.mmd`, re-exported whenever the graph changes shape (Rule 5).
