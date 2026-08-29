from __future__ import annotations

import copy
import inspect

import pytest

from grammar_kt.kc_candidates import make_kc_candidates
from grammar_kt.kc import project_kcs

from .helpers import GRAMMAR_SCHEMA, ROOT, base_bank


def _design() -> dict:
    from grammar_kt.io import read_yaml

    design = read_yaml(ROOT / "modules/kcs/candidate_design.yaml")
    operations = read_yaml(
        ROOT / "modules/grammar/canonical/english_operations.yaml"
    )
    return design | {"operation_declarations": operations["operations"]}


def _fixture_inventory() -> tuple[dict, list[dict], list[dict], list[dict]]:
    _mappings, cells, _candidates, items, _judgments, fold = base_bank()
    development_ids = {
        row["cell_id"]
        for row in fold
        if row["grammar_split"] == "development"
    }
    development_cells = [
        row for row in cells if row["cell_id"] in development_ids
    ]
    development_items = [
        row for row in items if row["cell_id"] in development_ids
    ]
    inventory = make_kc_candidates(
        GRAMMAR_SCHEMA, development_cells, development_items, _design()
    )
    return inventory, cells, development_cells, development_items


def test_candidates_are_schema_derived_and_background_is_explicit() -> None:
    inventory, _cells, _development_cells, _development_items = _fixture_inventory()
    features = {
        row["id"]: row
        for row in inventory["candidates"]
        if row["family"] == "feature_value"
    }
    assert set(features) == {
        "kc_feature__tense__present",
        "kc_feature__tense__past",
        "kc_feature__aspect__progressive",
        "kc_feature__voice__passive",
        "kc_feature__polarity__negative",
    }
    assert "kc_feature__aspect__none" not in features
    assert "kc_feature__voice__active" not in features
    assert inventory["metadata"] == {
        "item_fields_read": ["item_id", "cell_id"],
        "learner_outcomes_read": False,
        "held_out_grammar_read": False,
        "equivalence_scope": "development_item_bank_only",
    }


def test_background_treatment_changes_candidates_without_python_conventions() -> None:
    _inventory, _cells, development_cells, development_items = _fixture_inventory()
    changed = _design()
    changed["background_values"]["tense"].append("present")
    inventory = make_kc_candidates(
        GRAMMAR_SCHEMA, development_cells, development_items, changed
    )
    ids = {row["id"] for row in inventory["candidates"]}
    assert "kc_feature__tense__present" not in ids
    assert "kc_feature__tense__past" in ids


def test_pairwise_candidates_are_supported_and_activate_as_conjunctions() -> None:
    inventory, _cells, _development_cells, _development_items = _fixture_inventory()
    interactions = [
        row for row in inventory["candidates"] if row["family"] == "interaction"
    ]
    assert interactions
    assert all(row["item_support"] > 0 for row in interactions)
    past_negative = next(
        row
        for row in interactions
        if row["conditions"]
        == [["polarity", "negative"], ["tense", "past"]]
    )
    assert past_negative["supporting_development_cell_ids"] == ["cell_002"]
    assert past_negative["supporting_development_item_ids"] == [
        "candidate_cell_002_01"
    ]
    assert past_negative["cell_support"] == 1
    assert past_negative["item_support"] == 1
    assert past_negative["meets_support_threshold"] is False
    assert "below_interaction_support_threshold" in past_negative["exclusion_reasons"]


def test_repeated_items_do_not_inflate_interaction_cell_support() -> None:
    schema = {
        "schema_id": "support_toy",
        "dimension_order": ["left", "right"],
        "dimensions": {
            "left": {"allowed_values": ["reference", "marked"]},
            "right": {"allowed_values": ["reference", "marked"]},
        },
    }
    cells = [
        {
            "cell_id": "only_cell",
            "features": {"left": "marked", "right": "marked"},
        }
    ]
    items = [
        {"item_id": f"repeat_{index}", "cell_id": "only_cell"}
        for index in range(5)
    ]
    design = {
        "candidate_design_id": "support_toy",
        "candidate_types": {
            "feature_values": True,
            "operations": False,
            "pairwise_interactions": True,
            "full_cells": False,
        },
        "background_values": {
            "left": ["reference"],
            "right": ["reference"],
        },
        "minimum_interaction_cell_support": 2,
        "minimum_interaction_item_support": 3,
        "equivalence_representative_order": [
            "feature_value",
            "operation",
            "interaction",
            "full_cell",
        ],
    }
    inventory = make_kc_candidates(schema, cells, items, design)
    interaction = next(
        row for row in inventory["candidates"] if row["family"] == "interaction"
    )
    assert interaction["item_support"] == 5
    assert interaction["cell_support"] == 1
    assert interaction["meets_support_threshold"] is False


