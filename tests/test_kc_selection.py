from __future__ import annotations

import copy
import inspect

import pytest

from grammar_kt.io import read_yaml
from grammar_kt.kc import project_kcs
from grammar_kt.kc_candidates import make_kc_candidates
from grammar_kt.kc_selection import (
    fit_predict_kc_logistic,
    predict_kc_bkt,
    select_kcs,
)

from .helpers import ROOT


def _candidate(
    candidate_id: str,
    family: str,
    support: list[str],
    activation: dict,
) -> dict:
    return {
        "id": candidate_id,
        "family": family,
        "definition": candidate_id,
        "activation": activation,
        "supporting_development_item_ids": support,
        "cell_support": 2 if family == "interaction" else 3,
        "item_support": len(support),
        "selection_eligible": True,
    }


def _interaction_problem() -> tuple[dict, list[dict], dict]:
    inventory = {
        "candidate_design_id": "xor_candidates",
        "development_cell_ids": ["cell_a", "cell_b", "cell_ab"],
        "development_item_ids": ["item_a", "item_b", "item_ab"],
        "candidates": [
            _candidate(
                "kc_feature__left__marked",
                "feature_value",
                ["item_a", "item_ab"],
                {"cell": {"left": "marked"}},
            ),
            _candidate(
                "kc_feature__right__marked",
                "feature_value",
                ["item_b", "item_ab"],
                {"cell": {"right": "marked"}},
            ),
            _candidate(
                "kc_interaction__left_marked__and__right_marked",
                "interaction",
                ["item_ab"],
                {"cell": {"left": "marked", "right": "marked"}},
            ),
        ],
    }
    events = []
    order = ["item_a", "item_b", "item_ab"] * 4
    for learner_number in range(1, 61):
        for sequence, item_id in enumerate(order, 1):
            events.append(
                {
                    "event_id": f"event_{learner_number:03d}_{sequence:02d}",
                    "learner_id": f"learner_{learner_number:03d}",
                    "item_id": item_id,
                    "correct": int(item_id != "item_ab"),
                    "sequence_index": sequence,
                    "dataset_split": (
                        "train" if sequence <= 6 else "validation" if sequence <= 9 else "test"
                    ),
                    "grammar_split": "development",
                    "item_difficulty": 99.0 if item_id == "item_ab" else -99.0,
                }
            )
    design = read_yaml(ROOT / "modules/kcs/selection.yaml")
    design["objective"]["complexity_penalty"] = 0.001
    design["objective"]["minimum_improvement"] = 0.0
    return inventory, events, design


def test_forward_selector_recovers_interaction_and_preserves_marginals() -> None:
    inventory, events, design = _interaction_problem()
    policy = select_kcs(inventory, events, design)
    selected = set(policy["selection_metadata"]["selected_candidate_ids"])
    assert selected == {
        "kc_feature__left__marked",
        "kc_feature__right__marked",
        "kc_interaction__left_marked__and__right_marked",
    }
    actions = [row["action"] for row in policy["selection_metadata"]["trace"]]
    assert "forward_add" in actions
    assert policy["selection_metadata"]["reserved_or_holdout_outcomes_read"] is False
    assert policy["selection_metadata"]["selector_model"]["features"] == [
        "learner_success_rate",
        "learner_log_attempts",
        "per_kc_active",
        "per_kc_prior_successes",
        "per_kc_prior_failures",
    ]
    assert "item_difficulty" not in policy["selection_metadata"]["selector_model"]["features"]

    cells = [
        {"cell_id": "cell_a", "features": {"left": "marked", "right": "reference"}},
        {"cell_id": "cell_b", "features": {"left": "reference", "right": "marked"}},
        {"cell_id": "cell_ab", "features": {"left": "marked", "right": "marked"}},
    ]
    items = [
        {"item_id": "item_a", "cell_id": "cell_a"},
        {"item_id": "item_b", "cell_id": "cell_b"},
        {"item_id": "item_ab", "cell_id": "cell_ab"},
    ]
    projection = project_kcs(items, cells, policy)
    assert len(projection[2]["kc_ids"]) == 3


