#!/usr/bin/env python3
"""Run the Phase 2 outcome-free KC candidate analyses."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from functools import partial
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.canonicalise import canonicalise, validate_cell
from grammar_kt.fold import apply_fold
from grammar_kt.generate import generate_items
from grammar_kt.io import (
    call_model,
    load_typed_resource,
    read_jsonl,
    read_text,
    read_yaml,
    write_json,
)
from grammar_kt.kc_candidates import make_kc_candidates
from grammar_kt.kc import activation_matches
from grammar_kt.normalise import normalise
from grammar_kt.validate_items import validate_items


def _design() -> dict[str, Any]:
    design = read_yaml(ROOT / "modules/kcs/candidate_design.yaml")
    operations = read_yaml(
        ROOT / "modules/grammar/canonical/english_operations.yaml"
    )
    return design | {"operation_declarations": operations["operations"]}


def _fixture_bank() -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    schema = read_yaml(ROOT / "modules/grammar/canonical/schema.yaml")
    fixture_call = partial(
        call_model,
        fixture_responses=read_yaml(ROOT / "data/fixtures/model_responses.yaml"),
    )
    resources = load_typed_resource(
        ROOT / "data/fixtures/egp_pilot.jsonl",
        read_yaml(ROOT / "modules/grammar/resource/egp/schema.yaml"),
    )
    mappings = normalise(
        resources,
        read_text(ROOT / "modules/grammar/resource/egp/normalisation/phase1.txt"),
        read_text(ROOT / "modules/grammar/resource/egp/normalisation/phase2.txt"),
        read_text(ROOT / "modules/grammar/resource/egp/normalisation/rulebook.md"),
        schema,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=fixture_call,
    )
    cells = canonicalise(mappings, schema)
    candidates = generate_items(
        cells,
        read_text(ROOT / "modules/items/generation/prompt.txt"),
        read_text(ROOT / "modules/items/generation/rulebook.md"),
        read_yaml(ROOT / "data/fixtures/item_generation.yaml"),
        read_yaml(
            ROOT / "modules/items/generation/formats/controlled_production.yaml"
        ),
        model="fixture",
        reasoning_effort="deterministic",
        model_call=fixture_call,
    )
    items, _judgments = validate_items(
        candidates,
        cells,
        read_text(ROOT / "modules/items/validation/prompt.txt"),
        read_yaml(ROOT / "modules/items/validation/criteria.yaml"),
        model="fixture",
        reasoning_effort="deterministic",
        model_call=fixture_call,
    )
    fold = apply_fold(
        cells, read_yaml(ROOT / "data/fixtures/declarations/fold_reference.yaml")
    )
    return schema, cells, items, fold


def _partition_development(
    cells: list[dict[str, Any]],
    items: list[dict[str, Any]],
    fold: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    development_ids = {
        row["cell_id"]
        for row in fold
        if row["grammar_split"] == "development"
    }
    return (
        [row for row in cells if row["cell_id"] in development_ids],
        [row for row in items if row["cell_id"] in development_ids],
    )


def _legacy_structure(
    schema: dict[str, Any],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
    list[dict[str, Any]],
]:
    path = (
        ROOT
        / "experiments/post_training_v1/data/pilot_v1/opportunities.jsonl"
    )
    rows = read_jsonl(path)
    features_by_id: dict[str, dict[str, str]] = {}
    source_ids_by_id: dict[str, set[str]] = {}
    conflicts = []
    validation_errors = []
    for row in rows:
        cell_id = row["canonical_cell_id"]
        features = row["cell"]
        try:
            validate_cell(features, schema)
        except (KeyError, ValueError) as error:
            validation_errors.append({"cell_id": cell_id, "error": str(error)})
        if cell_id in features_by_id and features_by_id[cell_id] != features:
            conflicts.append(cell_id)
        features_by_id[cell_id] = features
        source_ids_by_id.setdefault(cell_id, set()).update(
            row["source_descriptor_ids"]
        )
    if conflicts or validation_errors:
        raise ValueError(
            f"legacy structure is incompatible: conflicts={conflicts}, "
            f"validation_errors={validation_errors}"
        )
    development_ids = {
        row["canonical_cell_id"]
        for row in rows
        if row["canonical_split"] == "development"
    }
    cells = [
        {
            "cell_id": cell_id,
            "features": features_by_id[cell_id],
            "source_ids": sorted(source_ids_by_id[cell_id]),
        }
        for cell_id in sorted(development_ids)
    ]
    items = [
        {
            "item_id": row["measurement_opportunity_id"],
            "cell_id": row["canonical_cell_id"],
        }
        for row in rows
        if row["canonical_split"] == "development"
    ]
    split_counts = {
        split: sum(row["canonical_split"] == split for row in rows)
        for split in sorted({row["canonical_split"] for row in rows})
    }
    compatibility = {
        "artifact": str(path.relative_to(ROOT)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "semantic_unit": "measurement opportunity; learner outcomes and legacy KCs absent",
        "rows": len(rows),
        "unique_cells": len(features_by_id),
        "development_cells": len(cells),
        "development_items": len(items),
        "split_item_counts": split_counts,
        "schema_validation_errors": validation_errors,
        "canonical_id_feature_conflicts": sorted(set(conflicts)),
        "feature_values": {
            dimension: sorted(
                {features[dimension] for features in features_by_id.values()}
            )
            for dimension in schema["dimension_order"]
        },
    }
    return cells, items, compatibility, rows


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sensitivity(
    schema: dict[str, Any],
    cells: list[dict[str, Any]],
    items: list[dict[str, Any]],
    design: dict[str, Any],
) -> dict[str, Any]:
    settings = []
    for threshold in (1, 2, 3, 5):
        settings.append((1, threshold, f"item_threshold_{threshold}"))
    for threshold in (1, 2, 3, 5):
        settings.append((threshold, 1, f"cell_threshold_{threshold}"))
    settings.append(
        (
            design["minimum_interaction_cell_support"],
            design["minimum_interaction_item_support"],
            "active_joint_threshold",
        )
    )
    output = []
    for cell_support, item_support, label in settings:
        changed = copy.deepcopy(design)
        changed["minimum_interaction_cell_support"] = cell_support
        changed["minimum_interaction_item_support"] = item_support
        inventory = make_kc_candidates(schema, cells, items, changed)
        interactions = [
            row for row in inventory["candidates"] if row["family"] == "interaction"
        ]
        output.append(
            {
                "label": label,
                "minimum_interaction_cell_support": cell_support,
                "minimum_interaction_item_support": item_support,
                "raw_interactions": len(interactions),
                "support_eligible_interactions": sum(
                    row["meets_support_threshold"] for row in interactions
                ),
                "selection_eligible_interactions": sum(
                    row["selection_eligible"] for row in interactions
                ),
                "total_selection_eligible_candidates": inventory[
                    "candidate_counts"
                ]["selection_eligible"],
            }
        )
    return {
        "note": (
            "Item support counts structural opportunities in this Phase 2 run; "
            "cell support prevents repeated opportunities in one cell from "
            "masquerading as reusable structural evidence."
        ),
        "settings": output,
    }


def _background_sensitivity(
    schema: dict[str, Any],
    cells: list[dict[str, Any]],
    items: list[dict[str, Any]],
    design: dict[str, Any],
) -> list[dict[str, Any]]:
    interventions: list[tuple[str, dict[str, Any]]] = [("active", copy.deepcopy(design))]

    present_reference = copy.deepcopy(design)
    present_reference["background_values"]["tense"].append("present")
    interventions.append(("present_as_reference", present_reference))

    for dimension, values in design["background_values"].items():
        for value in values:
            changed = copy.deepcopy(design)
            changed["background_values"][dimension].remove(value)
            interventions.append((f"explicit_{dimension}_{value}", changed))

    all_observed = copy.deepcopy(design)
    all_observed["background_values"] = {}
    interventions.append(("all_observed_values_explicit", all_observed))

    output = []
    for label, changed in interventions:
        inventory = make_kc_candidates(schema, cells, items, changed)
        features = [
            row for row in inventory["candidates"] if row["family"] == "feature_value"
        ]
        interactions = [
            row for row in inventory["candidates"] if row["family"] == "interaction"
        ]
        output.append(
            {
                "intervention": label,
                "feature_candidates": len(features),
                "raw_interactions": len(interactions),
                "support_eligible_interactions": sum(
                    row["meets_support_threshold"] for row in interactions
                ),
                "raw_total": inventory["candidate_counts"]["raw_total"],
                "activation_equivalence_classes": inventory["candidate_counts"][
                    "activation_equivalence_classes"
                ],
                "activation_duplicate_candidates": inventory["candidate_counts"][
                    "activation_duplicate_candidates"
                ],
                "selection_eligible": inventory["candidate_counts"][
                    "selection_eligible"
                ],
                "feature_support": {
                    row["id"]: {
                        "cells": row["cell_support"],
                        "items": row["item_support"],
                    }
                    for row in features
                },
            }
        )
    return output


def _operation_audit(
    cells: list[dict[str, Any]],
    fixture_items: list[dict[str, Any]],
    legacy_rows: list[dict[str, Any]],
    legacy_inventory: dict[str, Any],
) -> dict[str, Any]:
    historical_tags = read_yaml(
        ROOT / "data/fixtures/historical/english_generator_tag_rules.yaml"
    )
    declarations = historical_tags["tag_rules"]
    tag_rules = {
        row["generator_tag"]: row["activation"]
        for row in declarations
        if row.get("generator_tag")
    }
    cells_by_id = {row["cell_id"]: row["features"] for row in cells}
    fixture_checks = []
    for item in fixture_items:
        expected = sorted(
            tag
            for tag, activation in tag_rules.items()
            if activation_matches(cells_by_id[item["cell_id"]], activation)
        )
        historical_reported = historical_tags[
            "fixture_reported_tags_by_cell_id"
        ].get(item["cell_id"], [])
        reported = sorted(tag for tag in historical_reported if tag in tag_rules)
        fixture_checks.append(
            {
                "item_id": item["item_id"],
                "expected_cell_deterministic_tags": expected,
                "reported_cell_deterministic_tags": reported,
                "generator_only_or_excluded_tags": sorted(
                    set(historical_reported) - set(tag_rules)
                ),
                "agreement": expected == reported,
            }
        )

    legacy_development = [
        row for row in legacy_rows if row["canonical_split"] == "development"
    ]
    legacy_checks = []
    for row in legacy_development:
        expected = sorted(
            tag
            for tag, activation in tag_rules.items()
            if activation_matches(row["cell"], activation)
        )
        reported = sorted(
            tag for tag in row["expected_operations"] if tag in tag_rules
        )
        legacy_checks.append(
            {
                "measurement_opportunity_id": row["measurement_opportunity_id"],
                "expected_from_cell_declaration": expected,
                "legacy_rule_tags": reported,
                "legacy_realisation_dependent_tags": sorted(
                    set(row["expected_operations"]) - set(tag_rules)
                ),
                "agreement": expected == reported,
            }
        )

    operation_candidates = [
        {
            "id": row["id"],
            "cell_support": row["cell_support"],
            "item_support": row["item_support"],
            "equivalent_to": row["equivalent_to"],
            "selection_eligible": row["selection_eligible"],
        }
        for row in legacy_inventory["candidates"]
        if row["family"] == "operation"
    ]
    return {
        "scope": (
            "Agreement checks only cell-deterministic tags. Legacy tags were "
            "created by deterministic rules and are not independent validation."
        ),
        "fixture": {
            "items": len(fixture_checks),
            "agreements": sum(row["agreement"] for row in fixture_checks),
            "rows": fixture_checks,
        },
        "legacy_development": {
            "items": len(legacy_checks),
            "agreements": sum(row["agreement"] for row in legacy_checks),
            "rows": legacy_checks,
        },
        "legacy_candidate_support_and_equivalence": operation_candidates,
        "excluded_from_cell_deterministic_candidates": {
            "agreement": "depends on subject/person/number and realisation",
            "do_support": "depends on operator and predicate realisation",
            "emphatic_do": "realisation-dependent and not canonical-cell entailed",
            "let_imperative": "imperative subtype absent from the canonical cell",
        },
    }


def main() -> int:
    output = ROOT / "reports/phase2/artifacts"
    output.mkdir(parents=True, exist_ok=True)
    design = _design()

    schema, cells, items, fold = _fixture_bank()
    development_cells, development_items = _partition_development(
        cells, items, fold
    )
    fixture = make_kc_candidates(
        schema, development_cells, development_items, design
    )
    write_json(output / "fixture_candidate_inventory.json", fixture)

    mutated = copy.deepcopy(cells)
    development_ids = {row["cell_id"] for row in development_cells}
    for cell in mutated:
        if cell["cell_id"] not in development_ids:
            cell["features"] = {
                dimension: "UNREAD_HOLDOUT"
                for dimension in schema["dimension_order"]
            }
            cell["source_ids"] = ["mutated_holdout"]
    changed_development, changed_items = _partition_development(mutated, items, fold)
    fixture_after_mutation = make_kc_candidates(
        schema, changed_development, changed_items, design
    )
    negative_control = {
        "intervention": "replace every held-out feature value and source ID",
        "before_sha256": _digest(fixture),
        "after_sha256": _digest(fixture_after_mutation),
        "inventory_unchanged": fixture == fixture_after_mutation,
    }
    if not negative_control["inventory_unchanged"]:
        raise AssertionError("holdout mutation changed development candidate inventory")

    legacy_cells, legacy_items, compatibility, legacy_rows = _legacy_structure(schema)
    legacy = make_kc_candidates(schema, legacy_cells, legacy_items, design)
    write_json(output / "legacy_development_candidate_inventory.json", legacy)
    write_json(output / "legacy_compatibility.json", compatibility)
    write_json(output / "holdout_mutation_negative_control.json", negative_control)
    sensitivity = {
        "fixture": _sensitivity(
            schema, development_cells, development_items, design
        ),
        "legacy_development": _sensitivity(
            schema, legacy_cells, legacy_items, design
        ),
    }
    write_json(output / "support_sensitivity.json", sensitivity)
    background_sensitivity = {
        "fixture": _background_sensitivity(
            schema, development_cells, development_items, design
        ),
        "legacy_development": _background_sensitivity(
            schema, legacy_cells, legacy_items, design
        ),
    }
    write_json(output / "background_sensitivity.json", background_sensitivity)
    operation_audit = _operation_audit(
        development_cells,
        development_items,
        legacy_rows,
        legacy,
    )
    write_json(output / "operation_audit.json", operation_audit)
    summary = {
        "experiment_id": "P2-CANDIDATES-001",
        "fixture": fixture["candidate_counts"],
        "legacy_development": legacy["candidate_counts"],
        "legacy_compatibility": compatibility,
        "holdout_mutation_negative_control": negative_control,
        "support_sensitivity": sensitivity,
        "background_sensitivity": background_sensitivity,
        "operation_audit": {
            "fixture_tag_agreement": (
                f"{operation_audit['fixture']['agreements']}/"
                f"{operation_audit['fixture']['items']}"
            ),
            "legacy_rule_tag_agreement_not_independent": (
                f"{operation_audit['legacy_development']['agreements']}/"
                f"{operation_audit['legacy_development']['items']}"
            ),
        },
        "model_calls": "fixture responses only; no live model or learner outcome",
        "seed": None,
    }
    write_json(output / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
