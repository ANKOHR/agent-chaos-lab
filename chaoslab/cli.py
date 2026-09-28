"""Command line interface for the Agent Chaos Lab fixture harness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .faults import DEFAULT_SEED, FAULT_DEFINITIONS, FaultPlan, load_fault_plan
from .report import build_report, canonical_json, render_html, render_markdown
from .runner import run_fixture_agent

FAULT_DESCRIPTIONS = {
    "malformed_response": "Return a response missing a required order field.",
    "missing_credentials": "Make the fixture credential unavailable.",
    "latency_spike": "Attach simulated latency to a tool response without sleeping.",
    "duplicate_webhook": "Repeat a fixture webhook side effect.",
    "hallucinated_tool_parameters": "Replace a tool argument with an invalid fixture value.",
    "timeout": "Raise a scripted timeout before a fixture tool call completes.",
    "stale_state": "Return an older fixture account version with an incorrect balance.",
    "conflicting_instructions": "Return two incompatible scripted instructions.",
    "adversarial_document": "Return fixture document content containing an unsafe instruction.",
}


def _write_or_print(content: str, output: str | None) -> None:
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(content)


def _read_json(path: str) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError(f"{path} is not an Agent Chaos Lab run artifact.")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chaoslab", description="Deterministic chaos fixtures for a scripted agent.")
    commands = parser.add_subparsers(dest="command", required=True)

    faults = commands.add_parser("faults", help="List the supported scripted fault classes.")
    faults.add_argument("--format", choices=("json",), default="json")

    fixtures = commands.add_parser("fixtures", help="List bundled fixture scenarios and plans.")
    fixtures.add_argument("--write-demo-plan", metavar="PATH", help="Write the bundled multi-fault YAML plan to PATH.")

    run = commands.add_parser("run", help="Run the fixture agent through the injection harness.")
    run.add_argument("--scenario", choices=("demo",), default="demo")
    run.add_argument("--faults", metavar="YAML", help="Fault plan YAML. Omit for a clean baseline run.")
    run.add_argument("--output", metavar="JSON", help="Write the run artifact to a file.")

    report = commands.add_parser("report", help="Compare baseline and chaos run artifacts.")
    report.add_argument("--baseline", required=True, metavar="JSON")
    report.add_argument("--chaos", required=True, metavar="JSON")
    report.add_argument("--format", choices=("json", "md", "html"), default="md")
    report.add_argument("--output", metavar="PATH")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "faults":
            items = [
                {
                    "class": name,
                    "target": definition["target"],
                    "injection_point": definition["injection_point"],
                    "description": FAULT_DESCRIPTIONS[name],
                }
                for name, definition in FAULT_DEFINITIONS.items()
            ]
            _write_or_print(canonical_json({"faults": items}), None)
            return 0

        if args.command == "fixtures":
            result = {
                "scenarios": ["demo"],
                "demo_fault_plan": "fixtures/demo-chaos.yaml",
                "default_seed": DEFAULT_SEED,
                "agent": "scripted fixture, no real LLM calls",
            }
            if args.write_demo_plan:
                source = Path(__file__).resolve().parent / "data" / "demo-chaos.yaml"
                destination = Path(args.write_demo_plan)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
                result["written_plan"] = str(destination)
            _write_or_print(canonical_json(result), None)
            return 0

        if args.command == "run":
            plan = load_fault_plan(args.faults) if args.faults else FaultPlan(seed=DEFAULT_SEED)
            _write_or_print(canonical_json(run_fixture_agent(plan, args.scenario)), args.output)
            return 0

        if args.command == "report":
            report_data = build_report(_read_json(args.baseline), _read_json(args.chaos))
            if args.format == "json":
                output = canonical_json(report_data)
            elif args.format == "html":
                output = render_html(report_data)
            else:
                output = render_markdown(report_data)
            _write_or_print(output, args.output)
            return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(2, f"chaoslab: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
