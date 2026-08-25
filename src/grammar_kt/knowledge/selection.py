"""Development-only KC selection followed by frozen holdout evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..folds import fold_path, fold_rows, load_fold
from ..io import read_json, read_jsonl, repo_path, stable_id, write_json, write_jsonl
from ..measurement.opportunities import build_measurement_opportunities
from .candidates import discover_candidates, salient_facts
from .policy import apply_policy, evaluate_rule, load_policy


def partition_inputs(
    cells: list[dict[str, Any]], opportunities: list[dict[str, Any]], cell_splits: list[dict[str, str]]
) -> dict[str, Any]:
    split_by_id = {row["canonical_cell_id"]: row["split"] for row in cell_splits}
    cell_ids = {row["canonical_cell_id"] for row in cells}
    if set(split_by_id) != cell_ids:
        raise ValueError("fold assignments do not exactly cover canonical cells")
    development_ids = {cell_id for cell_id, split in split_by_id.items() if split == "development"}
    return {
        "split_by_id": split_by_id,
        "development_cells": [row for row in cells if row["canonical_cell_id"] in development_ids],
        "development_opportunities": [row for row in opportunities if row["canonical_cell_id"] in development_ids],
        "development_cell_ids": sorted(development_ids),
        "compositional_holdout_cell_ids": sorted(cell_id for cell_id, split in split_by_id.items() if split == "compositional_holdout"),
        "novel_feature_holdout_cell_ids": sorted(cell_id for cell_id, split in split_by_id.items() if split == "novel_feature_holdout"),
    }


def build_obligations(discovery: dict[str, Any]) -> list[dict[str, Any]]:
    obligations = []
    for cell_id, facts in sorted(discovery["development_cell_facts"].items()):
        for fact in facts:
            obligations.append(
                {
                    "obligation_id": stable_id("OBL", cell_id, fact),
                    "canonical_cell_id": cell_id,
                    "fact": fact,
                }
            )
    return obligations


def _candidate_coverage(discovery: dict[str, Any]) -> dict[str, set[str]]:
    obligations = build_obligations(discovery)
    active_cells: dict[str, set[str]] = {}
    cells_by_candidate: dict[str, set[str]] = {}
    opportunity_to_cell = discovery["opportunity_to_cell"]
    candidate_by_id = {row["candidate_id"]: row for row in discovery["candidates"]}
    for candidate_id in candidate_by_id:
        cells_by_candidate[candidate_id] = set()
    for activation in discovery["activations"]:
        if activation["activated"]:
            cells_by_candidate[activation["candidate_id"]].add(
                opportunity_to_cell[activation["measurement_opportunity_id"]]
            )
    for candidate_id, candidate in candidate_by_id.items():
        active_cells[candidate_id] = {
            obligation["obligation_id"]
            for obligation in obligations
            if obligation["canonical_cell_id"] in cells_by_candidate[candidate_id]
            and obligation["fact"] in set(candidate["represents"])
        }
    return active_cells


def select_inventory(discovery: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Deterministic greedy set cover with equivalence collapse and pruning."""

    obligations = build_obligations(discovery)
    obligation_ids = {row["obligation_id"] for row in obligations}
    coverage = _candidate_coverage(discovery)
    candidates = {row["candidate_id"]: row for row in discovery["candidates"]}
    eligible = {
        candidate_id
        for candidate_id, row in candidates.items()
        if row["selection_eligible"] and coverage[candidate_id]
    }
    selected: list[str] = []
    covered: set[str] = set()
    trace = []
    while covered != obligation_ids:
        available = []
        selected_kcs = {candidates[value]["kc_id"] for value in selected}
        for candidate_id in eligible - set(selected):
            candidate = candidates[candidate_id]
            if not set(candidate["requires_selected_kc_ids"]) <= selected_kcs:
                continue
            new = coverage[candidate_id] - covered
            if new:
                available.append(
                    (
                        -len(new),
                        candidate["rule_complexity"],
                        candidate["granularity_rank"],
                        candidate["kc_id"],
                        candidate_id,
                        new,
                    )
                )
        if not available:
            missing = sorted(obligation_ids - covered)
            raise RuntimeError(f"candidate family cannot cover development obligations: {missing[:10]}")
        *_rank, candidate_id, new = sorted(available)[0]
        selected.append(candidate_id)
        covered.update(new)
        trace.append(
            {
                "step": len(trace) + 1,
                "action": "greedy_add",
                "candidate_id": candidate_id,
                "kc_id": candidates[candidate_id]["kc_id"],
                "new_obligation_ids": sorted(new),
            }
        )
    # Backward pruning is deterministic and preserves exact obligation coverage.
    for candidate_id in list(reversed(selected)):
        trial = [value for value in selected if value != candidate_id]
        trial_coverage = set().union(*(coverage[value] for value in trial)) if trial else set()
        required_by_remaining = {
            kc_id
            for value in trial
            for kc_id in candidates[value]["requires_selected_kc_ids"]
        }
        if obligation_ids <= trial_coverage and candidates[candidate_id]["kc_id"] not in required_by_remaining:
            selected = trial
            trace.append(
                {
                    "step": len(trace) + 1,
                    "action": "backward_prune",
                    "candidate_id": candidate_id,
                    "kc_id": candidates[candidate_id]["kc_id"],
                }
            )
    selected_rows = [candidates[value] for value in selected]
    return {
        "selector_id": config.get("selector_id", "greedy_backward_v1"),
        "selected_candidates": selected_rows,
        "obligations": obligations,
        "selection_trace": trace,
        "objective": {
            "obligations": len(obligations),
            "covered_obligations": len(set().union(*(coverage[value] for value in selected)) if selected else set()),
            "selected_kcs": len(selected),
        },
        "diagnostics": discovery["diagnostics"],
    }


