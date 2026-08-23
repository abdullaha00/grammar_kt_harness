"""Development-only structural KC selection followed by frozen holdout evaluation."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .io import read_json, read_jsonl, repo_path, stable_id, write_json, write_jsonl
from .folds import annotate_items, fold_path, fold_rows, load_fold
from .kc import apply_policy, evaluate_rule, load_policy, project_items
from .kc_candidates import (
    discover_candidates,
    load_obligation_policy,
    nuisance_opportunities,
    salient_facts,
)
from .realisation import LEXICON
from .records import DIMENSIONS


HOLDOUT_SPLITS = {"compositional_holdout", "novel_feature_holdout"}


# Split boundary

def partition_inputs(
    cells: list[dict[str, Any]],
    realisations: list[dict[str, Any]],
    split_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Partition by IDs before any held-out cell content enters discovery."""

    split_by_id = {row["canonical_cell_id"]: row["split"] for row in split_rows}
    cell_ids = {row["canonical_cell_id"] for row in cells}
    if set(split_by_id) != cell_ids:
        raise RuntimeError(
            "KC-selection split rows must exactly cover canonical cells: "
            f"missing={sorted(cell_ids - set(split_by_id))}, unknown={sorted(set(split_by_id) - cell_ids)}"
        )
    unknown_splits = sorted(set(split_by_id.values()) - {"development", *HOLDOUT_SPLITS})
    if unknown_splits:
        raise ValueError(f"unknown KC-selection split labels: {unknown_splits}")

    development_ids = {cell_id for cell_id, split in split_by_id.items() if split == "development"}
    if not development_ids:
        raise RuntimeError("KC selection requires at least one development cell")
    development_cells = [row for row in cells if row["canonical_cell_id"] in development_ids]
    development_realisations = [
        row for row in realisations if row["spec"]["canonical_cell_id"] in development_ids
    ]
    if {row["canonical_cell_id"] for row in development_cells} != development_ids:
        raise RuntimeError("development split lost one or more canonical cells")
    return {
        "split_by_id": split_by_id,
        "development_cell_ids": sorted(development_ids),
        "development_cells": sorted(development_cells, key=lambda row: row["canonical_cell_id"]),
        "development_realisations": sorted(
            development_realisations, key=lambda row: row["spec"]["realization_id"]
        ),
        "compositional_holdout_cell_ids": sorted(
            cell_id for cell_id, split in split_by_id.items() if split == "compositional_holdout"
        ),
        "novel_feature_holdout_cell_ids": sorted(
            cell_id for cell_id, split in split_by_id.items() if split == "novel_feature_holdout"
        ),
    }


# Obligations and deterministic selection

def build_obligations(discovery: dict[str, Any]) -> list[dict[str, Any]]:
    obligations: list[dict[str, Any]] = []
    for cell_id, facts in sorted(discovery["development_cell_facts"].items()):
        obligations.append(
            {"obligation_id": f"CELL|{cell_id}", "kind": "cell", "canonical_cell_id": cell_id}
        )
        for fact in facts:
            obligations.append(
                {
                    "obligation_id": f"FACT|{cell_id}|{fact}",
                    "kind": "fact",
                    "canonical_cell_id": cell_id,
                    "fact": fact,
                }
            )
    for contrast in discovery["minimal_contrasts"]:
        obligations.append(
            {
                "obligation_id": f"CONTRAST|{contrast['contrast_id']}",
                "kind": "contrast",
                **contrast,
            }
        )
    return obligations


def _selection_inputs(discovery: dict[str, Any]) -> dict[str, Any]:
    candidates = {row["candidate_id"]: row for row in discovery["candidates"]}
    diagnostics = {row["candidate_id"]: row for row in discovery["diagnostics"]}
    activation = {
        (row["candidate_id"], row["canonical_cell_id"]): row["activated"]
        for row in discovery["activations"]
    }
    classes = {
        row["equivalence_class_id"]: row for row in discovery["equivalence_classes"]
    }
    representative = {
        member: row["representative_candidate_id"]
        for row in classes.values()
        for member in row["member_candidate_ids"]
    }
    return {
        "candidates": candidates,
        "diagnostics": diagnostics,
        "activation": activation,
        "representative": representative,
    }


