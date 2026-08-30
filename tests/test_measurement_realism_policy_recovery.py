from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/experiments/measurement_realism_policy_recovery.py"


def load_module():
    spec = importlib.util.spec_from_file_location("measurement_realism_policy_recovery", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_paired_interval_is_deterministic_and_signed() -> None:
    module = load_module()
    reference = {"a": 0.4, "b": 0.5, "c": 0.6}
    candidate = {"a": 0.3, "b": 0.4, "c": 0.5}
    first = module.paired_interval(reference, candidate, seed=7, repeats=100)
    second = module.paired_interval(reference, candidate, seed=7, repeats=100)
    assert first == second
    assert abs(first["point_estimate"] + 0.1) < 1e-12
    assert first["delta"] == "policy_minus_q_balanced_lab"


def test_frozen_plan_and_results_validate_when_present() -> None:
    module = load_module()
    plan_path = module.DERIVED_ROOT / "plan.json"
    if not plan_path.exists():
        return
    stored = module.load_json(plan_path)
    plan = module.validate_plan(
        plan_path,
        allow_missing_run_inputs=not module.run_inputs_present(stored),
    )
    assert plan["claim_boundary"]["release_eligible"] is False
    results_path = module.DERIVED_ROOT / "results/results.json"
    if results_path.exists():
        results = module.load_json(results_path)
        assert results["controlled_scenario"] is True
        assert results["release_eligible"] is False


def test_policy_run_inputs_must_be_all_present_or_all_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    plan = {
        "runs": [
            {
                "response_manifest": "runs/response.json",
                "reference_analysis_manifest": "runs/reference.json",
            }
        ]
    }
    assert module.run_inputs_present(plan) is False
    response = tmp_path / "runs/response.json"
    response.parent.mkdir(parents=True)
    response.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="partial raw-run input tree"):
        module.run_inputs_present(plan)
