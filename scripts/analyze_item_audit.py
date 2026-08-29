#!/usr/bin/env python3
"""Derive compact Phase-4 item-audit diagnostics without model calls."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.io import read_jsonl, read_yaml, write_json
from grammar_kt.kc import activation_matches


def _timing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [float(row["runtime_seconds"]) for row in rows]
    return {
        "calls": len(values),
        "summed_call_seconds": sum(values),
        "median_call_seconds": statistics.median(values) if values else 0.0,
    }


def _prefix_rows(
    rows: list[dict[str, Any]], condition: str, cell_ids: set[str], n: int
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row["condition"] == condition
        and row["cell_id"] in cell_ids
        and row["candidate_index"] <= n
    ]


def _matched_condition(
    condition: str,
    cell_ids: set[str],
    attempts: list[dict[str, Any]],
    validation: list[dict[str, Any]],
) -> dict[str, Any]:
    condition_attempts = _prefix_rows(attempts, condition, cell_ids, 3)
    condition_validation = _prefix_rows(validation, condition, cell_ids, 3)
    accepted = [row for row in condition_validation if row["accepted"]]
    accepted_by_cell = Counter(row["cell_id"] for row in accepted)
    return {
        "planned_attempts": len(condition_attempts),
        "structurally_valid_candidates": sum(
            row["structurally_valid"] for row in condition_attempts
        ),
        "valid_validator_outputs": sum(
            row["validator_output_valid"] for row in condition_validation
        ),
        "accepted_candidates": len(accepted),
        "end_to_end_acceptance_rate": (
            len(accepted) / len(condition_attempts) if condition_attempts else 0.0
        ),
        "covered_cells": len(accepted_by_cell),
        "accepted_count_by_cell": dict(sorted(accepted_by_cell.items())),
    }


def _accepted_variant_support(
    validation: list[dict[str, Any]], condition: str, maximum_n: int
) -> dict[str, Any]:
    accepted_by_cell = Counter(
        row["cell_id"]
        for row in validation
        if row["condition"] == condition
        and row["candidate_index"] <= maximum_n
        and row["accepted"]
    )
    eligible_cells = sorted(
        {
            row["cell_id"]
            for row in validation
            if row["condition"] == condition
            and row["candidate_index"] <= maximum_n
        }
    )
    counts = {cell_id: accepted_by_cell[cell_id] for cell_id in eligible_cells}
    at_least_two = [cell_id for cell_id, count in counts.items() if count >= 2]
    return {
        "maximum_n": maximum_n,
        "accepted_count_by_cell": counts,
        "cells_with_any_accepted": sum(count > 0 for count in counts.values()),
        "cells_with_at_least_two_accepted": at_least_two,
        "at_least_two_count": len(at_least_two),
        "at_least_two_rate": len(at_least_two) / len(counts) if counts else 0.0,
    }


def _criterion_failures(validation: list[dict[str, Any]]) -> dict[str, Any]:
    individual: Counter[str] = Counter()
    combinations: Counter[tuple[str, ...]] = Counter()
    by_condition: dict[str, Counter[str]] = {}
    rejected = 0
    for row in validation:
        if row["accepted"] or not row["validator_output_valid"]:
            continue
        rejected += 1
        failed = tuple(
            name for name, judgment in row["judgments"].items() if not judgment["passed"]
        )
        combinations[failed] += 1
        individual.update(failed)
        by_condition.setdefault(row["condition"], Counter()).update(failed)
    return {
        "rejected_candidates": rejected,
        "criterion_failure_counts": dict(individual),
        "failure_combination_counts": {
            " + ".join(names): count for names, count in combinations.items()
        },
        "criterion_failure_counts_by_condition": {
            condition: dict(counts) for condition, counts in sorted(by_condition.items())
        },
    }


def _operation_tag_agreement(
    candidates: list[dict[str, Any]], cells: list[dict[str, Any]]
) -> dict[str, Any]:
    deterministic = read_yaml(
        ROOT / "data/fixtures/historical/english_generator_tag_rules.yaml"
    )["tag_rules"]
    tag_universe = {row["generator_tag"] for row in deterministic}
    cells_by_id = {row["cell_id"]: row["features"] for row in cells}
    missing: Counter[str] = Counter()
    unexpected: Counter[str] = Counter()
    exact = 0
    mismatches = []
    for candidate in candidates:
        features = cells_by_id[candidate["cell_id"]]
        expected = {
            row["generator_tag"]
            for row in deterministic
            if activation_matches(features, row["activation"])
        }
        reported = set(candidate["operation_tags"]) & tag_universe
        missing.update(expected - reported)
        unexpected.update(reported - expected)
        agrees = expected == reported
        exact += agrees
        if not agrees:
            mismatches.append(
                {
                    "candidate_id": candidate["item_id"],
                    "expected_deterministic_tags": sorted(expected),
                    "reported_deterministic_tags": sorted(reported),
                }
            )
    return {
        "comparison_scope": (
            "Only generator tags with cell-deterministic declarations are compared; "
            "realisation-dependent tags such as do_support are ignored."
        ),
        "candidates": len(candidates),
        "exact_matches": exact,
        "exact_match_rate": exact / len(candidates) if candidates else 0.0,
        "missing_expected_tag_counts": dict(missing),
        "unexpected_deterministic_tag_counts": dict(unexpected),
        "mismatches": mismatches,
    }


def derive_diagnostics(run_dir: Path) -> dict[str, Any]:
    manifest = json.loads((run_dir / "manifest.json").read_text())
    attempts = read_jsonl(run_dir / "generation_attempts.jsonl")
    candidates = read_jsonl(run_dir / "candidates.jsonl")
    validation = read_jsonl(run_dir / "validation.jsonl")
    cells = read_jsonl(run_dir / "frozen_cells.jsonl")

    matched_cells = set(manifest["recoverable_readable_source_cells"])
    model_selected = _matched_condition(
        "model_selected", matched_cells, attempts, validation
    )
    readable_source = _matched_condition(
        "readable_source_evidence", matched_cells, attempts, validation
    )
    matched_delta = {
        name: readable_source[name] - model_selected[name]
        for name in (
            "structurally_valid_candidates",
            "accepted_candidates",
            "end_to_end_acceptance_rate",
            "covered_cells",
        )
    }
    per_cell_delta = {
        cell_id: (
            readable_source["accepted_count_by_cell"].get(cell_id, 0)
            - model_selected["accepted_count_by_cell"].get(cell_id, 0)
        )
        for cell_id in sorted(matched_cells)
    }

    return {
        "artifact_status": manifest["artifact_status"],
        "derivation": "offline analysis of frozen outputs; no model calls",
        "matched_readable_source_vs_model_selected_n3": {
            "matched_cell_ids": sorted(matched_cells),
            "model_selected": model_selected,
            "readable_source_evidence": readable_source,
            "source_minus_model_selected": {
                **matched_delta,
                "accepted_count_by_cell": per_cell_delta,
            },
            "interpretation_limit": (
                "One stochastic eight-cell pilot with only three matched source cells; "
                "equal aggregate acceptance is not evidence of equivalence or no effect."
            ),
        },
        "accepted_variant_support": {
            "model_selected": _accepted_variant_support(
                validation, "model_selected", 5
            ),
            "controlled_lexicon": _accepted_variant_support(
                validation, "controlled_lexicon", 5
            ),
            "readable_source_evidence": _accepted_variant_support(
                validation, "readable_source_evidence", 3
            ),
        },
        "criterion_failures": _criterion_failures(validation),
        "cell_deterministic_operation_tag_agreement": _operation_tag_agreement(
            candidates, cells
        ),
        "call_runtime": {
            "interpretation": (
                "Summed call duration is compute/wait time across concurrent calls, "
                "not experiment wall-clock duration."
            ),
            "generation": _timing(attempts),
            "validation": _timing(validation),
            "generation_by_condition": {
                condition: _timing(
                    [row for row in attempts if row["condition"] == condition]
                )
                for condition in ("model_selected", "controlled_lexicon", "readable_source_evidence")
            },
            "validation_by_condition": {
                condition: _timing(
                    [row for row in validation if row["condition"] == condition]
                )
                for condition in ("model_selected", "controlled_lexicon", "readable_source_evidence")
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    arguments = parser.parse_args()
    diagnostics = derive_diagnostics(arguments.run_dir)
    target = arguments.run_dir / "derived_diagnostics.json"
    write_json(target, diagnostics)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
