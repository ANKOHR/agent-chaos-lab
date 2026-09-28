from __future__ import annotations

import yaml
import pytest

from chaoslab.faults import FAULT_DEFINITIONS, FaultPlan, load_fault_plan, plan_from_mapping
from chaoslab.runner import run_fixture_agent, run_unwrapped_fixture_agent


@pytest.mark.parametrize("fault_class", sorted(FAULT_DEFINITIONS))
def test_every_fault_class_loads_yaml_and_injects_at_declared_point(tmp_path, fault_class):
    definition = FAULT_DEFINITIONS[fault_class]
    mapping = {
        "version": 1,
        "seed": 17,
        "faults": [{
            "id": f"case-{fault_class}",
            "class": fault_class,
            "target": definition["target"],
            "injection_point": definition["injection_point"],
            "params": {},
        }],
    }
    path = tmp_path / "faults.yaml"
    path.write_text(yaml.safe_dump(mapping, sort_keys=False), encoding="utf-8")
    plan = load_fault_plan(path)
    run = run_fixture_agent(plan)
    injected = [event for event in run["trace"] if event["type"] == "fault_injected"]
    assert len(injected) == 1
    assert injected[0]["fault_id"] == f"case-{fault_class}"
    assert injected[0]["target"] == definition["target"]
    assert injected[0]["details"]["fault_class"] == fault_class
    assert injected[0]["details"]["injection_point"] == definition["injection_point"]


def test_empty_yaml_plan_defaults_to_documented_seed(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("version: 1\nfaults: []\n", encoding="utf-8")
    plan = load_fault_plan(path)
    assert plan.seed == 20260928
    assert plan.faults == ()


def test_rejects_wrong_target_or_injection_point():
    with pytest.raises(ValueError, match="must target"):
        plan_from_mapping({"faults": [{"id": "bad", "class": "timeout", "target": "read_secret"}]})
    with pytest.raises(ValueError, match="must inject at"):
        plan_from_mapping({"faults": [{"id": "bad", "class": "timeout", "injection_point": "after_tool"}]})


def test_rejects_duplicate_fault_ids():
    fault = {"id": "repeat", "class": "timeout"}
    with pytest.raises(ValueError, match="Duplicate fault id"):
        plan_from_mapping({"faults": [fault, fault]})


def test_rejects_unknown_fault_class():
    with pytest.raises(ValueError, match="Unsupported fault class"):
        plan_from_mapping({"faults": [{"id": "unknown", "class": "random_failure"}]})


def test_rejects_invalid_yaml(tmp_path):
    path = tmp_path / "invalid.yaml"
    path.write_text("faults: [unclosed", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid YAML"):
        load_fault_plan(path)


def test_empty_fault_plan_is_identical_to_unwrapped_agent():
    clean = run_fixture_agent(FaultPlan(seed=20260928))
    direct = run_unwrapped_fixture_agent()
    assert clean["agent_state"] == direct["agent_state"]
    assert clean["fixture_effects"]["webhook_deliveries"] == direct["webhook_effects"]
    assert clean["summary"]["faults_injected"] == 0
    assert clean["scorecard"] == []


def test_fault_is_visible_in_trace():
    fault = {"id": "stale", "class": "stale_state"}
    run = run_fixture_agent(plan_from_mapping({"faults": [fault]}))
    event = next(event for event in run["trace"] if event["type"] == "fault_injected")
    assert event["fault_id"] == "stale"
    assert event["details"]["injection_point"] == "after_tool"
