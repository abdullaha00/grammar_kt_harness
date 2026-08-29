#!/usr/bin/env python3
"""Compare outcome-free generator-KC alternatives on one fixed item bank.

This pilot is deliberately structural.  It consumes only canonical cell
features, item-to-cell references, and researcher declarations.  It neither
accepts nor reads learner events, response outcomes, KC-selection output, or
KT results.

The four comparisons are:

* the declared reusable-operation hybrid;
* that hybrid plus one declared perfect-progressive-chain interaction;
* a data-driven feature-value control, excluding declared reference values;
* a one-KC-per-exact-cell diagnostic.

The generic controls contain no English feature names.  The one explicitly
English comparison is selected by the optional-interaction ID in the supplied
language declaration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.generator_kcs import construct_generator_kcs
from grammar_kt.io import read_jsonl, read_yaml, write_json
from grammar_kt.measurement import audit_measurement, build_true_q_matrix


PILOT_ID = "full_kc_001_structural_alternatives_v1"
ALTERNATIVE_ORDER = (
    "hybrid",
    "hybrid_plus_perfect_progressive_chain",
    "feature_only_control",
    "exact_cell_diagnostic",
)


def _slug(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_") or "empty"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _git_revision() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _structural_bank(
    cells: list[dict[str, Any]],
    items: list[dict[str, Any]],
    schema: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Copy only fields licensed by the structural pilot contract."""

    dimensions = list(schema["dimension_order"])
    if not cells:
        raise ValueError("generator-KC pilot needs at least one canonical cell")
    if not items:
        raise ValueError("generator-KC pilot needs at least one fixed item")

    structural_cells: list[dict[str, Any]] = []
    for row in cells:
        cell_id = row["cell_id"]
        features = row["features"]
        if not isinstance(cell_id, str) or not cell_id:
            raise ValueError("canonical cell IDs must be nonempty strings")
        if set(features) != set(dimensions):
            raise ValueError(f"wrong GrammarCell dimensions: {cell_id}")
        for dimension in dimensions:
            value = features[dimension]
            allowed = schema["dimensions"][dimension]["allowed_values"]
            if value not in allowed:
                raise ValueError(
                    f"invalid GrammarCell value: {cell_id} {dimension}={value}"
                )
        structural_cells.append(
            {
                "cell_id": cell_id,
                "features": {dimension: features[dimension] for dimension in dimensions},
            }
        )
    structural_cells.sort(key=lambda row: row["cell_id"])
    if len({row["cell_id"] for row in structural_cells}) != len(structural_cells):
        raise ValueError("canonical cells contain duplicate IDs")

    structural_items: list[dict[str, str]] = []
    for row in items:
        item_id = row["item_id"]
        cell_id = row["cell_id"]
        if not isinstance(item_id, str) or not item_id:
            raise ValueError("fixed item IDs must be nonempty strings")
        if not isinstance(cell_id, str) or not cell_id:
            raise ValueError("fixed item cell IDs must be nonempty strings")
        structural_items.append({"item_id": item_id, "cell_id": cell_id})
    structural_items.sort(key=lambda row: row["item_id"])
    if len({row["item_id"] for row in structural_items}) != len(structural_items):
        raise ValueError("fixed item bank contains duplicate item IDs")
    return structural_cells, structural_items


def _supporting_cells(
    cells: list[dict[str, Any]], dimension: str, value: str
) -> list[str]:
    return sorted(
        row["cell_id"] for row in cells if row["features"][dimension] == value
    )


