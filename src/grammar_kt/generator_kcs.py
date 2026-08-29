"""Construct an explicit generator-KC inventory before learner simulation."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .kc import activation_matches


def _slug(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_") or "empty"


def _validate_cells(
    cells: list[dict[str, Any]], grammar_schema: dict[str, Any]
) -> None:
    dimensions = list(grammar_schema["dimension_order"])
    if not cells:
        raise ValueError("generator-KC construction needs canonical cells")
    if len({row["cell_id"] for row in cells}) != len(cells):
        raise ValueError("canonical cells contain duplicate IDs")
    for cell in cells:
        if set(cell["features"]) != set(dimensions):
            raise ValueError(f"wrong GrammarCell dimensions: {cell['cell_id']}")


def _supporting_cells(
    activation_rule: dict[str, Any], cells: list[dict[str, Any]]
) -> list[str]:
    return sorted(
        cell["cell_id"]
        for cell in cells
        if activation_matches(cell["features"], activation_rule)
    )


def _make_record(
    declaration: dict[str, Any],
    cells: list[dict[str, Any]],
    *,
    design_id: str,
    declaration_id: str,
    language: str,
    family: str,
) -> dict[str, Any]:
    activation_rule = declaration["activation_rule"]
    supporting_cell_ids = _supporting_cells(activation_rule, cells)
    return {
        "id": declaration["id"],
        "name": declaration["name"],
        "description": declaration["description"],
        "family": family,
        "activation_rule": activation_rule,
        "linguistic_rationale": declaration["linguistic_rationale"],
        "source_dimensions": list(declaration["source_dimensions"]),
        "language_specific": True,
        "language": language,
        "supporting_cell_ids": supporting_cell_ids,
        "cell_support": len(supporting_cell_ids),
        "provenance": {
            "generator_design_id": design_id,
            "language_declaration_id": declaration_id,
            "learner_outcomes_read": False,
        },
    }


def construct_generator_kcs(
    cells: list[dict[str, Any]],
    grammar_schema: dict[str, Any],
    design: dict[str, Any],
    language_declaration: dict[str, Any],
    *,
    include_optional_interactions: list[str] | None = None,
) -> dict[str, Any]:
    """Build K* solely from fixed GrammarCells and researcher declarations.

    Unsupported declarations are retained in the construction audit but do not
    become latent learner dimensions. No item, response, KT, or discovered-KC
    input is accepted by this function.
    """

    _validate_cells(cells, grammar_schema)
    design_id = design["design_id"]
    declaration_id = language_declaration["declaration_id"]
    language = language_declaration["language"]
    requested_optional = set(include_optional_interactions or [])
    allowed_optional = {
        row["id"] for row in language_declaration.get("optional_interactions", [])
    }
    unknown_optional = requested_optional - allowed_optional
    if unknown_optional:
        raise ValueError(
            f"unknown optional generator interactions: {sorted(unknown_optional)}"
        )

    declarations: list[tuple[dict[str, Any], str]] = [
        (dict(row), "declared_operation")
        for row in language_declaration["fixed_kcs"]
    ]
    observed = {
        dimension: {cell["features"][dimension] for cell in cells}
        for dimension in grammar_schema["dimension_order"]
    }
    for expansion in language_declaration.get("expanded_dimension_kcs", []):
        dimension = expansion["dimension"]
        if dimension not in grammar_schema["dimensions"]:
            raise ValueError(f"KC expansion uses unknown dimension: {dimension}")
        excluded = set(expansion.get("excluded_values", []))
        for value in grammar_schema["dimensions"][dimension]["allowed_values"]:
            if value in excluded or value not in observed[dimension]:
                continue
            values = {
                "value": _slug(value),
                "value_upper": str(value).upper(),
                "dimension": dimension,
            }
            declarations.append(
                (
                    {
                        "id": expansion["id_template"].format(**values),
                        "name": expansion["name_template"].format(**values),
                        "description": expansion["description_template"].format(
                            **values
                        ),
                        "activation_rule": {"cell": {dimension: value}},
                        "linguistic_rationale": expansion[
                            "linguistic_rationale_template"
                        ].format(**values),
                        "source_dimensions": [dimension],
                    },
                    "dimension_value_operation",
                )
            )
    for row in language_declaration.get("optional_interactions", []):
        if row["id"] in requested_optional:
            declarations.append(
                (
                    {
                        **row,
                        "id": row["kc_id"],
                    },
                    "declared_interaction",
                )
            )

    ids = [row["id"] for row, _family in declarations]
    duplicate_ids = sorted(
        identifier for identifier, count in Counter(ids).items() if count > 1
    )
    if duplicate_ids:
        raise ValueError(f"duplicate generator-KC IDs: {duplicate_ids}")

    minimum_cells = int(design["support"]["minimum_cells_per_kc"])
    records = [
        _make_record(
            declaration,
            cells,
            design_id=design_id,
            declaration_id=declaration_id,
            language=language,
            family=family,
        )
        for declaration, family in declarations
    ]
    excluded = [
        {
            "id": row["id"],
            "reason": "below_minimum_cell_support",
            "cell_support": row["cell_support"],
            "minimum_cell_support": minimum_cells,
        }
        for row in records
        if row["cell_support"] < minimum_cells
    ]
    kcs = [row for row in records if row["cell_support"] >= minimum_cells]
    if not kcs:
        raise ValueError("generator-KC declaration produced no supported KCs")

    signatures: dict[tuple[str, ...], list[str]] = {}
    for kc in kcs:
        signature = tuple(kc["supporting_cell_ids"])
        signatures.setdefault(signature, []).append(kc["id"])
    equivalent = [
        {"kc_ids": sorted(kc_ids), "supporting_cell_ids": list(signature)}
        for signature, kc_ids in signatures.items()
        if len(kc_ids) > 1
    ]

    return {
        "inventory_id": design_id,
        "grammar_schema_id": grammar_schema["schema_id"],
        "language_declaration_id": declaration_id,
        "kcs": sorted(kcs, key=lambda row: row["id"]),
        "excluded_declarations": sorted(excluded, key=lambda row: row["id"]),
        "activation_equivalence_classes": sorted(
            equivalent, key=lambda row: row["kc_ids"]
        ),
        "metadata": {
            "canonical_cell_count": len(cells),
            "generator_kc_count": len(kcs),
            "optional_interactions_included": sorted(requested_optional),
            "learner_outcomes_read": False,
            "items_read": False,
            "discovered_kcs_read": False,
        },
    }


def generator_policy(inventory: dict[str, Any]) -> dict[str, Any]:
    """Expose the explicit K* in the small projection-policy contract."""

    return {
        "policy_id": inventory["inventory_id"],
        "kind": "generator_ground_truth",
        "kcs": [
            {
                "id": row["id"],
                "definition": row["description"],
                "activation": row["activation_rule"],
            }
            for row in inventory["kcs"]
        ],
        "metadata": {
            "learner_outcomes_read": False,
            "source_inventory_id": inventory["inventory_id"],
        },
    }
