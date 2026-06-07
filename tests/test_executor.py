"""Tests for run_tool — the four cases that matter for the loop's robustness:
real tool, chunk-id survival, unknown tool, and a raising tool.
"""

from filing_agent.executor import run_tool


def test_compare_numbers_runs_for_real():
    """compare_numbers is deterministic and real — the result is computed."""
    out = run_tool(
        "compare_numbers",
        {"a": 78509, "b": 82419, "label_a": "prior", "label_b": "current"},
    )
    assert "direction" in out and "up" in out
    assert "3910" in out  # the actual difference, computed not guessed


def test_search_stub_keeps_chunk_id():
    """The model must see chunk ids to cite them — they survive serialization."""
    out = run_tool("search_filings", {"query": "automotive revenue", "company": "Tesla"})
    assert "STUB-0001" in out          # the stub chunk's id is present
    assert out.startswith("[")          # id leads the line, unmissable


def test_unknown_tool_returns_error_string():
    """An unknown tool is a readable error, not an exception."""
    out = run_tool("nonexistent_tool", {})
    assert out.startswith("ERROR")
    assert "unknown tool" in out


def test_raising_tool_returns_error_string():
    """A tool that raises (here: missing required args) is caught, not crashed."""
    out = run_tool("compare_numbers", {"a": 1})  # missing b/label_a/label_b
    assert out.startswith("ERROR running compare_numbers")
    assert "TypeError" in out