def select_inventory(discovery: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Greedily cover explicit obligations, then remove every unnecessary KC."""

    inputs = _selection_inputs(discovery)
    candidates = inputs["candidates"]
    diagnostics = inputs["diagnostics"]
    activation = inputs["activation"]
    representative = inputs["representative"]
    obligations = build_obligations(discovery)
    obligation_by_id = {row["obligation_id"]: row for row in obligations}
    eligible_ids = sorted(
        candidate_id
        for candidate_id, diagnostic in diagnostics.items()
        if diagnostic["selection_eligible"]
    )

    covered_by: dict[str, set[str]] = {candidate_id: set() for candidate_id in eligible_ids}
    for candidate_id in eligible_ids:
        candidate = candidates[candidate_id]
        for obligation in obligations:
            kind = obligation["kind"]
            if kind == "cell":
                if activation[(candidate_id, obligation["canonical_cell_id"])] is True:
                    covered_by[candidate_id].add(obligation["obligation_id"])
            elif kind == "fact":
                if (
                    activation[(candidate_id, obligation["canonical_cell_id"])] is True
                    and obligation["fact"] in candidate["represents"]
                ):
                    covered_by[candidate_id].add(obligation["obligation_id"])
            elif kind == "contrast":
                if (
                    candidate["interaction_order"] == 1
                    and obligation["changed_dimension"] in candidate["canonical_dimensions"]
                    and len(candidate["canonical_dimensions"]) == 1
                    and activation[(candidate_id, obligation["left_cell_id"])]
                    != activation[(candidate_id, obligation["right_cell_id"])]
                ):
                    covered_by[candidate_id].add(obligation["obligation_id"])

    coverable = set().union(*(covered_by.values())) if covered_by else set()
    missing = sorted(set(obligation_by_id) - coverable)
    if missing:
        raise RuntimeError(f"candidate pool cannot satisfy development obligations: {missing}")

    def closure(candidate_id: str) -> set[str]:
        result = {candidate_id}
        pending = [candidate_id]
        while pending:
            current = candidates[pending.pop()]
            for parent_id in current["requires_selected_ids"]:
                parent = representative[parent_id]
                if parent not in eligible_ids:
                    raise RuntimeError(
                        f"eligible interaction {current['kc_id']} lacks eligible parent {candidates[parent_id]['kc_id']}"
                    )
                if parent not in result:
                    result.add(parent)
                    pending.append(parent)
        return result

    def normalized_requirements(candidate_id: str) -> set[str]:
        return {
            representative[parent_id]
            for parent_id in candidates[candidate_id]["requires_selected_ids"]
        }

    def obligations_covered(selected: set[str]) -> set[str]:
        return set().union(*(covered_by[candidate_id] for candidate_id in selected)) if selected else set()

    selected: list[str] = []
    selected_set: set[str] = set()
    remaining = set(obligation_by_id)
    trace: list[dict[str, Any]] = []
    step = 0
    while remaining:
        choices = []
        for candidate_id in eligible_ids:
            bundle = closure(candidate_id) - selected_set
            if not bundle:
                continue
            new_obligations = set().union(*(covered_by[value] for value in bundle)) & remaining
            if not new_obligations:
                continue
            kinds = {kind: 0 for kind in ("fact", "contrast", "cell")}
            for obligation_id in new_obligations:
                kinds[obligation_by_id[obligation_id]["kind"]] += 1
            complexity = sum(candidates[value]["rule_complexity"] for value in bundle)
            interactions = sum(candidates[value]["interaction_order"] > 1 for value in bundle)
            activations = sum(diagnostics[value]["development_cell_support"] for value in bundle)
            support = min(
                min(
                    diagnostics[value]["development_cell_support"],
                    diagnostics[value]["development_source_descriptor_support"],
                )
                for value in bundle
            )
            rank = (
                -len(new_obligations),
                len(bundle),
                complexity,
                activations,
                interactions,
                -support,
                candidates[candidate_id]["kc_id"],
            )
            choices.append((rank, candidate_id, bundle, new_obligations, kinds))
        if not choices:
            raise RuntimeError(f"selector stalled with uncovered obligations: {sorted(remaining)}")
        _rank, chosen, bundle, newly_covered, kinds = sorted(choices, key=lambda row: row[0])[0]
        ordered_bundle = sorted(bundle, key=lambda value: (candidates[value]["interaction_order"], candidates[value]["kc_id"]))
        for candidate_id in ordered_bundle:
            if candidate_id not in selected_set:
                selected.append(candidate_id)
                selected_set.add(candidate_id)
        remaining -= newly_covered
        step += 1
        trace.append(
            {
                "step": step,
                "action": "selected",
                "candidate_id": chosen,
                "kc_id": candidates[chosen]["kc_id"],
                "added_candidate_ids": ordered_bundle,
                "new_obligation_ids": sorted(newly_covered),
                "new_obligation_counts": kinds,
                "remaining_obligations": len(remaining),
                "reason": "best deterministic lexicographic marginal obligation coverage",
            }
        )

    # Backward deletion makes the result inclusion-minimal, not globally cardinality-optimal.
    for candidate_id in list(reversed(selected)):
        proposed = selected_set - {candidate_id}
        required_by = [
            current for current in proposed if candidate_id in normalized_requirements(current)
        ]
        if required_by:
            continue
        if obligations_covered(proposed) == set(obligation_by_id):
            selected_set = proposed
            selected.remove(candidate_id)
            step += 1
            trace.append(
                {
                    "step": step,
                    "action": "pruned",
                    "candidate_id": candidate_id,
                    "kc_id": candidates[candidate_id]["kc_id"],
                    "remaining_obligations": 0,
                    "reason": "all development obligations remain covered without this candidate",
                }
            )

    for candidate_id in sorted(candidates):
        if candidate_id in selected_set:
            status, reason = "selected", "retained after backward pruning"
        elif not diagnostics[candidate_id]["selection_eligible"]:
            status = "ineligible"
            reason = "; ".join(diagnostics[candidate_id]["rejection_reasons"]) or "not selection-eligible"
        elif covered_by.get(candidate_id):
            status, reason = "not_selected", "obligations were covered by a lexicographically preferred candidate"
        else:
            status, reason = "not_selected", "candidate introduced no Phase-A structural obligation"
        diagnostics[candidate_id]["selection_status"] = status
        diagnostics[candidate_id]["selection_reason"] = reason
        if candidate_id not in selected_set:
            step += 1
            trace.append(
                {
                    "step": step,
                    "action": status,
                    "candidate_id": candidate_id,
                    "kc_id": candidates[candidate_id]["kc_id"],
                    "reason": reason,
                }
            )

    selected_rows = [candidates[candidate_id] for candidate_id in sorted(selected_set, key=lambda value: candidates[value]["kc_id"])]
    objective = {
        "feasible": obligations_covered(selected_set) == set(obligation_by_id),
        "kc_count": len(selected_rows),
        "rule_complexity": sum(row["rule_complexity"] for row in selected_rows),
        "development_activation_entries": sum(
            diagnostics[row["candidate_id"]]["development_cell_support"] for row in selected_rows
        ),
        "interaction_count": sum(row["interaction_order"] > 1 for row in selected_rows),
        "minimum_cell_support": min(
            (diagnostics[row["candidate_id"]]["development_cell_support"] for row in selected_rows), default=0
        ),
        "minimum_source_descriptor_support": min(
            (
                diagnostics[row["candidate_id"]]["development_source_descriptor_support"]
                for row in selected_rows
            ),
            default=0,
        ),
        "obligations": len(obligations),
    }
    objective["lexicographic_preference"] = [
        "feasibility",
        "fewer KCs",
        "lower rule complexity",
        "fewer development activation entries",
        "fewer interactions",
        "better minimum cell/source-descriptor support",
    ]
    objective["algorithm_guarantee"] = (
        "deterministic feasible and backward-pruned inclusion-minimal cover; not a global optimum certificate"
    )
    return {
        "selector": config.get("selector_id", "greedy_backward_v0"),
        "selected_candidates": selected_rows,
        "diagnostics": sorted(diagnostics.values(), key=lambda row: row["candidate_id"]),
        "obligations": obligations,
        "selection_trace": trace,
        "objective": objective,
    }


# Policy compilation

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
                "realization_dependencies": candidate["realization_dependencies"],
                "near_neighbours": candidate["near_neighbours"],
                "rationale": candidate["rationale"],
                "candidate_id": candidate["candidate_id"],
                "represents": candidate["represents"],
                "canonical_dimensions": candidate["canonical_dimensions"],
                "interaction_order": candidate["interaction_order"],
            }
        )
    policy_id = stable_id("POLICY", selection["selector"], rules, development_cell_ids)
    return {
        "policy_id": policy_id,
        "kind": "rules",
        "description": "Development-only deterministic structural KC selection.",
        "selection_metadata": {
            "selector": selection["selector"],
            "baseline_category": "inductive",
            "development_cell_ids": development_cell_ids,
            "held_out_content_used": False,
            "objective": selection["objective"],
        },
        "rules": rules,
    }


def compile_predefined_policy(path: Path, development_cell_ids: list[str]) -> dict[str, Any]:
    loaded = load_policy(path)
    if loaded["kind"] == "full_cell":
        return {
            **loaded,
            "selection_metadata": {
                "selector": "predefined_transductive_baseline",
                "baseline_category": "transductive",
                "development_cell_ids": development_cell_ids,
                "held_out_content_used": "dynamic full-cell rules are created at application time",
            },
        }
    return {
        "policy_id": loaded["policy_id"],
        "kind": "rules",
        "description": loaded.get("description", "Predefined expert baseline."),
        "selection_metadata": {
            "selector": "predefined_expert_baseline",
            "baseline_category": "expert_prior",
            "development_cell_ids": development_cell_ids,
            "held_out_content_used": False,
            "source_policy": str(path),
        },
        "rules": loaded["rules"],
    }


def development_frozen_full_cell_policy(
    development_cells: list[dict[str, Any]],
    obligation_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rules = []
    for row in sorted(development_cells, key=lambda value: value["canonical_cell_id"]):
        suffix = row["canonical_cell_id"].removeprefix("CELL_")
        rules.append(
            {
                "kc_id": f"KC_FULL_DEV_{suffix}",
                "name": f"development-frozen full cell {suffix}",
                "definition": "Exact development-cell memorisation baseline.",
                "activation_rule": {"cell": row["cell"]},
                "required_conditions": [f"{key}={value}" for key, value in row["cell"].items()],
                "includes": [row["canonical_cell_id"]],
                "excludes": ["all non-identical cells"],
                "realization_dependencies": [],
                "near_neighbours": [],
                "rationale": "Honest full-cell baseline frozen before held-out application.",
                "represents": salient_facts(row["cell"], obligation_policy),
                "canonical_dimensions": list(DIMENSIONS),
                "interaction_order": 1,
            }
        )
    return {
        "policy_id": stable_id("POLICY", "FULL_CELL_DEV_FROZEN_v0", rules),
        "kind": "rules",
        "description": "Exact-cell baseline compiled from development cells only.",
        "selection_metadata": {
            "selector": "development_frozen_full_cell",
            "baseline_category": "inductive",
            "development_cell_ids": sorted(
                row["canonical_cell_id"] for row in development_cells
            ),
            "held_out_content_used": False,
        },
        "rules": rules,
    }


def development_frozen_factorized_policy(
    policy_path: Path,
    development_cells: list[dict[str, Any]],
    development_items: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Retain expert factor rules supported by development item opportunities only."""

    loaded = load_policy(policy_path)
    if loaded["kind"] != "rules":
        raise ValueError("FACTORIZED_DEV_FROZEN requires a rule policy")
    development_cell_ids = {
        row["canonical_cell_id"] for row in development_cells
    }
    if any(
        item["canonical_split"] != "development"
        or item["canonical_cell_id"] not in development_cell_ids
        for item in development_items
    ):
        raise RuntimeError("development-frozen factorized policy received held-out items")
    projections, _cards = project_items(development_items, development_cells, loaded)
    item_support = Counter(
        kc_id for row in projections for kc_id in row["kc_ids"]
    )
    cell_support: dict[str, set[str]] = defaultdict(set)
    for row in projections:
        for kc_id in row["kc_ids"]:
            cell_support[kc_id].add(row["canonical_cell_id"])
    kept_rules = [
        rule for rule in loaded["rules"] if item_support[rule["kc_id"]] > 0
    ]
    rejected = [
        rule["kc_id"] for rule in loaded["rules"] if item_support[rule["kc_id"]] == 0
    ]
    support = {
        rule["kc_id"]: {
            "development_item_support": item_support[rule["kc_id"]],
            "development_cell_support": len(cell_support[rule["kc_id"]]),
        }
        for rule in kept_rules
    }
    policy = {
        "policy_id": stable_id(
            "POLICY", "FACTORIZED_DEV_FROZEN_v0", kept_rules, sorted(development_cell_ids)
        ),
        "kind": "rules",
        "description": (
            "Expert factorization hypothesis with rules frozen by development-item support."
        ),
        "selection_metadata": {
            "selector": "development_frozen_factorized",
            "baseline_category": "inductive",
            "source_policy": str(policy_path),
            "development_cell_ids": sorted(development_cell_ids),
            "development_item_count": len(development_items),
            "held_out_content_used": False,
            "rule_support": support,
            "rejected_zero_development_support_kc_ids": sorted(rejected),
        },
        "rules": kept_rules,
    }
    return policy, support


# Post-freeze evaluation

def _opportunities_by_cell(
    cells: list[dict[str, Any]],
    realisations: list[dict[str, Any]],
    frames: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    observed: dict[str, dict[str, Any]] = {}
    for row in sorted(realisations, key=lambda value: value["spec"]["realization_id"]):
        observed.setdefault(row["spec"]["canonical_cell_id"], row)
    result = {}
    for cell_row in cells:
        cell_id = cell_row["canonical_cell_id"]
        if cell_id in observed:
            row = observed[cell_id]
            operations = row["derivation"]["operations"]
            spec = row["spec"]
        else:
            nuisance = nuisance_opportunities(cell_row, frames)[0]
            operations = nuisance["realization_operations"]
            spec = nuisance["realization_spec"]
        result[cell_id] = {
            "canonical_cell_id": cell_id,
            "cell": cell_row["cell"],
            "realization_spec": spec,
            "realization_operations": operations,
        }
    return result


def _rule_metadata(policy: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    metadata = {
        row["kc_id"]: {
            "represents": row["represents"],
            "dimensions": row["canonical_dimensions"],
            "interaction_order": row["interaction_order"],
        }
        for row in candidates
    }
    for rule in policy.get("rules", []):
        metadata.setdefault(
            rule["kc_id"],
            {
                "represents": rule.get("represents", []),
                "dimensions": rule.get("canonical_dimensions", []),
                "interaction_order": rule.get("interaction_order", 1),
            },
        )
    return metadata


def evaluate_policy(
    policy: dict[str, Any],
    *,
    label: str,
    cells: list[dict[str, Any]],
    split_by_id: dict[str, str],
    opportunities: dict[str, dict[str, Any]],
    candidate_metadata: list[dict[str, Any]],
    obligation_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    by_id = {row["canonical_cell_id"]: row for row in cells}
    metadata = _rule_metadata(policy, candidate_metadata)
    projection = {
        cell_id: apply_policy(policy, opportunities[cell_id])["activated_kcs"]
        for cell_id in sorted(by_id)
    }
    if policy["kind"] == "full_cell":
        for cell_id in projection:
            for kc_id in projection[cell_id]:
                metadata[kc_id] = {
                    "represents": salient_facts(by_id[cell_id]["cell"], obligation_policy),
                    "dimensions": list(DIMENSIONS),
                    "interaction_order": 1,
                }

    development_ids = sorted(cell_id for cell_id, split in split_by_id.items() if split == "development")
    development_kcs = {kc_id for cell_id in development_ids for kc_id in projection[cell_id]}

    def summarize(split_name: str) -> dict[str, Any]:
        ids = sorted(cell_id for cell_id, split in split_by_id.items() if split == split_name)
        rows = []
        fact_total = 0
        fact_covered = 0
        reused_assignments = 0
        active_assignments = 0
        for cell_id in ids:
            facts = salient_facts(by_id[cell_id]["cell"], obligation_policy)
            active = projection[cell_id]
            represented = sorted({fact for kc_id in active for fact in metadata.get(kc_id, {}).get("represents", [])})
            covered = sorted(set(facts) & set(represented))
            fact_total += len(facts)
            fact_covered += len(covered)
            active_assignments += len(active)
            reused_assignments += sum(kc_id in development_kcs for kc_id in active)
            rows.append(
                {
                    "canonical_cell_id": cell_id,
                    "active_kc_ids": active,
                    "salient_facts": facts,
                    "covered_facts": covered,
                    "uncovered_facts": sorted(set(facts) - set(covered)),
                    "covered": bool(active),
                    "only_development_reused_components": bool(active) and set(active) <= development_kcs,
                }
            )
        signatures = [tuple(row["active_kc_ids"]) for row in rows]
        contrasts = []
        target = set(ids)
        seen_pairs: set[tuple[str, str]] = set()
        for cell_id in ids:
            for other_id in sorted(set(development_ids) | target):
                if other_id == cell_id:
                    continue
                pair = tuple(sorted((cell_id, other_id)))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                changed = [dimension for dimension in DIMENSIONS if by_id[cell_id]["cell"][dimension] != by_id[other_id]["cell"][dimension]]
                if len(changed) != 1:
                    continue
                dimension = changed[0]
                left, right = set(projection[cell_id]), set(projection[other_id])
                witnesses = sorted(
                    kc_id
                    for kc_id in left ^ right
                    if dimension in metadata.get(kc_id, {}).get("dimensions", [])
                    and metadata.get(kc_id, {}).get("interaction_order", 1) == 1
                    and len(metadata.get(kc_id, {}).get("dimensions", [])) == 1
                )
                contrasts.append(
                    {
                        "left_cell_id": cell_id,
                        "right_cell_id": other_id,
                        "changed_dimension": dimension,
                        "signature_preserved": left != right,
                        "dimension_aligned_witness_kc_ids": witnesses,
                    }
                )
        return {
            "cells": len(ids),
            "covered_cells": sum(row["covered"] for row in rows),
            "coverage": sum(row["covered"] for row in rows) / len(rows) if rows else None,
            "fact_recall": fact_covered / fact_total if fact_total else 1.0,
            "component_reuse": reused_assignments / active_assignments if active_assignments else None,
            "cells_with_only_reused_components": sum(row["only_development_reused_components"] for row in rows),
            "unique_signature_rate": len(set(signatures)) / len(signatures) if signatures else None,
            "minimal_contrasts": len(contrasts),
            "signature_contrast_preservation": (
                sum(row["signature_preserved"] for row in contrasts) / len(contrasts) if contrasts else None
            ),
            "dimension_witness_preservation": (
                sum(bool(row["dimension_aligned_witness_kc_ids"]) for row in contrasts) / len(contrasts)
                if contrasts else None
            ),
            "cell_results": rows,
            "contrast_results": contrasts,
        }

    full_cell_rules = (
        len(cells)
        if policy["kind"] == "full_cell"
        else sum(
            set(rule.get("activation_rule", {}).get("cell", {})) == set(DIMENSIONS)
            for rule in policy.get("rules", [])
        )
    )
    return {
        "label": label,
        "policy_id": policy["policy_id"],
        "development": summarize("development"),
        "compositional_holdout": summarize("compositional_holdout"),
        "novel_feature_holdout": summarize("novel_feature_holdout"),
        "full_cell_rule_count": full_cell_rules,
        "absence_of_full_cell_memorisation": full_cell_rules == 0,
    }


def evaluate_after_freeze(
    selected_policy: dict[str, Any],
    *,
    cells: list[dict[str, Any]],
    realisations: list[dict[str, Any]],
    partition: dict[str, Any],
    discovery: dict[str, Any],
    frames: dict[str, dict[str, Any]],
    config: dict[str, Any],
    mode: str,
) -> dict[str, Any]:
    opportunities = _opportunities_by_cell(cells, realisations, frames)
    split_by_id = partition["split_by_id"]
    obligation_policy = load_obligation_policy(config.get("obligation_policy"))
    selected = evaluate_policy(
        selected_policy,
        label={
            "structural": "SELECTED_STRUCTURAL",
            "development_frozen_factorized": "FACTORIZED_DEV_FROZEN",
            "development_frozen_full_cell": "FULL_CELL_DEV_FROZEN",
        }.get(mode, "SELECTED_PREDEFINED_BASELINE"),
        cells=cells,
        split_by_id=split_by_id,
        opportunities=opportunities,
        candidate_metadata=discovery["candidates"],
        obligation_policy=obligation_policy,
    )
    baselines = []
    for baseline in config.get("baseline_policies", []):
        policy = load_policy(repo_path(baseline["policy"]))
        baselines.append(
            evaluate_policy(
                policy,
                label=baseline["label"],
                cells=cells,
                split_by_id=split_by_id,
                opportunities=opportunities,
                candidate_metadata=discovery["candidates"],
                obligation_policy=obligation_policy,
            )
        )
    frozen_full = development_frozen_full_cell_policy(
        partition["development_cells"], obligation_policy
    )
    baselines.append(
        evaluate_policy(
            frozen_full,
            label="FULL_CELL_DEV_FROZEN",
            cells=cells,
            split_by_id=split_by_id,
            opportunities=opportunities,
            candidate_metadata=discovery["candidates"],
            obligation_policy=obligation_policy,
        )
    )

    # Development-equivalent candidates may separate on holdout. This is
    # reported only after the selected policy has been frozen and never feeds
    # back into representative choice or ontology selection.
    candidate_by_id = {row["candidate_id"]: row for row in discovery["candidates"]}
    post_freeze_equivalence_diagnostics = []
    for equivalence in discovery["equivalence_classes"]:
        if not equivalence["unidentifiable_from_development"]:
            continue
        scope_results = {}
        for split_name in sorted(HOLDOUT_SPLITS):
            cell_ids = sorted(
                cell_id for cell_id, split in split_by_id.items() if split == split_name
            )
            activations_by_kc = {}
            for candidate_id in equivalence["member_candidate_ids"]:
                candidate = candidate_by_id[candidate_id]
                activations_by_kc[candidate["kc_id"]] = [
                    evaluate_rule(candidate["activation_rule"], opportunities[cell_id])[0]
                    for cell_id in cell_ids
                ]
            separating_cell_ids = [
                cell_id
                for index, cell_id in enumerate(cell_ids)
                if len({values[index] for values in activations_by_kc.values()}) > 1
            ]
            scope_results[split_name] = {
                "cell_ids": cell_ids,
                "activations_by_kc": activations_by_kc,
                "remains_activation_equivalent": not separating_cell_ids,
                "separating_cell_ids": separating_cell_ids,
            }
        post_freeze_equivalence_diagnostics.append(
            {
                "equivalence_class_id": equivalence["equivalence_class_id"],
                "member_kc_ids": equivalence["member_kc_ids"],
                "development_conclusion": "unidentifiable: identical activation columns",
                "holdout_results_are_evaluation_only": True,
                "holdout": scope_results,
            }
        )

    development_fact_vocabulary = {
        fact
        for row in partition["development_cells"]
        for fact in salient_facts(row["cell"], obligation_policy)
    }
    by_id = {row["canonical_cell_id"]: row for row in cells}
    split_audit: dict[str, Any] = {}
    split_mismatches: list[dict[str, Any]] = []
    for label, ids in (
        ("compositional_holdout", partition["compositional_holdout_cell_ids"]),
        ("novel_feature_holdout", partition["novel_feature_holdout_cell_ids"]),
    ):
        rows = []
        for cell_id in ids:
            facts = salient_facts(by_id[cell_id]["cell"], obligation_policy)
            rows.append(
                {
                    "canonical_cell_id": cell_id,
                    "unseen_salient_facts": sorted(set(facts) - development_fact_vocabulary),
                    "classification_matches_definition": (
                        not (set(facts) - development_fact_vocabulary)
                        if label == "compositional_holdout"
                        else bool(set(facts) - development_fact_vocabulary)
                    ),
                }
            )
        mismatches = [row for row in rows if not row["classification_matches_definition"]]
        split_mismatches.extend({"declared_split": label, **row} for row in mismatches)
        split_audit[label] = {
            "definition": (
                "every salient fact occurred in development; only the combination is held out"
                if label == "compositional_holdout"
                else "at least one salient fact did not occur in development"
            ),
            "cells": rows,
            "misclassified_cell_ids": [row["canonical_cell_id"] for row in mismatches],
        }
    split_audit["status"] = "PASS" if not split_mismatches else "FAIL"
    split_audit["mismatches"] = split_mismatches

    serialized_policy = json.dumps(selected_policy, sort_keys=True)
    holdout_ids = partition["compositional_holdout_cell_ids"] + partition["novel_feature_holdout_cell_ids"]
    return {
        "selected_policy_fingerprint": stable_id("FROZEN", selected_policy),
        "selected_policy_written_before_holdout_evaluation": True,
        "selection_data_partition": "development",
        "held_out_cell_ids_referenced_by_selected_policy": [cell_id for cell_id in holdout_ids if cell_id in serialized_policy],
        "split_audit": split_audit,
        "selected_ontology": selected,
        "baselines": baselines,
        "post_freeze_equivalence_diagnostics": post_freeze_equivalence_diagnostics,
        "claim_boundary": "Phase-A structural and compositional diagnostics only; item-bank, simulation, Q-matrix, and KT artifacts do not influence selection.",
    }


# Fixture and run entry points

def evaluate_fixture(fixture: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    frames = {row["predicate_frame_id"]: row for row in read_jsonl(LEXICON)}
    cells = fixture["canonical_cells"]
    realisations = fixture.get("realisations", [])
    partition = partition_inputs(cells, realisations, fixture["cell_splits"])
    discovery = discover_candidates(
        partition["development_cells"], partition["development_realisations"], frames, config
    )
    selection = select_inventory(discovery, config)
    policy = compile_policy(selection, partition["development_cell_ids"])
    evaluation = evaluate_after_freeze(
        policy, cells=cells, realisations=realisations, partition=partition,
        discovery=discovery, frames=frames, config=config, mode="structural",
    )
    return {
        "selected_kc_ids": [row["kc_id"] for row in selection["selected_candidates"]],
        "objective": selection["objective"],
        "equivalence_classes": [
            row for row in discovery["equivalence_classes"] if row["unidentifiable_from_development"]
        ],
        "selected_policy": policy,
        "evaluation": evaluation,
    }


def run(run_dir: Path, settings: dict[str, Any]) -> dict[str, Any]:
    output = run_dir / "kc_selection"
    output.mkdir(parents=True, exist_ok=False)
    config = read_json(repo_path(settings["config"]))
    mode = settings.get("mode", "structural")
    if mode not in {
        "structural",
        "predefined",
        "development_frozen_factorized",
        "development_frozen_full_cell",
    }:
        raise ValueError(f"unknown KC-selection mode: {mode}")

    cells = read_jsonl(run_dir / "canonical" / "canonical_cells.jsonl")
    realisations = read_jsonl(run_dir / "realisation" / "realisations.jsonl")
    manifest = load_fold(fold_path(settings))
    split_rows = fold_rows(cells, manifest)
    frames = {
        row["predicate_frame_id"]: row
        for row in read_jsonl(settings.get("lexicon", LEXICON))
    }
    partition = partition_inputs(cells, realisations, split_rows)

    # Candidate generation and every selection decision receive development rows only.
    discovery = discover_candidates(
        partition["development_cells"], partition["development_realisations"], frames, config
    )
    if mode == "structural":
        structural_selection = select_inventory(discovery, config)
        policy = compile_policy(structural_selection, partition["development_cell_ids"])
        diagnostics = structural_selection["diagnostics"]
        trace = structural_selection["selection_trace"]
        objective = structural_selection["objective"]
    elif mode == "predefined":
        policy_path = repo_path(settings["policy"])
        policy = compile_predefined_policy(policy_path, partition["development_cell_ids"])
        selected_kcs = {rule["kc_id"] for rule in policy.get("rules", [])}
        diagnostics = discovery["diagnostics"]
        for row in diagnostics:
            row["selection_status"] = "selected_predefined" if row["kc_id"] in selected_kcs else "not_selected_predefined"
            row["selection_reason"] = "declared expert baseline policy" if row["kc_id"] in selected_kcs else "absent from declared expert baseline policy"
        trace = [
            {
                "step": 1,
                "action": "predefined_policy",
                "policy": str(policy_path),
                "selected_kc_ids": sorted(selected_kcs),
                "reason": "explicit expert/transductive baseline; not data-selected",
            }
        ]
        objective = None
    elif mode == "development_frozen_factorized":
        all_items = read_jsonl(run_dir / "items" / "validation" / "accepted_items.jsonl")
        all_items = annotate_items(all_items, partition["split_by_id"])
        # Split labels and IDs establish the boundary before rule activation sees item content.
        development_items = [
            row
            for row in all_items
            if row["canonical_split"] == "development"
            and row["canonical_cell_id"] in set(partition["development_cell_ids"])
        ]
        policy_path = repo_path(settings["policy"])
        policy, development_rule_support = development_frozen_factorized_policy(
            policy_path, partition["development_cells"], development_items
        )
        selected_kcs = {rule["kc_id"] for rule in policy["rules"]}
        diagnostics = discovery["diagnostics"]
        for row in diagnostics:
            row["selection_status"] = (
                "selected_development_supported_expert_rule"
                if row["kc_id"] in selected_kcs
                else "not_selected_development_frozen_expert_rule"
            )
            row["selection_reason"] = (
                "expert factor rule has development-item support"
                if row["kc_id"] in selected_kcs
                else "rule absent from the expert factor policy or has zero development support"
            )
        trace = [
            {
                "step": 1,
                "action": "development_frozen_factorized_policy",
                "source_policy": str(policy_path),
                "development_item_count": len(development_items),
                "selected_kc_ids": sorted(selected_kcs),
                "development_rule_support": development_rule_support,
                "rejected_zero_support_kc_ids": policy["selection_metadata"][
                    "rejected_zero_development_support_kc_ids"
                ],
                "reason": (
                    "expert rules were retained solely when activated by a development item; "
                    "the policy was then frozen before holdout application"
                ),
            }
        ]
        objective = None
    else:
        policy = development_frozen_full_cell_policy(
            partition["development_cells"], discovery["obligation_policy"]
        )
        diagnostics = discovery["diagnostics"]
        for row in diagnostics:
            row["selection_status"] = "not_selected_full_cell_control"
            row["selection_reason"] = "development-frozen full-cell control does not select structural candidates"
        trace = [
            {
                "step": 1,
                "action": "development_frozen_full_cell_policy",
                "selected_kc_ids": sorted(rule["kc_id"] for rule in policy["rules"]),
                "reason": "exact rules were compiled from development cells only before holdout application",
            }
        ]
        objective = None

    write_jsonl(output / "candidates.jsonl", discovery["candidates"])
    write_json(output / "fold_manifest.json", manifest)
    write_jsonl(output / "cell_splits.jsonl", split_rows)
    write_jsonl(output / "activations.jsonl", discovery["activations"])
    write_jsonl(output / "diagnostics.jsonl", diagnostics)
    write_jsonl(output / "selection_trace.jsonl", trace)
    write_json(output / "selected_policy.json", policy)

    # The file is now frozen. Only this subsequent pass may inspect held-out cell content.
    frozen_policy = read_json(output / "selected_policy.json")
    evaluation = evaluate_after_freeze(
        frozen_policy, cells=cells, realisations=realisations, partition=partition,
        discovery=discovery, frames=frames, config=config, mode=mode,
    )
    evaluation["development_selection_objective"] = objective
    evaluation["development_minimal_contrasts"] = len(discovery["minimal_contrasts"])
    evaluation["unidentifiable_equivalence_classes"] = [
        row for row in discovery["equivalence_classes"] if row["unidentifiable_from_development"]
    ]
    evaluation["unidentifiable_granularity_alternatives"] = [
        {
            "equivalence_class_id": row["equivalence_class_id"],
            "alternatives": row["unidentifiable_granularity_alternatives"],
        }
        for row in discovery["equivalence_classes"]
        if row["unidentifiable_granularity_alternatives"]
    ]
    write_json(output / "evaluation.json", evaluation)
    if evaluation["split_audit"]["status"] != "PASS":
        raise RuntimeError(
            "KC-selection holdout split audit failed after policy freeze: "
            f"{evaluation['split_audit']['mismatches']}"
        )
    return {
        "mode": mode,
        "development_cells": len(partition["development_cell_ids"]),
        "compositional_holdout_cells": len(partition["compositional_holdout_cell_ids"]),
        "novel_feature_holdout_cells": len(partition["novel_feature_holdout_cell_ids"]),
        "candidates": len(discovery["candidates"]),
        "selection_kcs": len(policy.get("rules", [])) if policy["kind"] != "full_cell" else "dynamic_full_cell_baseline",
        "unidentifiable_equivalence_classes": sum(
            row["unidentifiable_from_development"] for row in discovery["equivalence_classes"]
        ),
        "unidentifiable_granularity_groups": sum(
            len(row["unidentifiable_granularity_alternatives"])
            for row in discovery["equivalence_classes"]
        ),
    }
