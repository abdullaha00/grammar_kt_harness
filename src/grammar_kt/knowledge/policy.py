"""Apply a frozen KC policy to validated structural evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..folds import annotate_items, assignment_for_cells, fold_path, load_fold
from ..io import read_jsonl, write_json, write_jsonl
from ..measurement.operations import evaluate_structural_rule, structural_evidence
from ..records import measurement_opportunity


def load_policy(path: Path) -> dict[str, Any]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    if policy["kind"] == "rules_plus_interactions":
        base = json.loads((path.parent / policy["base_policy"]).read_text(encoding="utf-8"))
        policy = {**policy, "rules": base["rules"] + policy["interaction_rules"]}
    if policy["kind"] not in {"rules", "rules_plus_interactions", "full_cell"}:
        raise ValueError(f"unknown policy kind {policy['kind']!r}")
    return policy


def evidence_for_opportunity(
    opportunity: dict[str, Any], validated_structure: dict[str, Any] | None = None
) -> dict[str, Any]:
    measurement_opportunity(opportunity)
    intended = structural_evidence(
        opportunity["cell"], opportunity["structural_conditions"]
    )
    if validated_structure is None:
        return intended
    required = {"cell", "operations", "predicate_class", "agreement_site"}
    if set(validated_structure) != required:
        raise ValueError("validated_structure fields differ from structural evidence schema")
    for field in required:
        actual, expected = validated_structure[field], intended[field]
        matches = set(actual) == set(expected) if field == "operations" else actual == expected
        if not matches:
            raise ValueError(
                f"validated {field} differs from MeasurementOpportunity: {actual!r} != {expected!r}"
            )
    return {**intended, **validated_structure}


def evaluate_rule(
    expression: dict[str, Any], opportunity_or_evidence: dict[str, Any]
) -> tuple[bool, dict[str, Any]]:
    evidence = (
        evidence_for_opportunity(opportunity_or_evidence)
        if "measurement_opportunity_id" in opportunity_or_evidence
        else opportunity_or_evidence
    )
    return evaluate_structural_rule(expression, evidence)


def apply_policy(
    policy: dict[str, Any], opportunity: dict[str, Any],
    *, validated_structure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence = evidence_for_opportunity(opportunity, validated_structure)
    if policy["kind"] == "full_cell":
        kc_id = "KC_FULL_" + opportunity["canonical_cell_id"].removeprefix("CELL_")
        return {
            "policy_id": policy["policy_id"],
            "activated_kcs": [kc_id],
            "rules": [{"kc_id": kc_id, "activated": True, "activation_rule": {"cell": evidence["cell"]}}],
        }
    results = []
    for rule in policy["rules"]:
        activated, rule_evidence = evaluate_structural_rule(rule["activation_rule"], evidence)
        results.append(
            {
                "kc_id": rule["kc_id"],
                "name": rule["name"],
                "activated": activated,
                "activation_rule": rule["activation_rule"],
                "evidence": rule_evidence,
            }
        )
    return {
        "policy_id": policy["policy_id"],
        "activated_kcs": sorted(row["kc_id"] for row in results if row["activated"]),
        "rules": results,
    }


def materialize_inventory(
    policy: dict[str, Any], opportunities: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    projections = [
        {
            "measurement_opportunity_id": opportunity["measurement_opportunity_id"],
            "canonical_cell_id": opportunity["canonical_cell_id"],
            "kc_ids": apply_policy(policy, opportunity)["activated_kcs"],
        }
        for opportunity in opportunities
    ]
    if policy["kind"] == "full_cell":
        templates = {
            "KC_FULL_" + opportunity["canonical_cell_id"].removeprefix("CELL_"): {
                "kc_id": "KC_FULL_" + opportunity["canonical_cell_id"].removeprefix("CELL_"),
                "name": f"full canonical cell {opportunity['canonical_cell_id']}",
                "definition": "Exact six-dimensional GrammarCell baseline.",
                "activation_rule": {"cell": opportunity["cell"]},
                "required_conditions": [f"{key}={value}" for key, value in opportunity["cell"].items()],
                "includes": [opportunity["canonical_cell_id"]],
                "excludes": ["non-identical GrammarCells"],
                "measurement_dependencies": ["complete GrammarCell"],
                "near_neighbours": [],
                "rationale": "High-resolution structural control; cognitive atomicity is not claimed.",
            }
            for opportunity in opportunities
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
                "required_conditions": template.get("required_conditions", []),
                "includes": template.get("includes", []),
                "excludes": template.get("excludes", []),
                "source_cell_ids": sorted({row["canonical_cell_id"] for row in domain}),
                "measurement_dependencies": template.get("measurement_dependencies", []),
                "near_neighbours": template.get("near_neighbours", []),
                "rationale": template.get("rationale", "Frozen structural rule."),
            }
        )
    return projections, cards


def project_items(
    items: list[dict[str, Any]], opportunities: list[dict[str, Any]], policy: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Project accepted items mechanically through their MeasurementOpportunity."""

    by_id = {row["measurement_opportunity_id"]: row for row in opportunities}
    structural_projections, cards = materialize_inventory(policy, opportunities)
    kcs_by_opportunity = {
        row["measurement_opportunity_id"]: row["kc_ids"] for row in structural_projections
    }
    rows = []
    for item in sorted(items, key=lambda row: row["item_id"]):
        opportunity = by_id.get(item["measurement_opportunity_id"])
        if opportunity is None:
            raise RuntimeError(f"item refers to unknown MeasurementOpportunity: {item['item_id']}")
        if item["canonical_cell_id"] != opportunity["canonical_cell_id"]:
            raise RuntimeError(f"item changes the opportunity GrammarCell: {item['item_id']}")
        evidence_for_opportunity(opportunity, item["validated_structure"])
        rows.append(
            {
                "item_id": item["item_id"],
                "measurement_opportunity_id": item["measurement_opportunity_id"],
                "canonical_cell_id": item["canonical_cell_id"],
                "canonical_split": item["canonical_split"],
                "kc_ids": kcs_by_opportunity[item["measurement_opportunity_id"]],
            }
        )
    return rows, cards


def run(run_dir: Path, settings: dict[str, Any]) -> dict[str, Any]:
    output = run_dir / "knowledge"
    output.mkdir(parents=True, exist_ok=False)
    policy_path = run_dir / "knowledge_selection" / "selected_policy.json"
    if not policy_path.is_file():
        raise FileNotFoundError("knowledge selection must freeze selected_policy.json before application")
    policy = load_policy(policy_path)
    opportunities = read_jsonl(run_dir / "measurement" / "measurement_opportunities.jsonl")
    items = read_jsonl(run_dir / "generation" / "accepted_items.jsonl")
    cells = read_jsonl(run_dir / "canonical" / "canonical_cells.jsonl")
    manifest = load_fold(fold_path(settings))
    items = annotate_items(items, assignment_for_cells(cells, manifest))
    projections, cards = project_items(items, opportunities, policy)
    write_json(output / "frozen_policy.json", policy)
    write_jsonl(output / "item_kc_projection.jsonl", projections, sort_keys=False)
    write_jsonl(output / "projected_kc_inventory.jsonl", cards, sort_keys=False)
    return {
        "policy_id": policy["policy_id"],
        "items": len(items),
        "kcs": len(cards),
        "generator_specific_branches": False,
    }
