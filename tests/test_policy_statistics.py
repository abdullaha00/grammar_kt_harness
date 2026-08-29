from __future__ import annotations

import copy

import pytest

from grammar_kt.evaluate import paired_policy_bootstrap


def _paired_inputs() -> tuple[list[dict], list[dict], list[dict]]:
    events = []
    left = []
    right = []
    for learner in range(1, 11):
        for sequence, correct in enumerate((1, 0, 1, 0), 1):
            event_id = f"e_{learner}_{sequence}"
            events.append(
                {
                    "event_id": event_id,
                    "learner_id": f"l_{learner}",
                    "correct": correct,
                }
            )
            left.append({"event_id": event_id, "probability": 0.5})
            right.append(
                {
                    "event_id": event_id,
                    "probability": 0.8 if correct else 0.2,
                }
            )
    return events, left, right


def test_policy_bootstrap_is_paired_by_learner_and_has_declared_sign() -> None:
    events, left, right = _paired_inputs()
    result = paired_policy_bootstrap(
        events, left, right, repeats=400, seed=20260827
    )
    assert result["sign_convention"] == (
        "candidate_minus_reference; negative favours candidate"
    )
    assert result["sampling_unit"] == "learner"
    assert result["aggregation"] == "event_weighted"
    assert result["reference_policy_id"] == "reference"
    assert result["candidate_policy_id"] == "candidate"
    assert result["n_learners"] == 10
    assert result["n_events"] == 40
    assert result["delta_log_loss"]["point_estimate"] < 0
    assert result["delta_log_loss"]["interval_95"][1] < 0
    assert result["delta_brier_score"]["point_estimate"] < 0
    assert result == paired_policy_bootstrap(
        events, left, right, repeats=400, seed=20260827
    )


def test_policy_bootstrap_requires_exact_paired_event_coverage() -> None:
    events, left, right = _paired_inputs()
    with pytest.raises(ValueError, match="exactly cover"):
        paired_policy_bootstrap(
            events, left[:-1], right, repeats=10, seed=1
        )
    duplicated = [*left, copy.deepcopy(left[0])]
    with pytest.raises(ValueError, match="duplicate"):
        paired_policy_bootstrap(
            events, duplicated, right, repeats=10, seed=1
        )


def test_policy_bootstrap_is_order_invariant_and_reverses_sign() -> None:
    events, reference, candidate = _paired_inputs()
    forward = paired_policy_bootstrap(
        events, reference, candidate, repeats=100, seed=9
    )
    reordered = paired_policy_bootstrap(
        list(reversed(events)),
        list(reversed(reference)),
        list(reversed(candidate)),
        repeats=100,
        seed=9,
    )
    reverse = paired_policy_bootstrap(
        events, candidate, reference, repeats=100, seed=9
    )
    assert reordered == forward
    assert reverse["delta_log_loss"]["point_estimate"] == pytest.approx(
        -forward["delta_log_loss"]["point_estimate"]
    )
    assert reverse["delta_brier_score"]["point_estimate"] == pytest.approx(
        -forward["delta_brier_score"]["point_estimate"]
    )


def test_policy_bootstrap_handles_empty_single_class_and_one_learner() -> None:
    empty = paired_policy_bootstrap([], [], [], repeats=10, seed=1)
    assert empty["available"] is False

    events, reference, candidate = _paired_inputs()
    one_learner = [row for row in events if row["learner_id"] == "l_1"]
    ids = {row["event_id"] for row in one_learner}
    result = paired_policy_bootstrap(
        one_learner,
        [row for row in reference if row["event_id"] in ids],
        [row for row in candidate if row["event_id"] in ids],
        repeats=10,
        seed=1,
    )
    assert result["delta_log_loss"]["interval_95"] is None

    all_correct = [{**row, "correct": 1} for row in events]
    result = paired_policy_bootstrap(
        all_correct, reference, candidate, repeats=10, seed=1
    )
    assert result["available"] is True


def test_policy_bootstrap_validates_targets_and_probabilities() -> None:
    events, reference, candidate = _paired_inputs()
    with pytest.raises(ValueError, match="binary"):
        paired_policy_bootstrap(
            [{**events[0], "correct": 2}, *events[1:]],
            reference,
            candidate,
            repeats=10,
            seed=1,
        )
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        paired_policy_bootstrap(
            events,
            [{**reference[0], "probability": 1.1}, *reference[1:]],
            candidate,
            repeats=10,
            seed=1,
        )


def test_policy_bootstrap_identical_predictions_have_exact_zero_delta() -> None:
    events, reference, _candidate = _paired_inputs()
    result = paired_policy_bootstrap(
        events, reference, copy.deepcopy(reference), repeats=50, seed=3
    )
    assert result["delta_log_loss"] == {
        "point_estimate": 0.0,
        "interval_95": [0.0, 0.0],
    }
    assert result["delta_brier_score"] == {
        "point_estimate": 0.0,
        "interval_95": [0.0, 0.0],
    }
