from __future__ import annotations

import json
import subprocess
import sys


def test_tiny_pipeline_runs_in_literal_stage_order(tmp_path) -> None:
    output = tmp_path / "run"
    result = subprocess.run(
        [sys.executable, "scripts/run.py", "fixture", "--output", str(output)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    expected = [
        "resolved_experiment.yaml",
        "normalisation/mappings.jsonl",
        "canonical/cells.jsonl",
        "items/candidates.jsonl",
        "items/validation.jsonl",
        "items/accepted.jsonl",
        "items/bank_summary.json",
        "fold/assignments.jsonl",
        "simulation/events.jsonl",
        "kc/frozen_policy.yaml",
        "kc/projection.jsonl",
        "kc/q_matrix.csv",
        "kt/predictions.jsonl",
        "evaluation/results.json",
    ]
    assert all((output / path).is_file() for path in expected)
    results = json.loads((output / "evaluation/results.json").read_text(encoding="utf-8"))
    assert results["dataset"]["accepted_items"] == 6
    assert results["input_counts"] == {"events": 576, "predictions": 1728, "prediction_events": 576}
    assert (output / "normalisation/calls/egp_present_simple_phase1/input.json").is_file()
    assert (output / "items/generation/calls/item_001/raw_output.txt").is_file()
    assert (output / "items/validation_evidence/calls/item_001/parsed_result.json").is_file()


def test_run_one_calls_real_stages() -> None:
    for stage in ("normalisation", "generation", "validation"):
        result = subprocess.run(
            [sys.executable, "scripts/run_one.py", stage],
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "INPUT" in result.stdout and "OUTPUT" in result.stdout
