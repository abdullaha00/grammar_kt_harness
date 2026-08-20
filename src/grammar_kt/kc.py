"""Deterministic KC policy loading, activation, and materialization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .io import read_jsonl, repo_path, stable_id, write_jsonl
from .records import kc_opportunity


# Policy loading

def load_policy(path: Path) -> dict[str, Any]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    if policy["kind"] == "rules_plus_interactions":
        base = json.loads((path.parent / policy["base_policy"]).read_text(encoding="utf-8"))
        policy = {**policy, "rules": base["rules"] + policy["interaction_rules"]}
    return policy


# Rule evaluation

def evaluate_rule(expression: dict[str, Any], opportunity: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Evaluate one activation expression and return its literal evidence."""

    if "all" in expression:
        evaluated = [evaluate_rule(part, opportunity) for part in expression["all"]]
        matched = all(result for result, _evidence in evaluated)
        return matched, {
            "matched": matched,
            "operator": "all",
            "parts": [evidence for _result, evidence in evaluated],
        }
    if "operation" in expression:
        expected = expression["operation"]
        actual = opportunity["realization_operations"]
        matched = expected in actual
        return matched, {
            "matched": matched,
            "field": "realization_operations",
            "expected": expected,
            "actual": actual,
        }
    if "cell" in expression:
        checks = []
        for key, expected in expression["cell"].items():
            actual = opportunity["cell"][key]
            matched = actual in expected if isinstance(expected, list) else actual == expected
            checks.append({"field": f"cell.{key}", "expected": expected, "actual": actual, "matched": matched})
        matched = all(check["matched"] for check in checks)
        return matched, {"matched": matched, "operator": "cell", "checks": checks}
    raise ValueError(f"unknown KC activation expression: {expression}")


def apply_policy(policy: dict[str, Any], opportunity: dict[str, Any]) -> dict[str, Any]:
    if policy["kind"] == "full_cell":
        kc_id = "KC_FULL_" + opportunity["canonical_cell_id"].removeprefix("CELL_")
        return {
            "policy_id": policy["policy_id"],
            "activated_kcs": [kc_id],
            "rules": [
                {
                    "kc_id": kc_id,
                    "activated": True,
                    "activation_rule": {"cell": opportunity["cell"]},
                    "reason": "the full-cell KC is defined by exact equality with this six-field cell",
                }
            ],
        }
    rules = []
    for rule in policy["rules"]:
        activated, evidence = evaluate_rule(rule["activation_rule"], opportunity)
        rules.append(
            {
                "kc_id": rule["kc_id"],
                "name": rule["name"],
                "activated": activated,
                "activation_rule": rule["activation_rule"],
                "evidence": evidence,
            }
        )
    return {
        "policy_id": policy["policy_id"],
        "activated_kcs": sorted(row["kc_id"] for row in rules if row["activated"]),
        "rules": rules,
    }


# Inventory construction

def materialize_inventory(
    policy: dict[str, Any], opportunities: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    projections = [
        {**opportunity, "kc_ids": apply_policy(policy, opportunity)["activated_kcs"]}
        for opportunity in opportunities
    ]
    templates: dict[str, dict[str, Any]] = {}
    if policy["kind"] == "full_cell":
        for opportunity in opportunities:
            suffix = opportunity["canonical_cell_id"].removeprefix("CELL_")
            kc_id = "KC_FULL_" + suffix
            templates[kc_id] = {
                "kc_id": kc_id,
                "name": f"full canonical cell {suffix}",
                "definition": "Require the complete six-dimensional canonical cell as one structural opportunity.",
                "activation_rule": {"cell": opportunity["cell"]},
                "required_conditions": [f"{key}={value}" for key, value in opportunity["cell"].items()],
                "includes": [opportunity["canonical_cell_id"]],
                "excludes": ["every non-identical canonical cell"],
                "realization_dependencies": ["entire RealizationSpec"],
                "near_neighbours": [],
                "rationale": "High-resolution structural baseline; cognitive atomicity is not claimed.",
            }
    else:
        templates = {rule["kc_id"]: rule for rule in policy["rules"]}
    cards = []
    for kc_id in sorted({kc for row in projections for kc in row["kc_ids"]}):
        template = templates[kc_id]
        domain = [row for row in projections if kc_id in row["kc_ids"]]
        cards.append(
            {
                "kc_id": kc_id,
                "name": template["name"],
                "definition": template["definition"],
                "activation_rule": template["activation_rule"],
                "required_conditions": template["required_conditions"],
                "includes": template["includes"],
                "excludes": template["excludes"],
                "source_cell_ids": sorted({row["canonical_cell_id"] for row in domain}),
                "source_descriptor_ids": sorted({sid for row in domain for sid in row["source_descriptor_ids"]}),
                "realization_dependencies": template["realization_dependencies"],
                "near_neighbours": template["near_neighbours"],
                "rationale": template["rationale"],
            }
        )
    return projections, cards


# Full stage

def run(run_dir: Path, settings: dict[str, Any]) -> dict[str, Any]:
    output = run_dir / "kc"
    output.mkdir(parents=True, exist_ok=False)
    cells = {row["canonical_cell_id"]: row for row in read_jsonl(run_dir / "canonical" / "canonical_cells.jsonl")}
    selected: dict[str, dict[str, Any]] = {}
    for row in sorted(read_jsonl(run_dir / "realisation" / "realisations.jsonl"), key=lambda value: value["spec"]["realization_id"]):
        selected.setdefault(row["spec"]["canonical_cell_id"], row)
    if set(selected) != set(cells):
        raise RuntimeError("KC opportunities do not cover every canonical cell")
    opportunities = []
    for cell_id in sorted(selected):
        realisation = selected[cell_id]
        opportunities.append(kc_opportunity({
            "opportunity_id": stable_id("OPP", cell_id, realisation["spec"]["realization_id"]),
            "split": realisation["split"],
            "canonical_cell_id": cell_id,
            "cell": cells[cell_id]["cell"],
            "realization_spec": realisation["spec"],
            "realization_operations": realisation["derivation"]["operations"],
            "source_descriptor_ids": cells[cell_id]["source_descriptor_ids"],
            "source_mapping_notes": cells[cell_id]["source_mapping_notes"],
        }))
    selected_policy = settings.get("selected_policy")
    selected_path = run_dir / selected_policy if selected_policy else None
    policy_path = selected_path if selected_path is not None and selected_path.is_file() else repo_path(settings["policy"])
    policy = load_policy(policy_path)
    projections, cards = materialize_inventory(policy, opportunities)
    empty_development = [
        row["canonical_cell_id"]
        for row in projections
        if row["split"] == "development" and not row["kc_ids"]
    ]
    if empty_development:
        raise RuntimeError(f"KC policy leaves development cells uncovered: {empty_development}")
    empty_holdout = [
        row["canonical_cell_id"]
        for row in projections
        if row["split"] != "development" and not row["kc_ids"]
    ]
    write_jsonl(output / "cell_kc_projection.jsonl", sorted(projections, key=lambda row: row["opportunity_id"]))
    write_jsonl(output / "kc_inventory.jsonl", sorted(cards, key=lambda row: row["kc_id"]))
    return {
        "policy": str(policy_path),
        "opportunities": len(projections),
        "kcs": len(cards),
        "uncovered_holdout_cells": empty_holdout,
    }
