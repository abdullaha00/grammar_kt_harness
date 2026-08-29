"""Development-only construction of interpretable structural KC candidates."""

from __future__ import annotations

import re
from collections import defaultdict
from itertools import combinations
from typing import Any

from .kc import activation_matches


def _slug(value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")
    return text or "empty"


def _feature_candidate(dimension: str, value: str) -> dict[str, Any]:
    return {
        "id": f"kc_feature__{_slug(dimension)}__{_slug(value)}",
        "family": "feature_value",
        "definition": f"Represent canonical {dimension}={value}.",
        "activation": {"cell": {dimension: value}},
        "dimensions": [dimension],
        "conditions": [[dimension, value]],
    }


def _operation_candidate(declaration: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"kc_operation__{_slug(declaration['id'])}",
        "family": "operation",
        "definition": declaration["definition"],
        "activation": declaration["activation"],
        "dimensions": sorted(_activation_dimensions(declaration["activation"])),
        "conditions": [],
        "operation_id": declaration["id"],
    }


def _interaction_candidate(
    left: dict[str, Any], right: dict[str, Any]
) -> dict[str, Any]:
    conditions = sorted(left["conditions"] + right["conditions"])
    label = "__and__".join(
        f"{_slug(dimension)}_{_slug(value)}" for dimension, value in conditions
    )
    return {
        "id": f"kc_interaction__{label}",
        "family": "interaction",
        "definition": "Represent the supported interaction "
        + " and ".join(f"{dimension}={value}" for dimension, value in conditions)
        + ".",
        "activation": {"cell": {dimension: value for dimension, value in conditions}},
        "dimensions": [dimension for dimension, _value in conditions],
        "conditions": conditions,
        "parent_ids": sorted([left["id"], right["id"]]),
    }


def _full_cell_candidate(
    cell: dict[str, Any], dimension_order: list[str]
) -> dict[str, Any]:
    features = {dimension: cell["features"][dimension] for dimension in dimension_order}
    label = "__".join(
        f"{_slug(dimension)}_{_slug(features[dimension])}"
        for dimension in dimension_order
    )
    return {
        "id": f"kc_cell__{label}",
        "family": "full_cell",
        "definition": "Represent the exact development GrammarCell "
        + ", ".join(f"{dimension}={features[dimension]}" for dimension in dimension_order)
        + ".",
        "activation": {"cell": features},
        "dimensions": list(dimension_order),
        "conditions": [[dimension, features[dimension]] for dimension in dimension_order],
        "development_cell_id": cell["cell_id"],
    }


def _activation_dimensions(activation: dict[str, Any]) -> set[str]:
    if "cell" in activation:
        return set(activation["cell"])
    if "all" in activation:
        return set().union(*(_activation_dimensions(row) for row in activation["all"]))
    if "any" in activation:
        return set().union(*(_activation_dimensions(row) for row in activation["any"]))
    raise ValueError(f"unknown KC activation primitive: {activation}")


def _validate_activation(
    activation: dict[str, Any], grammar_schema: dict[str, Any]
) -> None:
    if "cell" in activation:
        for dimension, expected in activation["cell"].items():
            if dimension not in grammar_schema["dimensions"]:
                raise ValueError(f"operation activation uses unknown dimension: {dimension}")
            allowed = set(grammar_schema["dimensions"][dimension]["allowed_values"])
            if isinstance(expected, list):
                values = set(expected)
            elif isinstance(expected, dict) and set(expected) == {"not"}:
                values = {expected["not"]}
            elif isinstance(expected, str):
                values = {expected}
            else:
                raise ValueError(
                    f"invalid operation activation value for {dimension}: {expected}"
                )
            unknown = values - allowed
            if unknown:
                raise ValueError(
                    f"operation activation uses undeclared values for {dimension}: "
                    f"{sorted(unknown)}"
                )
        return
    branches = activation.get("all", activation.get("any"))
    if not isinstance(branches, list) or not branches:
        raise ValueError(f"invalid operation activation: {activation}")
    for branch in branches:
        _validate_activation(branch, grammar_schema)


def _validate_inputs(
    grammar_schema: dict[str, Any],
    development_cells: list[dict[str, Any]],
    development_items: list[dict[str, Any]],
    design: dict[str, Any],
) -> None:
    dimensions = grammar_schema["dimension_order"]
    if len(dimensions) != len(set(dimensions)):
        raise ValueError("canonical dimension_order contains duplicates")
    if not development_cells:
        raise ValueError("KC candidate generation requires development cells")
    cell_ids = [row["cell_id"] for row in development_cells]
    if len(cell_ids) != len(set(cell_ids)):
        raise ValueError("development cell IDs must be unique")
    for cell in development_cells:
        if set(cell["features"]) != set(dimensions):
            raise ValueError(f"development cell has the wrong dimensions: {cell['cell_id']}")
        for dimension in dimensions:
            allowed = grammar_schema["dimensions"][dimension]["allowed_values"]
            if cell["features"][dimension] not in allowed:
                raise ValueError(
                    f"development cell uses undeclared value: "
                    f"{dimension}={cell['features'][dimension]}"
                )
    item_ids = [row["item_id"] for row in development_items]
    if len(item_ids) != len(set(item_ids)):
        raise ValueError("development item IDs must be unique")
    unknown_cells = {row["cell_id"] for row in development_items} - set(cell_ids)
    if unknown_cells:
        raise ValueError(
            "KC candidate generation received non-development item cells: "
            f"{sorted(unknown_cells)}"
        )
    background = design.get("background_values", {})
    unknown_dimensions = set(background) - set(dimensions)
    if unknown_dimensions:
        raise ValueError(
            f"background_values uses unknown dimensions: {sorted(unknown_dimensions)}"
        )
    for dimension, values in background.items():
        unknown = set(values) - set(
            grammar_schema["dimensions"][dimension]["allowed_values"]
        )
        if unknown:
            raise ValueError(
                f"background_values uses undeclared values for {dimension}: {sorted(unknown)}"
            )
    for operation in design.get("operation_declarations", []):
        _validate_activation(operation["activation"], grammar_schema)


def _add_support(
    candidates: list[dict[str, Any]],
    development_cells: list[dict[str, Any]],
    development_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    cells_by_id = {row["cell_id"]: row["features"] for row in development_cells}
    ordered_items = sorted(development_items, key=lambda row: row["item_id"])
    rows = []
    for candidate in candidates:
        supporting_cells = sorted(
            cell_id
            for cell_id, features in cells_by_id.items()
            if activation_matches(features, candidate["activation"])
        )
        supporting_items = [
            item["item_id"]
            for item in ordered_items
            if item["cell_id"] in supporting_cells
        ]
        active_items = set(supporting_items)
        rows.append(
            {
                **candidate,
                "supporting_development_cell_ids": supporting_cells,
                "supporting_development_item_ids": supporting_items,
                "cell_support": len(supporting_cells),
                "item_support": len(supporting_items),
                "activation_vector": [
                    int(item["item_id"] in active_items) for item in ordered_items
                ],
            }
        )
    return rows


def _mark_equivalence(
    candidates: list[dict[str, Any]], design: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    family_order = {
        family: index
        for index, family in enumerate(design["equivalence_representative_order"])
    }
    unknown = {row["family"] for row in candidates} - set(family_order)
    if unknown:
        raise ValueError(
            f"equivalence representative order omits candidate families: {sorted(unknown)}"
        )
    grouped: dict[tuple[int, ...], list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        grouped[tuple(candidate["activation_vector"])].append(candidate)

    classes = []
    representative_by_id = {}
    for class_number, (vector, members) in enumerate(
        sorted(grouped.items(), key=lambda row: (row[0], sorted(x["id"] for x in row[1]))),
        1,
    ):
        ordered = sorted(
            members, key=lambda row: (family_order[row["family"]], row["id"])
        )
        representative = ordered[0]["id"]
        class_id = f"activation_class_{class_number:03d}"
        classes.append(
            {
                "equivalence_class_id": class_id,
                "representative_id": representative,
                "member_ids": [row["id"] for row in ordered],
                "activation_vector": list(vector),
            }
        )
        for member in ordered:
            representative_by_id[member["id"]] = (class_id, representative)

    output = []
    for candidate in candidates:
        class_id, representative = representative_by_id[candidate["id"]]
        output.append(
            {
                **candidate,
                "equivalence_class_id": class_id,
                "equivalent_to": (
                    None if candidate["id"] == representative else representative
                ),
                "is_equivalence_representative": candidate["id"] == representative,
            }
        )
    return output, classes


def make_kc_candidates(
    grammar_schema: dict[str, Any],
    development_cells: list[dict[str, Any]],
    development_items: list[dict[str, Any]],
    candidate_design: dict[str, Any],
) -> dict[str, Any]:
    """Build structural hypotheses without learner outcomes or held-out grammar.

    Only ``item_id`` and ``cell_id`` are read from the fixed development items.
    The caller must partition development grammar before invoking this function.
    """

    _validate_inputs(
        grammar_schema, development_cells, development_items, candidate_design
    )
    dimensions = grammar_schema["dimension_order"]
    families = candidate_design["candidate_types"]
    background = {
        dimension: set(values)
        for dimension, values in candidate_design.get("background_values", {}).items()
    }

    feature_candidates = []
    if families["feature_values"]:
        for dimension in dimensions:
            observed = {
                row["features"][dimension] for row in development_cells
            }
            for value in grammar_schema["dimensions"][dimension]["allowed_values"]:
                if value in observed and value not in background.get(dimension, set()):
                    feature_candidates.append(_feature_candidate(dimension, value))

    operation_candidates = []
    if families["operations"]:
        operation_candidates = [
            _operation_candidate(row)
            for row in candidate_design.get("operation_declarations", [])
        ]

    interaction_candidates = []
    if families["pairwise_interactions"]:
        for left, right in combinations(feature_candidates, 2):
            if left["dimensions"] == right["dimensions"]:
                continue
            candidate = _interaction_candidate(left, right)
            supported = _add_support(
                [candidate], development_cells, development_items
            )[0]
            if supported["item_support"] > 0:
                interaction_candidates.append(candidate)

    full_cell_candidates = []
    if families["full_cells"]:
        full_cell_candidates = [
            _full_cell_candidate(cell, dimensions)
            for cell in sorted(development_cells, key=lambda row: row["cell_id"])
        ]

    candidates = _add_support(
        feature_candidates
        + operation_candidates
        + interaction_candidates
        + full_cell_candidates,
        development_cells,
        development_items,
    )
    minimum_cells = int(candidate_design["minimum_interaction_cell_support"])
    minimum_items = int(candidate_design["minimum_interaction_item_support"])
    if minimum_cells < 1 or minimum_items < 1:
        raise ValueError("interaction support thresholds must be positive")
    candidates = [
        {
            **candidate,
            "meets_support_threshold": (
                candidate["item_support"] > 0
                and (
                    candidate["family"] != "interaction"
                    or (
                        candidate["cell_support"] >= minimum_cells
                        and candidate["item_support"] >= minimum_items
                    )
                )
            ),
        }
        for candidate in candidates
    ]
    candidates, equivalence_classes = _mark_equivalence(candidates, candidate_design)
    candidates = [
        {
            **candidate,
            "selection_eligible": (
                candidate["meets_support_threshold"]
                and candidate["is_equivalence_representative"]
            ),
            "exclusion_reasons": [
                *(
                    []
                    if candidate["item_support"] > 0
                    else ["no_development_item_support"]
                ),
                *(
                    []
                    if (
                        candidate["family"] != "interaction"
                        or (
                            candidate["cell_support"] >= minimum_cells
                            and candidate["item_support"] >= minimum_items
                        )
                    )
                    else ["below_interaction_support_threshold"]
                ),
                *(
                    []
                    if candidate["is_equivalence_representative"]
                    else ["activation_equivalent_on_development_items"]
                ),
            ],
        }
        for candidate in candidates
    ]
    counts = {
        family: sum(row["family"] == family for row in candidates)
        for family in ("feature_value", "operation", "interaction", "full_cell")
    }
    return {
        "candidate_design_id": candidate_design["candidate_design_id"],
        "grammar_schema_id": grammar_schema["schema_id"],
        "development_cell_ids": sorted(row["cell_id"] for row in development_cells),
        "development_item_ids": sorted(row["item_id"] for row in development_items),
        "candidate_counts": {
            **counts,
            "raw_total": len(candidates),
            "support_eligible": sum(
                row["meets_support_threshold"] for row in candidates
            ),
            "selection_eligible": sum(row["selection_eligible"] for row in candidates),
            "activation_equivalence_classes": len(equivalence_classes),
            "activation_duplicate_candidates": len(candidates)
            - len(equivalence_classes),
        },
        "support_thresholds": {
            "minimum_interaction_cell_support": minimum_cells,
            "minimum_interaction_item_support": minimum_items,
        },
        "candidates": sorted(candidates, key=lambda row: row["id"]),
        "equivalence_classes": equivalence_classes,
        "metadata": {
            "item_fields_read": ["item_id", "cell_id"],
            "learner_outcomes_read": False,
            "held_out_grammar_read": False,
            "equivalence_scope": "development_item_bank_only",
        },
    }