def compile_policy(selection: dict[str, Any], development_cell_ids: list[str]) -> dict[str, Any]:
    rules = []
    for candidate in selection["selected_candidates"]:
        rules.append(
            {
                "kc_id": candidate["kc_id"],
                "name": candidate["name"],
                "definition": candidate["definition"],
                "activation_rule": candidate["activation_rule"],
                "required_conditions": candidate["required_conditions"],
                "includes": candidate["includes"],
                "excludes": candidate["excludes"],
                "measurement_dependencies": candidate["measurement_dependencies"],
                "near_neighbours": candidate["near_neighbours"],
                "rationale": candidate["rationale"],
            }
        )
    return {
        "policy_id": stable_id("POLICY", "development_selected_v1", rules, development_cell_ids),
        "kind": "rules",
        "description": "KC ontology selected from development cells and MeasurementOpportunities, then frozen.",
        "selection_metadata": {
            "data_partition": "development",
            "development_cell_ids": development_cell_ids,
            "generated_text_read": False,
            "simulation_or_kt_evidence_read": False,
        },
        "rules": rules,
    }


def compile_predefined_policy(path: Path, development_cell_ids: list[str]) -> dict[str, Any]:
    policy = load_policy(path)
    return {
        **policy,
        "policy_id": stable_id("POLICY", policy["policy_id"], development_cell_ids),
        "selection_metadata": {
            "data_partition": "development",
            "development_cell_ids": development_cell_ids,
            "predefined_expert_control": True,
            "generated_text_read": False,
        },
    }


def development_frozen_full_cell_policy(development_cells: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "policy_id": stable_id("POLICY", "development_full_cell", [row["canonical_cell_id"] for row in development_cells]),
        "kind": "rules",
        "description": "Full-cell rules compiled from development cells only.",
        "selection_metadata": {"data_partition": "development", "generated_text_read": False},
        "rules": [
            {
                "kc_id": "KC_FULL_" + row["canonical_cell_id"].removeprefix("CELL_"),
                "name": f"full cell {row['canonical_cell_id']}",
                "definition": "Exact development GrammarCell control.",
                "activation_rule": {"cell": row["cell"]},
                "required_conditions": [f"{key}={value}" for key, value in row["cell"].items()],
                "includes": [row["canonical_cell_id"]],
                "excludes": ["non-identical cells"],
                "measurement_dependencies": ["complete GrammarCell"],
                "near_neighbours": [],
                "rationale": "Development-only memorisation control.",
            }
            for row in development_cells
        ],
    }


def evaluate_after_freeze(
    policy: dict[str, Any], opportunities: list[dict[str, Any]], split_by_id: dict[str, str],
    development_cell_ids: list[str], obligation_policy: dict[str, Any],
) -> dict[str, Any]:
    development_kcs = {
        kc_id
        for row in opportunities
        if row["canonical_cell_id"] in set(development_cell_ids)
        for kc_id in apply_policy(policy, row)["activated_kcs"]
    }
    split_results = {}
    for split in ("development", "compositional_holdout", "novel_feature_holdout"):
        rows = [row for row in opportunities if split_by_id[row["canonical_cell_id"]] == split]
        projections = [apply_policy(policy, row)["activated_kcs"] for row in rows]
        assignments = sum(len(values) for values in projections)
        reused = sum(sum(kc_id in development_kcs for kc_id in values) for values in projections)
        split_results[split] = {
            "measurement_opportunities": len(rows),
            "covered_opportunities": sum(bool(values) for values in projections),
            "coverage": sum(bool(values) for values in projections) / len(rows) if rows else None,
            "component_reuse": reused / assignments if assignments else None,
            "unique_signature_rate": len({tuple(values) for values in projections}) / len(rows) if rows else None,
        }
    development_fact_vocabulary = {
        fact for row in opportunities if row["canonical_cell_id"] in set(development_cell_ids)
        for fact in salient_facts(row["cell"], obligation_policy)
    }
    holdout_audit = []
    seen_cells = set()
    for row in opportunities:
        cell_id = row["canonical_cell_id"]
        if cell_id in seen_cells or split_by_id[cell_id] == "development":
            continue
        seen_cells.add(cell_id)
        unseen = sorted(set(salient_facts(row["cell"], obligation_policy)) - development_fact_vocabulary)
        split = split_by_id[cell_id]
        matches = not unseen if split == "compositional_holdout" else bool(unseen)
        holdout_audit.append({"canonical_cell_id": cell_id, "split": split, "unseen_salient_facts": unseen, "classification_matches_definition": matches})
    return {
        "selected_policy_fingerprint": stable_id("FROZEN", policy),
        "selected_policy_written_before_holdout_evaluation": True,
        "selection_data_partition": "development",
        "generated_text_used_during_selection": False,
        "item_bank_simulation_or_kt_evidence_used_during_selection": False,
        "split_results": split_results,
        "split_audit": {
            "status": "PASS" if all(row["classification_matches_definition"] for row in holdout_audit) else "FAIL",
            "cells": holdout_audit,
        },
    }


