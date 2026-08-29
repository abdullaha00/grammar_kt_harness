#!/usr/bin/env python3
"""Run the Phase 4A outcome-free semantic grammar-fold analysis."""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.canonicalise import validate_cell
from grammar_kt.fold import build_semantic_fold
from grammar_kt.io import read_jsonl, read_yaml, write_json, write_jsonl


SOURCE = ROOT / "experiments/post_training_v1/data/pilot_v1/opportunities.jsonl"
OUTPUT = ROOT / "reports/phase4/artifacts/fold"


def _legacy_bank(
    schema: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rows = read_jsonl(SOURCE)
    features_by_cell: dict[str, dict[str, str]] = {}
    sources_by_cell: dict[str, set[str]] = {}
    for row in rows:
        cell_id = row["canonical_cell_id"]
        features = row["cell"]
        validate_cell(features, schema)
        if cell_id in features_by_cell and features_by_cell[cell_id] != features:
            raise ValueError(f"legacy cell ID has conflicting features: {cell_id}")
        features_by_cell[cell_id] = features
        sources_by_cell.setdefault(cell_id, set()).update(row["source_descriptor_ids"])
    cells = [
        {
            "cell_id": cell_id,
            "features": features_by_cell[cell_id],
            "source_ids": sorted(sources_by_cell[cell_id]),
        }
        for cell_id in sorted(features_by_cell)
    ]
    items = [
        {
            "item_id": row["measurement_opportunity_id"],
            "cell_id": row["canonical_cell_id"],
        }
        for row in rows
    ]
    return cells, items, rows


def _feature_pairs(
    rows: list[dict[str, Any]], dimensions: list[str]
) -> set[tuple[str, str, str, str]]:
    return {
        (left, row["features"][left], right, row["features"][right])
        for row in rows
        for left, right in itertools.combinations(dimensions, 2)
    }


def _support_summary(values: list[int]) -> dict[str, Any]:
    if not values:
        return {"minimum": None, "median": None, "maximum": None}
    return {
        "minimum": min(values),
        "median": statistics.median(values),
        "maximum": max(values),
    }


def _diagnostics(
    fold: list[dict[str, Any]],
    schema: dict[str, Any],
    design: dict[str, Any],
) -> dict[str, Any]:
    dimensions = schema["dimension_order"]
    by_split = {
        split: [row for row in fold if row["grammar_split"] == split]
        for split in (
            "development",
            "compositional_holdout",
            "novel_feature_holdout",
        )
    }
    development_support = Counter(
        (dimension, row["features"][dimension])
        for row in by_split["development"]
        if row["accepted_item_support"]
        >= design["minimum_accepted_items_per_holdout_cell"]
        for dimension in dimensions
    )
    development_pairs = _feature_pairs(by_split["development"], dimensions)
    compositional_pairs = _feature_pairs(
        by_split["compositional_holdout"], dimensions
    )
    novel_pairs = _feature_pairs(by_split["novel_feature_holdout"], dimensions)
    declared_novel = {
        (dimension, value)
        for dimension, values in design.get("novel_feature_values", {}).items()
        for value in values
    }
    eligible_nonnovel = [
        row
        for row in fold
        if not any(
            (dimension, row["features"][dimension]) in declared_novel
            for dimension in dimensions
        )
        and row["accepted_item_support"]
        >= design["minimum_accepted_items_per_holdout_cell"]
    ]
    requested_compositional = math.ceil(
        len(eligible_nonnovel) * design["compositional_holdout_fraction"]
    )
    split_support = {
        split: _support_summary(
            [row["accepted_item_support"] for row in split_rows]
        )
        for split, split_rows in by_split.items()
    }
    return {
        "cell_counts": {split: len(rows) for split, rows in by_split.items()},
        "accepted_item_counts": {
            split: sum(row["accepted_item_support"] for row in rows)
            for split, rows in by_split.items()
        },
        "accepted_items_per_cell": split_support,
        "cells_without_accepted_items": sum(
            row["accepted_item_support"] == 0 for row in fold
        ),
        "compositional_target": requested_compositional,
        "compositional_achieved": len(by_split["compositional_holdout"]),
        "compositional_target_shortfall": (
            requested_compositional - len(by_split["compositional_holdout"])
        ),
        "development_value_cell_support": {
            dimension: {
                value: development_support[(dimension, value)]
                for value in schema["dimensions"][dimension]["allowed_values"]
                if development_support[(dimension, value)]
            }
            for dimension in dimensions
        },
        "compositional_value_contract": {
            "cells_with_any_unseen_development_value": sum(
                bool(row["unseen_development_values"])
                for row in by_split["compositional_holdout"]
            ),
            "minimum_constituent_support_observed": min(
                (
                    development_support[(dimension, row["features"][dimension])]
                    for row in by_split["compositional_holdout"]
                    for dimension in dimensions
                ),
                default=None,
            ),
        },
        "novel_feature_contract": {
            "cells_with_unseen_development_value": sum(
                bool(row["unseen_development_values"])
                for row in by_split["novel_feature_holdout"]
            ),
            "unseen_values": sorted(
                {
                    (entry["dimension"], entry["value"])
                    for row in by_split["novel_feature_holdout"]
                    for entry in row["unseen_development_values"]
                }
            ),
        },
        "pairwise_coverage": {
            "development_unique_value_pairs": len(development_pairs),
            "compositional_unique_value_pairs": len(compositional_pairs),
            "compositional_pairs_seen_in_development": len(
                compositional_pairs & development_pairs
            ),
            "compositional_pairs_unseen_in_development": len(
                compositional_pairs - development_pairs
            ),
            "novel_unique_value_pairs": len(novel_pairs),
            "novel_pairs_seen_in_development": len(novel_pairs & development_pairs),
            "novel_pairs_unseen_in_development": len(novel_pairs - development_pairs),
        },
        "compositional_cells": [
            {
                "cell_id": row["cell_id"],
                "features": row["features"],
                "accepted_item_support": row["accepted_item_support"],
                "development_constituent_support": {
                    dimension: development_support[
                        (dimension, row["features"][dimension])
                    ]
                    for dimension in dimensions
                },
            }
            for row in by_split["compositional_holdout"]
        ],
        "novel_feature_cells": [
            {
                "cell_id": row["cell_id"],
                "features": row["features"],
                "accepted_item_support": row["accepted_item_support"],
                "unseen_development_values": row["unseen_development_values"],
            }
            for row in by_split["novel_feature_holdout"]
        ],
    }


def _by_tuple(
    fold: list[dict[str, Any]], dimensions: list[str]
) -> dict[tuple[str, ...], str]:
    return {
        tuple(row["features"][dimension] for dimension in dimensions): row[
            "grammar_split"
        ]
        for row in fold
    }


def _invariance_control(
    schema: dict[str, Any],
    cells: list[dict[str, Any]],
    items: list[dict[str, Any]],
    design: dict[str, Any],
    reference: list[dict[str, Any]],
) -> dict[str, Any]:
    renamed_cells = [
        {**cell, "cell_id": f"renamed_{index:03d}"}
        for index, cell in enumerate(reversed(cells), 1)
    ]
    renamed_by_tuple = {
        tuple(
            cell["features"][dimension] for dimension in schema["dimension_order"]
        ): cell["cell_id"]
        for cell in renamed_cells
    }
    old_features = {cell["cell_id"]: cell["features"] for cell in cells}
    renamed_items = [
        {
            "item_id": item["item_id"],
            "cell_id": renamed_by_tuple[
                tuple(
                    old_features[item["cell_id"]][dimension]
                    for dimension in schema["dimension_order"]
                )
            ],
        }
        for item in reversed(items)
    ]
    changed = build_semantic_fold(
        schema, renamed_cells, renamed_items, copy.deepcopy(design)
    )
    invariant = _by_tuple(reference, schema["dimension_order"]) == _by_tuple(
        changed, schema["dimension_order"]
    )
    if not invariant:
        raise AssertionError("fold changed after input reversal and cell-ID renaming")
    return {
        "intervention": "reverse cells/items and replace every cell ID",
        "semantic_assignments_unchanged": invariant,
        "comparison_unit": "canonical feature tuple",
    }


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    schema = read_yaml(ROOT / "modules/grammar/canonical/schema.yaml")
    active_design = read_yaml(ROOT / "modules/simulation/folds/semantic.yaml")
    cells, items, legacy_rows = _legacy_bank(schema)
    if len(cells) != 24 or len(items) != 42:
        raise AssertionError("legacy structural artifact changed unexpectedly")
    write_jsonl(OUTPUT / "legacy_canonical_cells.jsonl", cells)
    write_jsonl(OUTPUT / "legacy_structural_items.jsonl", items)
    write_json(OUTPUT / "active_design.json", active_design)

    sensitivity = []
    active_fold: list[dict[str, Any]] | None = None
    for fraction, minimum_support in itertools.product((0.20, 0.30), (1, 2)):
        design = copy.deepcopy(active_design)
        design["compositional_holdout_fraction"] = fraction
        design["minimum_development_value_cell_support"] = minimum_support
        fold = build_semantic_fold(schema, cells, items, design)
        diagnostics = _diagnostics(fold, schema, design)
        label = f"fraction_{str(fraction).replace('.', 'p')}_min_{minimum_support}"
        write_jsonl(OUTPUT / f"assignments_{label}.jsonl", fold)
        write_json(OUTPUT / f"diagnostics_{label}.json", diagnostics)
        sensitivity.append(
            {
                "label": label,
                "design": design,
                "assignment_artifact": (
                    f"reports/phase4/artifacts/fold/assignments_{label}.jsonl"
                ),
                "diagnostics_artifact": (
                    f"reports/phase4/artifacts/fold/diagnostics_{label}.json"
                ),
                "results": diagnostics,
            }
        )
        if fraction == active_design["compositional_holdout_fraction"] and (
            minimum_support
            == active_design["minimum_development_value_cell_support"]
        ):
            active_fold = fold

    if active_fold is None:
        raise AssertionError("active design was not included in sensitivity run")
    invariance = _invariance_control(
        schema, cells, items, active_design, active_fold
    )
    write_json(OUTPUT / "id_and_order_invariance.json", invariance)
    legacy_split = {
        row["canonical_cell_id"]: row["canonical_split"] for row in legacy_rows
    }
    active_by_id = {row["cell_id"]: row["grammar_split"] for row in active_fold}
    legacy_comparison = {
        "note": "The historical split is descriptive only and was not an input to the builder.",
        "matching_cell_assignments": sum(
            active_by_id[cell_id] == split for cell_id, split in legacy_split.items()
        ),
        "total_cells": len(active_by_id),
        "transition_counts": dict(
            sorted(
                Counter(
                    f"{legacy_split[cell_id]} -> {active_by_id[cell_id]}"
                    for cell_id in active_by_id
                ).items()
            )
        ),
    }
    write_json(OUTPUT / "legacy_split_comparison.json", legacy_comparison)
    summary = {
        "experiment_id": "P4-FOLD-001",
        "date": "2026-08-27",
        "rq": "RQ8/RQ9: scalable semantic grammar folds and clean holdout roles",
        "exact_command": ".venv/bin/python scripts/run_fold_analysis.py",
        "source_artifact": str(SOURCE.relative_to(ROOT)),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "source_scale": {"cells": len(cells), "structural_items": len(items)},
        "learner_outcomes_read": False,
        "models": None,
        "seed": active_design["semantic_sampling_seed"],
        "active_design": active_design,
        "active_result": _diagnostics(active_fold, schema, active_design),
        "sensitivity": sensitivity,
        "id_and_order_invariance": invariance,
        "legacy_split_comparison": legacy_comparison,
        "interpretation": (
            "The active 0.20 fold reaches five compositional cells and one "
            "declared-value novel cell. Every compositional constituent has at "
            "least two measured development cells. Raising the requested fraction "
            "to 0.30 reaches seven cells; changing the minimum support from one to "
            "two changes no assignment at either fraction on this inventory."
        ),
    }
    write_json(OUTPUT / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
