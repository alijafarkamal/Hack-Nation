"""MVD gate: run_agent on India-focused demo queries (needs full stack)."""

import os

import pytest

requires_creds = pytest.mark.skipif(
    not (os.getenv("DATABRICKS_HOST") and os.getenv("DATABRICKS_TOKEN")),
    reason="End-to-end requires Databricks + Genie + VS + LLM",
)

# Rubric-style queries (challenge brief)
DEMO_QUERIES = [
    "How many hospitals in Bihar have trust_flag VERIFIED?",
    "Show facilities in Maharashtra mentioning oncology in specialties or description",
    "Which records look suspicious: claim surgery or ICU but empty equipment array?",
    "Extract procedures and equipment signals for a rural Bihar clinic from the text fields",
    "Which states look like cardiology deserts based on the specialties field?",
]


@requires_creds
def test_mvd_at_least_3_demo_queries():
    from src.graph import run_agent

    successes = 0
    failures: list[str] = []
    for q in DEMO_QUERIES:
        try:
            answer = run_agent(q)
            if answer and len(answer) > 20 and "LLM unavailable" not in answer:
                successes += 1
            else:
                failures.append(f"  - {q!r} -> short or unavailable")
        except Exception as e:
            failures.append(f"  - {q!r} -> {type(e).__name__}: {e}")
    assert successes >= 3, "Expected >=3/5 working demos.\n" + "\n".join(failures)
