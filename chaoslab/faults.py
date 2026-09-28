"""Fault plan schema, validation, and YAML loading."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_SEED = 20260928

FAULT_DEFINITIONS: dict[str, dict[str, str]] = {
    "malformed_response": {"target": "lookup_order", "injection_point": "after_tool"},
    "missing_credentials": {"target": "read_secret", "injection_point": "before_tool"},
    "latency_spike": {"target": "search_docs", "injection_point": "before_tool"},
    "duplicate_webhook": {"target": "send_webhook", "injection_point": "after_tool"},
    "hallucinated_tool_parameters": {"target": "lookup_order", "injection_point": "before_tool"},
    "timeout": {"target": "fetch_inventory", "injection_point": "before_tool"},
    "stale_state": {"target": "read_balance", "injection_point": "after_tool"},
    "conflicting_instructions": {"target": "assistant", "injection_point": "model_response"},
    "adversarial_document": {"target": "read_document", "injection_point": "after_tool"},
}


@dataclass(frozen=True)
class FaultSpec:
    id: str
    fault_class: str
    target: str
    injection_point: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "class": self.fault_class,
            "target": self.target,
            "injection_point": self.injection_point,
            "params": self.params,
        }


@dataclass(frozen=True)
class FaultPlan:
    seed: int = DEFAULT_SEED
    faults: tuple[FaultSpec, ...] = ()
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "seed": self.seed, "faults": [fault.to_dict() for fault in self.faults]}


def plan_from_mapping(data: Any) -> FaultPlan:
    if not isinstance(data, dict):
        raise ValueError("Fault plan must be a YAML mapping.")
    unknown = set(data) - {"version", "seed", "faults"}
    if unknown:
        raise ValueError(f"Unknown fault plan fields: {', '.join(sorted(unknown))}.")
    version = data.get("version", 1)
    seed = data.get("seed", DEFAULT_SEED)
    raw_faults = data.get("faults", [])
    if version != 1:
        raise ValueError("Only fault plan version 1 is supported.")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("The plan seed must be an integer.")
    if not isinstance(raw_faults, list):
        raise ValueError("The faults field must be a list.")

    faults: list[FaultSpec] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_faults):
        if not isinstance(raw, dict):
            raise ValueError(f"Fault at index {index} must be a mapping.")
        extra = set(raw) - {"id", "class", "target", "injection_point", "params"}
        if extra:
            raise ValueError(f"Unknown fields in fault at index {index}: {', '.join(sorted(extra))}.")
        fault_id = raw.get("id")
        fault_class = raw.get("class")
        if not isinstance(fault_id, str) or not fault_id.strip():
            raise ValueError(f"Fault at index {index} needs a non-empty id.")
        if fault_id in seen_ids:
            raise ValueError(f"Duplicate fault id: {fault_id}.")
        if not isinstance(fault_class, str) or fault_class not in FAULT_DEFINITIONS:
            raise ValueError(f"Unsupported fault class: {fault_class!r}.")
        expected = FAULT_DEFINITIONS[fault_class]
        target = raw.get("target", expected["target"])
        injection_point = raw.get("injection_point", expected["injection_point"])
        if target != expected["target"]:
            raise ValueError(f"Fault {fault_id} class {fault_class} must target {expected['target']}.")
        if injection_point != expected["injection_point"]:
            raise ValueError(f"Fault {fault_id} class {fault_class} must inject at {expected['injection_point']}.")
        params = raw.get("params", {})
        if not isinstance(params, dict):
            raise ValueError(f"Fault {fault_id} params must be a mapping.")
        if any(not isinstance(key, str) for key in params):
            raise ValueError(f"Fault {fault_id} parameter names must be strings.")
        try:
            json.dumps(params, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Fault {fault_id} params must contain JSON-compatible values.") from exc
        faults.append(FaultSpec(fault_id, fault_class, target, injection_point, params))
        seen_ids.add(fault_id)
    return FaultPlan(seed=seed, faults=tuple(faults), version=version)


def load_fault_plan(path: str | Path) -> FaultPlan:
    """Load and validate a version 1 YAML fault plan."""
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML fault plan: {exc}") from exc
    return plan_from_mapping(data)
