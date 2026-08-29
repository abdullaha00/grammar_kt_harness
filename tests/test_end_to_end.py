from __future__ import annotations

import json
import subprocess
import sys

from scripts import run as pipeline_runner


def test_tiny_pipeline_runs_in_literal_stage_order(tmp_path) -> None:
    output = tmp_path / "run"
    result = subprocess.run(
        [sys.executable, "scripts/run.py", "--fixture", "--output", str(output)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    expected = [
        "run_settings.json",
        "normalisation/mappings.jsonl",
        "canonical/cells.jsonl",
        "items/candidates.jsonl",
        "items/validation.jsonl",
        "items/validator_accepted.jsonl",
        "items/selected_bank.jsonl",
        "items/bank_summary.json",
        "fold/assignments.jsonl",
        "kc/candidate_inventory.json",
        "simulation/events.jsonl",
        "simulation/oracle_debug.json",
        "kc/frozen_policy.yaml",
        "kc/selection_trace.json",
        "kc/projection.jsonl",
        "kc/q_matrix.csv",
        "kt/predictions.jsonl",
        "evaluation/results.json",
    ]
    assert all((output / path).is_file() for path in expected)
    results = json.loads((output / "evaluation/results.json").read_text(encoding="utf-8"))
    assert results["dataset"]["validator_accepted_candidates"] == 6
    assert results["dataset"]["selected_bank_items"] == 6
    assert results["input_counts"] == {
        "events": 624,
        "predictions": 1872,
        "prediction_events": 624,
    }
    assert (output / "normalisation/calls/egp_present_simple_phase1/input.json").is_file()
    assert (
        output / "items/generation/calls/candidate_cell_001_01/raw_output.txt"
    ).is_file()
    assert (
        output
        / "items/validation_evidence/calls/candidate_cell_001_01/parsed_result.json"
    ).is_file()
    settings = json.loads((output / "run_settings.json").read_text(encoding="utf-8"))
    assert settings["models"] == {
        stage: {"model": "fixture", "reasoning_effort": "deterministic"}
        for stage in ("normalisation", "generation", "validation")
    }


def test_runner_routes_each_model_backend_independently(tmp_path) -> None:
    backends = {
        "normalisation": {"model": "normalisation-probe", "reasoning_effort": "medium"},
        "generation": {"model": "generation-probe", "reasoning_effort": "high"},
        "validation": {"model": "validation-probe", "reasoning_effort": "xhigh"},
    }
    fixture_responses = pipeline_runner.read_yaml(
        pipeline_runner.FIXTURE_RESPONSES_PATH
    )
    observed = []

    def capturing_fixture_call(prompt, **call):
        observed.append(
            (call["stage"], call["model"], call["reasoning_effort"])
        )
        return pipeline_runner.call_model(
            prompt,
            model="fixture",
            reasoning_effort="deterministic",
            input_data=call["input_data"],
            stage=call["stage"],
            call_key=call["call_key"],
            evidence_dir=call["evidence_dir"],
            fixture_responses=fixture_responses,
        )

    output = tmp_path / "routed"
    pipeline_runner.run_pipeline(
        output,
        model_call=capturing_fixture_call,
        backend_settings=backends,
        fold_design=pipeline_runner.read_yaml(
            pipeline_runner.FIXTURE_FOLD_DESIGN_PATH
        ),
        item_design=pipeline_runner.read_yaml(
            pipeline_runner.FIXTURE_GENERATION_DESIGN_PATH
        ),
        world_design=pipeline_runner.read_yaml(pipeline_runner.FIXTURE_WORLD_PATH),
    )

    expected_by_stage = {
        "normalisation": ("normalisation-probe", "medium"),
        "generation": ("generation-probe", "high"),
        "validation": ("validation-probe", "xhigh"),
    }
    assert observed
    for stage, model, effort in observed:
        group = "normalisation" if stage.startswith("normalisation.") else stage
        assert (model, effort) == expected_by_stage[group]
    settings = json.loads((output / "run_settings.json").read_text(encoding="utf-8"))
    assert settings["models"] == backends


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