def test_complexity_penalty_can_reject_an_otherwise_predictive_addition() -> None:
    inventory, events, design = _interaction_problem()
    high_penalty = copy.deepcopy(design)
    high_penalty["objective"]["complexity_penalty"] = 1.0
    policy = select_kcs(inventory, events, high_penalty)
    assert policy["selection_metadata"]["selected_candidate_ids"] == [
        "kc_feature__left__marked",
        "kc_feature__right__marked",
    ]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("metric", "brier_score", "objective metric"),
        ("complexity", "q_edges", "complexity measure"),
    ],
)
def test_selector_rejects_undeclared_objective_semantics(
    field: str, value: str, message: str
) -> None:
    inventory, events, design = _interaction_problem()
    changed = copy.deepcopy(design)
    changed["objective"][field] = value
    with pytest.raises(ValueError, match=message):
        select_kcs(inventory, events, changed)


def test_alternate_schema_runs_candidates_selection_freezing_and_projection() -> None:
    schema = {
        "schema_id": "toy_language_v1",
        "dimension_order": ["mood", "person"],
        "dimensions": {
            "mood": {"allowed_values": ["plain", "witnessed"]},
            "person": {"allowed_values": ["first", "third"]},
        },
    }
    cells = [
        {
            "cell_id": "toy_plain_first",
            "features": {"mood": "plain", "person": "first"},
        },
        {
            "cell_id": "toy_witnessed_first",
            "features": {"mood": "witnessed", "person": "first"},
        },
        {
            "cell_id": "toy_plain_third",
            "features": {"mood": "plain", "person": "third"},
        },
        {
            "cell_id": "toy_witnessed_third",
            "features": {"mood": "witnessed", "person": "third"},
        },
    ]
    items = [
        {"item_id": f"toy_item_{index}", "cell_id": cell["cell_id"]}
        for index, cell in enumerate(cells, 1)
    ]
    candidate_design = {
        "candidate_design_id": "toy_candidates",
        "candidate_types": {
            "feature_values": True,
            "operations": False,
            "pairwise_interactions": True,
            "full_cells": True,
        },
        "background_values": {"mood": ["plain"], "person": ["first"]},
        "minimum_interaction_cell_support": 1,
        "minimum_interaction_item_support": 1,
        "equivalence_representative_order": [
            "feature_value",
            "operation",
            "interaction",
            "full_cell",
        ],
    }
    inventory = make_kc_candidates(schema, cells, items, candidate_design)
    events = []
    for learner_number in range(1, 21):
        for sequence, item in enumerate(items * 2, 1):
            events.append(
                {
                    "event_id": f"toy_{learner_number:02d}_{sequence:02d}",
                    "learner_id": f"toy_learner_{learner_number:02d}",
                    "item_id": item["item_id"],
                    "correct": int(item["item_id"] != "toy_item_4"),
                    "sequence_index": sequence,
                    "dataset_split": "train" if sequence <= 4 else "validation",
                    "grammar_split": "development",
                }
            )
    selection_design = read_yaml(ROOT / "modules/kcs/selection.yaml")
    selection_design["objective"]["complexity_penalty"] = 1.0
    frozen_policy = select_kcs(inventory, events, selection_design)
    projection = project_kcs(items, cells, frozen_policy)

    selected = frozen_policy["selection_metadata"]["selected_candidate_ids"]
    assert selected == [
        "kc_feature__mood__witnessed",
        "kc_feature__person__third",
    ]
    assert projection[-1]["kc_ids"] == selected
    assert all(
        not any(english_name in candidate_id for english_name in ("tense", "aspect", "voice"))
        for candidate_id in selected
    )


def test_reserved_outcomes_and_oracle_difficulty_cannot_change_selection() -> None:
    inventory, events, design = _interaction_problem()
    first = select_kcs(inventory, events, design)
    changed = copy.deepcopy(events)
    for event in changed:
        if event["dataset_split"] == "test":
            event["correct"] = 1 - event["correct"]
        event["item_difficulty"] *= -10
    second = select_kcs(inventory, changed, design)
    assert second == first


