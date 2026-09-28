from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def invoke(*args):
    return subprocess.run(
        [sys.executable, "-m", "chaoslab", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )


def test_faults_subcommand_lists_all_classes():
    result = invoke("faults")
    classes = [item["class"] for item in json.loads(result.stdout)["faults"]]
    assert len(classes) == 9
    assert "adversarial_document" in classes


def test_fixtures_subcommand_lists_demo():
    result = invoke("fixtures")
    assert json.loads(result.stdout)["scenarios"] == ["demo"]


def test_fixtures_subcommand_writes_bundled_plan(tmp_path):
    destination = tmp_path / "copied" / "demo.yaml"
    result = invoke("fixtures", "--write-demo-plan", str(destination))
    assert destination.read_text(encoding="utf-8") == (ROOT / "fixtures" / "demo-chaos.yaml").read_text(encoding="utf-8")
    assert json.loads(result.stdout)["written_plan"] == str(destination)


def test_run_subcommand_writes_real_baseline_and_chaos_artifacts(tmp_path):
    baseline = tmp_path / "baseline.json"
    chaos = tmp_path / "chaos.json"
    invoke("run", "--output", str(baseline))
    invoke("run", "--faults", "fixtures/demo-chaos.yaml", "--output", str(chaos))
    assert json.loads(baseline.read_text(encoding="utf-8"))["summary"]["faults_injected"] == 0
    chaos_data = json.loads(chaos.read_text(encoding="utf-8"))
    assert chaos_data["summary"]["faults_injected"] == 4
    assert any(row["outcome"] == "silently_wrong" for row in chaos_data["scorecard"])


def test_report_subcommand_renders_markdown_and_json(tmp_path):
    baseline = tmp_path / "baseline.json"
    chaos = tmp_path / "chaos.json"
    markdown = tmp_path / "report.md"
    report_json = tmp_path / "report.json"
    invoke("run", "--output", str(baseline))
    invoke("run", "--faults", "fixtures/demo-chaos.yaml", "--output", str(chaos))
    invoke("report", "--baseline", str(baseline), "--chaos", str(chaos), "--format", "md", "--output", str(markdown))
    invoke("report", "--baseline", str(baseline), "--chaos", str(chaos), "--format", "json", "--output", str(report_json))
    assert "Worst silent failure" in markdown.read_text(encoding="utf-8")
    assert json.loads(report_json.read_text(encoding="utf-8"))["worst_silent_failure"]["fault_class"] == "duplicate_webhook"
