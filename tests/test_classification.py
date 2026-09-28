from __future__ import annotations

import pytest

from chaoslab.faults import plan_from_mapping
from chaoslab.runner import run_fixture_agent


@pytest.mark.parametrize(("fault_class", "expected"), [
    ("malformed_response", "recovered"),
    ("missing_credentials", "escalated"),
    ("latency_spike", "detected"),
    ("duplicate_webhook", "silently_wrong"),
    ("hallucinated_tool_parameters", "contained"),
    ("timeout", "escalated"),
    ("stale_state", "silently_wrong"),
    ("conflicting_instructions", "escalated"),
    ("adversarial_document", "silently_wrong"),
])
def test_trace_classifier_scores_fixture_behavior(fault_class, expected):
    run = run_fixture_agent(plan_from_mapping({"faults": [{"id": "case", "class": fault_class}]}))
    row = run["scorecard"][0]
    assert row["fault_class"] == fault_class
    assert row["outcome"] == expected
    assert row["evidence"]
    assert any(item["event"] == "fault_injected" for item in row["evidence"])


def test_unhandled_fault_is_silently_wrong_with_evidence():
    run = run_fixture_agent(plan_from_mapping({"faults": [{"id": "old-balance", "class": "stale_state"}]}))
    row = run["scorecard"][0]
    assert row["outcome"] == "silently_wrong"
    assert [item["event"] for item in row["evidence"]] == ["fault_injected", "agent_consumed_result"]
    assert row["evidence"][1]["details"] == {"tool": "read_balance", "balance": 150, "version": 3}
