"""Stage 3 (data source): fetch a stock close price — no API key, stdlib only.

The pure data layer behind the MCP market tool: it knows how to get a price from
a free source and NOTHING about MCP or our agent. Keeping it separate lets us
verify "does the price source work?" independently of the MCP plumbing.

Source: Yahoo Finance's v8 chart endpoint (no key). We originally tried Stooq but
it now sits behind a JavaScript anti-bot challenge that returns HTML, not CSV.
  latest:     /v8/finance/chart/TSLA?range=5d&interval=1d   -> meta.regularMarketPrice
  historical: /v8/finance/chart/TSLA?period1=..&period2=..  -> per-day closes
A browser-like User-Agent is required or Yahoo 401s.
"""

import datetime
import json
import urllib.request
from typing import Any, Optional

_TIMEOUT = 10  # seconds — live calls can hang; fail fast with a readable note
_HEADERS = {"User-Agent": "Mozilla/5.0"}
_BASE = "https://query1.finance.yahoo.com/v8/finance/chart/"


def _get_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read())


def _utc_date(ts: int) -> str:
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d")


def fetch_price(ticker: str, date: Optional[str] = None) -> dict[str, Any]:
    """Return the closing price for `ticker` — latest, or on `date` (YYYY-MM-DD).

    For a date, returns the most recent trading-day close on or before it (so a
    weekend/holiday filing date still resolves). Success → {ticker, date, close,
    source}. No data or a network error → {ticker, date, close: None, note}.
    Never raises for a missing price — the agent should see a readable note.
    """
    sym = ticker.strip().upper()
    try:
        if date:
            anchor = datetime.datetime.strptime(date, "%Y-%m-%d")
            # Widen the window back a few days so a non-trading filing date still
            # resolves to the last trading day on/before it.
            p1 = int((anchor - datetime.timedelta(days=4)).timestamp())
            p2 = int((anchor + datetime.timedelta(days=1)).timestamp())
            result = _get_json(f"{_BASE}{sym}?period1={p1}&period2={p2}&interval=1d")
            res = result["chart"]["result"][0]
            timestamps = res.get("timestamp") or []
            closes = res["indicators"]["quote"][0].get("close") or []
            best = None
            for ts, close in zip(timestamps, closes):
                if close is None:
                    continue
                day = _utc_date(ts)
                if day <= date:  # last trading day on/before the requested date
                    best = (day, close)
            if best:
                return {
                    "ticker": sym,
                    "date": best[0],
                    "close": round(float(best[1]), 2),
                    "source": "finance.yahoo.com",
                }
            return {
                "ticker": sym,
                "date": date,
                "close": None,
                "note": f"No trading-day close on/before {date} for {sym}.",
            }

        meta = _get_json(f"{_BASE}{sym}?range=5d&interval=1d")["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice")
        if price is not None:
            ts = meta.get("regularMarketTime")
            return {
                "ticker": sym,
                "date": _utc_date(ts) if ts else None,
                "close": round(float(price), 2),
                "source": "finance.yahoo.com",
            }
        return {
            "ticker": sym,
            "date": None,
            "close": None,
            "note": f"No latest price for {sym} (unknown ticker or source unavailable).",
        }
    except Exception as exc:  # noqa: BLE001 — network/parse failure → note, never crash
        return {
            "ticker": sym,
            "date": date,
            "close": None,
            "note": f"Price lookup failed: {type(exc).__name__}: {exc}",
        }
