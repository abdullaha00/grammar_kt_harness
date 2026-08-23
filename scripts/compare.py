#!/usr/bin/env python3
"""Compare saved runs at scientific, not byte/hash, level."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# Prevent this directory's inspect.py from shadowing Python's standard inspect module.
sys.path.remove(str(Path(__file__).resolve().parent))

from grammar_kt.io import ROOT, read_json, read_jsonl, read_yaml
from grammar_kt.items import item_bank_fingerprint
from grammar_kt.kt import learner_bootstrap_log_loss_difference


def keyed(path: Path, key: str) -> dict[str, dict[str, Any]]:
    return {row[key]: row for row in read_jsonl(path)} if path.is_file() else {}


def delta(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    common = set(left) & set(right)
    return {
        "added": sorted(set(right) - set(left)),
        "removed": sorted(set(left) - set(right)),
        "changed": sorted(key for key in common if left[key] != right[key]),
    }


def configuration_changes(base: Any, target: Any, prefix: str = "") -> list[dict[str, Any]]:
    """Describe the resolved method choices that differ between two runs."""

    if isinstance(base, dict) and isinstance(target, dict):
        changes = []
        for key in sorted(set(base) | set(target)):
            dotted = f"{prefix}.{key}" if prefix else key
            if key not in base:
                changes.append({"path": dotted, "from": None, "to": target[key]})
            elif key not in target:
                changes.append({"path": dotted, "from": base[key], "to": None})
            else:
                changes.extend(configuration_changes(base[key], target[key], dotted))
        return changes
    return [] if base == target else [{"path": prefix, "from": base, "to": target}]


def normalisation(a: Path, b: Path) -> dict[str, Any]:
    left = keyed(a / "normalisation/final_mappings.jsonl", "egp_id")
    right = keyed(b / "normalisation/final_mappings.jsonl", "egp_id")
    changes = delta(left, right)
    return {
        "result_counts": {
            "run_a": dict(Counter(row["result"] for row in left.values())),
            "run_b": dict(Counter(row["result"] for row in right.values())),
        },
        "changed_egp_ids": changes["changed"],
        "added_egp_ids": changes["added"],
        "removed_egp_ids": changes["removed"],
        "result_class_changes": [
            {"egp_id": key, "from": left[key]["result"], "to": right[key]["result"]}
            for key in changes["changed"] if left[key]["result"] != right[key]["result"]
        ],
    }


def canonical_stage(a: Path, b: Path) -> dict[str, Any]:
    def source_edges(run: Path) -> dict[str, dict[str, Any]]:
        filename = run / "canonical/source_cell_edges.jsonl"
        if not filename.is_file():
            return {}
        return {
            f"{row['egp_id']}|{row['source_cell_index']}|{row['canonical_cell_id']}": row
            for row in read_jsonl(filename)
        }

    return {
        "cells": delta(
            keyed(a / "canonical/canonical_cells.jsonl", "canonical_cell_id"),
            keyed(b / "canonical/canonical_cells.jsonl", "canonical_cell_id"),
        ),
        "source_cell_edges": delta(source_edges(a), source_edges(b)),
    }


def realisation_stage(a: Path, b: Path) -> dict[str, Any]:
    def realisations_by_id(run: Path) -> dict[str, dict[str, Any]]:
        filename = run / "realisation/realisations.jsonl"
        return {row["spec"]["realization_id"]: row for row in read_jsonl(filename)} if filename.is_file() else {}
    return delta(realisations_by_id(a), realisations_by_id(b))


def kc_selection_stage(a: Path, b: Path) -> dict[str, Any]:
    def summary(run: Path) -> dict[str, Any]:
        directory = run / "kc_selection"
        candidates = keyed(directory / "candidates.jsonl", "candidate_id")
        policy = read_json(directory / "selected_policy.json")
        evaluation = read_json(directory / "evaluation.json")
        selected = sorted(rule["kc_id"] for rule in policy.get("rules", []))
        selected_eval = evaluation["selected_ontology"]
        return {
            "policy_id": policy["policy_id"],
            "selection_mode": policy.get("selection_metadata", {}).get("selector"),
            "candidate_count": len(candidates),
            "selected_kc_ids": selected,
            "unidentifiable_equivalence_classes": len(
                evaluation.get("unidentifiable_equivalence_classes", [])
            ),
            "split_audit_status": evaluation.get("split_audit", {}).get("status"),
            "development_objective": evaluation.get("development_selection_objective"),
            "compositional_holdout": {
                key: selected_eval["compositional_holdout"].get(key)
                for key in (
                    "coverage", "fact_recall", "component_reuse",
                    "signature_contrast_preservation", "dimension_witness_preservation",
                )
            },
            "novel_feature_holdout": {
                key: selected_eval["novel_feature_holdout"].get(key)
                for key in ("coverage", "fact_recall", "component_reuse")
            },
        }

    left, right = summary(a), summary(b)
    return {
        "run_a": left,
        "run_b": right,
        "added_selected_kcs": sorted(set(right["selected_kc_ids"]) - set(left["selected_kc_ids"])),
        "removed_selected_kcs": sorted(set(left["selected_kc_ids"]) - set(right["selected_kc_ids"])),
    }


def kc_stage(a: Path, b: Path) -> dict[str, Any]:
    left_cards = keyed(a / "kc/projected_kc_inventory.jsonl", "kc_id")
    right_cards = keyed(b / "kc/projected_kc_inventory.jsonl", "kc_id")
    left = keyed(a / "kc/item_kc_projection.jsonl", "item_id")
    right = keyed(b / "kc/item_kc_projection.jsonl", "item_id")
    changed = sorted(
        key for key in set(left) & set(right) if left[key]["kc_ids"] != right[key]["kc_ids"]
    )
    return {
        "kc_count": {"run_a": len(left_cards), "run_b": len(right_cards)},
        "inventory": delta(left_cards, right_cards),
        "activation_edges": {
            "run_a": sum(len(row["kc_ids"]) for row in left.values()),
            "run_b": sum(len(row["kc_ids"]) for row in right.values()),
        },
        "kcs_per_opportunity": {
            "run_a": dict(Counter(len(row["kc_ids"]) for row in left.values())),
            "run_b": dict(Counter(len(row["kc_ids"]) for row in right.values())),
        },
        "changed_item_activations": [
            {"item_id": key, "from": left[key]["kc_ids"], "to": right[key]["kc_ids"]}
            for key in changed
        ],
    }


def item_stage(a: Path, b: Path) -> dict[str, Any]:
    left = keyed(a / "items/validation/accepted_items.jsonl", "item_id")
    right = keyed(b / "items/validation/accepted_items.jsonl", "item_id")
    changes = delta(left, right)
    answer_changes = [{"item_id": key, "from": left[key]["target_answer"], "to": right[key]["target_answer"]} for key in changes["changed"] if left[key]["target_answer"] != right[key]["target_answer"]]
    generated = delta(
        keyed(a / "items/generation/candidate_items.jsonl", "item_id"),
        keyed(b / "items/generation/candidate_items.jsonl", "item_id"),
    )
    validation_a = keyed(a / "items/validation/validation_results.jsonl", "item_id")
    validation_b = keyed(b / "items/validation/validation_results.jsonl", "item_id")
    status_changes = [
        {"item_id": key, "from": validation_a[key]["status"], "to": validation_b[key]["status"]}
        for key in sorted(set(validation_a) & set(validation_b))
        if validation_a[key]["status"] != validation_b[key]["status"]
    ]
    left_hash = item_bank_fingerprint(list(left.values())) if left else None
    right_hash = item_bank_fingerprint(list(right.values())) if right else None
    return {
        "accepted_count": {"run_a": len(left), "run_b": len(right)},
        "intrinsic_item_bank_sha256": {"run_a": left_hash, "run_b": right_hash},
        "identical_item_bank": left_hash is not None and left_hash == right_hash,
        **changes,
        "generation": generated,
        "status_changes": status_changes,
        "answer_changes": answer_changes,
    }


def qmatrix_stage(a: Path, b: Path) -> dict[str, Any]:
    def item_kc_pairs(run: Path) -> set[tuple[str, str]]:
        filename = run / "qmatrix/item_kc_edges.jsonl"
        return {(row["item_id"], row["kc_id"]) for row in read_jsonl(filename)} if filename.is_file() else set()

    def matrix_shape(run: Path) -> tuple[set[str], set[str]]:
        filename = run / "qmatrix/q_matrix.csv"
        if not filename.is_file():
            return set(), set()
        with filename.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        return {row["item_id"] for row in rows}, set(rows[0]) - {"item_id"} if rows else set()
    left, right = item_kc_pairs(a), item_kc_pairs(b)
    rows_a, columns_a = matrix_shape(a)
    rows_b, columns_b = matrix_shape(b)
    audit_a = read_json(a / "qmatrix/audit.json")
    audit_b = read_json(b / "qmatrix/audit.json")
    return {
        "shape": {"run_a": [len(rows_a), len(columns_a)], "run_b": [len(rows_b), len(columns_b)]},
        "added_rows": sorted(rows_b - rows_a), "removed_rows": sorted(rows_a - rows_b),
        "added_columns": sorted(columns_b - columns_a), "removed_columns": sorted(columns_a - columns_b),
        "edges": {"run_a": len(left), "run_b": len(right)}, "added_edges": sorted(right - left), "removed_edges": sorted(left - right),
        "uncovered_items": {
            "run_a": audit_a["uncovered_items"],
            "run_b": audit_b["uncovered_items"],
        },
    }


def simulation_stage(a: Path, b: Path) -> dict[str, Any]:
    def interaction_summary(run: Path) -> dict[str, Any]:
        filename = run / "simulation/base_events.jsonl"
        rows = read_jsonl(filename) if filename.is_file() else []
        audit = read_json(run / "simulation/audit.json") if (run / "simulation/audit.json").is_file() else {}
        return {
            "interactions": len(rows), "learners": len({row["learner_id"] for row in rows}),
            "items": len({row["item_id"] for row in rows}),
            "correct_rate": statistics.fmean(row["correct"] for row in rows) if rows else None,
            "base_event_stream_sha256": audit.get("base_event_stream_sha256"),
            "intrinsic_item_bank_sha256": audit.get(
                "intrinsic_item_bank_sha256", audit.get("item_bank_sha256")
            ),
            "rows": rows,
        }
    left, right = interaction_summary(a), interaction_summary(b)
    left_rows, right_rows = left.pop("rows"), right.pop("rows")
    def values(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> list[tuple[Any, ...]]:
        return [tuple(row[field] for field in fields) for row in rows]
    invariance = {
        "event_stream_hash_equal": left["base_event_stream_sha256"] is not None and left["base_event_stream_sha256"] == right["base_event_stream_sha256"],
        "item_bank_hash_equal": left["intrinsic_item_bank_sha256"] is not None and left["intrinsic_item_bank_sha256"] == right["intrinsic_item_bank_sha256"],
        "event_ids_equal": bool(left_rows) and values(left_rows, ("event_id",)) == values(right_rows, ("event_id",)),
        "learner_ids_equal": values(left_rows, ("learner_id",)) == values(right_rows, ("learner_id",)),
        "item_ids_and_order_equal": values(left_rows, ("item_id", "sequence_index")) == values(right_rows, ("item_id", "sequence_index")),
        "learner_item_order_equal": values(left_rows, ("learner_id", "sequence_index", "item_id")) == values(right_rows, ("learner_id", "sequence_index", "item_id")),
        "timestamps_equal": values(left_rows, ("timestamp",)) == values(right_rows, ("timestamp",)),
        "difficulties_equal": values(left_rows, ("item_difficulty",)) == values(right_rows, ("item_difficulty",)),
        "correctness_equal": values(left_rows, ("correct",)) == values(right_rows, ("correct",)),
        "temporal_splits_equal": values(left_rows, ("dataset_split",)) == values(right_rows, ("dataset_split",)),
        "canonical_splits_equal": values(left_rows, ("canonical_split",)) == values(right_rows, ("canonical_split",)),
    }
    return {
        "run_a": left,
        "run_b": right,
        "all_fixed_data_equal": all(invariance.values()),
        "invariance": invariance,
    }


def kt_stage(a: Path, b: Path) -> dict[str, Any]:
    left = read_json(a / "kt/metrics.json") if (a / "kt/metrics.json").is_file() else {}
    right = read_json(b / "kt/metrics.json") if (b / "kt/metrics.json").is_file() else {}
    result = {"techniques": {"run_a": sorted(left.get("techniques", {})), "run_b": sorted(right.get("techniques", {}))}, "metric_differences": []}
    for technique in sorted(set(left.get("techniques", {})) & set(right.get("techniques", {}))):
        for split in ("validation", "test"):
            for scope in ("covered_events", "all_events_fixed_fallback"):
                for metric in ("auc", "log_loss", "accuracy_at_0_5"):
                    before = left["techniques"][technique][split][scope][metric]
                    after = right["techniques"][technique][split][scope][metric]
                    difference = after - before if before is not None and after is not None else None
                    result["metric_differences"].append({"technique": technique, "split": split, "scope": scope, "metric": metric, "run_a": before, "run_b": after, "difference": difference})
    result["coverage"] = {
        "run_a": left.get("coverage"),
        "run_b": right.get("coverage"),
    }
    return result


def compositional_stage(a: Path, b: Path) -> dict[str, Any]:
    """Compare fixed Phase-D probes and paired ontology predictions."""

    def fixed(run: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        directory = run / "simulation/compositional"
        audit = read_json(directory / "audit.json")
        probes = read_jsonl(directory / "compositional_probe_events.jsonl") + read_jsonl(
            directory / "novel_feature_probe_events.jsonl"
        )
        frozen = read_jsonl(directory / "learner_frozen_oracle_state.jsonl")
        return audit, probes, frozen

    audit_a, probes_a, frozen_a = fixed(a)
    audit_b, probes_b, frozen_b = fixed(b)
    fields = (
        "event_id",
        "learner_id",
        "item_id",
        "canonical_cell_id",
        "correct",
        "item_difficulty",
        "dataset_split",
        "canonical_split",
    )
    values_a = [tuple(row[field] for field in fields) for row in probes_a]
    values_b = [tuple(row[field] for field in fields) for row in probes_b]
    metrics_a = read_json(a / "kt/compositional/metrics.json")
    metrics_b = read_json(b / "kt/compositional/metrics.json")
    support_a = read_json(a / "kt/compositional/representation_support.json")
    support_b = read_json(b / "kt/compositional/representation_support.json")
    predictions_a = read_jsonl(a / "kt/compositional/predictions.jsonl")
    predictions_b = read_jsonl(b / "kt/compositional/predictions.jsonl")
    techniques = sorted(
        set(metrics_a.get("holdout_evaluation", {}))
        & set(metrics_b.get("holdout_evaluation", {}))
    )
    differences = []
    bootstraps = []
    bootstrap_config = read_json(a / "kt/compositional/bootstrap_comparisons.json")
    repetitions = int(bootstrap_config.get("repetitions", 1000))
    seed = int(bootstrap_config.get("seed", 20260817))
    for technique in techniques:
        for split_name in ("compositional_holdout", "novel_feature_holdout"):
            left = metrics_a["holdout_evaluation"][technique][split_name][
                "all_probes_fixed_fallback"
            ]
            right = metrics_b["holdout_evaluation"][technique][split_name][
                "all_probes_fixed_fallback"
            ]
            for metric in ("log_loss", "brier_score", "auc", "accuracy_at_0_5", "ece"):
                before, after = left[metric], right[metric]
                differences.append(
                    {
                        "technique": technique,
                        "canonical_split": split_name,
                        "metric": metric,
                        "run_a": before,
                        "run_b": after,
                        "run_b_minus_run_a": (
                            after - before
                            if before is not None and after is not None
                            else None
                        ),
                    }
                )
        if predictions_a and predictions_b:
            bootstraps.append(
                learner_bootstrap_log_loss_difference(
                    predictions_a,
                    predictions_b,
                    technique=technique,
                    probe_type="compositional_holdout",
                    repetitions=repetitions,
                    seed=seed,
                )
            )
    invariance = {
        "probe_stream_hash_equal": audit_a.get("all_probe_stream_sha256")
        == audit_b.get("all_probe_stream_sha256"),
        "probe_rows_equal": values_a == values_b,
        "probe_event_ids_equal": [row["event_id"] for row in probes_a]
        == [row["event_id"] for row in probes_b],
        "correctness_equal": [row["correct"] for row in probes_a]
        == [row["correct"] for row in probes_b],
        "learner_item_probe_identity_equal": [
            (row["learner_id"], row["item_id"]) for row in probes_a
        ]
        == [(row["learner_id"], row["item_id"]) for row in probes_b],
        "frozen_oracle_state_equal": frozen_a == frozen_b,
    }
    return {
        "fixed_probe_data": {
            "run_a_sha256": audit_a.get("all_probe_stream_sha256"),
            "run_b_sha256": audit_b.get("all_probe_stream_sha256"),
            "probe_events": {"run_a": len(probes_a), "run_b": len(probes_b)},
            "all_equal": all(invariance.values()),
            "invariance": invariance,
        },
        "representation_support": {
            "run_a": {
                "compositional_holdout": support_a.get("compositional_holdout"),
                "novel_feature_holdout": support_a.get("novel_feature_holdout"),
            },
            "run_b": {
                "compositional_holdout": support_b.get("compositional_holdout"),
                "novel_feature_holdout": support_b.get("novel_feature_holdout"),
            },
        },
        "metric_differences": differences,
        "paired_learner_bootstrap_a_minus_b": bootstraps,
    }


COMPARISON_STAGES = ("normalisation", "canonical", "realisation", "items", "simulation", "kc_selection", "kc", "qmatrix", "kt", "compositional")


def compare(a: Path, b: Path, stage: str | None = None) -> dict[str, Any]:
    names = [stage] if stage else COMPARISON_STAGES
    output = {}
    for name in names:
        try:
            if name == "normalisation":
                output[name] = normalisation(a, b)
            elif name == "canonical":
                output[name] = canonical_stage(a, b)
            elif name == "realisation":
                output[name] = realisation_stage(a, b)
            elif name == "kc_selection":
                output[name] = kc_selection_stage(a, b)
            elif name == "kc":
                output[name] = kc_stage(a, b)
            elif name == "items":
                output[name] = item_stage(a, b)
            elif name == "qmatrix":
                output[name] = qmatrix_stage(a, b)
            elif name == "simulation":
                output[name] = simulation_stage(a, b)
            elif name == "kt":
                output[name] = kt_stage(a, b)
            elif name == "compositional":
                output[name] = compositional_stage(a, b)
            else:
                raise ValueError(f"unknown comparison stage: {name}")
        except (FileNotFoundError, KeyError, TypeError) as error:
            output[name] = {"unavailable": str(error)}
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two experimental runs semantically.")
    parser.add_argument("run_a")
    parser.add_argument("run_b")
    parser.add_argument("--stage", choices=COMPARISON_STAGES)
    args = parser.parse_args()
    run_a = Path(args.run_a)
    run_b = Path(args.run_b)
    a = run_a.resolve() if run_a.is_dir() else (ROOT / "runs" / args.run_a).resolve()
    b = run_b.resolve() if run_b.is_dir() else (ROOT / "runs" / args.run_b).resolve()
    experiment_changes = configuration_changes(
        read_yaml(a / "experiment.yaml"),
        read_yaml(b / "experiment.yaml"),
    ) if (a / "experiment.yaml").is_file() and (b / "experiment.yaml").is_file() else []
    print(json.dumps({"run_a": str(a), "run_b": str(b), "experiment_changes": experiment_changes, "comparison": compare(a, b, args.stage)}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
