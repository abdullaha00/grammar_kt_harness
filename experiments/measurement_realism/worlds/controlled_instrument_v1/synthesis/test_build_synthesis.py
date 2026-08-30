from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest

import build_synthesis as synthesis


WORLD_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def result() -> dict:
    return synthesis.build_synthesis(WORLD_ROOT)


def test_full_synthesis_verifies_frozen_nonrelease_evidence(result: dict) -> None:
    assert result["verification"]["status"] == "PASS"
    assert result["verification"]["planned_response_runs_verified"] == 27
    assert result["verification"]["q_balanced_analysis_runs_verified"] == 18
    assert result["verification"]["error_analysis_runs_verified"] == 3
    assert result["verification"]["cross_world_evaluation_rows_aligned"] is True
    assert result["release_eligible"] is False
    assert result["content_free_instrument"] is True
    assert result["synthesis_timing"] == "post_response_derived_summary"
    assert result["claim_boundary"]["learner_facing_measurement_validity"] == "NOT_ASSESSED"
    assert result["claim_boundary"]["platform_plausibility"] == "NOT_ASSESSED"


def test_primary_results_and_interpretation_constraints_are_exact(result: dict) -> None:
    did = result["contrasts"]["primary_cross_world"]["format_confounding_difference_in_differences"]
    assert did["across_seed_point_estimate"]["mean"] == pytest.approx(-0.03155148583847481)
    assert "increases false format-split model B's predictive advantage" in did["corrected_sign_gloss"]
    assert "explicitly corrected candidate" in did["frozen_aggregate_sign_gloss"]
    item_split = result["contrasts"]["item_only_false_split_B_minus_A"]["point_estimate_across_seed"]
    assert item_split["values_by_seed"] == pytest.approx(
        {
            "20260829": 0.0011947255903524913,
            "20260830": 0.00084733254303488,
            "20260831": -0.0013275832961343469,
        }
    )
    assert "oracle-aligned same-seen-item positive control" in result["contrasts"]["interpretation"]["item"]


def test_error_and_schedule_controls_are_not_overclaimed(result: dict) -> None:
    error = result["error_history"]
    binary = error["secondary_terminal_kc_evidence_diagnostic"]["binary_only"]["across_seed"]["rmse"]["mean"]
    shuffled = error["secondary_terminal_kc_evidence_diagnostic"]["within_item_shuffled_negative_control"]["across_seed"]["rmse"]["mean"]
    assert shuffled < binary
    assert "not fitted A/B/C/D KC mastery" in error["interpretation"]["terminal_kc"]
    assert result["schedule_diagnostics"]["fixed_multiset_probe_accuracy_identical_per_seed"] is True
    assert "No randomized policy comparison" in result["schedule_diagnostics"]["interpretation"]


def test_alignment_and_claim_guards_reject_tampering() -> None:
    hashes = {
        str(seed): {world: f"same-{seed}" for world in synthesis.WORLDS}
        for seed in synthesis.SEEDS
    }
    synthesis.assert_cross_world_row_alignment(hashes, "fixture")
    tampered = copy.deepcopy(hashes)
    tampered[str(synthesis.SEEDS[0])][synthesis.WORLDS[-1]] = "different"
    with pytest.raises(synthesis.SynthesisError, match="differs across worlds"):
        synthesis.assert_cross_world_row_alignment(tampered, "fixture")

    plan = {
        "controlled_scenario": True,
        "release_eligible": False,
        "scenario_kind": synthesis.SCENARIO_KIND,
        "claim_boundary": {
            **{field: False for field in synthesis.FALSE_CLAIM_FIELDS},
            "permitted_claim": "controlled_structural_sensitivity_only",
        },
    }
    synthesis.validate_claim_boundary(plan)
    plan["claim_boundary"]["platform_plausibility_claimed"] = True
    with pytest.raises(synthesis.SynthesisError, match="platform_plausibility_claimed"):
        synthesis.validate_claim_boundary(plan)


def test_hash_guard_and_retained_outputs(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("frozen\n", encoding="utf-8")
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    recorded: dict[str, str] = {}
    synthesis.verify_hash(source, expected, "fixture", recorded, tmp_path)
    source.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(synthesis.SynthesisError, match="sha256"):
        synthesis.verify_hash(source, expected, "fixture", {}, tmp_path)

    synthesis.check_outputs(WORLD_ROOT)
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        synthesis.write_outputs(WORLD_ROOT)
