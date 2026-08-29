from __future__ import annotations

import pytest

from scripts.run_phase5_integrated_validation import (
    _pairwise_jaccard,
    paired_cluster_bootstrap,
    subset_development_learners,
)


def _event(event_id: str, learner: str, correct: int, split: str = "development") -> dict:
    return {
        "event_id": event_id,
        "learner_id": learner,
        "sequence_index": int(event_id.rsplit("_", 1)[-1]),
        "correct": correct,
        "grammar_split": split,
    }


def test_nested_learner_subset_is_deterministic_and_development_only() -> None:
    rows = [
        _event("e_4", "learner_b", 1),
        _event("e_1", "learner_a", 0),
        _event("e_2", "learner_a", 1, "compositional_holdout"),
        _event("e_3", "learner_b", 0),
        _event("e_5", "learner_c", 1),
    ]
    selected = subset_development_learners(rows, 2)
    assert [row["event_id"] for row in selected] == ["e_4", "e_1", "e_3"]
    assert {row["learner_id"] for row in selected} == {"learner_a", "learner_b"}
    assert {row["grammar_split"] for row in selected} == {"development"}
    with pytest.raises(ValueError, match="3-learner stream"):
        subset_development_learners(rows, 4)


def test_pairwise_jaccard_treats_two_empty_addition_sets_as_stable() -> None:
    assert _pairwise_jaccard([set(), set(), set()])["mean"] == 1.0
    assert _pairwise_jaccard([{"a"}, {"a", "b"}])["mean"] == 0.5


def test_vectorized_cluster_bootstrap_is_paired_deterministic_and_signed() -> None:
    events = [
        _event("e_1", "learner_a", 1),
        _event("e_2", "learner_a", 0),
        _event("e_3", "learner_b", 1),
        _event("e_4", "learner_b", 0),
    ]
    reference = {row["event_id"]: 0.5 for row in events}
    candidate = {"e_1": 0.8, "e_2": 0.2, "e_3": 0.8, "e_4": 0.2}
    first = paired_cluster_bootstrap(
        events,
        reference,
        candidate,
        repeats=100,
        seed=17,
        reference_policy_id="factorized",
        candidate_policy_id="automated",
    )
    repeated = paired_cluster_bootstrap(
        list(reversed(events)),
        reference,
        candidate,
        repeats=100,
        seed=17,
        reference_policy_id="factorized",
        candidate_policy_id="automated",
    )
    assert first == repeated
    assert first["sampling_unit"] == "learner"
    assert first["delta_log_loss"]["point_estimate"] < 0
    assert first["delta_brier_score"]["point_estimate"] < 0
    assert first["delta_log_loss"]["interval_95"][1] < 0


def test_vectorized_cluster_bootstrap_requires_exact_pairing() -> None:
    events = [_event("e_1", "learner_a", 1), _event("e_2", "learner_b", 0)]
    with pytest.raises(ValueError, match="exactly cover"):
        paired_cluster_bootstrap(
            events,
            {"e_1": 0.5},
            {"e_1": 0.7, "e_2": 0.3},
            repeats=10,
            seed=1,
            reference_policy_id="a",
            candidate_policy_id="b",
        )
