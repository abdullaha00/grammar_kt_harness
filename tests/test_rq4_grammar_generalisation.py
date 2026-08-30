from __future__ import annotations

import copy

import numpy as np

from grammar_kt.io import read_jsonl, read_yaml
from scripts.experiments.rq2_kc_misspecification import (
    build_observable_feature_matrix,
    file_sha256,
    fit_observable_logistic,
)
from scripts.experiments.rq4_grammar_generalisation import (
    DEFAULT_DATASET,
    _cell_evaluation,
    _load_q_sparse,
    build_item_novelty_schedule,
    make_item_novelty_partition,
    simulate_item_novelty,
)


def test_full_item_novelty_partition_is_deterministic_and_same_cell() -> None:
    items = read_jsonl(DEFAULT_DATASET / "items/items.jsonl")
    regimes = read_jsonl(DEFAULT_DATASET / "grammar/regime_assignments.jsonl")
    regime_by_cell = {row["cell_id"]: row["grammar_regime"] for row in regimes}
    first = make_item_novelty_partition(items, regime_by_cell, seed=20260830)
    second = make_item_novelty_partition(
        list(reversed(items)), regime_by_cell, seed=20260830
    )
    assert first == second
    assert len(first) == 30
    item_to_cell = {row["item_id"]: row["cell_id"] for row in items}
    assert all(
        item_to_cell[row["heldout_item_id"]]
        == item_to_cell[row["practised_item_id"]]
        == row["cell_id"]
        for row in first
    )
    assert not ({row["heldout_item_id"] for row in first} & {row["practised_item_id"] for row in first})


def test_item_novelty_schedule_preserves_length_and_every_kstar_opportunity() -> None:
    items = read_jsonl(DEFAULT_DATASET / "items/items.jsonl")
    regimes = read_jsonl(DEFAULT_DATASET / "grammar/regime_assignments.jsonl")
    regime_by_cell = {row["cell_id"]: row["grammar_regime"] for row in regimes}
    partition = make_item_novelty_partition(items, regime_by_cell, seed=20260830)
    q = _load_q_sparse(DEFAULT_DATASET / "oracle/q_matrix_sparse.jsonl")
    schedule, audit = build_item_novelty_schedule(
        items,
        q,
        regime_by_cell,
        partition,
        target_opportunities=12,
    )
    assert len(schedule) == 170
    assert audit["q_opportunity_counts_identical_to_baseline"] is True
    held = {row["heldout_item_id"] for row in partition}
    practised = {row["practised_item_id"] for row in partition}
    scheduled = {row["item"]["item_id"] for row in schedule}
    assert not held & scheduled
    assert practised <= scheduled


def test_probe_outcomes_never_change_features_or_fitted_predictions() -> None:
    events = []
    for learner, outcomes in (("l1", [0, 1]), ("l2", [1, 0])):
        for index, correct in enumerate(outcomes, 1):
            events.append(
                {
                    "event_id": f"{learner}_{index}",
                    "learner_id": learner,
                    "item_id": "i1",
                    "sequence_index": index,
                    "correct": correct,
                    "phase": "acquisition",
                    "updates_history": True,
                    "dataset_split": "train",
                    "grammar_regime": "seen",
                }
            )
        events.append(
            {
                "event_id": f"{learner}_3",
                "learner_id": learner,
                "item_id": "i1",
                "sequence_index": 3,
                "correct": 0,
                "phase": "probe",
                "updates_history": False,
                "dataset_split": "test",
                "grammar_regime": "seen",
            }
        )
    projection = {"i1": ("kc",)}
    first_x, _ = build_observable_feature_matrix(events, projection)
    first_probability, _ = fit_observable_logistic(events, projection)
    changed = copy.deepcopy(events)
    for row in changed:
        if row["phase"] == "probe":
            row["correct"] = 1
    second_x, _ = build_observable_feature_matrix(changed, projection)
    second_probability, _ = fit_observable_logistic(changed, projection)
    np.testing.assert_array_equal(first_x, second_x)
    np.testing.assert_allclose(first_probability, second_probability, atol=0, rtol=0)


