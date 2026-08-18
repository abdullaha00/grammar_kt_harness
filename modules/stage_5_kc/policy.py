"""Deterministic KC policy loading, activation, and materialization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_policy(path: Path) -> dict[str, Any]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    if policy["kind"] == "rules_plus_interactions":
        base = json.loads((path.parent / policy["base_policy"]).read_text(encoding="utf-8"))
        policy = {**policy, "rules": base["rules"] + policy["interaction_rules"]}
    return policy


def matches(expression: dict[str, Any], opportunity: dict[str, Any]) -> bool:
    if "all" in expression:
        return all(matches(part, opportunity) for part in expression["all"])
    if "operation" in expression:
        return expression["operation"] in opportunity["realization_operations"]
    if "cell" in expression:
        for key, expected in expression["cell"].items():
            actual = opportunity["cell"][key]
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
        return True
    raise ValueError(f"unknown KC activation expression: {expression}")


def explain_match(expression: dict[str, Any], opportunity: dict[str, Any]) -> dict[str, Any]:
    """Return the same decision as ``matches`` plus literal rule-level evidence."""

    if "all" in expression:
        parts = [explain_match(part, opportunity) for part in expression["all"]]
        return {
            "matched": all(part["matched"] for part in parts),
            "operator": "all",
            "parts": parts,
        }
    if "operation" in expression:
        expected = expression["operation"]
        actual = opportunity["realization_operations"]
        return {
            "matched": expected in actual,
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
        return {"matched": all(check["matched"] for check in checks), "operator": "cell", "checks": checks}
    raise ValueError(f"unknown KC activation expression: {expression}")


def explain_policy(policy: dict[str, Any], opportunity: dict[str, Any]) -> dict[str, Any]:
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
        evidence = explain_match(rule["activation_rule"], opportunity)
        rules.append(
            {
                "kc_id": rule["kc_id"],
                "name": rule["name"],
                "activated": evidence["matched"],
                "activation_rule": rule["activation_rule"],
                "evidence": evidence,
            }
        )
    return {
        "policy_id": policy["policy_id"],
        "activated_kcs": sorted(row["kc_id"] for row in rules if row["activated"]),
        "rules": rules,
    }


def activated_kcs(policy: dict[str, Any], opportunity: dict[str, Any]) -> list[str]:
    if policy["kind"] == "full_cell":
        return ["KC_FULL_" + opportunity["canonical_cell_id"].removeprefix("CELL_")]
    return sorted(
        rule["kc_id"] for rule in policy["rules"] if matches(rule["activation_rule"], opportunity)
    )


def materialize(policy: dict[str, Any], opportunities: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    projections = [{**opportunity, "kc_ids": activated_kcs(policy, opportunity)} for opportunity in opportunities]
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
