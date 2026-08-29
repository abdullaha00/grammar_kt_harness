#!/usr/bin/env python3
"""Merge blind reviews and select backend effort for BACKEND-THINKING-001.

The live-call procedure deliberately keeps condition identities out of the
review packets.  This script is the only place where the two frozen reviewer
files are joined to those private identities.  It keeps disagreements as
interval-valued evidence, compares matched calls with a unit-clustered
bootstrap, and applies the selection rule frozen in the experiment manifest.

Expected review files (whichever modules have completed) are::

    reviews/reviewer_a_normalisation.jsonl
    reviews/reviewer_b_normalisation.jsonl
    reviews/reviewer_a_validation.jsonl
    reviews/reviewer_b_validation.jsonl
    reviews/reviewer_a_generation.jsonl
    reviews/reviewer_b_generation.jsonl

No setting is reported as selected until its module has complete calls,
complete paired reviews, the required safety evidence, and a robust
non-inferiority result.  "Selected" means selected by the frozen
quality/parsimony rule; it is not a claim of statistical superiority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import mean, median
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "reports/backend_thinking/artifacts/live_v1"
EFFORTS = ("medium", "high", "xhigh")
SEED = 20260828
BOOTSTRAP_REPLICATES = 10_000

REVIEW_FILES = {
    module: {
        reviewer: f"reviewer_{reviewer}_{module}.jsonl"
        for reviewer in ("a", "b")
    }
    for module in ("normalisation", "validation", "generation")
}
REVIEW_INPUTS = {
    "normalisation": "review_packets/normalisation_outputs.jsonl",
    "validation": "review_packets/validation_items.jsonl",
    "generation": "review_packets/generation_position1.jsonl",
}
ADJUDICATOR_FILES = {
    module: f"adjudicator_{module}.jsonl"
    for module in ("normalisation", "validation", "generation")
}
PRIVATE_MAPS = {
    "normalisation": "private_mappings/normalisation_review_map.jsonl",
    "validation": "private_mappings/validation_review_map.jsonl",
    "generation": "private_mappings/generation_review_map.jsonl",
}
POSITIVE_DECISION = {
    "normalisation": "acceptable",
    "validation": "accept",
    "generation": "accept",
}
NEGATIVE_DECISION = {
    "normalisation": "incorrect",
    "validation": "reject",
    "generation": "reject",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _stable(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _mapping_signature(mapping: dict[str, Any] | None) -> str | None:
    """Compare mapping structure while ignoring note prose and list order."""

    if mapping is None:
        return None
    cells = []
    for cell in mapping.get("cells", []):
        cells.append(
            {
                name: sorted(value) if isinstance(value, list) else value
                for name, value in sorted(cell.items())
            }
        )
    return _stable(
        {
            "result": mapping.get("result"),
            "cells": sorted(_stable(cell) for cell in cells),
            "phase2_eligible": sorted(mapping.get("phase2_eligible", [])),
        }
    )


def _review_score(module: str, decision: str) -> int | None:
    if decision == POSITIVE_DECISION[module]:
        return 1
    if decision == NEGATIVE_DECISION[module]:
        return 0
    if decision == "uncertain":
        return None
    raise ValueError(f"unexpected {module} review decision: {decision!r}")


def _validate_review_rows(
    module: str,
    reviewer: str,
    rows: list[dict[str, Any]],
    expected_ids: set[str],
) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        review_id = row.get("review_id")
        if not isinstance(review_id, str):
            raise ValueError(f"{module} reviewer {reviewer}: review_id is missing")
        if review_id in by_id:
            raise ValueError(f"{module} reviewer {reviewer}: duplicate {review_id}")
        _review_score(module, row.get("decision"))
        if not isinstance(row.get("critical_error"), bool):
            raise ValueError(
                f"{module} reviewer {reviewer}: critical_error must be boolean for {review_id}"
            )
        by_id[review_id] = row
    missing = sorted(expected_ids - set(by_id))
    extra = sorted(set(by_id) - expected_ids)
    if missing or extra:
        raise ValueError(
            f"{module} reviewer {reviewer}: incomplete/mismatched packet; "
            f"missing={missing[:5]} ({len(missing)}), extra={extra[:5]} ({len(extra)})"
        )
    return by_id


def merge_frozen_reviews(
    output_dir: Path,
    review_dir: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Load both blind files first, then reveal the private condition maps."""

    merged: list[dict[str, Any]] = []
    completed_modules: list[str] = []
    for module in REVIEW_FILES:
        paths = {
            reviewer: review_dir / filename
            for reviewer, filename in REVIEW_FILES[module].items()
        }
        present = {reviewer: path.exists() for reviewer, path in paths.items()}
        if not any(present.values()):
            continue
        if not all(present.values()):
            raise ValueError(
                f"{module}: both blind review files must exist before condition merge: {paths}"
            )

        packet_path = output_dir / REVIEW_INPUTS[module]
        if not packet_path.exists():
            raise ValueError(f"{module}: frozen review packet is missing: {packet_path}")
        expected_ids = {row["review_id"] for row in read_jsonl(packet_path)}

        # Read and validate both independent files before touching the private map.
        blind_rows = {
            reviewer: read_jsonl(path)
            for reviewer, path in paths.items()
        }
        reviews = {
            reviewer: _validate_review_rows(
                module, reviewer, blind_rows[reviewer], expected_ids
            )
            for reviewer in ("a", "b")
        }

        disagreement_ids = {
            review_id
            for review_id in expected_ids
            if (
                reviews["a"][review_id]["decision"]
                != reviews["b"][review_id]["decision"]
                or reviews["a"][review_id]["critical_error"]
                != reviews["b"][review_id]["critical_error"]
            )
        }
        adjudicator_path = review_dir / ADJUDICATOR_FILES[module]
        adjudicator: dict[str, dict[str, Any]] = {}
        if adjudicator_path.exists():
            adjudicator = _validate_review_rows(
                module,
                "adjudicator",
                read_jsonl(adjudicator_path),
                disagreement_ids,
            )

        private_path = output_dir / PRIVATE_MAPS[module]
        if not private_path.exists():
            raise ValueError(f"{module}: private condition map is missing: {private_path}")
        private_by_id = {row["review_id"]: row for row in read_jsonl(private_path)}
        if set(private_by_id) != expected_ids:
            raise ValueError(f"{module}: private map does not match the frozen packet")

        for review_id in sorted(expected_ids):
            review_a = reviews["a"][review_id]
            review_b = reviews["b"][review_id]
            score_a = _review_score(module, review_a["decision"])
            score_b = _review_score(module, review_b["decision"])
            adjudication = adjudicator.get(review_id)
            if score_a is not None and score_a == score_b:
                score_lower = score_upper = score_a
                consensus = (
                    POSITIVE_DECISION[module]
                    if score_a == 1
                    else NEGATIVE_DECISION[module]
                )
            elif adjudication is not None:
                adjudicated_score = _review_score(
                    module, adjudication["decision"]
                )
                if adjudicated_score is None:
                    score_lower, score_upper = 0, 1
                    consensus = "ambiguous"
                else:
                    score_lower = score_upper = adjudicated_score
                    consensus = (
                        POSITIVE_DECISION[module]
                        if adjudicated_score == 1
                        else NEGATIVE_DECISION[module]
                    )
            else:
                # Do not force uncertain or conflicting reviewer evidence.
                score_lower, score_upper = 0, 1
                consensus = "ambiguous"
            if review_a["critical_error"] == review_b["critical_error"]:
                consensus_critical = review_a["critical_error"]
            elif adjudication is not None:
                consensus_critical = adjudication["critical_error"]
            else:
                consensus_critical = False
            merged.append(
                {
                    "review_id": review_id,
                    "module": module,
                    **private_by_id[review_id],
                    "reviewer_a": review_a,
                    "reviewer_b": review_b,
                    "adjudicator": adjudication,
                    "adjudicated": adjudication is not None,
                    "decision_agreement": review_a["decision"] == review_b["decision"],
                    "critical_error_agreement": (
                        review_a["critical_error"] == review_b["critical_error"]
                    ),
                    "consensus": consensus,
                    "quality_score_lower": score_lower,
                    "quality_score_upper": score_upper,
                    "any_reviewer_critical_error": (
                        review_a["critical_error"] or review_b["critical_error"]
                    ),
                    "confirmed_critical_error": consensus_critical,
                }
            )
        completed_modules.append(module)
    if not completed_modules:
        raise ValueError(f"no complete reviewer pair found in {review_dir}")
    return merged, completed_modules