def test_local_item_novelty_simulator_is_deterministic_and_non_updating() -> None:
    items = [
        {"item_id": "held", "cell_id": "cell"},
        {"item_id": "practice", "cell_id": "cell"},
    ]
    kcs = [{"id": "kc"}]
    q = {"held": ("kc",), "practice": ("kc",)}
    regimes = {"cell": "seen"}
    config = read_yaml(DEFAULT_DATASET / "provenance/simulation/baseline.yaml")
    config["learners"] = 2
    schedule = [
        {
            "item": {"item_id": "practice", "cell_id": "cell"},
            "schedule_stage": "exhaustive_coverage",
            "pass_index": 1,
            "item_exposure_index": 1,
        },
        {
            "item": {"item_id": "practice", "cell_id": "cell"},
            "schedule_stage": "q_balanced_top_up",
            "pass_index": 2,
            "item_exposure_index": 2,
        },
    ]
    partition = [
        {"cell_id": "cell", "heldout_item_id": "held", "practised_item_id": "practice"}
    ]
    frozen_inputs = copy.deepcopy((items, kcs, q, regimes, config, schedule, partition))
    first = simulate_item_novelty(items, kcs, q, regimes, config, schedule, partition)
    second = simulate_item_novelty(items, kcs, q, regimes, config, schedule, partition)
    assert first == second
    assert frozen_inputs == (items, kcs, q, regimes, config, schedule, partition)
    assert all(row["item_id"] != "held" for row in first if row["phase"] == "acquisition")
    probes = [row for row in first if row["phase"] == "probe"]
    assert len(probes) == 2
    assert all(row["item_id"] == "held" and not row["updates_history"] for row in probes)


def test_cell_macro_sensitivity_reports_every_leave_one_cell_out_value() -> None:
    events = [
        {"item_id": "i1", "correct": 1},
        {"item_id": "i1", "correct": 0},
        {"item_id": "i2", "correct": 1},
        {"item_id": "i2", "correct": 1},
        {"item_id": "i3", "correct": 0},
        {"item_id": "i3", "correct": 0},
    ]
    probabilities = np.asarray([0.8, 0.8, 0.7, 0.7, 0.3, 0.3])
    result = _cell_evaluation(
        events, probabilities, {"i1": "c1", "i2": "c2", "i3": "c3"}
    )
    assert result["cells"] == 3
    assert len(result["per_cell"]) == 3
    assert len(result["sensitivity"]["leave_one_cell_out"]) == 3
    assert result["sensitivity"]["leave_one_cell_out_log_loss_range"] is not None


def test_structural_analysis_does_not_mutate_frozen_baseline_files() -> None:
    paths = [
        DEFAULT_DATASET / "manifest.json",
        DEFAULT_DATASET / "interactions.jsonl.gz",
        DEFAULT_DATASET / "items/items.jsonl",
        DEFAULT_DATASET / "q_matrix.csv",
    ]
    before = [file_sha256(path) for path in paths]
    items = read_jsonl(DEFAULT_DATASET / "items/items.jsonl")
    regimes = read_jsonl(DEFAULT_DATASET / "grammar/regime_assignments.jsonl")
    make_item_novelty_partition(
        items,
        {row["cell_id"]: row["grammar_regime"] for row in regimes},
        seed=20260830,
    )
    assert before == [file_sha256(path) for path in paths]


def test_combination_cohort_is_pairwise_seen_full_tuple_unseen() -> None:
    rows = [
        row
        for row in read_jsonl(DEFAULT_DATASET / "grammar/regime_assignments.jsonl")
        if row["grammar_regime"] == "unseen_combination"
    ]
    assert len(rows) == 15
    assert all(
        row["constituent_seen"] is True
        and row["pairwise_seen"] is True
        and row["full_tuple_seen"] is False
        and row["combination_subtype"] == "pairwise_seen_full_tuple_unseen"
        for row in rows
    )
