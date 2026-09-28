"""Trace-based five-outcome classifier."""

from __future__ import annotations

from typing import Any

OUTCOMES = ("detected", "contained", "recovered", "escalated", "silently_wrong")


def classify_faults(plan: dict[str, Any], trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scorecard: list[dict[str, Any]] = []
    for fault in plan.get("faults", []):
        related = [event for event in trace if event.get("fault_id") == fault["id"]]
        types = {event.get("type") for event in related}
        if "agent_escalated" in types:
            outcome = "escalated"
        elif "recovery_completed" in types:
            outcome = "recovered"
        elif "fault_contained" in types:
            outcome = "contained"
        elif "agent_detected" in types:
            outcome = "detected"
        else:
            outcome = "silently_wrong"
        evidence_events = [event for event in related if event.get("type") in {
            "fault_injected", "agent_detected", "fault_contained", "recovery_completed",
            "agent_escalated", "external_effect_duplicate", "tool_result_returned",
            "model_response_returned", "agent_consumed_result",
        }]
        if not evidence_events:
            evidence_events = related[:1]
        scorecard.append({
            "fault_id": fault["id"],
            "fault_class": fault["class"],
            "outcome": outcome,
            "evidence": [
                {"seq": event["seq"], "event": event["type"], "details": event.get("details", {})}
                for event in evidence_events
            ],
        })
    return scorecard
