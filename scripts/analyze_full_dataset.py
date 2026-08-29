#!/usr/bin/env python3
"""Create paper-facing tables from the finalized medium grammar-KT dataset.

This script is deliberately a read-only scientific post-processor.  It makes
no model calls, does not resimulate learner evidence, and never rewrites the
dataset.  The one structural sensitivity recomputes the active outcome-free KC
candidate inventory with rank-1 versus all selected development items.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.io import read_jsonl, read_yaml, write_json
from grammar_kt.kc_candidates import make_kc_candidates
from grammar_kt.validate_items import select_item_bank


DEFAULT_DATASET = ROOT / "data/grammar_kt_medium_v1"
DEFAULT_OUTPUT = ROOT / "reports/phase6/artifacts/full_dataset_analysis"
SCHEMA_PATH = ROOT / "modules/grammar/canonical/schema.yaml"
OPERATIONS_PATH = ROOT / "modules/grammar/canonical/english_operations.yaml"
CANDIDATE_DESIGN_PATH = ROOT / "modules/kcs/candidate_design.yaml"
ITEM_DESIGN_PATH = ROOT / "modules/items/generation/design.yaml"
REGIMES = (
    "development",
    "compositional_holdout",
    "novel_feature_holdout",
)
COHORTS = ("default_n3", "conditional_rescue", "determinacy_intervention")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rate(numerator: int | float, denominator: int | float) -> float | None:
    return float(numerator / denominator) if denominator else None


def _median(values: Iterable[int | float]) -> float | None:
    rows = list(values)
    return float(statistics.median(rows)) if rows else None


def _json_cell(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple, set)):
        if isinstance(value, set):
            value = sorted(value)
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _json_cell(row.get(key)) for key in fields})


def _markdown_table(rows: list[dict[str, Any]], fields: list[str]) -> str:
    if not rows:
        return "_No retained rows._"

    def display(value: Any) -> str:
        if value is None:
            return "NA"
        if isinstance(value, float):
            return f"{value:.6f}"
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = [
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join("---" for _ in fields) + " |",
    ]
    lines.extend(
        "| " + " | ".join(display(row.get(field)) for field in fields) + " |"
        for row in rows
    )
    return "\n".join(lines)


def candidate_cohort(candidate: dict[str, Any]) -> str:
    """Classify immutable generation provenance, including future replays."""

    metadata = candidate.get("generation_metadata", {})
    provenance = metadata.get("provenance", {})
    index = int(metadata.get("candidate_index", 0))
    marker = " ".join(
        str(provenance.get(key, "")).casefold()
        for key in ("status", "protocol")
    )
    if "intervention" in marker or index in (6, 7):
        return "determinacy_intervention"
    if "rescue" in marker or index in (4, 5):
        return "conditional_rescue"
    return "default_n3"


def attempt_cohort(attempt: dict[str, Any]) -> str:
    provenance = attempt.get("provenance", {})
    index = int(attempt.get("candidate_index", 0))
    marker = " ".join(
        str(provenance.get(key, "")).casefold()
        for key in ("status", "protocol")
    )
    if "intervention" in marker or index in (6, 7):
        return "determinacy_intervention"
    if "rescue" in marker or index in (4, 5):
        return "conditional_rescue"
    return "default_n3"


def _token_summary(label: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    prompts = [row["prompt"].casefold().strip() for row in items]
    prompt_tokens = [re.findall(r"[a-z]+", prompt) for prompt in prompts]
    tokens = [token for row in prompt_tokens for token in row]
    distances = [
        float(row.get("selection_metadata", {}).get("token_set_distance_from_first", 0.0))
        for row in items
        if int(row.get("selection_metadata", {}).get("rank", 0)) == 2
    ]
    return {
        "material": label,
        "items": len(items),
        "unique_prompts": len(set(prompts)),
        "unique_prompt_rate": _rate(len(set(prompts)), len(prompts)),
        "prompt_lexical_tokens": len(tokens),
        "prompt_lexical_types": len(set(tokens)),
        "prompt_type_token_ratio": _rate(len(set(tokens)), len(tokens)),
        "median_prompt_tokens": _median(len(row) for row in prompt_tokens),
        "rank2_items": len(distances),
        "median_rank2_token_set_distance": _median(distances),
    }


def _feature_pairs(
    features: dict[str, str], dimensions: list[str]
) -> set[tuple[str, str, str, str]]:
    return {
        (left, features[left], right, features[right])
        for left, right in combinations(dimensions, 2)
    }


def _fold_tables(
    cells: list[dict[str, Any]],
    items: list[dict[str, Any]],
    fold: list[dict[str, Any]],
    dimensions: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    split_by_cell = {row["cell_id"]: row["grammar_split"] for row in fold}
    cells_by_split = {
        split: [row for row in cells if split_by_cell[row["cell_id"]] == split]
        for split in REGIMES
    }
    item_support = Counter(row["cell_id"] for row in items)
    development_values = {
        (dimension, cell["features"][dimension])
        for cell in cells_by_split["development"]
        for dimension in dimensions
    }
    development_pairs = set().union(
        *(
            _feature_pairs(cell["features"], dimensions)
            for cell in cells_by_split["development"]
        )
    ) if cells_by_split["development"] else set()
    rows = []
    unseen_values: dict[str, list[list[str]]] = {}
    for split in REGIMES:
        selected_cells = cells_by_split[split]
        supports = [item_support[row["cell_id"]] for row in selected_cells]
        values = {
            (dimension, cell["features"][dimension])
            for cell in selected_cells
            for dimension in dimensions
        }
        pairs = set().union(
            *(_feature_pairs(cell["features"], dimensions) for cell in selected_cells)
        ) if selected_cells else set()
        unseen = sorted(values - development_values)
        unseen_values[split] = [list(row) for row in unseen]
        rows.append(
            {
                "grammar_regime": split,
                "cells": len(selected_cells),
                "selected_items": sum(supports),
                "minimum_items_per_cell": min(supports) if supports else None,
                "median_items_per_cell": _median(supports),
                "maximum_items_per_cell": max(supports) if supports else None,
                "unique_feature_values": len(values),
                "unseen_development_feature_values": len(unseen),
                "unique_value_pairs": len(pairs),
                "value_pairs_seen_in_development": len(pairs & development_pairs),
                "value_pairs_unseen_in_development": len(pairs - development_pairs),
            }
        )
    return rows, {"unseen_development_values": unseen_values}


def _item_stage_rows(
    cells: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
    design: dict[str, Any],
) -> list[dict[str, Any]]:
    judgment_by_id = {row["item_id"]: row for row in judgments}
    candidate_by_id = {row["item_id"]: row for row in candidates}

    def stage(
        label: str,
        cohorts: set[str],
        *,
        maximum_default_index: int | None = None,
    ) -> dict[str, Any]:
        selected_attempts = [
            row
            for row in attempts
            if attempt_cohort(row) in cohorts
            and (
                maximum_default_index is None
                or attempt_cohort(row) != "default_n3"
                or int(row["candidate_index"]) <= maximum_default_index
            )
        ]
        selected_candidates = [
            row
            for row in candidates
            if candidate_cohort(row) in cohorts
            and (
                maximum_default_index is None
                or candidate_cohort(row) != "default_n3"
                or int(row["generation_metadata"]["candidate_index"])
                <= maximum_default_index
            )
        ]
        selected_ids = {row["item_id"] for row in selected_candidates}
        selected_judgments = [
            row for row in judgments if row["item_id"] in selected_ids
        ]
        accepted = [
            candidate_by_id[row["item_id"]]
            for row in selected_judgments
            if row.get("accepted") and row["item_id"] in candidate_by_id
        ]
        bank = select_item_bank(accepted, design) if accepted else []
        return {
            "stage": label,
            "cohorts_included": sorted(cohorts),
            "generation_attempts": len(selected_attempts),
            "structurally_valid_attempts": sum(
                bool(row.get("structurally_valid")) for row in selected_attempts
            ),
            "candidate_payloads": len(selected_candidates),
            "terminal_judgments": len(selected_judgments),
            "validator_accepted": len(accepted),
            "acceptance_per_candidate": _rate(len(accepted), len(selected_candidates)),
            "validator_covered_cells": len({row["cell_id"] for row in accepted}),
            "coverage_rate": _rate(
                len({row["cell_id"] for row in accepted}), len(cells)
            ),
            "would_select_items": len(bank),
            "would_select_cells": len({row["cell_id"] for row in bank}),
        }

    return [
        stage("default_prefix_n1", {"default_n3"}, maximum_default_index=1),
        stage("default_prefix_n2", {"default_n3"}, maximum_default_index=2),
        stage("default_prefix_n3", {"default_n3"}, maximum_default_index=3),
        stage("rescue_only", {"conditional_rescue"}),
        stage("cumulative_through_rescue", {"default_n3", "conditional_rescue"}),
        stage("intervention_only", {"determinacy_intervention"}),
        stage("final_cumulative", set(COHORTS)),
    ]


def _criterion_rows(
    candidates: list[dict[str, Any]], judgments: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    cohort_by_id = {row["item_id"]: candidate_cohort(row) for row in candidates}
    criteria = sorted(
        {
            name
            for row in judgments
            for name in row.get("judgments", {})
        }
    )
    rows = []
    for cohort in ("all", *COHORTS):
        selected = [
            row
            for row in judgments
            if cohort == "all" or cohort_by_id.get(row["item_id"]) == cohort
        ]
        for criterion in criteria:
            evaluated = [
                row for row in selected if criterion in row.get("judgments", {})
            ]
            failures = [
                row
                for row in evaluated
                if row["judgments"][criterion].get("passed") is False
            ]
            rows.append(
                {
                    "cohort": cohort,
                    "criterion": criterion,
                    "evaluated": len(evaluated),
                    "passed": len(evaluated) - len(failures),
                    "failed": len(failures),
                    "pass_rate": _rate(len(evaluated) - len(failures), len(evaluated)),
                    "failure_item_ids": sorted(row["item_id"] for row in failures),
                }
            )
    return rows


def _call_time_rows(
    attempts: list[dict[str, Any]], judgments: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    for stage in ("generation", "validation"):
        for cohort in (*COHORTS, "all"):
            if stage == "generation":
                retained = [
                    row
                    for row in attempts
                    if cohort == "all" or attempt_cohort(row) == cohort
                ]
                selected = [
                    float(row["runtime_seconds"])
                    for row in retained
                    if row.get("runtime_seconds") is not None
                ]
            else:
                def validation_cohort(row: dict[str, Any]) -> str:
                    status = str(
                        row.get("validation_metadata", {}).get("status", "")
                    ).casefold()
                    if "intervention" in status:
                        return "determinacy_intervention"
                    if "rescue" in status:
                        return "conditional_rescue"
                    return "default_n3"

                retained = [
                    row
                    for row in judgments
                    if cohort == "all" or validation_cohort(row) == cohort
                ]
                selected = [
                    float(row["validation_metadata"]["runtime_seconds"])
                    for row in retained
                    if row.get("validation_metadata", {}).get("runtime_seconds")
                    is not None
                ]
            rows.append(
                {
                    "stage": stage,
                    "cohort": cohort,
                    "retained_records": len(retained),
                    "calls_with_recorded_duration": len(selected),
                    "records_without_duration": len(retained) - len(selected),
                    "sum_seconds": sum(selected),
                    "median_seconds": _median(selected),
                    "mean_seconds": _rate(sum(selected), len(selected)),
                    "timing_interpretation": (
                        "sum of per-call durations; concurrent calls overlap, so this is not wall time"
                    ),
                }
            )
    return rows


def _candidate_tables(
    inventory: dict[str, Any]
) -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]
]:
    candidates = inventory["candidates"]
    families = []
    for family in ("feature_value", "operation", "interaction", "full_cell"):
        selected = [row for row in candidates if row["family"] == family]
        families.append(
            {
                "family": family,
                "raw_candidates": len(selected),
                "support_eligible": sum(
                    bool(row["meets_support_threshold"]) for row in selected
                ),
                "equivalence_representatives": sum(
                    bool(row["is_equivalence_representative"]) for row in selected
                ),
                "selection_eligible": sum(
                    bool(row["selection_eligible"]) for row in selected
                ),
                "activation_duplicates": sum(
                    not bool(row["is_equivalence_representative"])
                    for row in selected
                ),
                "minimum_cell_support": min(
                    (int(row["cell_support"]) for row in selected), default=None
                ),
                "median_cell_support": _median(
                    int(row["cell_support"]) for row in selected
                ),
                "minimum_item_support": min(
                    (int(row["item_support"]) for row in selected), default=None
                ),
                "median_item_support": _median(
                    int(row["item_support"]) for row in selected
                ),
            }
        )
    support = [
        {
            "candidate_id": row["id"],
            "family": row["family"],
            "cell_support": row["cell_support"],
            "item_support": row["item_support"],
            "meets_support_threshold": row["meets_support_threshold"],
            "equivalence_class_id": row["equivalence_class_id"],
            "equivalent_to": row.get("equivalent_to"),
            "is_equivalence_representative": row["is_equivalence_representative"],
            "selection_eligible": row["selection_eligible"],
            "exclusion_reasons": row["exclusion_reasons"],
        }
        for row in candidates
    ]
    operations = [row for row in support if row["family"] == "operation"]
    return families, support, operations


def _policy_and_kt_tables(dataset_dir: Path, inventory: dict[str, Any]) -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]
]:
    family_by_id = {row["id"]: row["family"] for row in inventory["candidates"]}
    granularity = []
    kt_rows = []
    selected_rows = []
    for result_path in sorted((dataset_dir / "evaluation").glob("*/results.json")):
        policy_name = result_path.parent.name
        result = _read_json(result_path)
        representation = result["representation"]
        policy_path = dataset_dir / "kc/policies" / f"{policy_name}.yaml"
        policy = read_yaml(policy_path) if policy_path.is_file() else {}
        kc_ids = (
            [row["id"] for row in policy.get("kcs", [])]
            if policy.get("kind") != "full_cell"
            else list(representation.get("kc_support", {}))
        )
        family_counts = Counter(
            family_by_id.get(kc_id, "oracle_full_cell") for kc_id in kc_ids
        )
        supports = list(representation.get("kc_support", {}).values())
        granularity.append(
            {
                "policy": policy_name,
                "policy_id": representation["policy_id"],
                "kcs": representation["kcs"],
                "feature_kcs": family_counts["feature_value"],
                "operation_kcs": family_counts["operation"],
                "interaction_kcs": family_counts["interaction"],
                "development_full_cell_kcs": family_counts["full_cell"],
                "oracle_full_cell_kcs": family_counts["oracle_full_cell"],
                "q_matrix_density": representation["q_matrix_density"],
                "kcs_per_item": representation["kcs_per_item"],
                "item_coverage": representation["item_coverage"],
                "minimum_item_support": min(supports) if supports else None,
                "median_item_support": _median(supports),
                "maximum_item_support": max(supports) if supports else None,
                "activation_redundant_pairs": len(
                    representation.get("redundant_kcs", [])
                ),
                "compositional_coverage": representation.get(
                    "compositional_coverage"
                ),
            }
        )
        for technique, metrics in result["kt"].items():
            for regime, values in (
                [("all_test", metrics)]
                + list(metrics["grammar_split_metrics"].items())
            ):
                kt_rows.append(
                    {
                        "policy": policy_name,
                        "kt_method": technique,
                        "grammar_regime": regime,
                        **{
                            key: values.get(key)
                            for key in (
                                "n",
                                "log_loss",
                                "brier_score",
                                "auc",
                                "ece",
                                "accuracy",
                            )
                        },
                    }
                )
        if policy_name == "automated":
            metadata = policy.get("selection_metadata", {})
            initial = set(metadata.get("initial_candidate_ids", []))
            selected = set(metadata.get("selected_candidate_ids", kc_ids))
            for candidate_id in sorted(selected):
                selected_rows.append(
                    {
                        "candidate_id": candidate_id,
                        "family": family_by_id.get(candidate_id),
                        "selection_role": (
                            "protected_initial" if candidate_id in initial else "selected_addition"
                        ),
                        **metadata.get("selected_support", {}).get(candidate_id, {}),
                    }
                )

    paired_rows = []
    paired_path = dataset_dir / "evaluation/paired_logistic.json"
    if paired_path.is_file():
        paired = _read_json(paired_path)
        for row in paired.get("comparisons", []):
            paired_rows.append(
                {
                    "grammar_regime": row["grammar_regime"],
                    "reference": row["reference"],
                    "candidate": row["candidate"],
                    "available": row.get("available"),
                    "n_learners": row.get("n_learners"),
                    "n_events": row.get("n_events"),
                    "delta_log_loss": row.get("delta_log_loss", {}).get(
                        "point_estimate"
                    ),
                    "delta_log_loss_interval_95": row.get(
                        "delta_log_loss", {}
                    ).get("interval_95"),
                    "delta_brier_score": row.get("delta_brier_score", {}).get(
                        "point_estimate"
                    ),
                    "delta_brier_interval_95": row.get(
                        "delta_brier_score", {}
                    ).get("interval_95"),
                    "sign_convention": row.get("sign_convention"),
                }
            )
    return granularity, kt_rows, paired_rows, selected_rows


def _structural_sensitivity(
    cells: list[dict[str, Any]],
    items: list[dict[str, Any]],
    fold: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    schema = read_yaml(SCHEMA_PATH)
    design = read_yaml(CANDIDATE_DESIGN_PATH) | {
        "operation_declarations": read_yaml(OPERATIONS_PATH)["operations"]
    }
    split_by_cell = {row["cell_id"]: row["grammar_split"] for row in fold}
    development_cells = [
        row for row in cells if split_by_cell[row["cell_id"]] == "development"
    ]
    full_items = [
        row for row in items if split_by_cell[row["cell_id"]] == "development"
    ]
    rank1_items = [
        row
        for row in full_items
        if int(row.get("selection_metadata", {}).get("rank", 1)) == 1
    ]
    inventories = {
        "one_rank1_variant_per_cell": make_kc_candidates(
            schema, development_cells, rank1_items, design
        ),
        "up_to_two_selected_variants_per_cell": make_kc_candidates(
            schema, development_cells, full_items, design
        ),
    }
    rows = []
    for label, inventory in inventories.items():
        interaction_rows = [
            row for row in inventory["candidates"] if row["family"] == "interaction"
        ]
        rows.append(
            {
                "item_bank": label,
                "development_items": len(inventory["development_item_ids"]),
                **inventory["candidate_counts"],
                "eligible_interactions": sum(
                    bool(row["selection_eligible"]) for row in interaction_rows
                ),
                "support_eligible_interactions": sum(
                    bool(row["meets_support_threshold"]) for row in interaction_rows
                ),
            }
        )
    eligible = {
        label: {
            row["id"]
            for row in inventory["candidates"]
            if row["selection_eligible"]
        }
        for label, inventory in inventories.items()
    }
    one = eligible["one_rank1_variant_per_cell"]
    two = eligible["up_to_two_selected_variants_per_cell"]
    comparison = {
        "outcomes_read": False,
        "learner_selector_rerun": False,
        "scope": "structural candidate support/equivalence only",
        "eligible_in_both": sorted(one & two),
        "eligible_only_with_rank1": sorted(one - two),
        "eligible_only_with_up_to_two": sorted(two - one),
        "eligible_inventory_jaccard": _rate(len(one & two), len(one | two)),
    }
    return rows, comparison


def _source_and_cell_tables(
    schema: dict[str, Any],
    sources: list[dict[str, Any]],
    mappings: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    relations: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
    items: list[dict[str, Any]],
    fold: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    result_counts = Counter(row["result"] for row in mappings)
    contributing = {row["source_id"] for row in relations}
    source_summary = {
        "descriptors": len(sources),
        "normalisation_counts": dict(sorted(result_counts.items())),
        "normalisation_proportions": {
            key: _rate(value, len(sources)) for key, value in sorted(result_counts.items())
        },
        "phase2_eligible_descriptors": sum(
            bool(row.get("phase2_eligible")) for row in mappings
        ),
        "phase2_eligible_by_dimension": dict(
            sorted(
                Counter(
                    dimension
                    for row in mappings
                    for dimension in (
                        row.get("phase2_eligible", [])
                        if isinstance(row.get("phase2_eligible", []), list)
                        else []
                    )
                ).items()
            )
        ),
        "contributing_descriptors": len(contributing),
        "source_cell_edges": len(relations),
        "unique_cells": len(cells),
        "all_descriptors_per_cell": _rate(len(sources), len(cells)),
        "contributing_descriptors_per_cell": _rate(len(contributing), len(cells)),
        "source_cell_edges_per_cell": _rate(len(relations), len(cells)),
    }
    split_by_cell = {row["cell_id"]: row["grammar_split"] for row in fold}
    relations_per_cell = Counter(row["cell_id"] for row in relations)
    attempts_per_cell = Counter(row["cell_id"] for row in attempts)
    candidate_by_id = {row["item_id"]: row for row in candidates}
    candidates_per_cell = Counter(row["cell_id"] for row in candidates)
    judgments_per_cell = Counter(
        candidate_by_id[row["item_id"]]["cell_id"]
        for row in judgments
        if row["item_id"] in candidate_by_id
    )
    criterion_failures_per_cell: dict[str, Counter[str]] = defaultdict(Counter)
    for judgment in judgments:
        candidate = candidate_by_id.get(judgment["item_id"])
        if candidate is None:
            continue
        for criterion, result in judgment.get("judgments", {}).items():
            if result.get("passed") is False:
                criterion_failures_per_cell[candidate["cell_id"]][criterion] += 1
    accepted_per_cell = Counter(
        candidate_by_id[row["item_id"]]["cell_id"]
        for row in judgments
        if row.get("accepted") and row["item_id"] in candidate_by_id
    )
    selected_per_cell = Counter(row["cell_id"] for row in items)
    cell_rows = []
    for cell in sorted(cells, key=lambda row: row["cell_id"]):
        cell_rows.append(
            {
                "cell_id": cell["cell_id"],
                **cell["features"],
                "grammar_regime": split_by_cell[cell["cell_id"]],
                "declared_source_ids": len(cell.get("source_ids", [])),
                "source_cell_edges": relations_per_cell[cell["cell_id"]],
                "generation_attempts": attempts_per_cell[cell["cell_id"]],
                "candidate_payloads": candidates_per_cell[cell["cell_id"]],
                "terminal_judgments": judgments_per_cell[cell["cell_id"]],
                "validator_accepted": accepted_per_cell[cell["cell_id"]],
                "validator_acceptance_rate": _rate(
                    accepted_per_cell[cell["cell_id"]],
                    candidates_per_cell[cell["cell_id"]],
                ),
                "selected_items": selected_per_cell[cell["cell_id"]],
                "failed_criteria": dict(
                    sorted(criterion_failures_per_cell[cell["cell_id"]].items())
                ),
            }
        )
    value_rows = []
    for dimension in schema["dimension_order"]:
        for value in schema["dimensions"][dimension]["allowed_values"]:
            matching = [
                row for row in cells if row["features"][dimension] == value
            ]
            matching_ids = {row["cell_id"] for row in matching}
            value_rows.append(
                {
                    "dimension": dimension,
                    "value": value,
                    "cell_support": len(matching),
                    "source_edge_support": sum(
                        relations_per_cell[cell_id] for cell_id in matching_ids
                    ),
                    "selected_item_support": sum(
                        selected_per_cell[cell_id] for cell_id in matching_ids
                    ),
                    **{
                        f"{split}_cell_support": sum(
                            split_by_cell[cell_id] == split for cell_id in matching_ids
                        )
                        for split in REGIMES
                    },
                }
            )
    return source_summary, value_rows, cell_rows


def _qualitative_rows(
    cells: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
    items: list[dict[str, Any]],
    fold: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    split_by_cell = {row["cell_id"]: row["grammar_split"] for row in fold}
    cell_by_id = {row["cell_id"]: row for row in cells}
    candidate_by_id = {row["item_id"]: row for row in candidates}
    rows = []
    for regime in REGIMES:
        examples = sorted(
            (row for row in items if split_by_cell[row["cell_id"]] == regime),
            key=lambda row: row["item_id"],
        )[:2]
        for item in examples:
            rows.append(
                {
                    "evidence_type": "selected_item_by_grammar_regime",
                    "grammar_regime": regime,
                    "cell_id": item["cell_id"],
                    "item_id": item["item_id"],
                    "features": cell_by_id[item["cell_id"]]["features"],
                    "prompt": item["prompt"],
                    "target_answer": item["target_answer"],
                    "criterion": None,
                }
            )
    for judgment in judgments:
        failed = sorted(
            name
            for name, value in judgment.get("judgments", {}).items()
            if value.get("passed") is False
        )
        if not failed or judgment["item_id"] not in candidate_by_id:
            continue
        item = candidate_by_id[judgment["item_id"]]
        rows.append(
            {
                "evidence_type": "retained_validation_failure",
                "grammar_regime": split_by_cell[item["cell_id"]],
                "cell_id": item["cell_id"],
                "item_id": item["item_id"],
                "features": cell_by_id[item["cell_id"]]["features"],
                "prompt": item["prompt"],
                "target_answer": item["target_answer"],
                "criterion": failed,
            }
        )
    return rows


def _rq_rows(optional_stability_available: bool) -> list[dict[str, Any]]:
    evidence = {
        "F1": ("answered", "summary.json:source_normalisation"),
        "F2": ("answered", "grammar_cells.csv"),
        "F3": ("answered", "summary.json:source_normalisation"),
        "F4": ("answered", "dimension_value_support.csv"),
        "F5": ("answered", "grammar_cells.csv"),
        "F6": ("answered", "fold_summary.csv"),
        "F7": ("answered", "fold_summary.csv"),
        "F8": ("answered", "item_generation_stages.csv"),
        "F9": ("partially_answered", "item_generation_stages.csv; N=5 is Phase-4 evidence"),
        "F10": ("answered", "item_generation_stages.csv"),
        "F11": ("answered", "grammar_cells.csv; qualitative_index.csv"),
        "F12": ("answered", "criterion_failures.csv; grammar_cells.csv"),
        "F13": ("answered", "lexical_diversity.csv"),
        "F14": ("answered", "criterion_failures.csv:non_target_language_simplicity"),
        "F15": ("answered", "kc_candidate_families.csv"),
        "F16": ("answered", "kc_candidate_families.csv; kc_candidate_support.csv"),
        "F17": ("answered", "operation_candidates.csv"),
        "F18": ("answered", "automated_selected_kcs.csv"),
        "F19": (
            "answered" if optional_stability_available else "partially_answered",
            "selection_stability.json if retained; otherwise Phase-4/5 evidence only",
        ),
        "F20": ("answered", "policy_granularity.csv"),
        "F21": ("answered", "policy_granularity.csv; kc_candidate_support.csv"),
        "F22": ("answered", "kt_metrics.csv; paired_logistic.csv"),
        "F23": ("answered", "kt_metrics.csv; paired_logistic.csv:compositional_holdout"),
        "F24": ("partially_answered", "primary mixed world here; four-world Phase-4 evidence external"),
        "F25": ("partially_answered", "finalization_manifest.json plus Phase-5 nested support evidence"),
        "F26": ("answered", "call_times.csv; provider price unavailable"),
        "F27": ("answered", "criterion_failures.csv; qualitative_index.csv"),
        "F28": ("partially_answered", "qualitative_index.csv is descriptive; no human usability study"),
        "F29": ("partially_answered", "declared-schema structural method; English-only empirical evidence"),
        "F30": ("partially_answered", "retained exact legacy mapping match; repeat/model stability unavailable"),
        "F31": ("answered", "rejection_stages.csv"),
        "F32": ("answered", "lexical_diversity.csv; item_generation_stages.csv"),
        "F33": ("answered", "item_generation_stages.csv; criterion_failures.csv"),
        "F34": ("answered", "one_vs_two_variant_sensitivity.csv"),
    }
    return [
        {"rq": rq, "status": status, "retained_evidence": artifact}
        for rq, (status, artifact) in evidence.items()
    ]


def analyse_dataset(
    dataset_dir: Path,
    output_dir: Path,
    *,
    exact_command: str = "direct Python call",
) -> dict[str, Any]:
    dataset_dir = dataset_dir.resolve()
    output_dir = output_dir.resolve()
    finalization_path = dataset_dir / "finalization_manifest.json"
    if not finalization_path.is_file():
        raise FileNotFoundError(
            "full-dataset analysis requires downstream finalization: "
            f"{finalization_path}"
        )
    finalization = _read_json(finalization_path)
    if finalization.get("status") != "downstream_finalized":
        raise ValueError(
            "full-dataset analysis requires status downstream_finalized, found "
            f"{finalization.get('status')!r}"
        )

    schema = read_yaml(SCHEMA_PATH)
    sources = read_jsonl(dataset_dir / "source/descriptors.jsonl")
    mappings = read_jsonl(dataset_dir / "normalisation/mappings.jsonl")
    cells = read_jsonl(dataset_dir / "canonical/cells.jsonl")
    relations = read_jsonl(dataset_dir / "canonical/source_cell_relations.jsonl")
    attempts = read_jsonl(dataset_dir / "items/generation_attempts.jsonl")
    manifest_path = dataset_dir / "manifest.json"
    dataset_manifest = _read_json(manifest_path) if manifest_path.exists() else {}
    if dataset_manifest.get("item_packaging_correction"):
        candidates = read_jsonl(dataset_dir / "items/curated_candidates.jsonl")
        judgments = read_jsonl(dataset_dir / "items/curated_validation.jsonl")
    else:
        candidates = read_jsonl(dataset_dir / "items/candidates.jsonl")
        judgments = read_jsonl(dataset_dir / "items/validation.jsonl")
    validator_accepted = read_jsonl(dataset_dir / "items/validator_accepted.jsonl")
    items = read_jsonl(dataset_dir / "items/selected_bank.jsonl")
    fold = read_jsonl(dataset_dir / "fold/assignments.jsonl")
    inventory = _read_json(dataset_dir / "kc/candidate_inventory.json")
    item_design = read_yaml(ITEM_DESIGN_PATH)

    source_summary, value_rows, cell_rows = _source_and_cell_tables(
        schema,
        sources,
        mappings,
        cells,
        relations,
        attempts,
        candidates,
        judgments,
        items,
        fold,
    )
    fold_rows, fold_details = _fold_tables(
        cells, items, fold, schema["dimension_order"]
    )
    stage_rows = _item_stage_rows(
        cells, attempts, candidates, judgments, item_design
    )
    criterion_rows = _criterion_rows(candidates, judgments)
    rejection_rows = [
        {"rejection_stage": key or "accepted", "judgments": value}
        for key, value in sorted(
            Counter(row.get("rejection_stage") for row in judgments).items(),
            key=lambda row: str(row[0]),
        )
    ]
    lexical_rows = [
        _token_summary("all_validator_accepted", validator_accepted),
        _token_summary("selected_bank", items),
        _token_summary(
            "selected_rank1_only",
            [
                row
                for row in items
                if int(row.get("selection_metadata", {}).get("rank", 1)) == 1
            ],
        ),
    ]
    call_rows = _call_time_rows(attempts, judgments)
    family_rows, candidate_rows, operation_rows = _candidate_tables(inventory)
    granularity_rows, kt_rows, paired_rows, selected_rows = _policy_and_kt_tables(
        dataset_dir, inventory
    )
    sensitivity_rows, sensitivity_comparison = _structural_sensitivity(
        cells, items, fold
    )
    qualitative_rows = _qualitative_rows(
        cells, candidates, judgments, items, fold
    )
    stability_path = dataset_dir / "kc/selection_stability.json"
    rq_rows = _rq_rows(stability_path.is_file())

    csv_outputs = {
        "source_normalisation.csv": [
            {
                "descriptors": source_summary["descriptors"],
                **{
                    f"{result}_count": count
                    for result, count in source_summary[
                        "normalisation_counts"
                    ].items()
                },
                **{
                    f"{result}_proportion": proportion
                    for result, proportion in source_summary[
                        "normalisation_proportions"
                    ].items()
                },
                "phase2_eligible_descriptors": source_summary[
                    "phase2_eligible_descriptors"
                ],
                "phase2_eligible_by_dimension": source_summary[
                    "phase2_eligible_by_dimension"
                ],
                "contributing_descriptors": source_summary[
                    "contributing_descriptors"
                ],
                "source_cell_edges": source_summary["source_cell_edges"],
                "unique_cells": source_summary["unique_cells"],
                "all_descriptors_per_cell": source_summary[
                    "all_descriptors_per_cell"
                ],
                "contributing_descriptors_per_cell": source_summary[
                    "contributing_descriptors_per_cell"
                ],
                "source_cell_edges_per_cell": source_summary[
                    "source_cell_edges_per_cell"
                ],
            }
        ],
        "dimension_value_support.csv": value_rows,
        "grammar_cells.csv": cell_rows,
        "fold_summary.csv": fold_rows,
        "item_generation_stages.csv": stage_rows,
        "criterion_failures.csv": criterion_rows,
        "rejection_stages.csv": rejection_rows,
        "lexical_diversity.csv": lexical_rows,
        "call_times.csv": call_rows,
        "kc_candidate_families.csv": family_rows,
        "kc_candidate_support.csv": candidate_rows,
        "operation_candidates.csv": operation_rows,
        "policy_granularity.csv": granularity_rows,
        "kt_metrics.csv": kt_rows,
        "paired_logistic.csv": paired_rows,
        "automated_selected_kcs.csv": selected_rows,
        "one_vs_two_variant_sensitivity.csv": sensitivity_rows,
        "qualitative_index.csv": qualitative_rows,
        "rq_evidence.csv": rq_rows,
    }
    for name, rows in csv_outputs.items():
        _write_csv(output_dir / name, rows)

    summary = {
        "analysis_id": "medium_v1_full_dataset_analysis",
        "dataset_dir": str(dataset_dir),
        "dataset_finalization": finalization,
        "exact_command": exact_command,
        "model_calls_made": False,
        "learner_outcomes_recomputed": False,
        "source_normalisation": source_summary,
        "canonical": {
            "dimensions": schema["dimension_order"],
            "unique_cells": len(cells),
            "dimension_value_table": "dimension_value_support.csv",
            "cell_table": "grammar_cells.csv",
        },
        "items": {
            "attempts": len(attempts),
            "candidate_payloads": len(candidates),
            "judgments": len(judgments),
            "validator_accepted": len(validator_accepted),
            "selected": len(items),
            "selected_cells": len({row["cell_id"] for row in items}),
            "stage_table": "item_generation_stages.csv",
            "criterion_table": "criterion_failures.csv",
            "timing_claim_boundary": (
                "Per-call duration sums are workload totals, not elapsed wall time, because calls overlap."
            ),
            "provider_price_available": False,
        },
        "fold": {"rows": fold_rows, **fold_details},
        "kc_candidates": inventory["candidate_counts"],
        "one_vs_two_variant_structural_sensitivity": sensitivity_comparison,
        "policy_count": len(granularity_rows),
        "kt_metric_rows": len(kt_rows),
        "paired_logistic_rows": len(paired_rows),
        "selection_stability": (
            _read_json(stability_path)
            if stability_path.is_file()
            else {
                "available": False,
                "reason": "no full-bank repeated-stream stability artifact retained",
            }
        ),
        "claim_boundaries": [
            "Item quality is model-judged; no human acceptability or pedagogical efficacy study was performed.",
            "Learner outcomes are synthetic under the declared mixed latent world, not observations of human learners.",
            "The KC algorithm consumes a declared schema structurally, but empirical evidence here is English-only.",
            "The retained normalization snapshot cannot establish repeated-run or cross-model stability.",
            "Qualitative rows are traceable item/cell IDs and validator evidence, not new analyst judgments.",
        ],
        "outputs": sorted(csv_outputs),
    }
    write_json(output_dir / "summary.json", summary)

    markdown = "\n".join(
        [
            "# Medium-v1 paper-facing evidence tables",
            "",
            "Generated deterministically from retained artifacts; no model calls or learner resimulation.",
            "",
            "## Source and normalization",
            "",
            _markdown_table(
                [
                    {
                        "descriptors": source_summary["descriptors"],
                        "complete": source_summary["normalisation_counts"].get("complete", 0),
                        "partial": source_summary["normalisation_counts"].get("partial", 0),
                        "unresolved": source_summary["normalisation_counts"].get("unresolved", 0),
                        "out_of_scope": source_summary["normalisation_counts"].get("out_of_scope", 0),
                        "unique_cells": source_summary["unique_cells"],
                        "source_cell_edges": source_summary["source_cell_edges"],
                    }
                ],
                [
                    "descriptors",
                    "complete",
                    "partial",
                    "unresolved",
                    "out_of_scope",
                    "unique_cells",
                    "source_cell_edges",
                ],
            ),
            "",
            "## Item construction by frozen cohort",
            "",
            _markdown_table(
                stage_rows,
                [
                    "stage",
                    "generation_attempts",
                    "candidate_payloads",
                    "validator_accepted",
                    "validator_covered_cells",
                    "would_select_items",
                ],
            ),
            "",
            "## Grammar fold",
            "",
            _markdown_table(
                fold_rows,
                [
                    "grammar_regime",
                    "cells",
                    "selected_items",
                    "unseen_development_feature_values",
                    "value_pairs_unseen_in_development",
                ],
            ),
            "",
            "## KC candidate space",
            "",
            _markdown_table(
                family_rows,
                [
                    "family",
                    "raw_candidates",
                    "support_eligible",
                    "activation_duplicates",
                    "selection_eligible",
                    "median_item_support",
                ],
            ),
            "",
            "## KC policy granularity",
            "",
            _markdown_table(
                granularity_rows,
                [
                    "policy",
                    "kcs",
                    "interaction_kcs",
                    "q_matrix_density",
                    "kcs_per_item",
                    "median_item_support",
                ],
            ),
            "",
            "## Fixed-logistic primary comparison",
            "",
            _markdown_table(
                paired_rows,
                [
                    "grammar_regime",
                    "candidate",
                    "delta_log_loss",
                    "delta_log_loss_interval_95",
                    "delta_brier_score",
                    "delta_brier_interval_95",
                ],
            ),
            "",
            "Negative paired deltas favour the candidate representation. Confidence intervals resample whole learners.",
            "",
            "## One versus up-to-two variants (structural only)",
            "",
            _markdown_table(
                sensitivity_rows,
                [
                    "item_bank",
                    "development_items",
                    "raw_total",
                    "selection_eligible",
                    "eligible_interactions",
                    "activation_duplicate_candidates",
                ],
            ),
            "",
            "This sensitivity recomputes support/equivalence only; it does not read outcomes or rerun learner-evidence selection.",
        ]
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "tables.md").write_text(markdown + "\n", encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    result = analyse_dataset(
        arguments.dataset_dir,
        arguments.output_dir,
        exact_command=" ".join([sys.executable, *sys.argv]),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
