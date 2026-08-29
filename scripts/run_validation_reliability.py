#!/usr/bin/env python3
"""Measure repeat and model sensitivity of the Phase-4 item validator.

This script consumes a *completed* live item-audit pilot.  It chooses a
deterministic sample while oversampling rejected items, assigns fresh neutral
IDs, and independently rejudges the same visible content with the original
validator model and a second model.  Original generation metadata is never
included in either rejudgment prompt.

The script is deliberately separate from the active validation stage: this is
an audit of that stage, not an ensemble acceptance rule.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.io import (
    call_model,
    read_jsonl,
    read_text,
    read_yaml,
    write_json,
    write_jsonl,
)
from scripts.run_item_audit import validate_one_blinded


DEFAULT_INPUT = ROOT / "reports/phase4/artifacts/item_audit/live_pilot"
DEFAULT_OUTPUT = ROOT / "reports/phase4/artifacts/validation_reliability"
VALIDATION_PROMPT = ROOT / "modules/items/validation/prompt.txt"
VALIDATION_CRITERIA = ROOT / "modules/items/validation/criteria.yaml"

SAMPLE_SEED = 20260827
DEFAULT_SAMPLE_SIZE = 24
DEFAULT_QUALITATIVE_SIZE = 6
DEFAULT_MODELS = (
    ("terra_repeat", "gpt-5.6-terra"),
    ("sol_sensitivity", "gpt-5.6-sol"),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_completed_live_input(input_dir: Path) -> dict[str, Any]:
    """Fail clearly unless all expected live-pilot artifacts are complete."""

    required = (
        "manifest.json",
        "summary.json",
        "frozen_cells.jsonl",
        "candidates.jsonl",
        "generation_attempts.jsonl",
        "validation.jsonl",
    )
    missing = [name for name in required if not (input_dir / name).is_file()]
    if missing:
        raise RuntimeError(
            "live item-audit input is incomplete; wait for run_item_audit.py "
            f"to finish. Missing: {', '.join(missing)}"
        )

    manifest = json.loads((input_dir / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((input_dir / "summary.json").read_text(encoding="utf-8"))
    if manifest.get("artifact_status") != "live_model_evidence" or not manifest.get(
        "scientific_evidence"
    ):
        raise RuntimeError("input must be the completed live-model item audit")

    attempts = read_jsonl(input_dir / "generation_attempts.jsonl")
    candidates = read_jsonl(input_dir / "candidates.jsonl")
    validation = read_jsonl(input_dir / "validation.jsonl")
    planned = int(manifest["planned_generation_calls"])
    if len(attempts) != planned:
        raise RuntimeError(
            f"live item-audit input is incomplete: {len(attempts)}/{planned} "
            "generation attempts"
        )
    if len(candidates) != int(summary["structurally_valid_candidates"]):
        raise RuntimeError("candidate count disagrees with the live summary")
    if len(validation) != len(candidates):
        raise RuntimeError(
            f"live item-audit input is incomplete: {len(validation)}/"
            f"{len(candidates)} candidates have validation rows"
        )
    candidate_ids = {row["item_id"] for row in candidates}
    validation_ids = {row["candidate_id"] for row in validation}
    if candidate_ids != validation_ids:
        raise RuntimeError("candidate and validation IDs do not match exactly")
    return {"manifest": manifest, "summary": summary}


def _failed_criteria(row: dict[str, Any]) -> set[str]:
    return {
        name
        for name, judgment in row["judgments"].items()
        if not judgment["passed"]
    }


def select_reliability_sample(
    validation: list[dict[str, Any]],
    *,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    seed: int = SAMPLE_SEED,
) -> list[dict[str, Any]]:
    """Select a deterministic, outcome-balanced and structurally diverse sample.

    Invalid model outputs cannot support criterion agreement and are excluded.
    When both outcomes exist, up to half the sample is reserved for rejections;
    this deliberately oversamples failures relative to their bank prevalence.
    Within each outcome, greedy coverage favours conditions, failure criteria,
    and cells that have not yet appeared.
    """

    eligible = [row for row in validation if row["validator_output_valid"]]
    if not eligible:
        raise ValueError("no valid original validator outputs are available")
    if sample_size <= 0:
        raise ValueError("sample_size must be positive")
    sample_size = min(sample_size, len(eligible))

    by_outcome = {
        outcome: [row for row in eligible if bool(row["accepted"]) is outcome]
        for outcome in (False, True)
    }
    if by_outcome[False] and by_outcome[True]:
        reject_n = min(len(by_outcome[False]), sample_size // 2)
        accept_n = min(len(by_outcome[True]), sample_size - reject_n)
        unused = sample_size - reject_n - accept_n
        if unused:
            reject_n += min(unused, len(by_outcome[False]) - reject_n)
            unused = sample_size - reject_n - accept_n
            accept_n += min(unused, len(by_outcome[True]) - accept_n)
    else:
        reject_n = min(sample_size, len(by_outcome[False]))
        accept_n = sample_size - reject_n

    rng = random.Random(seed)
    stable_tiebreak = list(range(len(eligible)))
    rng.shuffle(stable_tiebreak)
    tiebreak = {
        row["candidate_id"]: rank
        for rank, row in zip(stable_tiebreak, sorted(eligible, key=lambda x: x["candidate_id"]))
    }

    def choose(pool: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
        remaining = list(pool)
        chosen: list[dict[str, Any]] = []
        conditions: set[str] = set()
        cells: set[str] = set()
        failures: set[str] = set()
        while remaining and len(chosen) < count:
            def score(row: dict[str, Any]) -> tuple[int, int, int, int]:
                row_failures = _failed_criteria(row)
                return (
                    int(row["condition"] not in conditions),
                    len(row_failures - failures),
                    int(row["cell_id"] not in cells),
                    -tiebreak[row["candidate_id"]],
                )

            best = max(remaining, key=score)
            remaining.remove(best)
            chosen.append(best)
            conditions.add(best["condition"])
            cells.add(best["cell_id"])
            failures.update(_failed_criteria(best))
        return chosen

    selected = choose(by_outcome[False], reject_n) + choose(
        by_outcome[True], accept_n
    )
    rng.shuffle(selected)
    return [{**row, "sample_order": index} for index, row in enumerate(selected, 1)]


def _wilson_interval(successes: int, total: int) -> list[float] | None:
    if not total:
        return None
    z = 1.959963984540054
    estimate = successes / total
    denominator = 1.0 + z * z / total
    centre = (estimate + z * z / (2.0 * total)) / denominator
    margin = (
        z
        * math.sqrt(
            estimate * (1.0 - estimate) / total + z * z / (4.0 * total * total)
        )
        / denominator
    )
    return [centre - margin, centre + margin]


def _binary_agreement(reference: list[bool], comparison: list[bool]) -> dict[str, Any]:
    if len(reference) != len(comparison):
        raise ValueError("agreement vectors must have equal length")
    total = len(reference)
    both_pass = sum(left and right for left, right in zip(reference, comparison))
    both_fail = sum(not left and not right for left, right in zip(reference, comparison))
    reference_only = sum(left and not right for left, right in zip(reference, comparison))
    comparison_only = sum(not left and right for left, right in zip(reference, comparison))
    agreements = both_pass + both_fail

    if not total:
        kappa = None
    else:
        observed = agreements / total
        reference_rate = sum(reference) / total
        comparison_rate = sum(comparison) / total
        expected = (
            reference_rate * comparison_rate
            + (1.0 - reference_rate) * (1.0 - comparison_rate)
        )
        kappa = (observed - expected) / (1.0 - expected) if expected < 1.0 else None

    positive_denominator = 2 * both_pass + reference_only + comparison_only
    negative_denominator = 2 * both_fail + reference_only + comparison_only
    return {
        "n": total,
        "agreement_count": agreements,
        "agreement_rate": agreements / total if total else None,
        "agreement_wilson_95": _wilson_interval(agreements, total),
        "both_pass": both_pass,
        "both_fail": both_fail,
        "reference_pass_comparison_fail": reference_only,
        "reference_fail_comparison_pass": comparison_only,
        "positive_agreement": (
            2 * both_pass / positive_denominator if positive_denominator else None
        ),
        "negative_agreement": (
            2 * both_fail / negative_denominator if negative_denominator else None
        ),
        "cohen_kappa": kappa,
    }


def comparison_metrics(
    reference: list[dict[str, Any]],
    comparison: list[dict[str, Any]],
    criteria: list[str],
) -> dict[str, Any]:
    """Compare two judges over exactly matched, valid candidate judgments."""

    reference_by_id = {row["candidate_id"]: row for row in reference}
    comparison_by_id = {row["candidate_id"]: row for row in comparison}
    common = sorted(reference_by_id.keys() & comparison_by_id.keys())
    valid = [
        candidate_id
        for candidate_id in common
        if reference_by_id[candidate_id]["validator_output_valid"]
        and comparison_by_id[candidate_id]["validator_output_valid"]
    ]
    missing = sorted(reference_by_id.keys() ^ comparison_by_id.keys())

    overall = _binary_agreement(
        [bool(reference_by_id[candidate_id]["accepted"]) for candidate_id in valid],
        [bool(comparison_by_id[candidate_id]["accepted"]) for candidate_id in valid],
    )
    per_criterion = {}
    for criterion in criteria:
        per_criterion[criterion] = _binary_agreement(
            [
                bool(reference_by_id[candidate_id]["judgments"][criterion]["passed"])
                for candidate_id in valid
            ],
            [
                bool(comparison_by_id[candidate_id]["judgments"][criterion]["passed"])
                for candidate_id in valid
            ],
        )
    return {
        "reference_rows": len(reference),
        "comparison_rows": len(comparison),
        "joint_valid_rows": len(valid),
        "missing_or_extra_candidate_ids": missing,
        "overall_accept": overall,
        "criteria": per_criterion,
    }


def criterion_overlap(
    rows: list[dict[str, Any]], criteria: list[str]
) -> dict[str, Any]:
    """Report failure overlap without conflating shared passes with redundancy."""

    valid = [row for row in rows if row["validator_output_valid"]]
    failure_vectors = {
        criterion: tuple(
            not bool(row["judgments"][criterion]["passed"]) for row in valid
        )
        for criterion in criteria
    }
    pairs = []
    for left_index, left in enumerate(criteria):
        for right in criteria[left_index + 1 :]:
            left_vector = failure_vectors[left]
            right_vector = failure_vectors[right]
            both_fail = sum(a and b for a, b in zip(left_vector, right_vector))
            either_fail = sum(a or b for a, b in zip(left_vector, right_vector))
            left_fail = sum(left_vector)
            right_fail = sum(right_vector)
            pairs.append(
                {
                    "criterion_a": left,
                    "criterion_b": right,
                    "a_failures": left_fail,
                    "b_failures": right_fail,
                    "both_fail": both_fail,
                    "either_fail": either_fail,
                    "failure_jaccard": (
                        both_fail / either_fail if either_fail else None
                    ),
                    "p_b_failure_given_a_failure": (
                        both_fail / left_fail if left_fail else None
                    ),
                    "p_a_failure_given_b_failure": (
                        both_fail / right_fail if right_fail else None
                    ),
                    "decision_agreement": (
                        sum(a == b for a, b in zip(left_vector, right_vector))
                        / len(valid)
                        if valid
                        else None
                    ),
                    "failure_vectors_identical": left_vector == right_vector,
                    "informative_equivalence": (
                        left_vector == right_vector and any(left_vector)
                    ),
                }
            )

    groups: dict[tuple[bool, ...], list[str]] = {}
    for criterion, vector in failure_vectors.items():
        groups.setdefault(vector, []).append(criterion)
    equivalent_groups = [
        {
            "criteria": names,
            "failure_count": sum(vector),
            "informative": any(vector),
        }
        for vector, names in groups.items()
        if len(names) > 1
    ]
    return {
        "valid_rows": len(valid),
        "failure_counts": {
            criterion: sum(vector) for criterion, vector in failure_vectors.items()
        },
        "pairwise": pairs,
        "identical_failure_vector_groups": equivalent_groups,
        "interpretation_boundary": (
            "Exact equivalence with zero failures is uninformative: it may reflect "
            "a ceiling effect rather than redundant validation criteria."
        ),
    }


def choose_qualitative_sample(
    original: list[dict[str, Any]],
    rejudgments: dict[str, list[dict[str, Any]]],
    *,
    sample_size: int = DEFAULT_QUALITATIVE_SIZE,
) -> list[str]:
    """Declare a small review set prioritising disagreements and diversity."""

    original_by_id = {row["candidate_id"]: row for row in original}
    rejudgment_maps = {
        name: {row["candidate_id"]: row for row in rows}
        for name, rows in rejudgments.items()
    }
    scored = []
    for candidate_id, baseline in original_by_id.items():
        disagreement = 0
        criterion_names = list(baseline["judgments"])
        for mapping in rejudgment_maps.values():
            row = mapping.get(candidate_id)
            if row and row["validator_output_valid"]:
                disagreement += int(
                    bool(row["accepted"]) != bool(baseline["accepted"])
                )
                disagreement += sum(
                    bool(row["judgments"][name]["passed"])
                    != bool(baseline["judgments"][name]["passed"])
                    for name in criterion_names
                )
        scored.append((disagreement, candidate_id, baseline))

    selected: list[str] = []
    conditions: set[str] = set()
    cells: set[str] = set()
    outcomes: set[bool] = set()
    remaining = scored
    while remaining and len(selected) < min(sample_size, len(scored)):
        best = max(
            remaining,
            key=lambda value: (
                value[0],
                int(value[2]["condition"] not in conditions),
                int(value[2]["cell_id"] not in cells),
                int(bool(value[2]["accepted"]) not in outcomes),
                value[1],
            ),
        )
        remaining.remove(best)
        selected.append(best[1])
        conditions.add(best[2]["condition"])
        cells.add(best[2]["cell_id"])
        outcomes.add(bool(best[2]["accepted"]))
    return selected


def _make_blinded_sample(
    sample: list[dict[str, Any]], candidates: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_by_id = {row["item_id"]: row for row in candidates}
    blinded = []
    mapping = []
    for index, sample_row in enumerate(sample, 1):
        candidate = candidate_by_id[sample_row["candidate_id"]]
        blind_id = f"reliability_item_{index:04d}"
        blinded.append(
            {
                "item_id": blind_id,
                "cell_id": candidate["cell_id"],
                "format": candidate["format"],
                "prompt": candidate["prompt"],
                "target_answer": candidate["target_answer"],
                "accepted_answers": candidate["accepted_answers"],
            }
        )
        mapping.append(
            {
                "sample_order": index,
                "blind_item_id": blind_id,
                "candidate_id": candidate["item_id"],
                "condition": sample_row["condition"],
                "cell_id": sample_row["cell_id"],
                "candidate_index": sample_row["candidate_index"],
                "original_accepted": sample_row["accepted"],
                "original_failed_criteria": sorted(_failed_criteria(sample_row)),
            }
        )
    return blinded, mapping


def _parallel_map(
    values: list[dict[str, Any]],
    function: Callable[[dict[str, Any]], dict[str, Any]],
    workers: int,
) -> list[dict[str, Any]]:
    if workers <= 1:
        return [function(value) for value in values]
    output = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(function, value): value for value in values}
        for future in as_completed(futures):
            output.append(future.result())
    return output


def run_reliability(arguments: argparse.Namespace) -> dict[str, Any]:
    arguments.input_dir = arguments.input_dir.resolve()
    arguments.output_dir = arguments.output_dir.resolve()
    input_status = verify_completed_live_input(arguments.input_dir)
    candidates = read_jsonl(arguments.input_dir / "candidates.jsonl")
    original_validation = read_jsonl(arguments.input_dir / "validation.jsonl")
    cells = read_jsonl(arguments.input_dir / "frozen_cells.jsonl")
    cells_by_id = {row["cell_id"]: row for row in cells}
    criteria_config = read_yaml(VALIDATION_CRITERIA)
    criteria = list(criteria_config["criteria"])
    prompt = read_text(VALIDATION_PROMPT)

    sample = select_reliability_sample(
        original_validation,
        sample_size=arguments.sample_size,
        seed=arguments.seed,
    )
    blinded, mapping = _make_blinded_sample(sample, candidates)
    mapping_by_blind = {row["blind_item_id"]: row for row in mapping}
    sampled_ids = {row["candidate_id"] for row in mapping}
    original_sample = [
        row for row in original_validation if row["candidate_id"] in sampled_ids
    ]

    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(arguments.output_dir / "sample_mapping.jsonl", mapping)
    write_jsonl(arguments.output_dir / "blinded_items.jsonl", blinded)
    write_jsonl(arguments.output_dir / "original_judgments.jsonl", original_sample)

    model_declarations = [
        ("terra_repeat", arguments.repeat_model),
        ("sol_sensitivity", arguments.sensitivity_model),
    ]
    manifest = {
        "experiment": "phase4_validation_reliability",
        "date": date.today().isoformat(),
        "artifact_status": "live_model_evidence",
        "scientific_evidence": True,
        "role": "validator audit; rejudgments do not change item acceptance",
        "input": str(arguments.input_dir.relative_to(ROOT)),
        "input_manifest_sha256": _sha256(arguments.input_dir / "manifest.json"),
        "input_validation_sha256": _sha256(arguments.input_dir / "validation.jsonl"),
        "sample_seed": arguments.seed,
        "requested_sample_size": arguments.sample_size,
        "actual_sample_size": len(sample),
        "sampling": (
            "valid outputs only; rejected items oversampled to at most half; "
            "greedy condition, failed-criterion, and cell coverage"
        ),
        "models": {
            name: {"model": model, "reasoning_effort": arguments.reasoning_effort}
            for name, model in model_declarations
        },
        "original_validator": input_status["manifest"]["models"]["validation"],
        "criteria": criteria,
        "exact_command": " ".join([sys.executable, *sys.argv]),
    }
    manifest_path = arguments.output_dir / "manifest.json"
    if manifest_path.is_file() and any(
        arguments.output_dir.glob("*/results/*.json")
    ):
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        resume_keys = (
            "input_manifest_sha256",
            "input_validation_sha256",
            "sample_seed",
            "actual_sample_size",
            "models",
            "criteria",
        )
        changed = [key for key in resume_keys if previous.get(key) != manifest.get(key)]
        if changed:
            raise RuntimeError(
                "output contains model-call checkpoints from an incompatible run; "
                f"use a new output directory. Changed: {', '.join(changed)}"
            )
    write_json(manifest_path, manifest)

    all_rejudgments: dict[str, list[dict[str, Any]]] = {}
    for label, model in model_declarations:
        result_dir = arguments.output_dir / label / "results"
        result_dir.mkdir(parents=True, exist_ok=True)

        def retain_call_error(blind_item: dict[str, Any], row: dict[str, Any]) -> None:
            if row["validator_output_valid"]:
                return
            # The shared model helper parses before it writes call evidence.
            # Retain the recoverable failure information explicitly even though
            # malformed raw stdout is unavailable at this boundary.
            write_json(
                arguments.output_dir
                / label
                / "evidence"
                / "calls"
                / blind_item["item_id"]
                / "call_error.json",
                {
                    "model": model,
                    "reasoning_effort": arguments.reasoning_effort,
                    "errors": row["validation_errors"],
                    "raw_output_retained": False,
                    "reason": (
                        "shared call_model parses JSON before evidence writing; "
                        "the blinded input remains in blinded_items.jsonl"
                    ),
                },
            )

        def judge(blind_item: dict[str, Any]) -> dict[str, Any]:
            result_path = result_dir / f"{blind_item['item_id']}.json"
            if result_path.is_file():
                cached = json.loads(result_path.read_text(encoding="utf-8"))
                retain_call_error(blind_item, cached)
                return cached
            judgment = validate_one_blinded(
                blind_item,
                cells_by_id=cells_by_id,
                prompt=prompt,
                validation_criteria=criteria_config,
                model=model,
                reasoning_effort=arguments.reasoning_effort,
                model_call=call_model,
                evidence_dir=arguments.output_dir / label / "evidence",
            )
            mapped = {**mapping_by_blind[blind_item["item_id"]], **judgment}
            retain_call_error(blind_item, mapped)
            write_json(result_path, mapped)
            return mapped

        rows = _parallel_map(blinded, judge, arguments.workers)
        rows.sort(key=lambda row: row["sample_order"])
        write_jsonl(arguments.output_dir / f"{label}_judgments.jsonl", rows)
        all_rejudgments[label] = rows

    comparisons = {
        "original_vs_terra_repeat": comparison_metrics(
            original_sample, all_rejudgments["terra_repeat"], criteria
        ),
        "original_vs_sol_sensitivity": comparison_metrics(
            original_sample, all_rejudgments["sol_sensitivity"], criteria
        ),
        "terra_repeat_vs_sol_sensitivity": comparison_metrics(
            all_rejudgments["terra_repeat"],
            all_rejudgments["sol_sensitivity"],
            criteria,
        ),
    }
    overlap = {
        "original_full_bank": criterion_overlap(original_validation, criteria),
        "original": criterion_overlap(original_sample, criteria),
        **{
            label: criterion_overlap(rows, criteria)
            for label, rows in all_rejudgments.items()
        },
    }
    qualitative_ids = choose_qualitative_sample(original_sample, all_rejudgments)
    candidate_by_id = {row["item_id"]: row for row in candidates}
    original_by_id = {row["candidate_id"]: row for row in original_sample}
    rejudgment_maps = {
        label: {row["candidate_id"]: row for row in rows}
        for label, rows in all_rejudgments.items()
    }
    qualitative = []
    for candidate_id in qualitative_ids:
        candidate = candidate_by_id[candidate_id]
        qualitative.append(
            {
                "candidate_id": candidate_id,
                "condition": original_by_id[candidate_id]["condition"],
                "cell_id": candidate["cell_id"],
                "cell_features": cells_by_id[candidate["cell_id"]]["features"],
                "visible_item": {
                    key: candidate[key]
                    for key in (
                        "format",
                        "prompt",
                        "target_answer",
                        "accepted_answers",
                    )
                },
                "judgments": {
                    "original": original_by_id[candidate_id],
                    **{
                        label: mapping[candidate_id]
                        for label, mapping in rejudgment_maps.items()
                    },
                },
                "review_status": "declared_for_research_agent_review_not_human_validation",
            }
        )
    write_jsonl(arguments.output_dir / "qualitative_sample.jsonl", qualitative)

    summary = {
        "artifact_status": "live_model_evidence",
        "sample": {
            "n": len(sample),
            "original_accepted": sum(row["accepted"] for row in original_sample),
            "original_rejected": sum(not row["accepted"] for row in original_sample),
            "conditions": {
                condition: sum(row["condition"] == condition for row in original_sample)
                for condition in sorted({row["condition"] for row in original_sample})
            },
            "cells": len({row["cell_id"] for row in original_sample}),
            "original_failure_counts": overlap["original"]["failure_counts"],
        },
        "valid_rejudgments": {
            label: sum(row["validator_output_valid"] for row in rows)
            for label, rows in all_rejudgments.items()
        },
        "comparisons": comparisons,
        "criterion_overlap": overlap,
        "qualitative_sample_n": len(qualitative),
        "interpretation_boundary": (
            "This is model repeat/model sensitivity evidence on an enriched small "
            "sample. It is not human validation, and rejudgments do not determine "
            "active item-bank acceptance."
        ),
    }
    write_json(arguments.output_dir / "summary.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit repeatability and model sensitivity of item validation."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--seed", type=int, default=SAMPLE_SEED)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--repeat-model", default=DEFAULT_MODELS[0][1])
    parser.add_argument("--sensitivity-model", default=DEFAULT_MODELS[1][1])
    parser.add_argument("--reasoning-effort", default="medium")
    arguments = parser.parse_args()
    if shutil.which("codex") is None:
        parser.error("codex CLI is unavailable; live rejudgment cannot run")
    return arguments


def main() -> int:
    arguments = parse_args()
    summary = run_reliability(arguments)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
