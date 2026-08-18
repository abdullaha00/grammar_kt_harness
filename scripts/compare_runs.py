#!/usr/bin/env python3
"""Compare two runs at stage-specific semantic levels, never raw tree bytes."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.utils.config import diff_values
from shared.utils.io import read_json, read_jsonl, sha256_file
from shared.utils.research import resolve_run
from shared.utils.stages import STAGES


def _rows(path: Path) -> list[dict[str, Any]]:
    return read_jsonl(path) if path.is_file() else []


def _active_unit_dirs(units: Path) -> list[Path]:
    """Return canonical unit directories, excluding timestamped force backups."""
    if not units.is_dir():
        return []
    return sorted(
        path
        for path in units.iterdir()
        if path.is_dir() and ".backup-" not in path.name
    )


def _normalization_rows(run: Path) -> list[dict[str, Any]]:
    aggregate = run / "normalization/final_mappings.jsonl"
    if aggregate.is_file():
        return read_jsonl(aggregate)
    values = []
    for unit_dir in _active_unit_dirs(run / "normalization/units"):
        path = unit_dir / "result.json"
        if not path.is_file():
            continue
        value = read_json(path)
        values.append(value["final_mapping"])
    return values


def _normalization_unit_evidence(run: Path) -> dict[tuple[str, str], dict[str, Any]]:
    evidence: dict[tuple[str, str], dict[str, Any]] = {}
    units = run / "normalization/units"
    if not units.is_dir():
        return evidence
    for unit_dir in _active_unit_dirs(units):
        for phase_dir in sorted(unit_dir.glob("phase*")):
            if not phase_dir.is_dir():
                continue
            required = [
                phase_dir / "input.json",
                phase_dir / "rendered_prompt.txt",
                phase_dir / "invocation.json",
                phase_dir / "raw_output.txt",
            ]
            if not all(path.is_file() for path in required):
                continue
            input_value = read_json(required[0])
            invocation = read_json(required[2])
            parsed = phase_dir / "parsed_output.json"
            validation = phase_dir / "validation.json"
            key = (input_value["unit_id"], phase_dir.name)
            evidence[key] = {
                "egp_id": input_value["egp_id"],
                "unit_id": input_value["unit_id"],
                "phase": phase_dir.name,
                "rendered_prompt_sha256": sha256_file(required[1]),
                "raw_output_sha256": sha256_file(required[3]),
                "parsed_output_sha256": sha256_file(parsed) if parsed.is_file() else None,
                "validation": read_json(validation) if validation.is_file() else None,
                "invocation": {
                    key: invocation.get(key)
                    for key in (
                        "backend", "model", "reasoning_effort", "reasoning_options",
                        "timeout_seconds", "execution_isolation", "scientific_inputs",
                        "implementation",
                    )
                },
            }
    return evidence


def _record_changes(
    left: list[dict[str, Any]], right: list[dict[str, Any]], key: str
) -> dict[str, Any]:
    a = {row[key]: row for row in left}
    b = {row[key]: row for row in right}
    common = sorted(set(a) & set(b))
    return {
        "added": sorted(set(b) - set(a)),
        "removed": sorted(set(a) - set(b)),
        "changed": [value for value in common if a[value] != b[value]],
    }


def compare_source(a: Path, b: Path) -> dict[str, Any]:
    return _record_changes(_rows(a / "source/source_subset.jsonl"), _rows(b / "source/source_subset.jsonl"), "egp_id")


def compare_normalization(a: Path, b: Path) -> dict[str, Any]:
    left, right = _normalization_rows(a), _normalization_rows(b)
    x = {row["egp_id"]: row for row in left}
    y = {row["egp_id"]: row for row in right}
    common = sorted(set(x) & set(y))
    evidence_a = _normalization_unit_evidence(a)
    evidence_b = _normalization_unit_evidence(b)
    return {
        "counts": {
            "run_a": dict(sorted(Counter(row["result"] for row in left).items())),
            "run_b": dict(sorted(Counter(row["result"] for row in right).items())),
        },
        "added_egp_ids": sorted(set(y) - set(x)),
        "removed_egp_ids": sorted(set(x) - set(y)),
        "result_class_changes": [
            {"egp_id": key, "from": x[key]["result"], "to": y[key]["result"]}
            for key in common if x[key]["result"] != y[key]["result"]
        ],
        "grammar_cell_changes": [
            {"egp_id": key, "from": x[key]["cells"], "to": y[key]["cells"]}
            for key in common if x[key]["cells"] != y[key]["cells"]
        ],
        "note_changes": [key for key in common if x[key].get("note") != y[key].get("note")],
        "model_unit_evidence_changes": [
            {
                "unit_id": key[0],
                "phase": key[1],
                "egp_id": evidence_a.get(key, evidence_b.get(key, {})).get("egp_id"),
                "run_a": evidence_a.get(key),
                "run_b": evidence_b.get(key),
            }
            for key in sorted(set(evidence_a) | set(evidence_b))
            if evidence_a.get(key) != evidence_b.get(key)
        ],
    }


def compare_canonical(a: Path, b: Path) -> dict[str, Any]:
    cells = _record_changes(
        _rows(a / "canonical/canonical_cells.jsonl"),
        _rows(b / "canonical/canonical_cells.jsonl"),
        "canonical_cell_id",
    )
    def edge_map(run: Path) -> dict[tuple[str, int], str]:
        return {
            (row["egp_id"], row["source_cell_index"]): row["canonical_cell_id"]
            for row in _rows(run / "canonical/source_cell_edges.jsonl")
        }
    left, right = edge_map(a), edge_map(b)
    return {
        "cells": cells,
        "source_cell_edges": {
            "added": [list(key) for key in sorted(set(right) - set(left))],
            "removed": [list(key) for key in sorted(set(left) - set(right))],
            "changed": [
                {"source": list(key), "from": left[key], "to": right[key]}
                for key in sorted(set(left) & set(right)) if left[key] != right[key]
            ],
        },
    }


def compare_realization(a: Path, b: Path) -> dict[str, Any]:
    left = _rows(a / "realization/realizations.jsonl")
    right = _rows(b / "realization/realizations.jsonl")
    return {
        "records": _record_changes(
            [{**row, "_id": row["spec"]["realization_id"]} for row in left],
            [{**row, "_id": row["spec"]["realization_id"]} for row in right],
            "_id",
        ),
        "validation_files_changed": _unit_validation_changes(a / "realization/units", b / "realization/units"),
    }


def _unit_validation_changes(a: Path, b: Path) -> list[str]:
    def values(root: Path) -> dict[str, Any]:
        if not root.is_dir():
            return {}
        return {
            path.relative_to(root).as_posix(): read_json(path)
            for unit_dir in _active_unit_dirs(root)
            for path in unit_dir.rglob("validation.json")
        }

    left = values(a)
    right = values(b)
    return sorted(key for key in set(left) | set(right) if left.get(key) != right.get(key))


def _kc_stats(rows: list[dict[str, Any]], inventory: list[dict[str, Any]]) -> dict[str, Any]:
    domains: dict[str, frozenset[str]] = {
        kc: frozenset(row["canonical_cell_id"] for row in rows if kc in row["kc_ids"])
        for kc in (card["kc_id"] for card in inventory)
    }
    identical = sum(
        domains[left] == domains[right]
        for index, left in enumerate(sorted(domains))
        for right in sorted(domains)[index + 1 :]
    )
    widths = [len(row["kc_ids"]) for row in rows]
    return {
        "kcs": len(inventory),
        "opportunities": len(rows),
        "activations": sum(widths),
        "mean_kcs_per_opportunity": statistics.mean(widths) if widths else 0,
        "identical_activation_domain_pairs": identical,
    }


def compare_kc(a: Path, b: Path) -> dict[str, Any]:
    def values(run: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        inventory = _rows(run / "kc/kc_inventory.jsonl")
        projections = _rows(run / "kc/cell_kc_projection.jsonl")
        if not projections:
            for unit_dir in _active_unit_dirs(run / "kc/units"):
                path = unit_dir / "output.json"
                if not path.is_file():
                    continue
                value = read_json(path)
                projections.append(value["projection"])
                inventory.extend(value.get("kc_specs", []))
        inventory = list({row["kc_id"]: row for row in inventory}.values())
        return inventory, projections

    inv_a, proj_a = values(a)
    inv_b, proj_b = values(b)
    x = {row["canonical_cell_id"]: set(row["kc_ids"]) for row in proj_a}
    y = {row["canonical_cell_id"]: set(row["kc_ids"]) for row in proj_b}
    return {
        "inventory": _record_changes(inv_a, inv_b, "kc_id"),
        "activation_changes": [
            {
                "canonical_cell_id": key,
                "gained": sorted(y.get(key, set()) - x.get(key, set())),
                "lost": sorted(x.get(key, set()) - y.get(key, set())),
            }
            for key in sorted(set(x) | set(y)) if x.get(key, set()) != y.get(key, set())
        ],
        "redundancy_statistics": {"run_a": _kc_stats(proj_a, inv_a), "run_b": _kc_stats(proj_b, inv_b)},
    }


def _rejection_categories(run: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in _rows(run / "items/validation/rejected_items.jsonl"):
        for reason in row.get("reasons", []):
            counts[reason.split(":", 1)[0]] += 1
    return counts


def compare_items(a: Path, b: Path) -> dict[str, Any]:
    generated_a = _rows(a / "items/generation/candidate_items.jsonl")
    generated_b = _rows(b / "items/generation/candidate_items.jsonl")
    accepted_a = _rows(a / "items/validation/accepted_items.jsonl")
    accepted_b = _rows(b / "items/validation/accepted_items.jsonl")
    x = {row["item_id"]: row for row in generated_a}
    y = {row["item_id"]: row for row in generated_b}
    common = sorted(set(x) & set(y))
    accepted_x = {row["item_id"] for row in accepted_a}
    accepted_y = {row["item_id"] for row in accepted_b}
    return {
        "generation": _record_changes(generated_a, generated_b, "item_id"),
        "acceptance_changes": {
            "newly_accepted": sorted(accepted_y - accepted_x),
            "no_longer_accepted": sorted(accepted_x - accepted_y),
        },
        "answer_changes": [
            {"item_id": key, "from": x[key]["accepted_answers"], "to": y[key]["accepted_answers"]}
            for key in common if x[key]["accepted_answers"] != y[key]["accepted_answers"]
        ],
        "validation_failure_categories": {
            "run_a": dict(sorted(_rejection_categories(a).items())),
            "run_b": dict(sorted(_rejection_categories(b).items())),
        },
    }


def _q(run: Path) -> tuple[list[str], dict[str, set[str]]]:
    path = run / "qmatrix/q_matrix.csv"
    if not path.is_file():
        return [], {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        columns = (reader.fieldnames or [])[1:]
    return columns, {row["item_id"]: {kc for kc in columns if row[kc] == "1"} for row in rows}


def compare_qmatrix(a: Path, b: Path) -> dict[str, Any]:
    cols_a, rows_a = _q(a)
    cols_b, rows_b = _q(b)
    edges_a = {(row["item_id"], row["kc_id"]) for row in _rows(a / "qmatrix/item_kc_edges.jsonl")}
    edges_b = {(row["item_id"], row["kc_id"]) for row in _rows(b / "qmatrix/item_kc_edges.jsonl")}
    return {
        "columns": {"added": sorted(set(cols_b) - set(cols_a)), "removed": sorted(set(cols_a) - set(cols_b))},
        "rows": {"added": sorted(set(rows_b) - set(rows_a)), "removed": sorted(set(rows_a) - set(rows_b))},
        "changed_rows": [
            {"item_id": key, "gained": sorted(rows_b[key] - rows_a[key]), "lost": sorted(rows_a[key] - rows_b[key])}
            for key in sorted(set(rows_a) & set(rows_b)) if rows_a[key] != rows_b[key]
        ],
        "edges": {
            "added": [list(value) for value in sorted(edges_b - edges_a)],
            "removed": [list(value) for value in sorted(edges_a - edges_b)],
        },
    }


def _simulation_stats(run: Path) -> dict[str, Any]:
    rows = _rows(run / "simulation/observable_interactions.jsonl")
    by_split: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        by_split[row["dataset_split"]].append(row["correct"])
    learners = Counter(row["learner_id"] for row in rows)
    return {
        "interactions": len(rows),
        "learners": len(learners),
        "items": len({row["item_id"] for row in rows}),
        "kcs": len({kc for row in rows for kc in row["kc_ids"]}),
        "events_per_learner": sorted(set(learners.values())),
        "response_rate": sum(row["correct"] for row in rows) / len(rows) if rows else None,
        "response_rate_by_split": {
            split: sum(values) / len(values) for split, values in sorted(by_split.items())
        },
    }


def compare_simulation(a: Path, b: Path) -> dict[str, Any]:
    left, right = _simulation_stats(a), _simulation_stats(b)
    return {"run_a": left, "run_b": right, "differences": diff_values(left, right)}


def compare_kt(a: Path, b: Path) -> dict[str, Any]:
    left_path, right_path = a / "kt/metrics.json", b / "kt/metrics.json"
    left = read_json(left_path) if left_path.is_file() else {}
    right = read_json(right_path) if right_path.is_file() else {}
    return {"run_a": left, "run_b": right, "metric_differences": diff_values(left, right)}


def compare_provenance(a: Path, b: Path) -> dict[str, Any]:
    def counts(run: Path) -> dict[str, int]:
        return dict(sorted(Counter(row["edge_type"] for row in _rows(run / "provenance/provenance_edges.jsonl")).items()))
    left, right = counts(a), counts(b)
    return {"edge_type_counts": {"run_a": left, "run_b": right}, "differences": diff_values(left, right)}


COMPARATORS: dict[str, Callable[[Path, Path], dict[str, Any]]] = {
    "source": compare_source,
    "normalization": compare_normalization,
    "canonical": compare_canonical,
    "realization": compare_realization,
    "kc": compare_kc,
    "items": compare_items,
    "qmatrix": compare_qmatrix,
    "simulation": compare_simulation,
    "kt": compare_kt,
    "provenance": compare_provenance,
}


def _causal_context(a: Path, b: Path, stage: str) -> dict[str, Any]:
    manifest_a, manifest_b = a / stage / "manifest.json", b / stage / "manifest.json"
    if not manifest_a.is_file() or not manifest_b.is_file():
        return {"available": False}
    left, right = read_json(manifest_a), read_json(manifest_b)
    basis_a, basis_b = left.get("fingerprint_basis", {}), right.get("fingerprint_basis", {})
    return {
        "available": bool(basis_a and basis_b),
        "fingerprint_a": left.get("stage_fingerprint"),
        "fingerprint_b": right.get("stage_fingerprint"),
        "configuration_changes": diff_values(basis_a.get("configuration", {}), basis_b.get("configuration", {})),
        "input_hash_changes": diff_values(basis_a.get("inputs", []), basis_b.get("inputs", [])),
        "scientific_resource_hash_changes": diff_values(
            basis_a.get("scientific_resources", []), basis_b.get("scientific_resources", [])
        ),
        "implementation_hash_changes": diff_values(
            basis_a.get("implementation", []), basis_b.get("implementation", [])
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_a")
    parser.add_argument("run_b")
    parser.add_argument("--stage", choices=STAGES)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    a, b = resolve_run(args.run_a), resolve_run(args.run_b)
    config_a = read_json(a / "experiment_manifest.json").get("resolved_config", {})
    config_b = read_json(b / "experiment_manifest.json").get("resolved_config", {})
    stages = [args.stage] if args.stage else list(STAGES)
    scientific_changes = [
        change
        for change in diff_values(config_a, config_b)
        if change["path"] != "experiment_id"
    ]
    result = {
        "run_a": str(a),
        "run_b": str(b),
        "experiment_ids": {
            "run_a": config_a.get("experiment_id"),
            "run_b": config_b.get("experiment_id"),
        },
        "experiment_configuration_changes": scientific_changes,
        "stages": {
            stage: {
                "semantic_comparison": COMPARATORS[stage](a, b),
                "causal_context": _causal_context(a, b, stage),
            }
            for stage in stages
        },
        "interpretation": "Stochastic stages are compared by structure and statistics, not byte identity.",
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
