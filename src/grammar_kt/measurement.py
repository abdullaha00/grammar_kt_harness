"""Deterministic Q* construction and pre-simulation measurement diagnostics."""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Any

import numpy as np

from .kc import activation_matches


def build_true_q_matrix(
    items: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    generator_inventory: dict[str, Any],
    *,
    require_nonempty: bool = True,
) -> list[dict[str, Any]]:
    """Project fixed items onto fixed K* without learner-response evidence."""

    cell_by_id = {row["cell_id"]: row for row in cells}
    if len(cell_by_id) != len(cells):
        raise ValueError("Q* construction received duplicate GrammarCell IDs")
    kc_ids = [row["id"] for row in generator_inventory["kcs"]]
    if len(kc_ids) != len(set(kc_ids)):
        raise ValueError("Q* construction received duplicate generator-KC IDs")
    rows = []
    for item in sorted(items, key=lambda row: row["item_id"]):
        cell_id = item["cell_id"]
        if cell_id not in cell_by_id:
            raise ValueError(f"item refers to unknown GrammarCell: {item['item_id']}")
        features = cell_by_id[cell_id]["features"]
        active = sorted(
            kc["id"]
            for kc in generator_inventory["kcs"]
            if activation_matches(features, kc["activation_rule"])
        )
        if require_nonempty and not active:
            raise ValueError(f"item has no active generator KC: {item['item_id']}")
        rows.append(
            {
                "item_id": item["item_id"],
                "cell_id": cell_id,
                "generator_kc_ids": active,
            }
        )
    return rows


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def audit_measurement(
    cells: list[dict[str, Any]],
    items: list[dict[str, Any]],
    generator_inventory: dict[str, Any],
    q_rows: list[dict[str, Any]],
    design: dict[str, Any],
    *,
    grammar_regime_by_cell: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Audit support, co-occurrence, equivalence, and Q* rank before simulation."""

    item_by_id = {row["item_id"]: row for row in items}
    if len(item_by_id) != len(items):
        raise ValueError("measurement audit received duplicate item IDs")
    if {row["item_id"] for row in q_rows} != set(item_by_id):
        raise ValueError("Q* rows and fixed item IDs differ")
    cell_ids = {row["cell_id"] for row in cells}
    kc_ids = sorted(row["id"] for row in generator_inventory["kcs"])
    if not kc_ids:
        raise ValueError("measurement audit received an empty K* inventory")

    active_by_item = {
        row["item_id"]: set(row["generator_kc_ids"]) for row in q_rows
    }
    unknown_edges = set().union(*active_by_item.values()) - set(kc_ids)
    if unknown_edges:
        raise ValueError(f"Q* contains unknown generator KCs: {sorted(unknown_edges)}")
    q = np.asarray(
        [
            [int(kc_id in active_by_item[item_id]) for kc_id in kc_ids]
            for item_id in sorted(item_by_id)
        ],
        dtype=float,
    )
    rank = int(np.linalg.matrix_rank(q))
    item_support = {
        kc_id: int(q[:, index].sum()) for index, kc_id in enumerate(kc_ids)
    }
    cells_by_kc = {
        kc_id: {
            item_by_id[item_id]["cell_id"]
            for item_id, active in active_by_item.items()
            if kc_id in active
        }
        for kc_id in kc_ids
    }
    cell_support = {kc_id: len(values) for kc_id, values in cells_by_kc.items()}
    isolated_support = {
        kc_id: sum(
            active == {kc_id} for active in active_by_item.values()
        )
        for kc_id in kc_ids
    }

    identical_columns = []
    near_identical_columns = []
    pair_contrasts = []
    near_threshold = float(
        design.get("identifiability", {}).get("near_identical_jaccard", 0.9)
    )
    supporting_items = {
        kc_id: {
            item_id for item_id, active in active_by_item.items() if kc_id in active
        }
        for kc_id in kc_ids
    }
    for left, right in combinations(kc_ids, 2):
        left_items = supporting_items[left]
        right_items = supporting_items[right]
        left_only = left_items - right_items
        right_only = right_items - left_items
        both = left_items & right_items
        similarity = _jaccard(left_items, right_items)
        contrast = {
            "left_kc_id": left,
            "right_kc_id": right,
            "left_only_items": len(left_only),
            "right_only_items": len(right_only),
            "cooccurring_items": len(both),
            "jaccard": round(similarity, 6),
            "columns_distinguishable": bool(left_only or right_only),
            "two_sided_contrast": bool(left_only and right_only),
        }
        pair_contrasts.append(contrast)
        if not left_only and not right_only:
            identical_columns.append(contrast)
        elif similarity >= near_threshold:
            near_identical_columns.append(contrast)

    cells_to_pattern: dict[str, tuple[str, ...]] = {}
    for item_id, active in active_by_item.items():
        cell_id = item_by_id[item_id]["cell_id"]
        pattern = tuple(sorted(active))
        previous = cells_to_pattern.setdefault(cell_id, pattern)
        if previous != pattern:
            raise ValueError(
                "items in one GrammarCell received inconsistent deterministic Q* rows"
            )
    pattern_counts = Counter(cells_to_pattern.values())
    activation_equivalence_classes = [
        {
            "generator_kc_ids": list(pattern),
            "cell_ids": sorted(
                cell_id
                for cell_id, cell_pattern in cells_to_pattern.items()
                if cell_pattern == pattern
            ),
        }
        for pattern, count in pattern_counts.items()
        if count > 1
    ]

    row_sums = [len(active) for active in active_by_item.values()]
    edge_count = int(q.sum())
    rare_cell_threshold = int(design["support"]["rare_kc_cell_threshold"])
    rare_item_threshold = int(design["support"]["rare_kc_item_threshold"])
    rare_kcs = [
        {
            "kc_id": kc_id,
            "cell_support": cell_support[kc_id],
            "item_support": item_support[kc_id],
        }
        for kc_id in kc_ids
        if cell_support[kc_id] < rare_cell_threshold
        or item_support[kc_id] < rare_item_threshold
    ]

    regime_support: dict[str, dict[str, int]] = {}
    if grammar_regime_by_cell is not None:
        unknown_regime_cells = set(grammar_regime_by_cell) - cell_ids
        if unknown_regime_cells:
            raise ValueError(
                f"grammar regimes refer to unknown cells: {sorted(unknown_regime_cells)}"
            )
        regimes = sorted(set(grammar_regime_by_cell.values()))
        regime_support = {
            regime: {
                kc_id: sum(
                    kc_id in active
                    and grammar_regime_by_cell[item_by_id[item_id]["cell_id"]]
                    == regime
                    for item_id, active in active_by_item.items()
                )
                for kc_id in kc_ids
            }
            for regime in regimes
        }

    requirements = design["identifiability"]
    failures = []
    zero_kc_items = sorted(
        item_id for item_id, active in active_by_item.items() if not active
    )
    zero_support_kcs = sorted(
        kc_id for kc_id, support in item_support.items() if support == 0
    )
    minimum_items = int(design["support"]["minimum_items_per_kc_before_simulation"])
    below_minimum_items = sorted(
        kc_id for kc_id, support in item_support.items() if support < minimum_items
    )
    if requirements["require_nonempty_item_projection"] and zero_kc_items:
        failures.append("items_without_generator_kcs")
    if zero_support_kcs:
        failures.append("generator_kcs_without_items")
    if below_minimum_items:
        failures.append("generator_kcs_below_minimum_item_support")
    if requirements["require_unique_q_columns"] and identical_columns:
        failures.append("identical_q_columns")
    if requirements["require_full_column_rank"] and rank < len(kc_ids):
        failures.append("rank_deficient_q_matrix")

    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "counts": {
            "cells": len(cells),
            "items": len(items),
            "generator_kcs": len(kc_ids),
            "q_edges": edge_count,
            "q_density": edge_count / (len(items) * len(kc_ids)),
            "q_rank": rank,
            "distinct_cell_activation_rows": len(pattern_counts),
        },
        "kc_support": [
            {
                "kc_id": kc_id,
                "item_support": item_support[kc_id],
                "cell_support": cell_support[kc_id],
                "isolated_item_support": isolated_support[kc_id],
            }
            for kc_id in kc_ids
        ],
        "kcs_per_item_distribution": dict(sorted(Counter(row_sums).items())),
        "zero_kc_item_ids": zero_kc_items,
        "zero_support_kc_ids": zero_support_kcs,
        "below_minimum_item_support_kc_ids": below_minimum_items,
        "rare_kcs": rare_kcs,
        "identical_q_columns": identical_columns,
        "near_identical_q_columns": near_identical_columns,
        "pair_contrasts": pair_contrasts,
        "repeated_cell_activation_patterns": activation_equivalence_classes,
        "grammar_regime_item_support": regime_support,
        "metadata": {
            "learner_responses_read": False,
            "near_identical_jaccard_threshold": near_threshold,
        },
    }
