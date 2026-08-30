from __future__ import annotations

import copy
import inspect
from pathlib import Path

import numpy as np
import pytest

from grammar_kt.io import read_jsonl, read_yaml

from scripts.experiments.rq3_kc_discovery import (
    DEFAULT_DATASET,
    build_candidate_space,
    build_observable_history_matrix,
    make_plan,
    project_policy,
    run_selection,
    selection_events_from_rows,
    structural_recovery_metrics,
)


def test_selection_boundary_ignores_probe_outcomes_and_rejects_oracle_fields() -> None:
    rows = [
        {
            "learner_id": "learner_1",
            "item_id": "seen_item",
            "sequence_index": 1,
            "correct": 1,
            "phase": "acquisition",
            "pass_index": 1,
            "grammar_regime": "seen",
        },
        {
            "learner_id": "learner_1",
            "item_id": "probe_item",
            "sequence_index": 2,
            "correct": 0,
            "phase": "probe",
            "pass_index": 1,
            "grammar_regime": "unseen_value",
        },
    ]
    first = selection_events_from_rows(rows, learner_ids={"learner_1"})
    changed = copy.deepcopy(rows)
    changed[1]["correct"] = 1
    changed[1]["mastery_before"] = 0.99
    second = selection_events_from_rows(changed, learner_ids={"learner_1"})
    assert first == second
    assert first == [
        {
            "event_id": "learner_1__0001",
            "learner_id": "learner_1",
            "item_id": "seen_item",
            "sequence_index": 1,
            "correct": 1,
        }
    ]
    leaked = copy.deepcopy(rows)
    leaked[0]["response_probability"] = 0.8
    with pytest.raises(ValueError, match="oracle fields"):
        selection_events_from_rows(leaked, learner_ids={"learner_1"})


def test_observable_histories_are_prior_only_and_probes_do_not_update() -> None:
    events = [
        {
            "learner_id": "l1",
            "item_id": "i1",
            "sequence_index": 1,
            "correct": 1,
            "updates_history": True,
        },
        {
            "learner_id": "l1",
            "item_id": "i1",
            "sequence_index": 2,
            "correct": 0,
            "updates_history": False,
        },
        {
            "learner_id": "l1",
            "item_id": "i1",
            "sequence_index": 3,
            "correct": 0,
            "updates_history": False,
        },
    ]
    support = {"kc": {"i1"}}
    first, first_y, _ = build_observable_history_matrix(
        events, ["kc"], support, alpha=1.0, beta=1.0, update_field="updates_history"
    )
    changed = copy.deepcopy(events)
    changed[1]["correct"] = 1
    changed[2]["correct"] = 1
    second, second_y, _ = build_observable_history_matrix(
        changed, ["kc"], support, alpha=1.0, beta=1.0, update_field="updates_history"
    )
    np.testing.assert_array_equal(first, second)
    assert first_y.tolist() == [1, 0, 0]
    assert second_y.tolist() == [1, 1, 1]
    # Both probes see exactly one prior success; the first probe never updates.
    np.testing.assert_array_equal(first[1], first[2])


def test_name_free_structural_recovery_detects_exact_merge_split_and_spurious() -> None:
    true = {
        "i1": {"a"},
        "i2": {"b"},
        "i3": {"a", "b"},
        "i4": set(),
    }
    exact_renamed = {
        "i1": {"x"},
        "i2": {"y"},
        "i3": {"x", "y"},
        "i4": set(),
    }
    exact = structural_recovery_metrics(
        true, exact_renamed, item_ids=sorted(true)
    )
    assert exact["characterisation"]["unique_exact_recovery"] is True
    assert exact["aligned_q_edges"]["f1"] == 1.0

    merged = {item: ({"m"} if values else set()) for item, values in true.items()}
    merge_result = structural_recovery_metrics(true, merged, item_ids=sorted(true))
    assert merge_result["characterisation"]["merge_candidates"]

    split_true = {"i1": {"a"}, "i2": {"a"}, "i3": {"a"}, "i4": set()}
    split_predicted = {
        "i1": {"left"},
        "i2": {"right"},
        "i3": {"third"},
        "i4": {"noise"},
    }
    split_result = structural_recovery_metrics(
        split_true, split_predicted, item_ids=sorted(split_true)
    )
    assert split_result["characterisation"]["split_true_kcs"]
    assert split_result["characterisation"]["spurious_zero_overlap_predicted_kc_ids"] == [
        "noise"
    ]