def evaluate_fixture(fixture: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    cells = fixture["canonical_cells"]
    opportunities = fixture.get("measurement_opportunities") or build_measurement_opportunities(
        cells, fixture.get("measurement_config")
    )
    partition = partition_inputs(cells, opportunities, fixture["cell_splits"])
    discovery = discover_candidates(partition["development_cells"], partition["development_opportunities"], config)
    selection = select_inventory(discovery, config)
    policy = compile_policy(selection, partition["development_cell_ids"])
    return {"discovery": discovery, "selection": selection, "selected_policy": policy}


def run(run_dir: Path, settings: dict[str, Any]) -> dict[str, Any]:
    output = run_dir / "knowledge_selection"
    output.mkdir(parents=True, exist_ok=False)
    config = read_json(repo_path(settings["config"]))
    mode = settings.get("mode", "structural")
    cells = read_jsonl(run_dir / "canonical" / "canonical_cells.jsonl")
    opportunities = read_jsonl(run_dir / "measurement" / "measurement_opportunities.jsonl")
    manifest = load_fold(fold_path(settings))
    split_rows = fold_rows(cells, manifest)
    partition = partition_inputs(cells, opportunities, split_rows)
    discovery = discover_candidates(
        partition["development_cells"], partition["development_opportunities"], config
    )
    if mode == "structural":
        selection = select_inventory(discovery, config)
        policy = compile_policy(selection, partition["development_cell_ids"])
        trace = selection["selection_trace"]
        objective = selection["objective"]
    elif mode in {"predefined", "development_frozen_factorized"}:
        policy = compile_predefined_policy(repo_path(settings["policy"]), partition["development_cell_ids"])
        if mode == "development_frozen_factorized":
            supported_rules = [
                rule for rule in policy["rules"]
                if any(evaluate_rule(rule["activation_rule"], row)[0] for row in partition["development_opportunities"])
            ]
            policy = {**policy, "rules": supported_rules, "policy_id": stable_id("POLICY", policy["policy_id"], [row["kc_id"] for row in supported_rules])}
        trace = [{"step": 1, "action": mode, "selected_kc_ids": sorted(row["kc_id"] for row in policy["rules"]), "generated_text_read": False}]
        objective = None
    elif mode == "development_frozen_full_cell":
        policy = development_frozen_full_cell_policy(partition["development_cells"])
        trace = [{"step": 1, "action": mode, "selected_kc_ids": sorted(row["kc_id"] for row in policy["rules"])}]
        objective = None
    else:
        raise ValueError(f"unknown KC selection mode: {mode}")
    write_json(output / "fold_manifest.json", manifest)
    write_jsonl(output / "cell_splits.jsonl", split_rows, sort_keys=False)
    write_jsonl(output / "candidates.jsonl", discovery["candidates"], sort_keys=False)
    write_jsonl(output / "activations.jsonl", discovery["activations"], sort_keys=False)
    write_jsonl(output / "diagnostics.jsonl", discovery["diagnostics"], sort_keys=False)
    write_jsonl(output / "selection_trace.jsonl", trace, sort_keys=False)
    write_json(output / "selected_policy.json", policy)
    frozen = read_json(output / "selected_policy.json")
    evaluation = evaluate_after_freeze(
        frozen,
        opportunities,
        partition["split_by_id"],
        partition["development_cell_ids"],
        discovery["obligation_policy"],
    )
    evaluation["development_selection_objective"] = objective
    evaluation["unidentifiable_equivalence_classes"] = [
        row for row in discovery["equivalence_classes"] if row["unidentifiable_from_development"]
    ]
    write_json(output / "evaluation.json", evaluation)
    if evaluation["split_audit"]["status"] != "PASS":
        raise RuntimeError("fold semantic audit failed after policy freeze")
    return {
        "mode": mode,
        "development_cells": len(partition["development_cell_ids"]),
        "development_opportunities": len(partition["development_opportunities"]),
        "candidates": len(discovery["candidates"]),
        "selected_kcs": len(policy["rules"]),
        "selected_policy_fingerprint": evaluation["selected_policy_fingerprint"],
    }
