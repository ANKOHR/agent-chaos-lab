"""Build stable comparative reports from serialized run artifacts."""

from __future__ import annotations

import html
import json
from typing import Any

BANNER = (
    "FIXTURE-DRIVEN DEMONSTRATION: the harness, agent, tools, and faults are scripted fixtures. "
    "No real LLM calls or APIs are used. This is not a certification or production chaos result."
)

SILENT_IMPACT_RANK = {
    "duplicate_webhook": 100,
    "adversarial_document": 90,
    "stale_state": 80,
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def build_report(baseline: dict[str, Any], chaos: dict[str, Any]) -> dict[str, Any]:
    baseline_state = baseline.get("agent_state", {})
    chaos_state = chaos.get("agent_state", {})
    changed_fields = sorted(
        key for key in set(baseline_state) | set(chaos_state)
        if baseline_state.get(key) != chaos_state.get(key)
    )
    scorecard = chaos.get("scorecard", [])
    counts = {outcome: sum(item.get("outcome") == outcome for item in scorecard) for outcome in (
        "detected", "contained", "recovered", "escalated", "silently_wrong"
    )}
    silent = [item for item in scorecard if item.get("outcome") == "silently_wrong"]
    trace_order = {
        event.get("fault_id"): event.get("seq", 0)
        for event in chaos.get("trace", [])
        if event.get("type") == "fault_injected"
    }
    worst = None
    if silent:
        worst = sorted(
            silent,
            key=lambda item: (-SILENT_IMPACT_RANK.get(item.get("fault_class"), 50), trace_order.get(item.get("fault_id"), 0)),
        )[0]
    return {
        "schema_version": 1,
        "banner": BANNER,
        "baseline": {
            "scenario": baseline.get("scenario"),
            "summary": baseline.get("summary", {}),
            "agent_state": baseline_state,
        },
        "chaos": {
            "scenario": chaos.get("scenario"),
            "seed": chaos.get("seed"),
            "summary": chaos.get("summary", {}),
            "agent_state": chaos_state,
        },
        "comparison": {"changed_agent_state_fields": changed_fields},
        "scorecard_counts": counts,
        "scorecard": scorecard,
        "worst_silent_failure": worst,
    }


def render_markdown(report: dict[str, Any]) -> str:
    counts = report["scorecard_counts"]
    lines = [
        "# Agent Chaos Lab report",
        "",
        f"> {report['banner']}",
        "",
        "## Baseline versus chaos",
        "",
        f"Baseline tool calls: {report['baseline']['summary'].get('tool_calls', 0)}",
        f"Chaos tool calls: {report['chaos']['summary'].get('tool_calls', 0)}",
        f"Seed: {report['chaos'].get('seed')}",
        f"Changed fixture state fields: {', '.join(report['comparison']['changed_agent_state_fields']) or 'none'}",
        "",
        "## Degradation scorecard",
        "",
        "| Fault | Class | Outcome | Trace evidence |",
        "| --- | --- | --- | --- |",
    ]
    for item in report["scorecard"]:
        evidence = ", ".join(f"#{part['seq']} {part['event']}" for part in item["evidence"])
        lines.append(f"| {item['fault_id']} | {item['fault_class']} | **{item['outcome']}** | {evidence} |")
    lines.extend(["", "Outcome counts: " + ", ".join(f"{name}={count}" for name, count in counts.items()), ""])
    worst = report.get("worst_silent_failure")
    if worst:
        evidence = ", ".join(f"#{part['seq']} {part['event']}" for part in worst["evidence"])
        lines.extend([
            "## Worst silent failure",
            "",
            f"**{worst['fault_id']} ({worst['fault_class']})** was ranked highest by the fixture report's impact heuristic. "
            "The trace contains no detection, containment, recovery, or escalation marker for this fault.",
            "",
            f"Evidence: {evidence}.",
            "",
        ])
    else:
        lines.extend(["## Worst silent failure", "", "No silently wrong outcome was recorded.", ""])
    lines.extend([
        "## Honest interpretation",
        "",
        "This report measures only scripted fixture behavior. It does not certify a real agent or report production chaos testing.",
        "",
    ])
    return "\n".join(lines)


def render_html(report: dict[str, Any]) -> str:
    rows = []
    for item in report["scorecard"]:
        evidence = ", ".join(f"#{part['seq']} {part['event']}" for part in item["evidence"])
        rows.append(
            "<tr>"
            f"<td>{html.escape(item['fault_id'])}</td>"
            f"<td>{html.escape(item['fault_class'])}</td>"
            f"<td>{html.escape(item['outcome'])}</td>"
            f"<td>{html.escape(evidence)}</td></tr>"
        )
    worst = report.get("worst_silent_failure")
    if worst:
        highlight = (
            f"<section class=\"worst\"><h2>Worst silent failure</h2><p><strong>"
            f"{html.escape(worst['fault_id'])} ({html.escape(worst['fault_class'])})"
            "</strong> was ranked highest by the fixture impact heuristic.</p></section>"
        )
    else:
        highlight = "<section><h2>Worst silent failure</h2><p>No silently wrong outcome was recorded.</p></section>"
    return (
        "<!doctype html>\n<html lang=\"en\"><meta charset=\"utf-8\"><title>Agent Chaos Lab report</title>\n"
        "<style>body{font:16px system-ui,sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem}"
        ".banner{padding:1rem;background:#fff2cc;border:1px solid #9b7200}table{border-collapse:collapse;width:100%}"
        "td,th{padding:.5rem;border:1px solid #bbb;text-align:left}.worst{padding:1rem;background:#ffe4e4}</style>\n"
        f"<body><h1>Agent Chaos Lab report</h1><p class=\"banner\">{html.escape(report['banner'])}</p>\n"
        f"<h2>Baseline versus chaos</h2><p>Seed: {html.escape(str(report['chaos'].get('seed')))}</p>\n"
        "<h2>Degradation scorecard</h2><table><thead><tr><th>Fault</th><th>Class</th><th>Outcome</th><th>Trace evidence</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>{highlight}<p>This report measures only scripted fixture behavior. "
        "It does not certify a real agent or report production chaos testing.</p></body></html>\n"
    )
