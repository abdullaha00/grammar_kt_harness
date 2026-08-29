from __future__ import annotations

from copy import deepcopy

import pytest

from grammar_kt.generator_kcs import construct_generator_kcs
from grammar_kt.io import read_jsonl, read_yaml
from grammar_kt.measurement import audit_measurement, build_true_q_matrix

from .helpers import ROOT


def _toy_inputs():
    schema = {
        "schema_id": "toy_mood_person_v1",
        "dimension_order": ["mood", "person"],
        "dimensions": {
            "mood": {"allowed_values": ["indicative", "subjunctive"]},
            "person": {"allowed_values": ["first", "third"]},
        },
    }
    cells = [
        {
            "cell_id": "toy_1",
            "features": {"mood": "indicative", "person": "first"},
            "source_ids": ["s1"],
        },
        {
            "cell_id": "toy_2",
            "features": {"mood": "indicative", "person": "third"},
            "source_ids": ["s2"],
        },
        {
            "cell_id": "toy_3",
            "features": {"mood": "subjunctive", "person": "first"},
            "source_ids": ["s3"],
        },
    ]
    items = [
        {"item_id": f"item_{index}", "cell_id": cell["cell_id"]}
        for index, cell in enumerate(cells, 1)
    ]
    declaration = {
        "declaration_id": "toy_declared_kcs_v1",
        "language": "ToyLanguage",
        "fixed_kcs": [
            {
                "id": "toy_mood_indicative",
                "name": "indicative mood",
                "description": "Select indicative mood.",
                "activation_rule": {"cell": {"mood": "indicative"}},
                "linguistic_rationale": "Declared toy contrast.",
                "source_dimensions": ["mood"],
            },
            {
                "id": "toy_mood_subjunctive",
                "name": "subjunctive mood",
                "description": "Select subjunctive mood.",
                "activation_rule": {"cell": {"mood": "subjunctive"}},
                "linguistic_rationale": "Declared toy contrast.",
                "source_dimensions": ["mood"],
            },
            {
                "id": "toy_person_first",
                "name": "first person",
                "description": "Select first person.",
                "activation_rule": {"cell": {"person": "first"}},
                "linguistic_rationale": "Declared toy contrast.",
                "source_dimensions": ["person"],
            },
            {
                "id": "toy_person_third",
                "name": "third person",
                "description": "Select third person.",
                "activation_rule": {"cell": {"person": "third"}},
                "linguistic_rationale": "Declared toy contrast.",
                "source_dimensions": ["person"],
            },
        ],
        "expanded_dimension_kcs": [],
        "optional_interactions": [],
    }
    design = {
        "design_id": "toy_generator_v1",
        "support": {
            "minimum_cells_per_kc": 1,
            "minimum_items_per_kc_before_simulation": 1,
            "rare_kc_cell_threshold": 1,
            "rare_kc_item_threshold": 1,
        },
        "identifiability": {
            "require_nonempty_item_projection": True,
            "require_unique_q_columns": True,
            "require_full_column_rank": False,
            "near_identical_jaccard": 0.9,
        },
    }
    return schema, cells, items, declaration, design


def test_medium_hybrid_reproduces_outcome_free_nine_kc_structure() -> None:
    cells = read_jsonl(ROOT / "data/grammar_kt_medium_v1/canonical/cells.jsonl")
    items = read_jsonl(ROOT / "data/grammar_kt_medium_v1/items/selected_bank.jsonl")
    schema = read_yaml(ROOT / "modules/grammar/canonical/schema.yaml")
    design = read_yaml(ROOT / "modules/kcs/generator/design.yaml")
    declaration = read_yaml(ROOT / "modules/kcs/generator/english_kcs.yaml")

    inventory = construct_generator_kcs(cells, schema, design, declaration)
    q_rows = build_true_q_matrix(items, cells, inventory)
    audit = audit_measurement(cells, items, inventory, q_rows, design)

    assert len(inventory["kcs"]) == 9
    assert inventory["metadata"]["learner_outcomes_read"] is False
    assert inventory["metadata"]["items_read"] is False
    assert audit["status"] == "PASS"
    assert audit["counts"] | {
        "generator_kcs": 9,
        "q_rank": 9,
        "distinct_cell_activation_rows": 24,
    } == audit["counts"]
    assert audit["identical_q_columns"] == []


def test_generic_toy_schema_constructs_k_star_and_q_without_english_names() -> None:
    schema, cells, items, declaration, design = _toy_inputs()
    inventory = construct_generator_kcs(cells, schema, design, declaration)
    q_rows = build_true_q_matrix(items, cells, inventory)

    assert {row["id"] for row in inventory["kcs"]} == {
        "toy_mood_indicative",
        "toy_mood_subjunctive",
        "toy_person_first",
        "toy_person_third",
    }
    assert all(row["generator_kc_ids"] for row in q_rows)
    assert all("tense" not in str(row) for row in [*inventory["kcs"], *q_rows])


def test_measurement_audit_rejects_activation_equivalent_generator_kcs() -> None:
    schema, cells, items, declaration, design = _toy_inputs()
    duplicate = deepcopy(declaration["fixed_kcs"][0])
    duplicate["id"] = "toy_duplicate_indicative"
    declaration["fixed_kcs"].append(duplicate)
    inventory = construct_generator_kcs(cells, schema, design, declaration)
    q_rows = build_true_q_matrix(items, cells, inventory)
    audit = audit_measurement(cells, items, inventory, q_rows, design)

    assert audit["status"] == "FAIL"
    assert "identical_q_columns" in audit["failures"]
    assert inventory["activation_equivalence_classes"]


def test_true_q_requires_every_item_to_activate_generator_truth() -> None:
    schema, cells, items, declaration, design = _toy_inputs()
    declaration["fixed_kcs"] = [declaration["fixed_kcs"][1]]
    inventory = construct_generator_kcs(cells, schema, design, declaration)

    with pytest.raises(ValueError, match="no active generator KC"):
        build_true_q_matrix(items, cells, inventory)
