from __future__ import annotations

import copy

from grammar_kt.evaluate import evaluate
from grammar_kt.kc import project_kcs
from grammar_kt.kt import history_features, run_kt
from grammar_kt.simulate import simulate

from .helpers import (
    EVALUATION_PROTOCOL,
    FACTORIZED_POLICY,
    FULL_CELL_POLICY,
    KT_PROTOCOL,
    SIMULATION_WORLD,
    base_bank,
)


def test_empirical_bkt_and_logistic_return_valid_probabilities_on_same_events() -> None:
    _mappings, cells, candidates, accepted, judgments, fold = base_bank()
    events = simulate(accepted, fold, SIMULATION_WORLD)
    projection = project_kcs(accepted, cells, FACTORIZED_POLICY)
    predictions = run_kt(events, projection, KT_PROTOCOL)
    assert {row["technique"] for row in predictions} == {
        "empirical",
        "bkt",
        "logistic",
    }
    for technique in ("empirical", "bkt", "logistic"):
        rows = [row for row in predictions if row["technique"] == technique]
        assert [row["event_id"] for row in rows] == [
            row["event_id"] for row in events
        ]
        assert all(0.0 < row["probability"] < 1.0 for row in rows)

    results = evaluate(
        candidates,
        judgments,
        accepted,
        cells,
        fold,
        events,
        FACTORIZED_POLICY,
        projection,
        predictions,
        EVALUATION_PROTOCOL,
    )
    assert results["input_counts"]["events"] == len(events)
    assert set(results["kt"]) == {"empirical", "bkt", "logistic"}
    assert results["representation"]["compositional_coverage"] == 1.0


def test_temporal_features_use_only_prior_events() -> None:
    events = [
        {
            "event_id": "event_1",
            "learner_id": "learner_1",
            "item_id": "item_1",
            "correct": 1,
            "sequence_index": 1,
            "dataset_split": "train",
            "item_difficulty": 0.0,
            "grammar_split": "development",
        },
        {
            "event_id": "event_2",
            "learner_id": "learner_1",
            "item_id": "item_1",
            "correct": 0,
            "sequence_index": 2,
            "dataset_split": "test",
            "item_difficulty": 0.0,
            "grammar_split": "development",
        },
    ]
    projection = [{"item_id": "item_1", "kc_ids": ["kc_x"]}]
    first, _ = history_features(events, projection, 1.0, 1.0)
    changed = copy.deepcopy(events)
    changed[1]["correct"] = 1
    second, _ = history_features(changed, projection, 1.0, 1.0)
    assert first[0] == second[0]
    assert first[1] == second[1]
    assert first[1]["history_events"] == 1


def test_factorized_and_full_cell_change_only_kc_dependent_outputs() -> None:
    _mappings, cells, _candidates, accepted, _judgments, fold = base_bank()
    events = simulate(accepted, fold, SIMULATION_WORLD)
    fixed_items = copy.deepcopy(accepted)
    fixed_events = copy.deepcopy(events)
    left_projection = project_kcs(accepted, cells, FACTORIZED_POLICY)
    right_projection = project_kcs(accepted, cells, FULL_CELL_POLICY)
    assert left_projection != right_projection
    assert accepted == fixed_items
    assert events == fixed_events
    assert run_kt(events, left_projection, KT_PROTOCOL) != run_kt(
        events, right_projection, KT_PROTOCOL
    )
