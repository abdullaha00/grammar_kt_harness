from __future__ import annotations

from scripts.run_validation_reliability import (
    comparison_metrics,
    criterion_overlap,
    select_reliability_sample,
    verify_completed_live_input,
)


CRITERIA = ["fidelity", "naturalness", "determinacy"]


def _row(
    index: int,
    condition: str,
    accepted: bool,
    failed: set[str] | None = None,
) -> dict:
    failed = failed or set()
    return {
        "candidate_id": f"candidate_{index:02d}",
        "condition": condition,
        "cell_id": f"cell_{index % 4}",
        "candidate_index": index,
        "validator_output_valid": True,
        "accepted": accepted,
        "judgments": {
            criterion: {
                "passed": criterion not in failed,
                "note": "fixture judgment",
            }
            for criterion in CRITERIA
        },
    }


def test_reliability_sample_is_deterministic_balanced_and_stratified() -> None:
    rows = [
        _row(1, "model_selected", False, {"fidelity"}),
        _row(2, "controlled_lexicon", False, {"naturalness"}),
        _row(3, "readable_source_evidence", False, {"determinacy"}),
        _row(4, "model_selected", True),
        _row(5, "controlled_lexicon", True),
        _row(6, "readable_source_evidence", True),
        _row(7, "model_selected", True),
        _row(8, "controlled_lexicon", True),
    ]
    selected = select_reliability_sample(rows, sample_size=6, seed=17)
    reversed_selected = select_reliability_sample(
        list(reversed(rows)), sample_size=6, seed=17
    )
    assert [row["candidate_id"] for row in selected] == [
        row["candidate_id"] for row in reversed_selected
    ]
    assert sum(row["accepted"] for row in selected) == 3
    assert {row["condition"] for row in selected} == {
        "model_selected",
        "controlled_lexicon",
        "readable_source_evidence",
    }
    assert set().union(*(_failed(row) for row in selected)) == set(CRITERIA)


def _failed(row: dict) -> set[str]:
    return {
        name for name, judgment in row["judgments"].items() if not judgment["passed"]
    }


def test_comparison_metrics_reports_directional_disagreements() -> None:
    reference = [
        _row(1, "x", True),
        _row(2, "x", False, {"fidelity"}),
        _row(3, "x", False, {"naturalness"}),
        _row(4, "x", True),
    ]
    comparison = [
        _row(1, "x", True),
        _row(2, "x", True),
        _row(3, "x", False, {"naturalness"}),
        _row(4, "x", False, {"determinacy"}),
    ]
    metrics = comparison_metrics(reference, comparison, CRITERIA)
    overall = metrics["overall_accept"]
    assert metrics["joint_valid_rows"] == 4
    assert overall["agreement_count"] == 2
    assert overall["agreement_rate"] == 0.5
    assert overall["reference_pass_comparison_fail"] == 1
    assert overall["reference_fail_comparison_pass"] == 1
    assert metrics["criteria"]["fidelity"]["reference_fail_comparison_pass"] == 1
    assert metrics["criteria"]["determinacy"]["reference_pass_comparison_fail"] == 1


def test_failure_overlap_marks_only_informative_equivalence() -> None:
    rows = [
        _row(1, "x", False, {"fidelity", "naturalness"}),
        _row(2, "x", True),
        _row(3, "x", False, {"determinacy"}),
        _row(4, "x", True),
    ]
    overlap = criterion_overlap(rows, CRITERIA)
    pair = next(
        row
        for row in overlap["pairwise"]
        if {row["criterion_a"], row["criterion_b"]}
        == {"fidelity", "naturalness"}
    )
    assert pair["failure_jaccard"] == 1.0
    assert pair["informative_equivalence"] is True
    assert {
        tuple(group["criteria"])
        for group in overlap["identical_failure_vector_groups"]
        if group["informative"]
    } == {("fidelity", "naturalness")}


def test_incomplete_live_input_fails_with_actionable_message(tmp_path) -> None:
    try:
        verify_completed_live_input(tmp_path)
    except RuntimeError as error:
        assert "input is incomplete" in str(error)
        assert "run_item_audit.py" in str(error)
    else:
        raise AssertionError("incomplete input must not start model calls")
