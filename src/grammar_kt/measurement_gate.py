"""Deterministic Q* construction and the mandatory pre-simulation gate.

This module deliberately has a narrow scientific boundary.  It accepts only
the fixed GrammarCells, fixed learner-facing items, the already-declared
generator-KC inventory, and the researcher-facing measurement design.  It
does not accept learner events, response outcomes, discovered KCs, or KT
results.

The public functions make three guarantees that are useful when freezing a
baseline dataset:

* every Q* edge is re-derived from the declared KC activation language;
* row and column order are canonical and independent of input file order;
* written artifacts are immutable and hash-linked by a small manifest.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

from .kc import activation_matches


Q_ROW_FIELDS = {"item_id", "cell_id", "generator_kc_ids"}
_FORBIDDEN_ITEM_FIELDS = {
    "correct",
    "dataset_split",
    "event_id",
    "learner_id",
    "learner_outcome",
    "learner_outcomes",
    "latent_mastery",
    "mastery_before",
    "mastery_after",
    "outcome",
    "pass_index",
    "phase",
    "response_probability",
    "sequence_index",
    "updates_history",
    "generator_kc_ids",
    "kc_ids",
}


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{label} must be a non-empty, trimmed string")
    return value


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def semantic_sha256(value: Any) -> str:
    """Hash JSON semantics rather than incidental whitespace."""

    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_condition(
    dimension: Any,
    expected: Any,
    dimensions: set[str],
    *,
    label: str,
) -> None:
    name = _nonempty_string(dimension, f"{label} dimension")
    if name not in dimensions:
        raise ValueError(f"{label} uses unknown GrammarCell dimension: {name}")
    if isinstance(expected, str):
        _nonempty_string(expected, f"{label}.{name}")
        return
    if isinstance(expected, list):
        if not expected:
            raise ValueError(f"{label}.{name} list must not be empty")
        values = [
            _nonempty_string(value, f"{label}.{name} value") for value in expected
        ]
        if len(values) != len(set(values)):
            raise ValueError(f"{label}.{name} list contains duplicates")
        return
    if isinstance(expected, dict):
        if set(expected) != {"not"}:
            raise ValueError(f"{label}.{name} supports only the 'not' condition")
        _nonempty_string(expected["not"], f"{label}.{name}.not")
        return
    raise ValueError(
        f"{label}.{name} must be a string, string list, or one 'not' condition"
    )


def _validate_activation_rule(
    rule: Any,
    dimensions: set[str],
    *,
    label: str,
) -> None:
    if not isinstance(rule, dict) or len(rule) != 1:
        raise ValueError(
            f"{label} must contain exactly one of cell, all, or any"
        )
    primitive, body = next(iter(rule.items()))
    if primitive == "cell":
        if not isinstance(body, dict) or not body:
            raise ValueError(f"{label}.cell must be a non-empty object")
        for dimension, expected in body.items():
            _validate_condition(dimension, expected, dimensions, label=label)
        return
    if primitive in {"all", "any"}:
        if not isinstance(body, list) or not body:
            raise ValueError(f"{label}.{primitive} must be a non-empty list")
        for index, part in enumerate(body):
            _validate_activation_rule(
                part,
                dimensions,
                label=f"{label}.{primitive}[{index}]",
            )
        return
    raise ValueError(f"{label} uses unknown activation primitive: {primitive}")


def _validate_cells(
    cells: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], set[str]]:
    if not isinstance(cells, list) or not cells:
        raise ValueError("Q* construction needs at least one canonical GrammarCell")
    seen_ids: set[str] = set()
    feature_signatures: dict[tuple[tuple[str, str], ...], str] = {}
    dimensions: set[str] | None = None
    canonical: list[dict[str, Any]] = []
    for index, cell in enumerate(cells):
        if not isinstance(cell, dict):
            raise ValueError(f"GrammarCell row {index} must be an object")
        cell_id = _nonempty_string(cell.get("cell_id"), f"GrammarCell row {index} ID")
        if cell_id in seen_ids:
            raise ValueError(f"duplicate GrammarCell ID: {cell_id}")
        seen_ids.add(cell_id)
        features = cell.get("features")
        if not isinstance(features, dict) or not features:
            raise ValueError(f"GrammarCell {cell_id} features must be non-empty")
        clean_features: dict[str, str] = {}
        for name, value in features.items():
            dimension = _nonempty_string(name, f"GrammarCell {cell_id} dimension")
            clean_features[dimension] = _nonempty_string(
                value, f"GrammarCell {cell_id}.{dimension}"
            )
        row_dimensions = set(clean_features)
        if dimensions is None:
            dimensions = row_dimensions
        elif row_dimensions != dimensions:
            raise ValueError(
                f"GrammarCell {cell_id} dimensions differ from the canonical schema"
            )
        signature = tuple(sorted(clean_features.items()))
        if signature in feature_signatures:
            raise ValueError(
                "duplicate canonical GrammarCell feature tuple: "
                f"{feature_signatures[signature]} and {cell_id}"
            )
        feature_signatures[signature] = cell_id
        canonical.append({"cell_id": cell_id, "features": clean_features})
    return sorted(canonical, key=lambda row: row["cell_id"]), dimensions or set()


def _validate_items(
    items: list[dict[str, Any]], cell_ids: set[str]
) -> list[dict[str, str]]:
    if not isinstance(items, list) or not items:
        raise ValueError("Q* construction needs at least one fixed item")
    seen: set[str] = set()
    canonical: list[dict[str, str]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"item row {index} must be an object")
        forbidden = set(item) & _FORBIDDEN_ITEM_FIELDS
        if forbidden:
            raise ValueError(
                "fixed item bank contains learner/oracle/Q fields: "
                f"{sorted(forbidden)}"
            )
        item_id = _nonempty_string(item.get("item_id"), f"item row {index} ID")
        if item_id in seen:
            raise ValueError(f"duplicate item ID: {item_id}")
        seen.add(item_id)
        cell_id = _nonempty_string(item.get("cell_id"), f"item {item_id} cell_id")
        if cell_id not in cell_ids:
            raise ValueError(f"item {item_id} refers to unknown GrammarCell: {cell_id}")
        canonical.append({"item_id": item_id, "cell_id": cell_id})
    return sorted(canonical, key=lambda row: row["item_id"])


def _validate_kcs(
    kcs: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    dimensions: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(kcs, list) or not kcs:
        raise ValueError("Q* construction needs a non-empty generator-KC inventory")
    seen: set[str] = set()
    canonical: list[dict[str, Any]] = []
    for index, kc in enumerate(kcs):
        if not isinstance(kc, dict):
            raise ValueError(f"generator KC row {index} must be an object")
        kc_id = _nonempty_string(kc.get("id"), f"generator KC row {index} ID")
        if kc_id in seen:
            raise ValueError(f"duplicate generator-KC ID: {kc_id}")
        seen.add(kc_id)
        rule = kc.get("activation_rule")
        _validate_activation_rule(
            rule,
            dimensions,
            label=f"generator KC {kc_id} activation_rule",
        )
        computed_support = sorted(
            cell["cell_id"]
            for cell in cells
            if activation_matches(cell["features"], rule)
        )
        declared_support = kc.get("supporting_cell_ids")
        if not isinstance(declared_support, list) or any(
            not isinstance(cell_id, str) for cell_id in declared_support
        ):
            raise ValueError(
                f"generator KC {kc_id} must declare supporting_cell_ids"
            )
        if len(declared_support) != len(set(declared_support)):
            raise ValueError(f"generator KC {kc_id} support contains duplicate cells")
        if sorted(declared_support) != computed_support:
            raise ValueError(
                f"generator KC {kc_id} declared support does not match its "
                "activation rule"
            )
        declared_count = _integer(
            kc.get("cell_support"),
            f"generator KC {kc_id} cell_support",
        )
        if declared_count != len(computed_support):
            raise ValueError(
                f"generator KC {kc_id} cell_support does not match supporting cells"
            )
        if not computed_support:
            raise ValueError(f"generator KC {kc_id} has zero canonical-cell support")
        canonical.append(
            {
                "id": kc_id,
                "activation_rule": rule,
                "supporting_cell_ids": computed_support,
                "cell_support": len(computed_support),
            }
        )
    return sorted(canonical, key=lambda row: row["id"])


def _canonical_input_rows(
    rows: list[dict[str, Any]], identifier: str
) -> list[dict[str, Any]]:
    """Sort full source rows for order-independent provenance hashes."""

    return sorted(rows, key=lambda row: str(row[identifier]))


def _normalise_regimes(
    grammar_regime_by_cell: Mapping[str, str] | Iterable[dict[str, Any]] | None,
    cell_ids: set[str],
) -> dict[str, str] | None:
    if grammar_regime_by_cell is None:
        return None
    if isinstance(grammar_regime_by_cell, Mapping):
        pairs = list(grammar_regime_by_cell.items())
    else:
        pairs = []
        for index, row in enumerate(grammar_regime_by_cell):
            if not isinstance(row, dict):
                raise ValueError(f"grammar regime row {index} must be an object")
            forbidden = set(row) & _FORBIDDEN_ITEM_FIELDS
            if forbidden:
                raise ValueError(
                    "grammar regime rows contain learner/oracle/Q fields: "
                    f"{sorted(forbidden)}"
                )
            regime_fields = {name for name in ("grammar_regime", "regime") if name in row}
            if "cell_id" not in row or len(regime_fields) != 1:
                raise ValueError(
                    "grammar regime rows require cell_id and exactly one of "
                    "grammar_regime or regime"
                )
            regime_field = next(iter(regime_fields))
            pairs.append((row["cell_id"], row[regime_field]))
    result: dict[str, str] = {}
    for raw_cell_id, raw_regime in pairs:
        cell_id = _nonempty_string(raw_cell_id, "grammar regime cell_id")
        regime = _nonempty_string(raw_regime, f"grammar regime for {cell_id}")
        if cell_id in result:
            raise ValueError(f"duplicate grammar regime assignment: {cell_id}")
        result[cell_id] = regime
    missing = cell_ids - set(result)
    unknown = set(result) - cell_ids
    if missing or unknown:
        raise ValueError(
            "grammar regimes must cover exactly the canonical cells: "
            f"missing={sorted(missing)}, unknown={sorted(unknown)}"
        )
    return dict(sorted(result.items()))


def project_q_star(
    cells: list[dict[str, Any]],
    items: list[dict[str, Any]],
    generator_kcs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Derive one canonical sparse Q* row per item from activation rules only."""

    canonical_cells, dimensions = _validate_cells(cells)
    cell_by_id = {row["cell_id"]: row for row in canonical_cells}
    canonical_items = _validate_items(items, set(cell_by_id))
    canonical_kcs = _validate_kcs(generator_kcs, canonical_cells, dimensions)
    return [
        {
            "item_id": item["item_id"],
            "cell_id": item["cell_id"],
            "generator_kc_ids": [
                kc["id"]
                for kc in canonical_kcs
                if activation_matches(
                    cell_by_id[item["cell_id"]]["features"],
                    kc["activation_rule"],
                )
            ],
        }
        for item in canonical_items
    ]


