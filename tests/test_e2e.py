"""Phase 2.5 MVD Gate — end-to-end demo query validation.

At least 3 of 5 demo queries must return a non-empty answer.
This is the Minimum Viable Demo gate — do NOT proceed to Phase 3
unless this passes.

Usage: pytest tests/test_e2e.py -v
"""

import pytest

DEMO_QUERIES = [
    "How many hospitals have cardiology?",
    "What services does Korle Bu Teaching Hospital offer?",
    "Which facilities claim surgery but lack equipment?",
    "Extract capabilities for Tamale Teaching Hospital",
    "Where are ophthalmology deserts in Ghana?",
]


def test_mvd_at_least_3_queries_work():
    """At least 3 of 5 demo queries must return a non-empty answer.

    This is the Minimum Viable Demo gate. If this fails, stop and debug
    the LangGraph graph + Databricks connection before moving to Phase 3.
    """
    from src.graph import run_agent

    successes = 0
    failures = []

    for q in DEMO_QUERIES:
        try:
            answer = run_agent(q)
            if answer and len(answer) > 20:
                successes += 1
            else:
                failures.append(f"  - '{q}' → empty or too short answer")
        except Exception as e:
            failures.append(f"  - '{q}' → {type(e).__name__}: {e}")

    failure_report = "\n".join(failures) if failures else ""
    assert successes >= 3, (
        f"Only {successes}/5 demo queries worked. Fix before moving on.\n"
        f"Failures:\n{failure_report}"
    )