def test_candidate_space_uses_seen_construction_and_every_policy_projects_all_items() -> None:
    schema = {
        "schema_id": "toy",
        "dimension_order": ["mood", "polarity"],
        "dimensions": {
            "mood": {"allowed_values": ["plain", "marked"]},
            "polarity": {"allowed_values": ["positive", "negative"]},
        },
    }
    cells = [
        {"cell_id": "c1", "features": {"mood": "plain", "polarity": "positive"}},
        {"cell_id": "c2", "features": {"mood": "marked", "polarity": "positive"}},
        {"cell_id": "c3", "features": {"mood": "marked", "polarity": "negative"}},
    ]
    items = [
        {"item_id": f"i{index}", "cell_id": cell["cell_id"]}
        for index, cell in enumerate(cells, 1)
    ]
    regimes = [
        {"cell_id": "c1", "grammar_regime": "seen"},
        {"cell_id": "c2", "grammar_regime": "seen"},
        {"cell_id": "c3", "grammar_regime": "unseen_combination"},
    ]
    design = {
        "candidate_design_id": "toy",
        "candidate_types": {
            "feature_values": True,
            "operations": True,
            "pairwise_interactions": True,
            "full_cells": True,
        },
        "background_values": {"mood": ["plain"], "polarity": ["positive"]},
        "minimum_interaction_cell_support": 1,
        "minimum_interaction_item_support": 1,
        "equivalence_representative_order": [
            "feature_value",
            "operation",
            "interaction",
            "full_cell",
        ],
    }
    operations = {
        "operations": [
            {
                "id": "perfect_dependency",
                "definition": "toy replacement",
                "activation": {"cell": {"mood": "marked"}},
            },
            {
                "id": "progressive_dependency",
                "definition": "toy replacement",
                "activation": {"cell": {"mood": "marked"}},
            },
        ]
    }
    plan = {
        "candidate_space": {
            "hash_distractor_seed": 7,
            "hash_distractor_count": 1,
        },
        "selection": {
            "whole_policy_ids": [
                "atomic_features",
                "compositional_operations",
                "coarse_operations",
                "fine_exact_cells",
                "structural_splits",
                "compositional_plus_interactions",
                "hash_distractor_negative_control",
            ]
        },
    }
    # The production English replacements are intentionally schema-specific;
    # this toy contract exercises the projection primitive directly instead.
    candidate = {
        "id": "fine_c1",
        "rule": {
            "kind": "activation",
            "activation": {"cell": cells[0]["features"]},
        },
    }
    projection = project_policy(items, cells, {"fine_c1": candidate}, ["fine_c1"])
    assert len(projection) == len(items)
    assert projection[-1]["kc_ids"] == []


def test_full_candidate_space_retains_seen_ambiguity_and_truth_reachable_ceiling() -> None:
    plan = make_plan(DEFAULT_DATASET)
    # Repository-relative paths resolve from the repository root, not data/.
    root = DEFAULT_DATASET.parents[1]
    paths = {
        name: Path(row["path"]) if Path(row["path"]).is_absolute() else root / row["path"]
        for name, row in plan["inputs"]["selection_public"].items()
    }
    cells = read_jsonl(paths["cells"])
    items = read_jsonl(paths["items"])
    space = build_candidate_space(
        read_yaml(paths["grammar_schema"]),
        cells,
        items,
        read_jsonl(paths["regimes"]),
        read_yaml(paths["candidate_design"]),
        read_yaml(paths["operation_declarations"]),
        plan,
    )
    candidates = {row["id"]: row for row in space["candidates"]}
    atomic = project_policy(
        items, cells, candidates, space["policies"]["atomic_features"]
    )
    compositional = project_policy(
        items, cells, candidates, space["policies"]["compositional_operations"]
    )
    seen_items = set(space["seen_item_ids"])
    def signature(rows: list[dict]) -> list[tuple[str, ...]]:
        selected = [row for row in rows if row["item_id"] in seen_items]
        kc_ids = sorted({kc_id for row in selected for kc_id in row["kc_ids"]})
        return sorted(
            tuple(row["item_id"] for row in selected if kc_id in row["kc_ids"])
            for kc_id in kc_ids
        )

    assert signature(atomic) == signature(compositional)
    assert any(
        len(left["kc_ids"]) != len(right["kc_ids"])
        for left, right in zip(atomic, compositional, strict=True)
        if left["item_id"] not in seen_items
    )


def test_selection_entry_point_cannot_accept_truth_inputs() -> None:
    parameters = inspect.signature(run_selection).parameters
    assert "generator_kcs" not in parameters
    assert "q_matrix" not in parameters
    assert "oracle" not in parameters
