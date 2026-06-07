"""Export the compiled graph's structure as mermaid — the win-condition check.

Prints LangGraph's own diagram of what it compiled and saves it to
docs/graph-stage1.mmd, so you can compare your from-memory drawing against the
real thing.

Run from the repo root:
    .venv/bin/python scripts/draw_graph.py
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from filing_agent.graph import app  # noqa: E402

OUT_PATH = pathlib.Path(__file__).resolve().parent.parent / "docs" / "graph-stage1.mmd"


def main() -> None:
    mermaid = app.get_graph().draw_mermaid()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(mermaid)
    print(mermaid)
    print(f"\nSaved to {OUT_PATH.relative_to(pathlib.Path.cwd())}")


if __name__ == "__main__":
    main()
