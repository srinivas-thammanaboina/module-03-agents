"""Stage 3: the MCP CLIENT side — our agent's connection to the market server.

Decision 1: we run our OWN client and dispatch through run_tool (not Anthropic's
server-side MCP connector), so the call stays inside our graph and gets reflected
like any other tool. For simplicity (a learning project) we connect per call over
stdio — spawn the server, call the tool, tear down. A production agent would hold
one persistent session.

Decision 4: the result is mapped into our unified chunk shape with an `MKT-...`
citation id (hyphens only, so it matches the Stage 2 citation regex), so live data
is grounded and cited exactly like a filing chunk — no change needed in reflect.
"""

import asyncio
import json
import pathlib
import sys
from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_SERVER = pathlib.Path(__file__).resolve().parent / "mcp_server.py"


async def _call(ticker: str, date: Optional[str]) -> dict[str, Any]:
    """One MCP round-trip: launch the server, call the tool, return its dict."""
    params = StdioServerParameters(command=sys.executable, args=[str(_SERVER)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "get_stock_price", {"ticker": ticker, "date": date}
            )
            # FastMCP returns the dict as structured output and/or JSON text.
            structured = getattr(result, "structuredContent", None)
            if isinstance(structured, dict) and "ticker" in structured:
                return structured
            text = "".join(getattr(c, "text", "") for c in result.content)
            return json.loads(text)


def get_stock_price_tool(ticker: str, date: Optional[str] = None) -> Any:
    """Sync tool entrypoint dispatched by run_tool.

    Returns our unified chunk shape (list of one chunk WITH an `MKT-` id) on a
    real price, so the executor captures the id and the model can cite it. On a
    no-data/error result, returns the raw note dict (no citable id).
    """
    data = asyncio.run(_call(ticker, date))
    if data.get("close") is None:
        return data  # note dict → executor JSON-dumps it; nothing to cite

    sym = data.get("ticker", ticker.upper())
    used = data.get("date") or "LATEST"
    citation_id = f"MKT-{sym}-{used}"  # hyphens only → matches _CITATION_RE
    text = (
        f"{sym} closing price on {used}: ${data['close']} "
        f"(source: {data.get('source')})."
    )
    return [
        {
            "id": citation_id,
            "text": text,
            "company": sym,
            "section": "market",
            "filing_date": used,
            "source_url": f"https://finance.yahoo.com/quote/{sym}",
            "score": 1.0,
        }
    ]
