"""Stage 0 smoke test: prove the Claude pipe works before any agent logic.

If this prints a reply, the env, the key, the client, and the model string are
all good — so when a later graph misbehaves, we know the plumbing isn't the cause.

Run from the repo root:
    .venv/bin/python scripts/smoke_test.py
"""

import pathlib
import sys

# Make `filing_agent` importable when this file is run directly (Python only puts
# the script's own dir on the path, not the repo root).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from filing_agent.llm import call_model  # noqa: E402  (after the path tweak)


def main() -> None:
    resp = call_model([{"role": "user", "content": "Reply with exactly: OK"}])
    text = "".join(block.text for block in resp.content if block.type == "text")
    print("model       :", resp.model)
    print("stop_reason :", resp.stop_reason)
    print("reply       :", text)


if __name__ == "__main__":
    main()
