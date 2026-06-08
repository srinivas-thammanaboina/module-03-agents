"""Tests for run_tool — the cases that matter for the loop's robustness:
real tool, chunk-id survival (string + structured), unknown tool, raising tool.
"""

from filing_agent.executor import run_tool


def test_compare_numbers_runs_for_real():
    """compare_numbers is deterministic and real — the result is computed."""
    out = run_tool(
        "compare_numbers",
        {"a": 78509, "b": 82419, "label_a": "prior", "label_b": "current"},
    )
    assert "direction" in out.content and "up" in out.content
    assert "3910" in out.content      # the actual difference, computed not guessed
    assert out.retrieved_ids == []    # not a search → no chunk ids


def test_search_stub_keeps_chunk_id():
    """The model must see chunk ids to cite them — in the string AND structured."""
    out = run_tool("search_filings", {"query": "automotive revenue", "company": "Tesla"})
    assert "STUB-0001" in out.content       # id present in the model-readable string
    assert out.content.startswith("[")      # id leads the line, unmissable
    assert "STUB-0001" in out.retrieved_ids  # and captured for Stage 2's audit


def test_unknown_tool_returns_error_string():
    """An unknown tool is a readable error, not an exception."""
    out = run_tool("nonexistent_tool", {})
    assert out.content.startswith("ERROR")
    assert "unknown tool" in out.content
    assert out.retrieved_ids == []


def test_raising_tool_returns_error_string():
    """A tool that raises (here: missing required args) is caught, not crashed."""
    out = run_tool("compare_numbers", {"a": 1})  # missing b/label_a/label_b
    assert out.content.startswith("ERROR running compare_numbers")
    assert "TypeError" in out.content
