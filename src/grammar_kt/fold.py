"""Stage 5: construct or apply a grammar-level fold without learner outcomes."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from typing import Any

SPLITS = {"development", "compositional_holdout", "novel_feature_holdout"}


def _semantic_key(
    cell: dict[str, Any], dimensions: list[str], seed: int
) -> tuple[str, tuple[str, ...]]:
    """Return an ID-independent deterministic pseudo-random ordering key."""

    values = tuple(cell["features"][dimension] for dimension in dimensions)
    payload = json.dumps([seed, *values], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest(), values


def build_semantic_fold(
    schema: dict[str, Any],
    cells: list[dict[str, Any]],
    accepted_items: list[dict[str, Any]],
    design: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build a deterministic semantic fold from the fixed accepted item bank.

    Novel values are an explicit language/resource-facing choice.  All cells
    containing one are held out, which makes the value absent from development.
    Compositional cells are sampled by their feature tuple (never by cell ID)
    while retaining the configured development-cell support for every one of
    their individual feature values.  Learner responses are neither required
    nor read.
    """

    dimensions = list(schema["dimension_order"])
    if not cells:
        raise ValueError("semantic fold requires at least one GrammarCell")
    cell_ids = [cell["cell_id"] for cell in cells]
    if len(set(cell_ids)) != len(cell_ids):
        raise ValueError("GrammarCell IDs must be unique")
    expected_dimensions = set(dimensions)
    feature_tuples: set[tuple[str, ...]] = set()
    for cell in cells:
        features = cell["features"]
        if set(features) != expected_dimensions:
            raise ValueError(f"GrammarCell has wrong dimensions: {cell['cell_id']}")
        for dimension in dimensions:
            allowed = schema["dimensions"][dimension]["allowed_values"]
            if features[dimension] not in allowed:
                raise ValueError(
                    f"invalid GrammarCell value: {dimension}={features[dimension]}"
                )
        feature_tuple = tuple(features[dimension] for dimension in dimensions)
        if feature_tuple in feature_tuples:
            raise ValueError("semantic fold requires unique feature tuples")
        feature_tuples.add(feature_tuple)

    item_ids: set[str] = set()
    item_count_by_cell: Counter[str] = Counter()
    known_cells = set(cell_ids)
    for item in accepted_items:
        item_id = item["item_id"]
        if item_id in item_ids:
            raise ValueError(f"accepted item ID is duplicated: {item_id}")
        if item["cell_id"] not in known_cells:
            raise ValueError(f"accepted item refers to unknown cell: {item_id}")
        item_ids.add(item_id)
        item_count_by_cell[item["cell_id"]] += 1

    fraction = float(design["compositional_holdout_fraction"])
    if not 0.0 <= fraction < 1.0:
        raise ValueError("compositional_holdout_fraction must be in [0, 1)")
    minimum_value_support = int(design["minimum_development_value_cell_support"])
    minimum_item_support = int(design["minimum_accepted_items_per_holdout_cell"])
    if minimum_value_support < 1 or minimum_item_support < 1:
        raise ValueError("semantic fold support minima must be positive")

    novel_pairs: set[tuple[str, str]] = set()
    for dimension, values in design.get("novel_feature_values", {}).items():
        if dimension not in expected_dimensions:
            raise ValueError(f"unknown novel-value dimension: {dimension}")
        allowed = set(schema["dimensions"][dimension]["allowed_values"])
        for value in values:
            if value not in allowed:
                raise ValueError(f"unknown novel feature value: {dimension}={value}")
            novel_pairs.add((dimension, value))
    observed_pairs = {
        (dimension, cell["features"][dimension])
        for cell in cells
        for dimension in dimensions
    }
    unobserved_declarations = novel_pairs - observed_pairs
    if unobserved_declarations:
        raise ValueError(
            f"declared novel values are absent from the cells: {sorted(unobserved_declarations)}"
        )

    novel_ids = {
        cell["cell_id"]
        for cell in cells
        if any(
            (dimension, cell["features"][dimension]) in novel_pairs
            for dimension in dimensions
        )
    }
    eligible = [
        cell
        for cell in cells
        if cell["cell_id"] not in novel_ids
        and item_count_by_cell[cell["cell_id"]] >= minimum_item_support
    ]
    target = math.ceil(len(eligible) * fraction)

    development_ids = {cell["cell_id"] for cell in eligible}
    value_support: Counter[tuple[str, str]] = Counter(
        (dimension, cell["features"][dimension])
        for cell in eligible
        for dimension in dimensions
    )
    compositional_ids: set[str] = set()
    seed = int(design["semantic_sampling_seed"])
    for cell in sorted(eligible, key=lambda row: _semantic_key(row, dimensions, seed)):
        if len(compositional_ids) >= target:
            break
        constituents = [
            (dimension, cell["features"][dimension]) for dimension in dimensions
        ]
        if any(
            value_support[constituent] - 1 < minimum_value_support
            for constituent in constituents
        ):
            continue
        compositional_ids.add(cell["cell_id"])
        development_ids.remove(cell["cell_id"])
        value_support.subtract(constituents)

    # Cells without sufficient fixed-bank support remain available grammar but
    # cannot be evaluation holdouts.  They do not count as measured value support.
    development_ids.update(known_cells - novel_ids - compositional_ids)
    measured_development_ids = {
        cell_id
        for cell_id in development_ids
        if item_count_by_cell[cell_id] >= minimum_item_support
    }
    measured_development_support: Counter[tuple[str, str]] = Counter(
        (dimension, cell["features"][dimension])
        for cell in cells
        if cell["cell_id"] in measured_development_ids
        for dimension in dimensions
    )
    seen = set(measured_development_support)

    item_ids_by_cell: dict[str, list[str]] = {cell_id: [] for cell_id in cell_ids}
    for item in accepted_items:
        item_ids_by_cell[item["cell_id"]].append(item["item_id"])
    rows = []
    for cell in sorted(cells, key=lambda row: _semantic_key(row, dimensions, seed)):
        cell_id = cell["cell_id"]
        constituents = [
            (dimension, cell["features"][dimension]) for dimension in dimensions
        ]
        unseen = [
            {"dimension": dimension, "value": value}
            for dimension, value in constituents
            if (dimension, value) not in seen
        ]
        if cell_id in novel_ids:
            split = "novel_feature_holdout"
            reason = "contains_declared_novel_feature_value"
            if not unseen:
                raise ValueError(f"novel-feature holdout lacks an unseen value: {cell_id}")
        elif cell_id in compositional_ids:
            split = "compositional_holdout"
            reason = "semantic_sample_with_supported_development_constituents"
            if unseen:
                raise ValueError(f"compositional holdout has unseen values: {cell_id}")
            if any(
                measured_development_support[constituent] < minimum_value_support
                for constituent in constituents
            ):
                raise ValueError(
                    f"compositional holdout lacks configured value support: {cell_id}"
                )
        else:
            split = "development"
            reason = (
                "insufficient_fixed_item_support_for_holdout"
                if item_count_by_cell[cell_id] < minimum_item_support
                else "development_acquisition"
            )
        rows.append(
            {
                "cell_id": cell_id,
                "grammar_split": split,
                "features": dict(cell["features"]),
                "accepted_item_ids": sorted(item_ids_by_cell[cell_id]),
                "accepted_item_support": item_count_by_cell[cell_id],
                "unseen_development_values": unseen,
                "selection_reason": reason,
            }
        )
    return rows


def apply_fold(
    cells: list[dict[str, Any]], fold_spec: dict[str, Any]
) -> list[dict[str, Any]]:
    declared = fold_spec["assignments"]
    cell_ids = {cell["cell_id"] for cell in cells}
    if set(declared) != cell_ids:
        raise ValueError("fold manifest must assign every and only canonical cell")
    rows = []
    for cell in cells:
        split = declared[cell["cell_id"]]["split"]
        if split not in SPLITS:
            raise ValueError(f"unknown grammar split: {split}")
        rows.append({"cell_id": cell["cell_id"], "grammar_split": split, "features": cell["features"]})

    development = [row for row in rows if row["grammar_split"] == "development"]
    seen = {(field, value) for row in development for field, value in row["features"].items()}
    for row in rows:
        unseen = {(field, value) for field, value in row["features"].items() if (field, value) not in seen}
        if row["grammar_split"] == "compositional_holdout" and unseen:
            raise ValueError(f"compositional holdout has unseen features: {row['cell_id']}")
        if row["grammar_split"] == "novel_feature_holdout" and not unseen:
            raise ValueError(f"novel-feature holdout lacks an unseen feature: {row['cell_id']}")
    return rows