def test_selector_rejects_holdout_items_and_grammar_events() -> None:
    inventory, events, design = _interaction_problem()
    item_leak = [
        *events,
        {
            **events[0],
            "event_id": "holdout_item_event",
            "item_id": "holdout_item",
        },
    ]
    with pytest.raises(ValueError, match="non-development items"):
        select_kcs(inventory, item_leak, design)
    grammar_leak = copy.deepcopy(events)
    grammar_leak[0]["grammar_split"] = "compositional_holdout"
    with pytest.raises(ValueError, match="non-development grammar"):
        select_kcs(inventory, grammar_leak, design)


def test_learner_level_internal_split_is_supported_without_reserved_test() -> None:
    inventory, events, design = _interaction_problem()
    learner_design = copy.deepcopy(design)
    learner_design["selection_split"] = {
        "mode": "learner",
        "source_dataset_splits": ["train", "validation"],
        "validation_fraction": 0.25,
        "random_seed": 17,
    }
    policy = select_kcs(inventory, events, learner_design)
    split = policy["selection_metadata"]["split"]
    assert split["mode"] == "learner"
    assert split["train_learners"] == 45
    assert split["validation_learners"] == 15
    assert split["reserved_events_read"] is False


def test_selector_history_uses_only_prior_outcomes() -> None:
    inventory, events, design = _interaction_problem()
    subset = [row for row in events if row["learner_id"] == "learner_001"]
    train_ids = {row["event_id"] for row in subset if row["dataset_split"] == "train"}
    ids = [
        "kc_feature__left__marked",
        "kc_feature__right__marked",
    ]
    first = fit_predict_kc_logistic(
        inventory, subset, ids, design["selector_model"], train_ids
    )
    changed = copy.deepcopy(subset)
    changed[7]["correct"] = 1 - changed[7]["correct"]
    second = fit_predict_kc_logistic(
        inventory, changed, ids, design["selector_model"], train_ids
    )
    assert first[7] == second[7]


def test_observable_selector_uses_nested_no_oracle_history_features() -> None:
    inventory, events, design = _interaction_problem()
    train_ids = {row["event_id"] for row in events if row["dataset_split"] == "train"}
    base = [
        "kc_feature__left__marked",
        "kc_feature__right__marked",
    ]
    first = fit_predict_kc_logistic(
        inventory, events, base, design["selector_model"], train_ids
    )
    second = fit_predict_kc_logistic(
        inventory,
        events,
        [*base, "kc_interaction__left_marked__and__right_marked"],
        design["selector_model"],
        train_ids,
    )
    assert len(first) == len(second) == len(events)
    assert design["selector_model"]["features"] == [
        "learner_success_rate",
        "learner_log_attempts",
        "per_kc_active",
        "per_kc_prior_successes",
        "per_kc_prior_failures",
    ]


def test_bkt_selector_control_returns_online_probabilities() -> None:
    inventory, events, design = _interaction_problem()
    bkt_design = {
        "model": "bkt",
        "initial_mastery": 0.35,
        "learn": 0.12,
        "guess": 0.18,
        "slip": 0.10,
    }
    predictions = predict_kc_bkt(
        inventory,
        events,
        ["kc_feature__left__marked", "kc_feature__right__marked"],
        bkt_design,
    )
    assert len(predictions) == len(events)
    assert all(0 < row["probability"] < 1 for row in predictions)
    selector = copy.deepcopy(design)
    selector["selector_model"] = bkt_design
    policy = select_kcs(inventory, events, selector)
    assert policy["selection_metadata"]["selector_model"]["model"] == "bkt"


def test_active_selector_api_has_no_cells_fold_holdouts_or_kt_metrics() -> None:
    assert list(inspect.signature(select_kcs).parameters) == [
        "candidate_inventory",
        "development_events",
        "selection_design",
    ]


def test_addition_without_train_activation_is_reported_and_excluded() -> None:
    inventory, events, design = _interaction_problem()
    changed = copy.deepcopy(events)
    for event in changed:
        if event["item_id"] == "item_ab" and event["dataset_split"] == "train":
            event["item_id"] = "item_a"
    policy = select_kcs(inventory, changed, design)
    interaction = "kc_interaction__left_marked__and__right_marked"
    assert interaction not in policy["selection_metadata"]["eligible_addition_ids"]
    assert policy["selection_metadata"]["excluded_additions"][interaction] == {
        "train_events": 0,
        "validation_events": 60,
        "reason": "zero_train_or_validation_event_support",
    }