def test_full_cell_candidates_are_development_only() -> None:
    inventory, _cells, development_cells, _development_items = _fixture_inventory()
    full_cells = [
        row for row in inventory["candidates"] if row["family"] == "full_cell"
    ]
    assert {row["development_cell_id"] for row in full_cells} == {
        row["cell_id"] for row in development_cells
    }
    assert not any("should" in row["id"] for row in full_cells)


def test_activation_equivalence_is_deterministic_and_bank_scoped() -> None:
    first, _cells, development_cells, development_items = _fixture_inventory()
    second = make_kc_candidates(
        GRAMMAR_SCHEMA,
        list(reversed(development_cells)),
        list(reversed(development_items)),
        _design(),
    )
    assert first == second
    progressive_operation = next(
        row
        for row in first["candidates"]
        if row["id"] == "kc_operation__progressive_dependency"
    )
    assert progressive_operation["equivalent_to"] == "kc_feature__aspect__progressive"
    assert progressive_operation["selection_eligible"] is False


def test_holdout_mutation_and_item_outcomes_cannot_change_candidates() -> None:
    inventory, cells, development_cells, development_items = _fixture_inventory()
    cells_before = copy.deepcopy(development_cells)
    items_before = copy.deepcopy(development_items)
    development_ids = {row["cell_id"] for row in development_cells}
    changed_cells = copy.deepcopy(cells)
    for cell in changed_cells:
        if cell["cell_id"] not in development_ids:
            cell["features"] = {
                dimension: "UNREAD_HOLDOUT"
                for dimension in GRAMMAR_SCHEMA["dimension_order"]
            }
    partitioned = [
        row for row in changed_cells if row["cell_id"] in development_ids
    ]
    outcome_items = [
        {**row, "correct": index % 2, "response_probability": index / 10}
        for index, row in enumerate(development_items)
    ]
    changed = make_kc_candidates(
        GRAMMAR_SCHEMA, partitioned, outcome_items, _design()
    )
    assert changed == inventory
    assert development_cells == cells_before
    assert development_items == items_before
    assert list(inspect.signature(make_kc_candidates).parameters) == [
        "grammar_schema",
        "development_cells",
        "development_items",
        "candidate_design",
    ]


def test_alternate_schema_works_without_english_feature_names() -> None:
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
            "cell_id": "toy_1",
            "features": {"mood": "plain", "person": "first"},
        },
        {
            "cell_id": "toy_2",
            "features": {"mood": "witnessed", "person": "third"},
        },
    ]
    items = [
        {"item_id": "toy_item_1", "cell_id": "toy_1"},
        {"item_id": "toy_item_2", "cell_id": "toy_2"},
    ]
    design = {
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
    inventory = make_kc_candidates(schema, cells, items, design)
    ids = {row["id"] for row in inventory["candidates"]}
    assert "kc_feature__mood__witnessed" in ids
    assert "kc_feature__person__third" in ids
    assert (
        "kc_interaction__mood_witnessed__and__person_third" in ids
    )
    assert inventory["grammar_schema_id"] == "toy_language_v1"
    policy = {
        "policy_id": "toy_selected",
        "kcs": [
            {
                "id": row["id"],
                "definition": row["definition"],
                "activation": row["activation"],
            }
            for row in inventory["candidates"]
            if row["selection_eligible"]
        ],
    }
    projection = project_kcs(items, cells, policy)
    assert projection[1]["kc_ids"]


def test_nondevelopment_items_are_rejected_before_support() -> None:
    _inventory, _cells, development_cells, development_items = _fixture_inventory()
    with pytest.raises(ValueError, match="non-development item cells"):
        make_kc_candidates(
            GRAMMAR_SCHEMA,
            development_cells,
            [*development_items, {"item_id": "leak", "cell_id": "cell_005"}],
            _design(),
        )
