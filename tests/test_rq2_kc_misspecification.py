from __future__ import annotations

import copy

import numpy as np
import pytest

from grammar_kt.kt import history_features
from scripts.experiments.rq2_kc_misspecification import (
    all_merged_projection,
    build_observable_feature_matrix,
    exact_cell_projection,
    paired_learner_bootstrap,
    perturb_projection,
    prediction_metrics,
    structural_split_projection,
    validate_projection,
)


def _items() -> list[dict]:
    return [
        {"item_id": "i1", "cell_id": "c1"},
        {"item_id": "i2", "cell_id": "c2"},
        {"item_id": "i3", "cell_id": "c3"},
        {"item_id": "i4", "cell_id": "c4"},
    ]


def _cells() -> list[dict]:
    return [
        {"cell_id": "c1", "features": {"mood": "indicative", "person": "first"}},
        {"cell_id": "c2", "features": {"mood": "indicative", "person": "third"}},
        {"cell_id": "c3", "features": {"mood": "subjunctive", "person": "first"}},
        {"cell_id": "c4", "features": {"mood": "subjunctive", "person": "third"}},
    ]


def _projection() -> dict[str, tuple[str, ...]]:
    return {
        "i1": ("kc_mood", "kc_first"),
        "i2": ("kc_mood", "kc_third"),
        "i3": ("kc_mood", "kc_first"),
        "i4": ("kc_mood", "kc_third"),
    }


def _events() -> list[dict]:
    return [
        {
            "event_id": "a1",
            "learner_id": "a",
            "sequence_index": 1,
            "item_id": "i1",
            "correct": 1,
            "phase": "acquisition",
            "updates_history": True,
        },
        {
            "event_id": "a2",
            "learner_id": "a",
            "sequence_index": 2,
            "item_id": "i2",
            "correct": 0,
            "phase": "probe",
            "updates_history": False,
        },
        {
            "event_id": "a3",
            "learner_id": "a",
            "sequence_index": 3,
            "item_id": "i1",
            "correct": 0,
            "phase": "probe",
            "updates_history": False,
        },
    ]


def test_granularity_transforms_change_only_projection_and_are_structural() -> None:
    true = _projection()
    original = copy.deepcopy(true)
    merged = all_merged_projection(true)
    split2 = structural_split_projection(true, _items(), _cells(), 2)
    split4 = structural_split_projection(true, _items(), _cells(), 4)
    exact = exact_cell_projection(_items())

    assert true == original
    assert {values for values in merged.values()} == {("coarse_all_grammar",)}
    assert len({kc for values in split2.values() for kc in values}) > 3
    assert len({kc for values in split4.values() for kc in values}) >= len(
        {kc for values in split2.values() for kc in values}
    )
    assert exact == {
        "i1": ("exact_cell::c1",),
        "i2": ("exact_cell::c2",),
        "i3": ("exact_cell::c3",),
        "i4": ("exact_cell::c4",),
    }
    assert validate_projection(split2, true)["empty_items"] == 0


@pytest.mark.parametrize("kind", ["false_positive", "false_negative", "mixed"])
def test_q_perturbations_are_fixed_budget_deterministic_and_do_not_mutate_truth(
    kind: str,
) -> None:
    true = _projection()
    original = copy.deepcopy(true)
    first, metadata = perturb_projection(
        true,
        ["kc_first", "kc_mood", "kc_third"],
        kind=kind,
        rate=0.5,
        seed=17,
    )
    repeated, repeated_metadata = perturb_projection(
        true,
        ["kc_first", "kc_mood", "kc_third"],
        kind=kind,
        rate=0.5,
        seed=17,
    )
    assert true == original
    assert first == repeated
    assert metadata == repeated_metadata
    assert metadata["hamming_budget"] == 4
    assert metadata["removed_edges"] + metadata["added_edges"] == 4
    if kind in {"false_negative", "mixed"}:
        assert all(first[item_id] for item_id in first)
        assert {
            kc_id for active in first.values() for kc_id in active
        } >= {"kc_first", "kc_mood", "kc_third"}


def test_vectorized_observable_features_match_active_history_implementation() -> None:
    events = _events()
    projection = [{"item_id": key, "kc_ids": list(value)} for key, value in _projection().items()]
    expected, expected_kcs = history_features(
        events,
        projection,
        1.0,
        1.0,
        {
            "include_item_difficulty": False,
            "include_kc_count": True,
            "include_kc_indicators": True,
        },
    )
    observed, observed_kcs = build_observable_feature_matrix(
        events, _projection(), alpha=1.0, beta=1.0
    )
    assert observed_kcs == expected_kcs
    np.testing.assert_allclose(
        observed, np.asarray([row["vector"] for row in expected]), rtol=1e-6
    )


def test_probe_outcome_cannot_change_later_probe_features() -> None:
    events = _events()
    first, _ = build_observable_feature_matrix(events, _projection())
    changed = copy.deepcopy(events)
    changed[1]["correct"] = 1
    second, _ = build_observable_feature_matrix(changed, _projection())
    np.testing.assert_array_equal(first, second)


def test_paired_learner_bootstrap_is_deterministic_and_signed() -> None:
    events = [
        {"learner_id": "a", "correct": 1},
        {"learner_id": "a", "correct": 0},
        {"learner_id": "b", "correct": 1},
        {"learner_id": "b", "correct": 0},
    ]
    reference = np.asarray([0.5, 0.5, 0.5, 0.5])
    candidate = np.asarray([0.8, 0.2, 0.8, 0.2])
    first = paired_learner_bootstrap(
        events,
        reference,
        candidate,
        repeats=100,
        seed=9,
        reference_id="true",
        candidate_id="candidate",
    )
    repeated = paired_learner_bootstrap(
        events,
        reference,
        candidate,
        repeats=100,
        seed=9,
        reference_id="true",
        candidate_id="candidate",
    )
    assert first == repeated
    assert first["delta_log_loss"]["point_estimate"] < 0
    assert first["delta_log_loss"]["interval_95"][1] < 0
    with pytest.raises(ValueError, match="exactly pair"):
        paired_learner_bootstrap(
            events,
            reference[:-1],
            candidate,
            repeats=10,
            seed=9,
            reference_id="true",
            candidate_id="candidate",
        )


def test_prediction_metrics_handle_empty_and_single_class() -> None:
    assert prediction_metrics([], [])["n"] == 0
    metrics = prediction_metrics([1, 1], [0.8, 0.9])
    assert metrics["n"] == 2
    assert metrics["auc"] is None
    assert metrics["log_loss"] > 0
