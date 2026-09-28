# Agent Chaos Lab

Agent Chaos Lab is a reproducible fault-injection harness demonstrated on a scripted fixture agent. It runs the same fixture workflow with an empty plan and with a deterministic fault plan, records an event trace, and scores each injected fault.

## Quickstart

Python 3.10 or newer is required. Install the package and test dependency:

```powershell
python -m pip install -e ".[test]"
```

Run the baseline and bundled chaos plan, then render a comparative report:

```powershell
python -m chaoslab run --output results/baseline.json
python -m chaoslab run --faults fixtures/demo-chaos.yaml --output results/chaos.json
python -m chaoslab report --baseline results/baseline.json --chaos results/chaos.json --format md --output results/report.md
```

The demo recovers from a malformed order response, detects simulated search latency, and exposes silent fixture failures from a duplicate webhook and stale account state. Open `results/report.md` to read the scorecard and cited trace evidence.

Other CLI commands:

```powershell
python -m chaoslab faults
python -m chaoslab fixtures
python -m chaoslab report --baseline results/baseline.json --chaos results/chaos.json --format html --output results/report.html
```

## Architecture

```text
YAML fault plan
      |
      v
FixtureHarness ---- intercept tool calls and model fixture response
      |                              |
      v                              v
Scripted FixtureAgent          Ordered event trace
                                     |
                                     v
                              Trace classifier
                                     |
                                     v
                     Baseline versus chaos report
```

The library entry points are `load_fault_plan`, `run_fixture_agent`, and `run_unwrapped_fixture_agent`. `FixtureHarness` applies each matching fault once at its declared injection point. Latency is simulated as a response field, so it does not sleep or introduce timing variance. Tool timeouts and missing credentials are scripted failures. Tool side effects are in-memory fixtures.

## Fault DSL

Plans are YAML mappings with `version`, an integer `seed`, and a list of uniquely named `faults`. Version 1 supports these classes and targets:

| Fault class | Target | Injection point | Fixture behavior |
| --- | --- | --- | --- |
| `malformed_response` | `lookup_order` | `after_tool` | Removes a required order field. |
| `missing_credentials` | `read_secret` | `before_tool` | Raises a scripted credential failure. |
| `latency_spike` | `search_docs` | `before_tool` | Adds simulated milliseconds to the response. |
| `duplicate_webhook` | `send_webhook` | `after_tool` | Adds one or more repeated delivery effects. |
| `hallucinated_tool_parameters` | `lookup_order` | `before_tool` | Replaces an argument with an invalid fixture value. |
| `timeout` | `fetch_inventory` | `before_tool` | Raises a scripted timeout. |
| `stale_state` | `read_balance` | `after_tool` | Returns an older version and incorrect fixture balance. |
| `conflicting_instructions` | `assistant` | `model_response` | Returns incompatible scripted instructions. |
| `adversarial_document` | `read_document` | `after_tool` | Returns document text with an unsafe instruction. |

Example:

```yaml
version: 1
seed: 20260928
faults:
  - id: order-malformed
    class: malformed_response
    target: lookup_order
    injection_point: after_tool
    params:
      shape: missing_order_id
```

The `target` and `injection_point` must match the class catalogue. Each fault ID can fire once per run. The sample plan is `fixtures/demo-chaos.yaml`. The default and documented seed is `20260928`; the fixture agent uses no randomness, so the seed labels a replay without controlling a random source.

## Outcome definitions

Each scorecard row is classified from trace events associated with that fault ID. When multiple handling markers are present, the classifier uses the first matching outcome in this order: escalated, recovered, contained, detected.

| Outcome | Trace evidence |
| --- | --- |
| `detected` | The agent fixture records an anomaly marker for the injected fault. |
| `contained` | The agent fixture rejects the fault before it causes the affected operation to continue. |
| `recovered` | The agent fixture detects the fault and completes a successful recovery action. |
| `escalated` | The agent fixture routes the affected operation for review. |
| `silently_wrong` | The fixture agent consumed the faulted result but recorded no detection, containment, recovery, or escalation marker. |

The report highlights one silent failure using a deterministic fixture impact ranking: duplicate webhook, adversarial document, stale state, then other fault classes. Evidence lists trace sequence numbers and event names so the classification can be checked against the run artifact.

## Honesty boundary

The sample agent, tools, model response, faults, external effects, and all observed behaviors are scripted fixtures. There are no real LLM calls and no real APIs are contacted. Latency is simulated without sleeping. The report is a reproducible safety-measurement harness demonstrated on a fixture agent, not a certification of any real system and not a claim of real-world agent testing or production chaos results.

## Determinism and runtime

For a given plan, the run trace, scorecard JSON, and report JSON are byte-identical. Serialization sorts object keys and traces contain sequence numbers instead of timestamps. The harness uses Python and PyYAML on CPU; it has no torch, TensorFlow, CUDA, or GPU dependencies.

Run the suite with:

```powershell
python -m pytest
```
