from __future__ import annotations

import json
from pathlib import Path

from chaoslab.faults import load_fault_plan
from chaoslab.report import build_report, canonical_json, render_html, render_markdown
from chaoslab.runner import run_fixture_agent

ROOT = Path(__file__).resolve().parents[1]


def make_report():
    baseline = run_fixture_agent()
    chaos = run_fixture_agent(load_fault_plan(ROOT / "fixtures" / "demo-chaos.yaml"))
    return build_report(baseline, chaos)


def test_report_has_comparison_scorecard_and_worst_silent_failure():
    report = make_report()
    markdown = render_markdown(report)
    assert "Baseline versus chaos" in markdown
    assert "Degradation scorecard" in markdown
    assert "order-malformed" in markdown
    assert "**recovered**" in markdown
    assert "**detected**" in markdown
    assert "Worst silent failure" in markdown
    assert "webhook-duplicate" in markdown
    assert "FIXTURE-DRIVEN DEMONSTRATION" in markdown
    assert report["worst_silent_failure"]["fault_class"] == "duplicate_webhook"


def test_same_plan_produces_byte_identical_scorecard_and_report_json():
    plan = load_fault_plan(ROOT / "fixtures" / "demo-chaos.yaml")
    first_run = run_fixture_agent(plan)
    second_run = run_fixture_agent(plan)
    assert canonical_json(first_run["scorecard"]).encode() == canonical_json(second_run["scorecard"]).encode()
    first_report = canonical_json(build_report(run_fixture_agent(), first_run)).encode()
    second_report = canonical_json(build_report(run_fixture_agent(), second_run)).encode()
    assert first_report == second_report
    json.loads(first_report)


def test_html_report_escapes_fixture_content_and_has_banner():
    html = render_html(make_report())
    assert "FIXTURE-DRIVEN DEMONSTRATION" in html
    assert "Worst silent failure" in html
    assert "<table>" in html


def test_no_em_dash_in_project_text_and_source_files():
    forbidden = chr(0x2014)
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or ".pytest_cache" in path.parts or "results" in path.parts:
            continue
        if path.name in {"cl-launch.py", "cl-prompt.txt", "cl-codex.log"}:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        assert forbidden not in content, f"Unexpected em dash in {path.relative_to(ROOT)}"
