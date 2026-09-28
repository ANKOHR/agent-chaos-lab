"""Run the scripted agent through either the harness or direct fixture tools."""

from __future__ import annotations

from typing import Any

from .agent import FixtureAgent
from .classify import classify_faults
from .faults import DEFAULT_SEED, FaultPlan
from .harness import DirectFixtureRuntime, FixtureHarness


def run_fixture_agent(plan: FaultPlan | None = None, scenario: str = "demo") -> dict[str, Any]:
    if scenario != "demo":
        raise ValueError(f"Unknown fixture scenario: {scenario}")
    effective_plan = plan or FaultPlan(seed=DEFAULT_SEED)
    harness = FixtureHarness(effective_plan)
    state = FixtureAgent().run(harness)
    harness._record("agent_run_completed", details={"scenario": scenario})
    raw_plan = effective_plan.to_dict()
    return {
        "schema_version": 1,
        "scenario": scenario,
        "seed": effective_plan.seed,
        "plan": raw_plan,
        "trace": harness.trace,
        "agent_state": state,
        "fixture_effects": {"webhook_deliveries": list(harness.webhook_effects)},
        "summary": {
            "tool_calls": sum(event["type"] == "tool_call_started" for event in harness.trace),
            "faults_injected": sum(event["type"] == "fault_injected" for event in harness.trace),
        },
        "scorecard": classify_faults(raw_plan, harness.trace),
    }


def run_unwrapped_fixture_agent(scenario: str = "demo") -> dict[str, Any]:
    """Run the same scripted agent against the tools without interception."""
    if scenario != "demo":
        raise ValueError(f"Unknown fixture scenario: {scenario}")
    runtime = DirectFixtureRuntime()
    state = FixtureAgent().run(runtime)
    return {"scenario": scenario, "agent_state": state, "webhook_effects": runtime.webhook_effects}
