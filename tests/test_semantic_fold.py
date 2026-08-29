from __future__ import annotations

import copy
import inspect
import itertools
from collections import Counter

from grammar_kt.fold import build_semantic_fold


def _toy_bank() -> tuple[dict, list[dict], list[dict], dict]:
    schema = {
        "schema_id": "alternate_mood_schema",
        "dimension_order": ["mood", "person", "number"],
        "dimensions": {
            "mood": {
                "allowed_values": ["indicative", "subjunctive", "imperative"]
            },
            "person": {"allowed_values": ["first", "second", "third"]},
            "number": {"allowed_values": ["singular", "plural"]},
        },
    }
    tuples = list(
        itertools.product(
            ["indicative", "subjunctive"],
            ["first", "second", "third"],
            ["singular", "plural"],
        )
    ) + [
        ("imperative", "second", "singular"),
        ("imperative", "second", "plural"),
    ]
    cells = [
        {
            "cell_id": f"toy_{index:02d}",
            "features": dict(zip(schema["dimension_order"], values, strict=True)),
        }
        for index, values in enumerate(tuples, 1)
    ]
    items = [
        {"item_id": f"item_{index:02d}", "cell_id": cell["cell_id"]}
        for index, cell in enumerate(cells, 1)
    ]
    design = {
        "fold_id": "alternate_semantic_fold",
        "compositional_holdout_fraction": 0.25,
        "minimum_development_value_cell_support": 2,
        "minimum_accepted_items_per_holdout_cell": 1,
        "semantic_sampling_seed": 31,
        "novel_feature_values": {"mood": ["imperative"]},
    }
    return schema, cells, items, design


def _by_features(rows: list[dict], dimensions: list[str]) -> dict[tuple, str]:
    return {
        tuple(row["features"][dimension] for dimension in dimensions): row[
            "grammar_split"
        ]
        for row in rows
    }


def test_semantic_fold_has_true_compositional_and_novel_feature_roles() -> None:
    schema, cells, items, design = _toy_bank()
    fold = build_semantic_fold(schema, cells, items, design)
    by_split = Counter(row["grammar_split"] for row in fold)
    assert by_split == {
        "development": 9,
        "compositional_holdout": 3,
        "novel_feature_holdout": 2,
    }

    development = [row for row in fold if row["grammar_split"] == "development"]
    support = Counter(
        (dimension, row["features"][dimension])
        for row in development
        for dimension in schema["dimension_order"]
    )
    for row in fold:
        if row["grammar_split"] == "compositional_holdout":
            assert not row["unseen_development_values"]
            assert all(
                support[(dimension, row["features"][dimension])] >= 2
                for dimension in schema["dimension_order"]
            )
        if row["grammar_split"] == "novel_feature_holdout":
            assert row["features"]["mood"] == "imperative"
            assert {entry["dimension"] for entry in row["unseen_development_values"]} == {
                "mood"
            }


def test_semantic_fold_is_input_order_and_cell_id_invariant() -> None:
    schema, cells, items, design = _toy_bank()
    first = build_semantic_fold(schema, cells, items, design)
    second = build_semantic_fold(
        schema, list(reversed(cells)), list(reversed(items)), design
    )
    assert first == second

    renamed_cells = [
        {**cell, "cell_id": f"renamed_{index:02d}"}
        for index, cell in enumerate(reversed(cells), 1)
    ]
    rename_by_features = {
        tuple(cell["features"].values()): cell["cell_id"] for cell in renamed_cells
    }
    renamed_items = [
        {
            "item_id": item["item_id"],
            "cell_id": rename_by_features[
                tuple(
                    next(
                        cell["features"]
                        for cell in cells
                        if cell["cell_id"] == item["cell_id"]
                    ).values()
                )
            ],
        }
        for item in items
    ]
    renamed = build_semantic_fold(schema, renamed_cells, renamed_items, design)
    assert _by_features(first, schema["dimension_order"]) == _by_features(
        renamed, schema["dimension_order"]
    )


def test_semantic_fold_reads_only_item_identity_and_cell_membership() -> None:
    schema, cells, items, design = _toy_bank()
    first = build_semantic_fold(schema, cells, items, design)
    outcome_mutation = [
        {**item, "correct": index % 2, "response_probability": index / 100}
        for index, item in enumerate(items)
    ]
    assert build_semantic_fold(schema, cells, outcome_mutation, design) == first
    assert list(inspect.signature(build_semantic_fold).parameters) == [
        "schema",
        "cells",
        "accepted_items",
        "design",
    ]


def test_cells_without_fixed_item_support_cannot_become_holdouts() -> None:
    schema, cells, items, design = _toy_bank()
    unsupported_id = cells[0]["cell_id"]
    items = [item for item in items if item["cell_id"] != unsupported_id]
    changed = copy.deepcopy(design)
    changed["compositional_holdout_fraction"] = 0.9
    changed["minimum_development_value_cell_support"] = 1
    fold = build_semantic_fold(schema, cells, items, changed)
    unsupported = next(row for row in fold if row["cell_id"] == unsupported_id)
    assert unsupported["grammar_split"] == "development"
    assert unsupported["selection_reason"] == (
        "insufficient_fixed_item_support_for_holdout"
    )
    assert unsupported["accepted_item_support"] == 0