def _activation_equivalence_classes(
    kcs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    signatures: dict[tuple[str, ...], list[str]] = {}
    for kc in kcs:
        signature = tuple(kc["supporting_cell_ids"])
        signatures.setdefault(signature, []).append(kc["id"])
    return sorted(
        (
            {
                "kc_ids": sorted(kc_ids),
                "supporting_cell_ids": list(signature),
            }
            for signature, kc_ids in signatures.items()
            if len(kc_ids) > 1
        ),
        key=lambda row: row["kc_ids"],
    )


def _control_inventory(
    *,
    inventory_id: str,
    schema: dict[str, Any],
    declaration: dict[str, Any],
    cells: list[dict[str, Any]],
    kcs: list[dict[str, Any]],
    control_kind: str,
) -> dict[str, Any]:
    ids = [row["id"] for row in kcs]
    if len(ids) != len(set(ids)):
        duplicates = sorted(
            identifier
            for identifier, count in Counter(ids).items()
            if count > 1
        )
        raise ValueError(f"control inventory has duplicate KC IDs: {duplicates}")
    if not kcs:
        raise ValueError(f"{control_kind} produced no KCs")
    ordered = sorted(kcs, key=lambda row: row["id"])
    return {
        "inventory_id": inventory_id,
        "grammar_schema_id": schema["schema_id"],
        "language_declaration_id": declaration["declaration_id"],
        "kcs": ordered,
        "excluded_declarations": [],
        "activation_equivalence_classes": _activation_equivalence_classes(ordered),
        "metadata": {
            "canonical_cell_count": len(cells),
            "generator_kc_count": len(ordered),
            "control_kind": control_kind,
            "learner_outcomes_read": False,
            "items_read": False,
            "discovered_kcs_read": False,
        },
    }


def build_feature_only_inventory(
    cells: list[dict[str, Any]],
    schema: dict[str, Any],
    declaration: dict[str, Any],
) -> dict[str, Any]:
    """Create one KC per observed non-reference dimension value.

    Dimension and value names come solely from the supplied schema and
    declaration, so this helper also works for non-English toy schemas.
    """

    reference_conditions = declaration.get("reference_conditions", {})
    kcs: list[dict[str, Any]] = []
    for dimension in schema["dimension_order"]:
        declared_reference = reference_conditions.get(dimension, [])
        if not isinstance(declared_reference, list):
            declared_reference = [declared_reference]
        reference_values = set(declared_reference)
        observed_values = {row["features"][dimension] for row in cells}
        for value in schema["dimensions"][dimension]["allowed_values"]:
            if value not in observed_values or value in reference_values:
                continue
            supporting_cell_ids = _supporting_cells(cells, dimension, value)
            kcs.append(
                {
                    "id": f"gkc_feature__{_slug(dimension)}__{_slug(value)}",
                    "name": f"feature value {dimension}={value}",
                    "description": (
                        f"Represent the observed non-reference value "
                        f"{dimension}={value}."
                    ),
                    "family": "feature_value_control",
                    "activation_rule": {"cell": {dimension: value}},
                    "linguistic_rationale": (
                        "Structural control: treat one declared canonical "
                        "dimension value as a reusable latent skill."
                    ),
                    "source_dimensions": [dimension],
                    "language_specific": bool(
                        declaration.get("language_specific", True)
                    ),
                    "language": declaration.get("language"),
                    "supporting_cell_ids": supporting_cell_ids,
                    "cell_support": len(supporting_cell_ids),
                    "provenance": {
                        "method": "observed_non_reference_dimension_values",
                        "language_declaration_id": declaration["declaration_id"],
                        "learner_outcomes_read": False,
                    },
                }
            )
    return _control_inventory(
        inventory_id="feature_only_control_v1",
        schema=schema,
        declaration=declaration,
        cells=cells,
        kcs=kcs,
        control_kind="feature_only",
    )


def build_exact_cell_inventory(
    cells: list[dict[str, Any]],
    schema: dict[str, Any],
    declaration: dict[str, Any],
) -> dict[str, Any]:
    """Create the diagnostic upper bound with one declared KC per exact tuple."""

    dimensions = list(schema["dimension_order"])
    kcs: list[dict[str, Any]] = []
    for cell in sorted(cells, key=lambda row: row["cell_id"]):
        features = {
            dimension: cell["features"][dimension] for dimension in dimensions
        }
        supporting_cell_ids = sorted(
            other["cell_id"]
            for other in cells
            if all(
                other["features"][dimension] == features[dimension]
                for dimension in dimensions
            )
        )
        kcs.append(
            {
                "id": f"gkc_exact_cell__{_slug(cell['cell_id'])}",
                "name": f"exact GrammarCell {cell['cell_id']}",
                "description": (
                    "Diagnostic exact-tuple latent variable for "
                    f"GrammarCell {cell['cell_id']}."
                ),
                "family": "exact_cell_diagnostic",
                "activation_rule": {"cell": features},
                "linguistic_rationale": (
                    "Upper-bound structural diagnostic; it intentionally "
                    "does not assert reusable linguistic competence."
                ),
                "source_dimensions": dimensions,
                "language_specific": bool(declaration.get("language_specific", True)),
                "language": declaration.get("language"),
                "supporting_cell_ids": supporting_cell_ids,
                "cell_support": len(supporting_cell_ids),
                "provenance": {
                    "method": "one_kc_per_exact_canonical_tuple",
                    "language_declaration_id": declaration["declaration_id"],
                    "learner_outcomes_read": False,
                },
            }
        )
    return _control_inventory(
        inventory_id="exact_cell_diagnostic_v1",
        schema=schema,
        declaration=declaration,
        cells=cells,
        kcs=kcs,
        control_kind="exact_cell",
    )


def _pair_geometry(audit: dict[str, Any]) -> dict[str, int]:
    pairs = audit["pair_contrasts"]
    complete_three_pattern = [
        row
        for row in pairs
        if row["left_only_items"]
        and row["right_only_items"]
        and row["cooccurring_items"]
    ]
    nested = [
        row
        for row in pairs
        if row["cooccurring_items"]
        and bool(row["left_only_items"]) != bool(row["right_only_items"])
    ]
    disjoint = [
        row
        for row in pairs
        if row["left_only_items"]
        and row["right_only_items"]
        and not row["cooccurring_items"]
    ]
    return {
        "total_pairs": len(pairs),
        "distinguishable_pairs": sum(row["columns_distinguishable"] for row in pairs),
        "two_sided_contrast_pairs": sum(row["two_sided_contrast"] for row in pairs),
        "a_only_b_only_and_a_plus_b_pairs": len(complete_three_pattern),
        "nested_support_pairs": len(nested),
        "disjoint_support_pairs": len(disjoint),
        "cooccurring_pairs": sum(bool(row["cooccurring_items"]) for row in pairs),
        "identical_pairs": len(audit["identical_q_columns"]),
        "near_identical_nonidentical_pairs": len(audit["near_identical_q_columns"]),
    }


def _range_summary(values: list[int]) -> dict[str, int | float | None]:
    if not values:
        return {"minimum": None, "median": None, "maximum": None}
    return {
        "minimum": min(values),
        "median": median(values),
        "maximum": max(values),
    }


def _comparison_summary(audit: dict[str, Any]) -> dict[str, Any]:
    supports = audit["kc_support"]
    counts = audit["counts"]
    pair_geometry = _pair_geometry(audit)
    return {
        "audit_status": audit["status"],
        "failures": audit["failures"],
        "generator_kcs": counts["generator_kcs"],
        "q_edges": counts["q_edges"],
        "q_density": counts["q_density"],
        "q_rank": counts["q_rank"],
        "full_column_rank": counts["q_rank"] == counts["generator_kcs"],
        "distinct_cell_activation_rows": counts["distinct_cell_activation_rows"],
        "item_support": _range_summary(
            [row["item_support"] for row in supports]
        ),
        "cell_support": _range_summary(
            [row["cell_support"] for row in supports]
        ),
        "reused_across_multiple_cells": sum(
            row["cell_support"] >= 2 for row in supports
        ),
        "kcs_with_isolating_items": sum(
            row["isolated_item_support"] > 0 for row in supports
        ),
        "zero_support_kcs": len(audit["zero_support_kc_ids"]),
        "rare_kcs": len(audit["rare_kcs"]),
        "identical_q_column_pairs": len(audit["identical_q_columns"]),
        "near_identical_q_column_pairs": len(audit["near_identical_q_columns"]),
        "pair_geometry": pair_geometry,
    }


def _optional_interaction_kc_id(
    declaration: dict[str, Any], optional_interaction_id: str
) -> str:
    matches = [
        row["kc_id"]
        for row in declaration.get("optional_interactions", [])
        if row["id"] == optional_interaction_id
    ]
    if len(matches) != 1:
        raise ValueError(
            "optional interaction must resolve to exactly one declaration: "
            f"{optional_interaction_id}"
        )
    return matches[0]


def investigate_generator_kcs(
    cells: list[dict[str, Any]],
    items: list[dict[str, Any]],
    schema: dict[str, Any],
    design: dict[str, Any],
    declaration: dict[str, Any],
    *,
    optional_interaction_id: str = "perfect_progressive_chain",
    input_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the fixed four-way comparison and return one JSON-ready artifact."""

    structural_cells, structural_items = _structural_bank(cells, items, schema)
    interaction_kc_id = _optional_interaction_kc_id(
        declaration, optional_interaction_id
    )
    inventories = {
        "hybrid": construct_generator_kcs(
            structural_cells, schema, design, declaration
        ),
        "hybrid_plus_perfect_progressive_chain": construct_generator_kcs(
            structural_cells,
            schema,
            design,
            declaration,
            include_optional_interactions=[optional_interaction_id],
        ),
        "feature_only_control": build_feature_only_inventory(
            structural_cells, schema, declaration
        ),
        "exact_cell_diagnostic": build_exact_cell_inventory(
            structural_cells, schema, declaration
        ),
    }

    alternatives: dict[str, Any] = {}
    comparison = []
    for name in ALTERNATIVE_ORDER:
        inventory = inventories[name]
        # Empty rows are retained for diagnosis rather than aborting the
        # comparison.  The measurement audit marks them as gate failures.
        q_rows = build_true_q_matrix(
            structural_items,
            structural_cells,
            inventory,
            require_nonempty=False,
        )
        audit = audit_measurement(
            structural_cells,
            structural_items,
            inventory,
            q_rows,
            design,
        )
        summary = _comparison_summary(audit)
        interaction_contrasts = [
            row
            for row in audit["pair_contrasts"]
            if interaction_kc_id in {row["left_kc_id"], row["right_kc_id"]}
        ]
        alternatives[name] = {
            "inventory": inventory,
            "q_projection": {
                "row_count": len(q_rows),
                "logical_sha256": _json_sha256(q_rows),
                "rows_embedded": True,
                "rows": q_rows,
                "reconstruction": (
                    "Re-run deterministic build_true_q_matrix on the retained "
                    "structural inputs and embedded inventory."
                ),
            },
            "summary": summary,
            "optional_interaction_pair_contrasts": interaction_contrasts,
            "measurement_audit": audit,
        }
        comparison.append({"alternative": name, **summary})

    return {
        "pilot_id": PILOT_ID,
        "question": (
            "Which declared ontology alternatives are reusable and structurally "
            "distinguishable on the fixed measurement bank before simulation?"
        ),
        "scientific_boundary": {
            "outcome_free": True,
            "fields_consumed": {
                "cells": ["cell_id", "features"],
                "items": ["item_id", "cell_id"],
            },
            "inputs_not_accepted": [
                "learner_events",
                "response_outcomes",
                "oracle_mastery",
                "discovered_kcs",
                "kc_selection",
                "kt_metrics",
            ],
            "learner_outcomes_read": False,
            "kc_selector_used": False,
            "kt_used": False,
        },
        "alternative_definitions": {
            "hybrid": "Fixed reusable-operation declaration with no interaction.",
            "hybrid_plus_perfect_progressive_chain": (
                "The same hybrid plus the single declared optional "
                f"interaction {optional_interaction_id}."
            ),
            "feature_only_control": (
                "One KC per observed schema dimension/value after excluding "
                "declared reference conditions."
            ),
            "exact_cell_diagnostic": (
                "One KC per exact canonical feature tuple; diagnostic rather "
                "than a reusable-skill claim."
            ),
        },
        "optional_interaction_id": optional_interaction_id,
        "optional_interaction_kc_id": interaction_kc_id,
        "inputs": {
            "cells": len(structural_cells),
            "items": len(structural_items),
            "grammar_schema_id": schema["schema_id"],
            "generator_design_id": design["design_id"],
            "language_declaration_id": declaration["declaration_id"],
            "structural_cells_sha256": _json_sha256(structural_cells),
            "structural_items_sha256": _json_sha256(structural_items),
            **(input_metadata or {}),
        },
        "comparison": comparison,
        "alternatives": alternatives,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cells",
        type=Path,
        default=ROOT / "data/grammar_kt_medium_v1/canonical/cells.jsonl",
    )
    parser.add_argument(
        "--items",
        type=Path,
        default=ROOT / "data/grammar_kt_medium_v1/items/selected_bank.jsonl",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=ROOT / "modules/grammar/canonical/schema.yaml",
    )
    parser.add_argument(
        "--design",
        type=Path,
        default=ROOT / "modules/kcs/generator/design.yaml",
    )
    parser.add_argument(
        "--declaration",
        type=Path,
        default=ROOT / "modules/kcs/generator/english_kcs.yaml",
    )
    parser.add_argument(
        "--optional-interaction-id",
        default="perfect_progressive_chain",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    paths = {
        "cells_path": arguments.cells.resolve(),
        "items_path": arguments.items.resolve(),
        "schema_path": arguments.schema.resolve(),
        "design_path": arguments.design.resolve(),
        "declaration_path": arguments.declaration.resolve(),
    }
    for name, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"{name} does not exist: {path}")
    input_metadata = {
        name: _display_path(path) for name, path in paths.items()
    } | {
        f"{name.removesuffix('_path')}_file_sha256": _sha256_file(path)
        for name, path in paths.items()
    }
    input_metadata.update(
        {
            "script_path": str(Path(__file__).resolve()),
            "script_sha256": _sha256_file(Path(__file__).resolve()),
            "git_revision": _git_revision(),
            "exact_command": " ".join([sys.executable, *sys.argv]),
        }
    )
    artifact = investigate_generator_kcs(
        read_jsonl(paths["cells_path"]),
        read_jsonl(paths["items_path"]),
        read_yaml(paths["schema_path"]),
        read_yaml(paths["design_path"]),
        read_yaml(paths["declaration_path"]),
        optional_interaction_id=arguments.optional_interaction_id,
        input_metadata=input_metadata,
    )
    write_json(arguments.output, artifact)
    print(
        json.dumps(
            {
                "output": str(arguments.output.resolve()),
                "cells": artifact["inputs"]["cells"],
                "items": artifact["inputs"]["items"],
                "comparison": artifact["comparison"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
