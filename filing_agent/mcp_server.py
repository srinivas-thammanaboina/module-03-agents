"""Stage 3: a minimal MCP SERVER exposing live market data as a tool.

FastMCP over stdio. The host (our agent) launches this as a subprocess and speaks
the MCP protocol to it. It wraps filing_agent.prices.fetch_price — clean layering:
the server knows the protocol, prices.py knows the data source, neither knows the
agent.

Run directly to sanity-check it imports/starts (it then waits on stdio for a
client; Ctrl-C to exit):  .venv/bin/python filing_agent/mcp_server.py
"""

import pathlib
import sys

# Make `filing_agent` importable when this file is launched directly as a
# subprocess (the script's own dir is on the path, not the repo root).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from filing_agent.prices import fetch_price  # noqa: E402

mcp = FastMCP("filing-agent-market")


@mcp.tool()
def get_stock_price(ticker: str, date: str | None = None) -> dict:
    """Get a US stock's daily CLOSING price — latest, or on a specific date.

    Args:
        ticker: e.g. "TSLA", "AAPL", "NVDA".
        date: optional "YYYY-MM-DD"; omit for the latest price. For a date, you
            get the most recent trading-day close on or before it.

    Returns {ticker, date, close, source} or {.., close: null, note}.
    """
    return fetch_price(ticker, date)


if __name__ == "__main__":
    mcp.run()  # stdio transport