def _canonicalise_q_rows(
    q_rows: list[dict[str, Any]],
    *,
    item_ids: set[str],
    kc_ids: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(q_rows, list):
        raise ValueError("sparse Q* must be a list")
    seen: set[str] = set()
    canonical: list[dict[str, Any]] = []
    for index, row in enumerate(q_rows):
        if not isinstance(row, dict) or set(row) != Q_ROW_FIELDS:
            raise ValueError(f"sparse Q* row {index} has the wrong fields")
        item_id = _nonempty_string(row["item_id"], f"sparse Q* row {index} item_id")
        cell_id = _nonempty_string(row["cell_id"], f"sparse Q* row {index} cell_id")
        if item_id in seen:
            raise ValueError(f"duplicate sparse Q* item row: {item_id}")
        seen.add(item_id)
        active = row["generator_kc_ids"]
        if not isinstance(active, list) or any(
            not isinstance(kc_id, str) for kc_id in active
        ):
            raise ValueError(f"sparse Q* active KCs must be a list: {item_id}")
        if len(active) != len(set(active)):
            raise ValueError(f"sparse Q* contains a duplicate edge: {item_id}")
        unknown = set(active) - kc_ids
        if unknown:
            raise ValueError(
                f"sparse Q* contains unknown generator KCs: {sorted(unknown)}"
            )
        canonical.append(
            {
                "item_id": item_id,
                "cell_id": cell_id,
                "generator_kc_ids": sorted(active),
            }
        )
    missing = item_ids - seen
    unknown_items = seen - item_ids
    if missing or unknown_items:
        raise ValueError(
            "sparse Q* rows differ from the fixed item bank: "
            f"missing={sorted(missing)}, unknown={sorted(unknown_items)}"
        )
    return sorted(canonical, key=lambda row: row["item_id"])


def _geometry(left_only: int, right_only: int, both: int) -> str:
    if not left_only and not right_only:
        return "activation_equivalent"
    if not left_only:
        return "left_nested_in_right"
    if not right_only:
        return "right_nested_in_left"
    if both:
        return "a_only_b_only_and_a_plus_b"
    return "two_sided_without_cooccurrence"


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def _distribution(values: Iterable[int]) -> dict[str, int]:
    return {
        str(value): count for value, count in sorted(Counter(values).items())
    }


def _design_settings(design: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(design, dict):
        raise ValueError("measurement design must be an object")
    support = design.get("support")
    identifiability = design.get("identifiability")
    if not isinstance(support, dict) or not isinstance(identifiability, dict):
        raise ValueError("measurement design requires support and identifiability")
    near = identifiability.get("near_identical_jaccard", 0.9)
    if isinstance(near, bool) or not isinstance(near, (int, float)) or not 0 <= near <= 1:
        raise ValueError("near_identical_jaccard must be between zero and one")

    def boolean(name: str, default: bool) -> bool:
        value = identifiability.get(name, default)
        if not isinstance(value, bool):
            raise ValueError(f"identifiability.{name} must be boolean")
        return value

    return {
        "minimum_items_per_kc": _integer(
            support.get("minimum_items_per_kc_before_simulation"),
            "support.minimum_items_per_kc_before_simulation",
            minimum=1,
        ),
        "rare_kc_cell_threshold": _integer(
            support.get("rare_kc_cell_threshold"),
            "support.rare_kc_cell_threshold",
            minimum=1,
        ),
        "rare_kc_item_threshold": _integer(
            support.get("rare_kc_item_threshold"),
            "support.rare_kc_item_threshold",
            minimum=1,
        ),
        "near_identical_jaccard": float(near),
        "require_nonempty_item_projection": boolean(
            "require_nonempty_item_projection", True
        ),
        "require_unique_q_columns": boolean("require_unique_q_columns", True),
        "require_full_column_rank": boolean("require_full_column_rank", True),
        "require_every_canonical_cell_measured": boolean(
            "require_every_canonical_cell_measured", True
        ),
        "require_isolating_item_per_kc": boolean(
            "require_isolating_item_per_kc", False
        ),
        "require_two_sided_pair_contrast": boolean(
            "require_two_sided_pair_contrast", False
        ),
        "reject_near_identical_columns": boolean(
            "reject_near_identical_columns", False
        ),
    }


def audit_q_star(
    cells: list[dict[str, Any]],
    items: list[dict[str, Any]],
    generator_kcs: list[dict[str, Any]],
    q_rows: list[dict[str, Any]],
    design: dict[str, Any],
    *,
    grammar_regime_by_cell: Mapping[str, str] | Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Verify Q* against K* and calculate the pre-simulation diagnostics."""

    canonical_cells, dimensions = _validate_cells(cells)
    cell_by_id = {row["cell_id"]: row for row in canonical_cells}
    canonical_items = _validate_items(items, set(cell_by_id))
    item_by_id = {row["item_id"]: row for row in canonical_items}
    canonical_kcs = _validate_kcs(generator_kcs, canonical_cells, dimensions)
    kc_ids = [row["id"] for row in canonical_kcs]
    expected = project_q_star(cells, items, generator_kcs)
    observed = _canonicalise_q_rows(
        q_rows,
        item_ids=set(item_by_id),
        kc_ids=set(kc_ids),
    )
    if observed != expected:
        raise ValueError("sparse Q* does not match declared activation rules")
    regimes = _normalise_regimes(grammar_regime_by_cell, set(cell_by_id))
    settings = _design_settings(design)

    active_by_item = {
        row["item_id"]: set(row["generator_kc_ids"]) for row in expected
    }
    cell_ids_by_kc = {
        kc["id"]: set(kc["supporting_cell_ids"]) for kc in canonical_kcs
    }
    items_by_kc = {
        kc_id: {
            item_id for item_id, active in active_by_item.items() if kc_id in active
        }
        for kc_id in kc_ids
    }
    measured_cells_by_kc = {
        kc_id: {item_by_id[item_id]["cell_id"] for item_id in item_ids}
        for kc_id, item_ids in items_by_kc.items()
    }
    measured_cell_ids = {row["cell_id"] for row in canonical_items}
    uncovered_cells = sorted(set(cell_by_id) - measured_cell_ids)

    item_order = [row["item_id"] for row in canonical_items]
    matrix = np.asarray(
        [
            [int(kc_id in active_by_item[item_id]) for kc_id in kc_ids]
            for item_id in item_order
        ],
        dtype=np.int8,
    )
    rank = int(np.linalg.matrix_rank(matrix.astype(float)))
    edge_count = int(matrix.sum())

    canonical_active_by_cell = {
        cell["cell_id"]: {
            kc["id"]
            for kc in canonical_kcs
            if activation_matches(cell["features"], kc["activation_rule"])
        }
        for cell in canonical_cells
    }
    isolating_item_ids = {
        kc_id: sorted(
            item_id
            for item_id, active in active_by_item.items()
            if active == {kc_id}
        )
        for kc_id in kc_ids
    }
    isolating_cell_ids = {
        kc_id: sorted(
            cell_id
            for cell_id, active in canonical_active_by_cell.items()
            if active == {kc_id}
        )
        for kc_id in kc_ids
    }

    pair_geometry: list[dict[str, Any]] = []
    near_pairs: list[dict[str, Any]] = []
    for left, right in combinations(kc_ids, 2):
        left_items = items_by_kc[left]
        right_items = items_by_kc[right]
        left_cells = cell_ids_by_kc[left]
        right_cells = cell_ids_by_kc[right]
        left_only_items = left_items - right_items
        right_only_items = right_items - left_items
        both_items = left_items & right_items
        left_only_cells = left_cells - right_cells
        right_only_cells = right_cells - left_cells
        both_cells = left_cells & right_cells
        item_similarity = _jaccard(left_items, right_items)
        cell_similarity = _jaccard(left_cells, right_cells)
        row = {
            "left_kc_id": left,
            "right_kc_id": right,
            "a_only_items": len(left_only_items),
            "b_only_items": len(right_only_items),
            "a_plus_b_items": len(both_items),
            "neither_items": len(canonical_items) - len(left_items | right_items),
            "a_only_cells": len(left_only_cells),
            "b_only_cells": len(right_only_cells),
            "a_plus_b_cells": len(both_cells),
            "item_jaccard": round(item_similarity, 6),
            "cell_jaccard": round(cell_similarity, 6),
            "q_hamming_distance": len(left_items ^ right_items),
            "geometry": _geometry(
                len(left_only_items), len(right_only_items), len(both_items)
            ),
            "two_sided_contrast": bool(left_only_items and right_only_items),
            "has_a_only_b_only_and_a_plus_b": bool(
                left_only_items and right_only_items and both_items
            ),
        }
        pair_geometry.append(row)
        if 1 > item_similarity >= settings["near_identical_jaccard"]:
            near_pairs.append(row)

    column_groups: dict[tuple[str, ...], list[str]] = defaultdict(list)
    canonical_column_groups: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for kc_id in kc_ids:
        column_groups[tuple(sorted(items_by_kc[kc_id]))].append(kc_id)
        canonical_column_groups[tuple(sorted(cell_ids_by_kc[kc_id]))].append(kc_id)
    identical_q_columns = [
        {
            "generator_kc_ids": sorted(group),
            "supporting_item_ids": list(signature),
        }
        for signature, group in column_groups.items()
        if len(group) > 1
    ]
    identical_q_columns.sort(key=lambda row: row["generator_kc_ids"])
    canonical_kc_equivalence = [
        {
            "generator_kc_ids": sorted(group),
            "supporting_cell_ids": list(signature),
        }
        for signature, group in canonical_column_groups.items()
        if len(group) > 1
    ]
    canonical_kc_equivalence.sort(key=lambda row: row["generator_kc_ids"])

    cell_pattern_groups: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for cell_id, active in canonical_active_by_cell.items():
        cell_pattern_groups[tuple(sorted(active))].append(cell_id)
    cell_activation_equivalence = [
        {
            "generator_kc_ids": list(pattern),
            "cell_ids": sorted(group),
        }
        for pattern, group in cell_pattern_groups.items()
        if len(group) > 1
    ]
    cell_activation_equivalence.sort(
        key=lambda row: (row["generator_kc_ids"], row["cell_ids"])
    )

    kc_support = []
    for kc_id in kc_ids:
        regime_support: dict[str, dict[str, int]] = {}
        if regimes is not None:
            for regime in sorted(set(regimes.values())):
                regime_support[regime] = {
                    "items": sum(
                        regimes[item_by_id[item_id]["cell_id"]] == regime
                        for item_id in items_by_kc[kc_id]
                    ),
                    "cells": sum(
                        regimes[cell_id] == regime
                        for cell_id in measured_cells_by_kc[kc_id]
                    ),
                }
        kc_support.append(
            {
                "kc_id": kc_id,
                "items": len(items_by_kc[kc_id]),
                "measured_cells": len(measured_cells_by_kc[kc_id]),
                "canonical_cells": len(cell_ids_by_kc[kc_id]),
                "isolating_items": len(isolating_item_ids[kc_id]),
                "isolating_item_ids": isolating_item_ids[kc_id],
                "isolating_cells": len(isolating_cell_ids[kc_id]),
                "isolating_cell_ids": isolating_cell_ids[kc_id],
                "regime_support": regime_support,
            }
        )

    rare_kcs = [
        {
            "kc_id": row["kc_id"],
            "items": row["items"],
            "measured_cells": row["measured_cells"],
            "rare_by_item_threshold": (
                row["items"] < settings["rare_kc_item_threshold"]
            ),
            "rare_by_cell_threshold": (
                row["measured_cells"] < settings["rare_kc_cell_threshold"]
            ),
        }
        for row in kc_support
        if row["items"] < settings["rare_kc_item_threshold"]
        or row["measured_cells"] < settings["rare_kc_cell_threshold"]
    ]

    zero_item_kcs = sorted(
        kc_id for kc_id in kc_ids if not items_by_kc[kc_id]
    )
    below_minimum = sorted(
        kc_id
        for kc_id in kc_ids
        if len(items_by_kc[kc_id]) < settings["minimum_items_per_kc"]
    )
    zero_kc_items = sorted(
        item_id for item_id, active in active_by_item.items() if not active
    )
    no_isolating = sorted(
        kc_id for kc_id in kc_ids if not isolating_item_ids[kc_id]
    )
    no_two_sided = sorted(
        [row["left_kc_id"], row["right_kc_id"]]
        for row in pair_geometry
        if not row["two_sided_contrast"]
    )
    failures: list[str] = []
    if settings["require_every_canonical_cell_measured"] and uncovered_cells:
        failures.append("canonical_cells_without_items")
    if settings["require_nonempty_item_projection"] and zero_kc_items:
        failures.append("items_without_generator_kcs")
    if zero_item_kcs:
        failures.append("generator_kcs_without_items")
    if below_minimum:
        failures.append("generator_kcs_below_minimum_item_support")
    if settings["require_unique_q_columns"] and identical_q_columns:
        failures.append("identical_q_columns")
    if settings["require_full_column_rank"] and rank < len(kc_ids):
        failures.append("rank_deficient_q_matrix")
    if settings["require_isolating_item_per_kc"] and no_isolating:
        failures.append("generator_kcs_without_isolating_items")
    if settings["require_two_sided_pair_contrast"] and no_two_sided:
        failures.append("kc_pairs_without_two_sided_contrast")
    if settings["reject_near_identical_columns"] and near_pairs:
        failures.append("near_identical_q_columns")

    grammar_regime_support: dict[str, Any] = {}
    if regimes is not None:
        for regime in sorted(set(regimes.values())):
            regime_cells = {cell_id for cell_id, value in regimes.items() if value == regime}
            regime_items = {
                item["item_id"]
                for item in canonical_items
                if item["cell_id"] in regime_cells
            }
            grammar_regime_support[regime] = {
                "canonical_cells": len(regime_cells),
                "measured_cells": len(regime_cells & measured_cell_ids),
                "items": len(regime_items),
                "q_edges": sum(len(active_by_item[item_id]) for item_id in regime_items),
                "generator_kcs_with_item_support": sum(
                    bool(items_by_kc[kc_id] & regime_items) for kc_id in kc_ids
                ),
            }

    geometry_distribution = dict(
        sorted(Counter(row["geometry"] for row in pair_geometry).items())
    )
    canonical_inputs = {
        "cells": _canonical_input_rows(cells, "cell_id"),
        "items": _canonical_input_rows(items, "item_id"),
        "generator_kcs": _canonical_input_rows(generator_kcs, "id"),
        "measurement_design": design,
        "grammar_regime_by_cell": regimes,
    }
    return {
        "audit_id": "full_v1_pre_simulation_measurement_gate_v1",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "counts": {
            "canonical_cells": len(canonical_cells),
            "measured_cells": len(measured_cell_ids),
            "items": len(canonical_items),
            "generator_kcs": len(kc_ids),
            "q_edges": edge_count,
            "q_density": edge_count / (len(canonical_items) * len(kc_ids)),
            "q_rank": rank,
            "full_column_rank": rank == len(kc_ids),
            "distinct_canonical_cell_activation_rows": len(cell_pattern_groups),
            "kc_pairs": len(pair_geometry),
        },
        "support": {
            "by_generator_kc": kc_support,
            "items_per_kc_distribution": _distribution(
                len(items_by_kc[kc_id]) for kc_id in kc_ids
            ),
            "measured_cells_per_kc_distribution": _distribution(
                len(measured_cells_by_kc[kc_id]) for kc_id in kc_ids
            ),
            "kcs_per_item_distribution": _distribution(
                len(active) for active in active_by_item.values()
            ),
            "uncovered_canonical_cell_ids": uncovered_cells,
            "zero_generator_kc_item_ids": zero_kc_items,
            "zero_item_support_generator_kc_ids": zero_item_kcs,
            "below_minimum_item_support_generator_kc_ids": below_minimum,
            "generator_kcs_without_isolating_items": no_isolating,
            "rare_generator_kcs": rare_kcs,
        },
        "identifiability": {
            "identical_q_columns": identical_q_columns,
            "near_identical_q_column_pairs": near_pairs,
            "canonical_kc_activation_equivalence_classes": canonical_kc_equivalence,
            "repeated_cell_activation_classes": cell_activation_equivalence,
            "pair_geometry": pair_geometry,
            "pair_geometry_distribution": geometry_distribution,
            "pairs_without_two_sided_contrast": no_two_sided,
        },
        "grammar_regime_support": grammar_regime_support,
        "thresholds_and_requirements": settings,
        "provenance": {
            "input_semantic_sha256": {
                name: semantic_sha256(value)
                for name, value in canonical_inputs.items()
                if value is not None
            },
            "q_star_semantic_sha256": semantic_sha256(expected),
            "q_projection": "declared_generator_kc_activation_rules_only",
            "learner_events_read": False,
            "learner_outcomes_read": False,
            "oracle_learner_truth_read": False,
            "discovered_kcs_read": False,
            "kt_results_read": False,
        },
    }


def build_measurement_bundle(
    cells: list[dict[str, Any]],
    items: list[dict[str, Any]],
    generator_kcs: list[dict[str, Any]],
    design: dict[str, Any],
    *,
    grammar_regime_by_cell: Mapping[str, str] | Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build canonical Q* and its audit without reading learner evidence."""

    q_rows = project_q_star(cells, items, generator_kcs)
    audit = audit_q_star(
        cells,
        items,
        generator_kcs,
        q_rows,
        design,
        grammar_regime_by_cell=grammar_regime_by_cell,
    )
    return {
        "generator_kc_ids": sorted(kc["id"] for kc in generator_kcs),
        "q_rows": q_rows,
        "audit": audit,
    }


def render_dense_q_matrix_csv(
    q_rows: list[dict[str, Any]], generator_kc_ids: Iterable[str]
) -> bytes:
    """Render the complete dense matrix, retaining zero-support KC columns."""

    kc_ids = sorted(generator_kc_ids)
    if not kc_ids or len(kc_ids) != len(set(kc_ids)):
        raise ValueError("dense Q* requires unique generator-KC columns")
    item_ids = {row.get("item_id") for row in q_rows if isinstance(row, dict)}
    canonical = _canonicalise_q_rows(
        q_rows,
        item_ids=item_ids,
        kc_ids=set(kc_ids),
    )
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["item_id", *kc_ids])
    for row in canonical:
        active = set(row["generator_kc_ids"])
        writer.writerow([row["item_id"], *(int(kc_id in active) for kc_id in kc_ids)])
    return stream.getvalue().encode("utf-8")


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    ).encode("utf-8")


def _jsonl_bytes(rows: Iterable[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=False) + "\n" for row in rows
    ).encode("utf-8")


def _freeze_bytes(path: str | Path, payload: bytes, label: str) -> None:
    target = Path(path)
    if target.exists():
        if target.read_bytes() != payload:
            raise ValueError(f"refusing to overwrite changed frozen {label}: {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)


def write_measurement_artifacts(
    bundle: dict[str, Any],
    *,
    dense_q_matrix_path: str | Path,
    sparse_q_matrix_path: str | Path,
    audit_path: str | Path,
    manifest_path: str | Path,
) -> dict[str, Any]:
    """Freeze dense/sparse Q*, the gate audit, and their hash manifest."""

    if set(bundle) != {"generator_kc_ids", "q_rows", "audit"}:
        raise ValueError("measurement bundle has the wrong fields")
    dense_payload = render_dense_q_matrix_csv(
        bundle["q_rows"], bundle["generator_kc_ids"]
    )
    sparse_payload = _jsonl_bytes(bundle["q_rows"])
    audit_payload = _json_bytes(bundle["audit"])
    _freeze_bytes(dense_q_matrix_path, dense_payload, "dense Q* matrix")
    _freeze_bytes(sparse_q_matrix_path, sparse_payload, "sparse Q* matrix")
    _freeze_bytes(audit_path, audit_payload, "measurement audit")
    artifacts = {
        "dense_q_matrix": {
            "filename": Path(dense_q_matrix_path).name,
            "sha256": hashlib.sha256(dense_payload).hexdigest(),
            "bytes": len(dense_payload),
        },
        "sparse_q_matrix": {
            "filename": Path(sparse_q_matrix_path).name,
            "sha256": hashlib.sha256(sparse_payload).hexdigest(),
            "bytes": len(sparse_payload),
        },
        "measurement_audit": {
            "filename": Path(audit_path).name,
            "sha256": hashlib.sha256(audit_payload).hexdigest(),
            "bytes": len(audit_payload),
        },
    }
    manifest = {
        "manifest_id": "full_v1_q_star_measurement_artifacts_v1",
        "measurement_status": bundle["audit"]["status"],
        "canonical_order": {
            "rows": "item_id_lexicographic",
            "columns": "generator_kc_id_lexicographic",
        },
        "input_semantic_sha256": bundle["audit"]["provenance"][
            "input_semantic_sha256"
        ],
        "q_star_semantic_sha256": bundle["audit"]["provenance"][
            "q_star_semantic_sha256"
        ],
        "artifacts": artifacts,
        "scientific_boundary": {
            "learner_events_read": False,
            "discovered_kcs_read": False,
            "projection_depends_only_on_fixed_items_cells_and_k_star": True,
        },
    }
    _freeze_bytes(manifest_path, _json_bytes(manifest), "Q* artifact manifest")
    return manifest


def verify_measurement_artifacts(
    bundle: dict[str, Any],
    *,
    dense_q_matrix_path: str | Path,
    sparse_q_matrix_path: str | Path,
    audit_path: str | Path,
    manifest_path: str | Path,
) -> None:
    """Reject any byte or semantic drift in a previously frozen bundle."""

    paths = {
        "dense_q_matrix": Path(dense_q_matrix_path),
        "sparse_q_matrix": Path(sparse_q_matrix_path),
        "measurement_audit": Path(audit_path),
    }
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if manifest.get("manifest_id") != "full_v1_q_star_measurement_artifacts_v1":
        raise ValueError("wrong Q* artifact manifest ID")
    expected_manifest = write_measurement_artifacts(
        bundle,
        dense_q_matrix_path=dense_q_matrix_path,
        sparse_q_matrix_path=sparse_q_matrix_path,
        audit_path=audit_path,
        manifest_path=manifest_path,
    )
    if manifest != expected_manifest:
        raise ValueError("Q* artifact manifest differs from deterministic inputs")
    for name, path in paths.items():
        if file_sha256(path) != manifest["artifacts"][name]["sha256"]:
            raise ValueError(f"frozen {name} hash mismatch")
