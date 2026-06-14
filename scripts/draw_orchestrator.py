"""Export the orchestrator graph's structure as mermaid → docs/graph-stage4.mmd.

The companion to draw_graph.py (which draws the analyst). Together they're the
"two graphs" of Stage 4. No API calls — just the compiled structure.

Run from the repo root:
    .venv/bin/python scripts/draw_orchestrator.py
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from filing_agent.orchestrator import orchestrator  # noqa: E402

OUT_PATH = pathlib.Path(__file__).resolve().parent.parent / "docs" / "graph-stage4.mmd"


def main() -> None:
    mermaid = orchestrator.get_graph().draw_mermaid()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(mermaid)
    print(mermaid)
    print(f"\nSaved to {OUT_PATH.relative_to(pathlib.Path.cwd())}")


if __name__ == "__main__":
    main()