def _percentile(values: list[float], percentile: float) -> float | None:
    return float(np.percentile(values, percentile)) if values else None


def _efficiency(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tokens = [float(row["tokens_used"]) for row in rows if row.get("tokens_used") is not None]
    runtimes = [
        float(row["model_runtime_seconds"])
        for row in rows
        if row.get("model_runtime_seconds") is not None
    ]
    return {
        "calls_with_token_evidence": len(tokens),
        "total_tokens": int(sum(tokens)),
        "mean_tokens_per_call": mean(tokens) if tokens else None,
        "median_tokens_per_call": median(tokens) if tokens else None,
        "p90_tokens_per_call": _percentile(tokens, 90),
        "calls_with_latency_evidence": len(runtimes),
        "total_model_runtime_seconds": sum(runtimes),
        "mean_model_runtime_seconds": mean(runtimes) if runtimes else None,
        "median_model_runtime_seconds": median(runtimes) if runtimes else None,
        "p90_model_runtime_seconds": _percentile(runtimes, 90),
    }


def _quality_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [row for row in rows if row["success"]]
    return {
        "calls": len(rows),
        "successful_calls": len(successful),
        "failed_calls": len(rows) - len(successful),
        "quality_denominator_successful_calls": len(successful),
        "quality_rate_lower": (
            mean(row["quality_score_lower"] for row in successful)
            if successful
            else None
        ),
        "quality_rate_upper": (
            mean(row["quality_score_upper"] for row in successful)
            if successful
            else None
        ),
        "unanimous_clear_positive": sum(
            row["quality_score_lower"] == row["quality_score_upper"] == 1
            for row in successful
        ),
        "unanimous_clear_negative": sum(
            row["quality_score_lower"] == row["quality_score_upper"] == 0
            for row in successful
        ),
        "reviewer_ambiguous": sum(
            row["quality_score_lower"] != row["quality_score_upper"]
            for row in successful
        ),
        "confirmed_critical_errors": sum(
            row.get("confirmed_critical_error", False) for row in successful
        ),
        "any_reviewer_critical_errors": sum(
            row.get("any_reviewer_critical_error", False) for row in successful
        ),
        "efficiency_all_calls": _efficiency(rows),
    }


def _bootstrap_seed(label: str) -> int:
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()
    return SEED + int(digest[:8], 16)


def paired_unit_bootstrap(
    rows: list[dict[str, Any]],
    left_effort: str,
    right_effort: str,
    left_score_name: str,
    *,
    right_score_name: str | None = None,
    bootstrap_replicates: int,
    label: str,
) -> dict[str, Any]:
    """Bootstrap matched call differences by resampling semantic units."""

    right_score_name = right_score_name or left_score_name

    left = {
        row["match_key"]: row
        for row in rows
        if row["effort"] == left_effort and row["success"]
    }
    right = {
        row["match_key"]: row
        for row in rows
        if row["effort"] == right_effort and row["success"]
    }
    keys = sorted(set(left) & set(right))
    paired = [
        {
            "cluster": left[key]["cluster_key"],
            "delta": float(left[key][left_score_name])
            - float(right[key][right_score_name]),
        }
        for key in keys
    ]
    by_cluster: dict[str, list[float]] = defaultdict(list)
    for row in paired:
        by_cluster[row["cluster"]].append(row["delta"])
    clusters = sorted(by_cluster)
    result = {
        "contrast": f"{left_effort}_minus_{right_effort}",
        "left_score": left_score_name,
        "right_score": right_score_name,
        "paired_successful_calls": len(paired),
        "unit_clusters": len(clusters),
        "observed_delta": mean(row["delta"] for row in paired) if paired else None,
        "bootstrap_seed": _bootstrap_seed(label),
        "bootstrap_replicates": bootstrap_replicates,
        "ci_95": None,
    }
    if len(clusters) < 2 or not paired or bootstrap_replicates < 1:
        return result

    rng = np.random.default_rng(result["bootstrap_seed"])
    estimates = np.empty(bootstrap_replicates, dtype=float)
    for index in range(bootstrap_replicates):
        sampled = rng.choice(clusters, size=len(clusters), replace=True)
        deltas = [delta for cluster in sampled for delta in by_cluster[str(cluster)]]
        estimates[index] = float(np.mean(deltas))
    result["ci_95"] = [
        float(np.percentile(estimates, 2.5)),
        float(np.percentile(estimates, 97.5)),
    ]
    return result


def _pairwise_bootstraps(
    module: str,
    rows: list[dict[str, Any]],
    bootstrap_replicates: int,
) -> dict[str, dict[str, Any]]:
    comparisons = {}
    for score_name in ("quality_score_lower", "quality_score_upper"):
        sensitivity = score_name.removeprefix("quality_score_")
        for left in EFFORTS:
            for right in EFFORTS:
                if left == right:
                    continue
                key = f"{sensitivity}:{left}_minus_{right}"
                comparisons[key] = paired_unit_bootstrap(
                    rows,
                    left,
                    right,
                    score_name,
                    bootstrap_replicates=bootstrap_replicates,
                    label=f"{module}:{key}",
                )
    # Reviewer ambiguity is call-specific.  A genuinely robust decision must
    # survive the candidate's pessimistic labels and the comparator's
    # optimistic labels, rather than setting every ambiguous label to the same
    # global endpoint (which could create a spurious tie).
    for left in EFFORTS:
        for right in EFFORTS:
            if left == right:
                continue
            key = f"worst_case:{left}_minus_{right}"
            comparisons[key] = paired_unit_bootstrap(
                rows,
                left,
                right,
                "quality_score_lower",
                right_score_name="quality_score_upper",
                bootstrap_replicates=bootstrap_replicates,
                label=f"{module}:{key}",
            )
    return comparisons


def _normalisation_analysis(
    output_dir: Path,
    reviews: list[dict[str, Any]],
    bootstrap_replicates: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    review_by_key = {
        (row["stage"], row["source_id"], row["effort"], row["replicate"]): row
        for row in reviews
    }
    raw_results = [
        *read_jsonl(output_dir / "normalisation/phase1/results.jsonl"),
        *read_jsonl(output_dir / "normalisation/phase2/results.jsonl"),
    ]
    analysis_rows = []
    for result in raw_results:
        stage = "phase1" if "stratum" in result else "phase2"
        key = (stage, result["source_id"], result["effort"], result["replicate"])
        if key not in review_by_key:
            raise ValueError(f"normalisation result has no frozen blind review: {key}")
        review = review_by_key[key]
        analysis_rows.append(
            {
                **result,
                "stage": stage,
                "match_key": f"{stage}:{result['source_id']}:r{result['replicate']}",
                "cluster_key": result["source_id"],
                "quality_score_lower": review["quality_score_lower"],
                "quality_score_upper": review["quality_score_upper"],
                "confirmed_critical_error": review["confirmed_critical_error"],
                "any_reviewer_critical_error": review["any_reviewer_critical_error"],
            }
        )

    by_effort = {}
    for effort in EFFORTS:
        subset = [row for row in analysis_rows if row["effort"] == effort]
        successful_pairs = []
        for stage, source_id in sorted({(row["stage"], row["source_id"]) for row in subset}):
            by_replicate = {
                row["replicate"]: row
                for row in subset
                if row["stage"] == stage and row["source_id"] == source_id
            }
            if set(by_replicate) == {1, 2} and all(
                row["success"] for row in by_replicate.values()
            ):
                successful_pairs.append((by_replicate[1], by_replicate[2]))
        by_effort[effort] = {
            **_quality_summary(subset),
            "stage_breakdown": {
                stage: _quality_summary([row for row in subset if row["stage"] == stage])
                for stage in ("phase1", "phase2")
            },
            "repeat_successful_pairs": len(successful_pairs),
            "repeat_structural_agreements": sum(
                _mapping_signature(left["mapping"]) == _mapping_signature(right["mapping"])
                for left, right in successful_pairs
            ),
            "repeat_structural_agreement_rate": (
                mean(
                    _mapping_signature(left["mapping"])
                    == _mapping_signature(right["mapping"])
                    for left, right in successful_pairs
                )
                if successful_pairs
                else None
            ),
        }
    return {
        "quality_definition": (
            "Blind mapping acceptability among contract-successful calls; reviewer "
            "uncertainty/disagreement is [0,1], not forced to a label."
        ),
        "by_effort": by_effort,
        "paired_unit_bootstrap": _pairwise_bootstraps(
            "normalisation", analysis_rows, bootstrap_replicates
        ),
    }, analysis_rows


def _validation_analysis(
    output_dir: Path,
    reviews: list[dict[str, Any]],
    bootstrap_replicates: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    reference_by_item = {row["item_id"]: row for row in reviews}
    raw_results = read_jsonl(output_dir / "validation/results.jsonl")
    analysis_rows = []
    for result in raw_results:
        if result["item_id"] not in reference_by_item:
            raise ValueError(f"validation result has no blind reference: {result['item_id']}")
        reference = reference_by_item[result["item_id"]]
        if reference["quality_score_lower"] == reference["quality_score_upper"]:
            truth = bool(reference["quality_score_lower"])
            lower = upper = int(bool(result["accepted"]) == truth)
        else:
            lower, upper = 0, 1
        analysis_rows.append(
            {
                **result,
                "match_key": f"{result['item_id']}:r{result['replicate']}",
                "cluster_key": result["item_id"],
                "quality_score_lower": lower,
                "quality_score_upper": upper,
                "reference_consensus": reference["consensus"],
                "confirmed_reference_critical_error": reference["confirmed_critical_error"],
                "any_reference_critical_error": reference["any_reviewer_critical_error"],
                "confirmed_critical_false_accept": (
                    result["success"]
                    and result["accepted"]
                    and reference["confirmed_critical_error"]
                ),
                "any_reviewer_critical_false_accept": (
                    result["success"]
                    and result["accepted"]
                    and reference["any_reviewer_critical_error"]
                ),
            }
        )

    by_effort = {}
    for effort in EFFORTS:
        subset = [row for row in analysis_rows if row["effort"] == effort]
        primary_subset = [row for row in subset if not row["adversarial_safety"]]
        successful_pairs = []
        for item_id in sorted({row["item_id"] for row in primary_subset}):
            by_replicate = {
                row["replicate"]: row
                for row in primary_subset
                if row["item_id"] == item_id
            }
            if set(by_replicate) == {1, 2} and all(
                row["success"] for row in by_replicate.values()
            ):
                successful_pairs.append((by_replicate[1], by_replicate[2]))
        successful = [row for row in subset if row["success"]]
        primary_summary = _quality_summary(primary_subset)
        # The authored adversarial controls are a separate safety gate, not
        # extra easy negatives that may improve the primary accuracy estimate.
        primary_summary.update(
            {
                "calls": len(subset),
                "successful_calls": len(successful),
                "failed_calls": len(subset) - len(successful),
                "primary_cohort_calls": len(primary_subset),
                "efficiency_all_calls": _efficiency(subset),
            }
        )
        by_effort[effort] = {
            **primary_summary,
            "authored_adversarial_safety_calls": sum(
                row["adversarial_safety"] for row in successful
            ),
            "authored_adversarial_safety_false_accepts": sum(
                row["adversarial_safety"] and row["accepted"] for row in successful
            ),
            "confirmed_critical_false_accepts": sum(
                row["confirmed_critical_false_accept"] for row in successful
            ),
            "any_reviewer_critical_false_accepts": sum(
                row["any_reviewer_critical_false_accept"] for row in successful
            ),
            "repeat_successful_pairs": len(successful_pairs),
            "repeat_accept_agreements": sum(
                left["accepted"] == right["accepted"]
                for left, right in successful_pairs
            ),
            "repeat_accept_agreement_rate": (
                mean(left["accepted"] == right["accepted"] for left, right in successful_pairs)
                if successful_pairs
                else None
            ),
        }
    return {
        "quality_definition": (
            "Agreement with the blind item-acceptability reference among successful "
            "primary-cohort validator calls; ambiguous references contribute [0,1]. "
            "Authored adversarial controls are excluded from accuracy and form a "
            "separate safety gate."
        ),
        "by_effort": by_effort,
        "paired_unit_bootstrap": _pairwise_bootstraps(
            "validation",
            [row for row in analysis_rows if not row["adversarial_safety"]],
            bootstrap_replicates,
        ),
    }, analysis_rows


def _generation_analysis(
    output_dir: Path,
    reviews: list[dict[str, Any]],
    bootstrap_replicates: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    generated = read_jsonl(output_dir / "generation/results.jsonl")
    judgment_path = output_dir / "generation/judgment/results.jsonl"
    judgments = read_jsonl(judgment_path) if judgment_path.exists() else []
    judgment_by_id = {row["experiment_item_id"]: row for row in judgments}
    review_by_item = {row["experiment_item_id"]: row for row in reviews}

    analysis_rows = []
    for result in generated:
        judgment = judgment_by_id.get(result["experiment_item_id"])
        review = review_by_item.get(result["experiment_item_id"])
        judged_successfully = bool(judgment and judgment["success"])
        analysis_rows.append(
            {
                **result,
                "success": bool(result["success"] and judged_successfully),
                "generation_success": result["success"],
                "judgment_success": judged_successfully,
                "fixed_judge_accepted": judgment["accepted"] if judgment else None,
                "match_key": f"{result['cell_id']}:c{result['candidate_index']}",
                "cluster_key": result["cell_id"],
                "quality_score_lower": int(judgment["accepted"]) if judged_successfully else 0,
                "quality_score_upper": int(judgment["accepted"]) if judged_successfully else 1,
                "confirmed_review_critical_error": bool(
                    review and review["confirmed_critical_error"]
                ),
                "any_review_critical_error": bool(
                    review and review["any_reviewer_critical_error"]
                ),
                "confirmed_critical_false_accept": bool(
                    review
                    and review["confirmed_critical_error"]
                    and judged_successfully
                    and judgment["accepted"]
                ),
                "any_reviewer_critical_false_accept": bool(
                    review
                    and review["any_reviewer_critical_error"]
                    and judged_successfully
                    and judgment["accepted"]
                ),
            }
        )

    by_effort = {}
    secondary_reviews = {}
    for effort in EFFORTS:
        subset = [row for row in analysis_rows if row["effort"] == effort]
        judged = [row for row in subset if row["success"]]
        reviewed = [
            row for row in reviews if row["effort"] == effort
        ]
        covered_cells = {
            row["cell_id"] for row in judged if row["fixed_judge_accepted"]
        }
        summary = _quality_summary(subset)
        # _quality_summary sees the combined generation+judgment success flag.
        summary.update(
            {
                "generation_payload_successes": sum(
                    row["generation_success"] for row in subset
                ),
                "fixed_judgment_successes": sum(row["judgment_success"] for row in subset),
                "fixed_judge_accepts": sum(
                    row["fixed_judge_accepted"] is True for row in judged
                ),
                "N3_cell_coverage": len(covered_cells),
                "answer_span_failures": sum(
                    row["generation_success"] and row["answer_span_passed"] is False
                    for row in subset
                ),
                "confirmed_critical_false_accepts": sum(
                    row["confirmed_critical_false_accept"] for row in subset
                ),
                "any_reviewer_critical_false_accepts": sum(
                    row["any_reviewer_critical_false_accept"] for row in subset
                ),
                "repeat_stability": "not_estimable_single_generation_replicate",
            }
        )
        by_effort[effort] = summary
        secondary_reviews[effort] = {
            "position1_review_denominator": len(reviewed),
            "position1_quality_rate_lower": (
                mean(row["quality_score_lower"] for row in reviewed) if reviewed else None
            ),
            "position1_quality_rate_upper": (
                mean(row["quality_score_upper"] for row in reviewed) if reviewed else None
            ),
            "position1_reviewer_ambiguous": sum(
                row["quality_score_lower"] != row["quality_score_upper"]
                for row in reviewed
            ),
            "position1_confirmed_critical_errors": sum(
                row["confirmed_critical_error"] for row in reviewed
            ),
        }
    return {
        "quality_definition": (
            "Acceptance by the single frozen validator setting among successfully "
            "generated and successfully judged candidates. Blind position-1 reviews "
            "are a separate safety/quality sensitivity check."
        ),
        "fixed_judge_available": bool(judgments),
        "by_effort": by_effort,
        "secondary_blind_position1_review": secondary_reviews,
        "paired_unit_bootstrap": _pairwise_bootstraps(
            "generation", analysis_rows, bootstrap_replicates
        ),
    }, analysis_rows


def _expected_calls(module: str, manifest: dict[str, Any]) -> int:
    scale = manifest["scale"]
    replicates = manifest["replicates"]
    if module == "normalisation":
        return (
            scale["normalisation_phase1_descriptors"]
            + scale["normalisation_phase2_fixed_transitions"]
        ) * replicates["normalisation"]
    if module == "validation":
        return (
            scale["validation_items"]
            + manifest.get("supplementary_scale", {}).get(
                "validation_adversarial_safety_items", 0
            )
        ) * replicates["validation"]
    return scale["generation_cells"] * scale["generation_candidates_per_cell"]


def _admissibility(
    module: str,
    effort: str,
    summary: dict[str, Any],
    manifest: dict[str, Any],
) -> tuple[bool, list[str]]:
    reasons = []
    expected = _expected_calls(module, manifest)
    if summary["calls"] != expected:
        reasons.append(f"incomplete calls ({summary['calls']}/{expected})")
    if summary["successful_calls"] != expected:
        reasons.append(
            f"call/output failures ({summary['successful_calls']}/{expected} successful)"
        )
    if summary.get("confirmed_critical_errors", 0):
        reasons.append("confirmed critical review error")
    if module == "validation":
        if summary.get("authored_adversarial_safety_false_accepts", 0):
            reasons.append("authored adversarial safety false accept")
        if summary.get("confirmed_critical_false_accepts", 0):
            reasons.append("confirmed reviewer-critical false accept")
    if module == "generation":
        if summary.get("generation_payload_successes") != expected:
            reasons.append("incomplete generation payloads")
        if summary.get("fixed_judgment_successes") != expected:
            reasons.append("incomplete frozen-validator judgments")
        if summary.get("confirmed_critical_false_accepts", 0):
            reasons.append("frozen validator accepted a confirmed critical item")
        max_coverage = max(
            row["N3_cell_coverage"]
            for row in manifest["_generation_summaries"].values()
        )
        tolerance = manifest["selection_rule"]["generation_coverage_tolerance_cells"]
        if summary["N3_cell_coverage"] < max_coverage - tolerance:
            reasons.append(
                f"N=3 coverage trails best by more than {tolerance} cell(s)"
            )
    return not reasons, reasons


def apply_frozen_selection_rule(
    module: str,
    analysis: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    margin = float(manifest["selection_rule"][f"{module}_margin"])
    summaries = analysis["by_effort"]
    if module == "generation":
        manifest = {**manifest, "_generation_summaries": summaries}
    admissibility = {}
    for effort in EFFORTS:
        admissible, reasons = _admissibility(
            module, effort, summaries[effort], manifest
        )
        admissibility[effort] = {"admissible": admissible, "reasons": reasons}

    if not any(row["admissible"] for row in admissibility.values()):
        return {
            "status": "inconclusive",
            "selected_effort": None,
            "reason": "no effort passed completeness and safety gates",
            "margin": margin,
            "admissibility": admissibility,
        }

    sensitivity_results: dict[str, Any] = {}
    comparisons = analysis["paired_unit_bootstrap"]
    for sensitivity in ("lower", "upper"):
        score_name = f"quality_rate_{sensitivity}"
        admissible_efforts = [
            effort for effort in EFFORTS if admissibility[effort]["admissible"]
        ]
        best = max(admissible_efforts, key=lambda effort: summaries[effort][score_name])
        candidates = {}
        for effort in EFFORTS:
            if not admissibility[effort]["admissible"]:
                candidates[effort] = {
                    "noninferior": False,
                    "reason": "failed admissibility gate",
                }
                continue
            if effort == best:
                candidates[effort] = {
                    "noninferior": True,
                    "observed_delta_vs_best": 0.0,
                    "ci_95": [0.0, 0.0],
                }
                continue
            contrast = comparisons[f"{sensitivity}:{effort}_minus_{best}"]
            ci = contrast["ci_95"]
            noninferior = bool(ci is not None and ci[0] >= -margin)
            candidates[effort] = {
                "noninferior": noninferior,
                "observed_delta_vs_best": contrast["observed_delta"],
                "ci_95": ci,
                "paired_successful_calls": contrast["paired_successful_calls"],
                "unit_clusters": contrast["unit_clusters"],
                "criterion": f"95% CI lower bound >= -{margin:.3f}",
            }
        sensitivity_results[sensitivity] = {
            "best_observed_admissible_effort": best,
            "quality_rate": summaries[best][score_name],
            "candidates": candidates,
        }

    robust_tests: dict[str, Any] = {}
    robust_noninferior = {}
    for effort in EFFORTS:
        if not admissibility[effort]["admissible"]:
            robust_noninferior[effort] = False
            robust_tests[effort] = {
                "noninferior_to_every_plausible_comparator": False,
                "reason": "failed admissibility gate",
                "comparisons": {},
            }
            continue
        effort_tests = {}
        for comparator in EFFORTS:
            if comparator == effort or not admissibility[comparator]["admissible"]:
                continue
            contrast = comparisons[f"worst_case:{effort}_minus_{comparator}"]
            ci = contrast["ci_95"]
            passes = bool(ci is not None and ci[0] >= -margin)
            effort_tests[comparator] = {
                "noninferior": passes,
                "candidate_pessimistic_minus_comparator_optimistic": contrast[
                    "observed_delta"
                ],
                "ci_95": ci,
                "paired_successful_calls": contrast["paired_successful_calls"],
                "unit_clusters": contrast["unit_clusters"],
                "criterion": f"95% CI lower bound >= -{margin:.3f}",
            }
        passes_all = all(
            test["noninferior"] for test in effort_tests.values()
        )
        robust_noninferior[effort] = passes_all
        robust_tests[effort] = {
            "noninferior_to_every_plausible_comparator": passes_all,
            "comparisons": effort_tests,
        }

    selected = next(
        (
            effort
            for effort in EFFORTS
            if admissibility[effort]["admissible"] and robust_noninferior[effort]
        ),
        None,
    )
    if selected is None:
        status = "inconclusive"
        reason = (
            "no single admissible effort is non-inferior under both reviewer "
            "best/worst-case sensitivities"
        )
    else:
        status = "selected_by_frozen_rule"
        reason = (
            "lowest admissible effort whose paired 95% lower bound clears the "
            "non-inferiority margin under both reviewer sensitivities"
        )
    return {
        "status": status,
        "selected_effort": selected,
        "reason": reason,
        "superiority_claim": False,
        "margin": margin,
        "admissibility": admissibility,
        "sensitivity_results": sensitivity_results,
        "robust_ambiguity_tests": robust_tests,
    }


def analyze_reviews(
    output_dir: Path,
    review_dir: Path,
    bootstrap_replicates: int,
) -> dict[str, Any]:
    manifest = read_json(output_dir / "manifest.json")
    if manifest.get("experiment_id") != "BACKEND-THINKING-001":
        raise ValueError("unexpected experiment manifest")
    if manifest.get("seed_use", {}).get("seed") != SEED:
        raise ValueError("manifest bootstrap seed does not match this frozen analysis")

    merged, completed_modules = merge_frozen_reviews(output_dir, review_dir)
    analysis_dir = output_dir / "analysis"
    write_jsonl(analysis_dir / "merged_blind_reviews.jsonl", merged)
    disagreements = [
        row
        for row in merged
        if not row["decision_agreement"] or not row["critical_error_agreement"]
    ]
    write_jsonl(analysis_dir / "reviewer_disagreements.jsonl", disagreements)

    report: dict[str, Any] = {
        "experiment_id": "BACKEND-THINKING-001",
        "analysis_date": date.today().isoformat(),
        "bootstrap": {
            "method": "paired semantic-unit cluster percentile bootstrap",
            "seed": SEED,
            "replicates": bootstrap_replicates,
            "confidence_interval": 0.95,
        },
        "claim_boundary": (
            "Research-agent reviews are independent blind research checks, not "
            "human/expert gold labels. Selection denotes the frozen parsimonious "
            "decision rule and never statistical superiority."
        ),
        "completed_review_modules": completed_modules,
        "review_accounting": {
            "merged_rows": len(merged),
            "exact_decision_agreements": sum(row["decision_agreement"] for row in merged),
            "decision_disagreements": sum(not row["decision_agreement"] for row in merged),
            "critical_flag_disagreements": sum(
                not row["critical_error_agreement"] for row in merged
            ),
            "adjudicated_rows": sum(row["adjudicated"] for row in merged),
            "ambiguous_score_intervals": sum(row["consensus"] == "ambiguous" for row in merged),
            "disagreement_artifact": "analysis/reviewer_disagreements.jsonl",
            "merged_artifact": "analysis/merged_blind_reviews.jsonl",
        },
        "modules": {},
        "recommendations": {},
    }

    for module in completed_modules:
        module_reviews = [row for row in merged if row["module"] == module]
        if module == "normalisation":
            required = [
                output_dir / "normalisation/phase1/results.jsonl",
                output_dir / "normalisation/phase2/results.jsonl",
            ]
            if not all(path.exists() for path in required):
                raise ValueError("normalisation reviews exist but live result files are incomplete")
            module_analysis, _ = _normalisation_analysis(
                output_dir, module_reviews, bootstrap_replicates
            )
        elif module == "validation":
            if not (output_dir / "validation/results.jsonl").exists():
                raise ValueError("validation reviews exist but live result file is incomplete")
            module_analysis, _ = _validation_analysis(
                output_dir, module_reviews, bootstrap_replicates
            )
        else:
            if not (output_dir / "generation/results.jsonl").exists():
                raise ValueError("generation reviews exist but live result file is incomplete")
            module_analysis, _ = _generation_analysis(
                output_dir, module_reviews, bootstrap_replicates
            )
        report["modules"][module] = module_analysis
        report["recommendations"][module] = apply_frozen_selection_rule(
            module, module_analysis, manifest
        )

    write_json(analysis_dir / "review_analysis.json", report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="BACKEND-THINKING-001 artifact directory",
    )
    parser.add_argument(
        "--review-dir",
        type=Path,
        default=None,
        help="review directory (default: <output-dir>/reviews)",
    )
    parser.add_argument(
        "--bootstrap-replicates",
        type=int,
        default=BOOTSTRAP_REPLICATES,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.bootstrap_replicates < 1:
        raise ValueError("--bootstrap-replicates must be positive")
    output_dir = args.output_dir.resolve()
    review_dir = (
        args.review_dir.resolve()
        if args.review_dir is not None
        else output_dir / "reviews"
    )
    report = analyze_reviews(output_dir, review_dir, args.bootstrap_replicates)
    print(json.dumps(report["recommendations"], indent=2))
    print(f"Full analysis: {output_dir / 'analysis/review_analysis.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
