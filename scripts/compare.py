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
from typing import Any, Callable

sys.path.remove(str(Path(__file__).resolve().parent))

from grammar_kt.config import changed_values
from grammar_kt.io import ROOT, read_json, read_jsonl, read_yaml


def run_path(value: str) -> Path:
    direct = Path(value)
    return direct.resolve() if direct.is_dir() else (ROOT / "runs" / value).resolve()


def keyed(path: Path, key: str) -> dict[str, dict[str, Any]]:
    return {row[key]: row for row in read_jsonl(path)} if path.is_file() else {}


def delta(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    common = set(left) & set(right)
    return {
        "added": sorted(set(right) - set(left)),
        "removed": sorted(set(left) - set(right)),
        "changed": sorted(key for key in common if left[key] != right[key]),
    }


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


def records(a: Path, b: Path, filename: str, key: str) -> dict[str, Any]:
    return delta(keyed(a / filename, key), keyed(b / filename, key))


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
        "cells": records(a, b, "canonical/canonical_cells.jsonl", "canonical_cell_id"),
        "source_cell_edges": delta(source_edges(a), source_edges(b)),
    }


def realisation_stage(a: Path, b: Path) -> dict[str, Any]:
    def load(run: Path) -> dict[str, dict[str, Any]]:
        filename = run / "realisation/realisations.jsonl"
        return {row["spec"]["realization_id"]: row for row in read_jsonl(filename)} if filename.is_file() else {}
    return delta(load(a), load(b))


def kc_stage(a: Path, b: Path) -> dict[str, Any]:
    left_cards = keyed(a / "kc/kc_inventory.jsonl", "kc_id")
    right_cards = keyed(b / "kc/kc_inventory.jsonl", "kc_id")
    left = keyed(a / "kc/cell_kc_projection.jsonl", "canonical_cell_id")
    right = keyed(b / "kc/cell_kc_projection.jsonl", "canonical_cell_id")
    changed = sorted(key for key in set(left) & set(right) if left[key]["kc_ids"] != right[key]["kc_ids"])
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
        "changed_activations": [
            {"canonical_cell_id": key, "from": left[key]["kc_ids"], "to": right[key]["kc_ids"]}
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
    return {"accepted_count": {"run_a": len(left), "run_b": len(right)}, **changes, "generation": generated, "status_changes": status_changes, "answer_changes": answer_changes}


def qmatrix_stage(a: Path, b: Path) -> dict[str, Any]:
    def edges(run: Path) -> set[tuple[str, str]]:
        filename = run / "qmatrix/item_kc_edges.jsonl"
        return {(row["item_id"], row["kc_id"]) for row in read_jsonl(filename)} if filename.is_file() else set()
    def shape(run: Path) -> tuple[set[str], set[str]]:
        filename = run / "qmatrix/q_matrix.csv"
        if not filename.is_file():
            return set(), set()
        with filename.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        return {row["item_id"] for row in rows}, set(rows[0]) - {"item_id"} if rows else set()
    left, right = edges(a), edges(b)
    rows_a, columns_a = shape(a)
    rows_b, columns_b = shape(b)
    return {
        "shape": {"run_a": [len(rows_a), len(columns_a)], "run_b": [len(rows_b), len(columns_b)]},
        "added_rows": sorted(rows_b - rows_a), "removed_rows": sorted(rows_a - rows_b),
        "added_columns": sorted(columns_b - columns_a), "removed_columns": sorted(columns_a - columns_b),
        "edges": {"run_a": len(left), "run_b": len(right)}, "added_edges": sorted(right - left), "removed_edges": sorted(left - right),
    }


def simulation_stage(a: Path, b: Path) -> dict[str, Any]:
    def summary(run: Path) -> dict[str, Any]:
        filename = run / "simulation/observable_interactions.jsonl"
        rows = read_jsonl(filename) if filename.is_file() else []
        return {
            "interactions": len(rows), "learners": len({row["learner_id"] for row in rows}),
            "items": len({row["item_id"] for row in rows}),
            "correct_rate": statistics.fmean(row["correct"] for row in rows) if rows else None,
            "multi_kc_rows": sum(len(row["kc_ids"]) > 1 for row in rows),
        }
    return {"run_a": summary(a), "run_b": summary(b)}


def kt_stage(a: Path, b: Path) -> dict[str, Any]:
    left = read_json(a / "kt/metrics.json") if (a / "kt/metrics.json").is_file() else {}
    right = read_json(b / "kt/metrics.json") if (b / "kt/metrics.json").is_file() else {}
    result = {"techniques": {"run_a": sorted(left.get("techniques", {})), "run_b": sorted(right.get("techniques", {}))}, "metric_differences": []}
    for technique in sorted(set(left.get("techniques", {})) & set(right.get("techniques", {}))):
        for split in ("validation", "test"):
            for metric in ("auc", "log_loss", "accuracy_at_0_5"):
                before = left["techniques"][technique][split][metric]
                after = right["techniques"][technique][split][metric]
                result["metric_differences"].append({"technique": technique, "split": split, "metric": metric, "run_a": before, "run_b": after, "difference": after - before})
    return result


COMPARATORS: dict[str, Callable[[Path, Path], dict[str, Any]]] = {
    "normalisation": normalisation,
    "canonical": canonical_stage,
    "realisation": realisation_stage,
    "kc": kc_stage,
    "items": item_stage,
    "qmatrix": qmatrix_stage,
    "simulation": simulation_stage,
    "kt": kt_stage,
}


def compare(a: Path, b: Path, stage: str | None = None) -> dict[str, Any]:
    names = [stage] if stage else list(COMPARATORS)
    output = {}
    for name in names:
        try:
            output[name] = COMPARATORS[name](a, b)
        except (FileNotFoundError, KeyError, TypeError) as error:
            output[name] = {"unavailable": str(error)}
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two experimental runs semantically.")
    parser.add_argument("run_a")
    parser.add_argument("run_b")
    parser.add_argument("--stage", choices=tuple(COMPARATORS))
    args = parser.parse_args()
    a, b = run_path(args.run_a), run_path(args.run_b)
    experiment_changes = changed_values(read_yaml(a / "experiment.yaml"), read_yaml(b / "experiment.yaml")) if (a / "experiment.yaml").is_file() and (b / "experiment.yaml").is_file() else []
    print(json.dumps({"run_a": str(a), "run_b": str(b), "experiment_changes": experiment_changes, "comparison": compare(a, b, args.stage)}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
