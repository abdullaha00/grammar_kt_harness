import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/analyze_backend_thinking_reviews.py"
SPEC = importlib.util.spec_from_file_location("backend_thinking_review_analysis", SCRIPT)
analysis = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(analysis)


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_condition_map_is_not_required_until_both_reviews_exist(tmp_path):
    output = tmp_path / "artifacts"
    reviews = output / "reviews"
    _write_jsonl(
        output / "review_packets/validation_items.jsonl",
        [{"review_id": "validation_review_001"}],
    )
    _write_jsonl(
        reviews / "reviewer_a_validation.jsonl",
        [
            {
                "review_id": "validation_review_001",
                "decision": "accept",
                "critical_error": False,
            }
        ],
    )

    with pytest.raises(ValueError, match="both blind review files"):
        analysis.merge_frozen_reviews(output, reviews)


def test_validation_selection_uses_complete_successful_paired_calls(tmp_path):
    output = tmp_path / "artifacts"
    reviews = output / "reviews"
    review_ids = ["validation_review_001", "validation_review_002"]
    _write_json(
        output / "manifest.json",
        {
            "experiment_id": "BACKEND-THINKING-001",
            "seed_use": {"seed": 20260828},
            "scale": {
                "normalisation_phase1_descriptors": 1,
                "normalisation_phase2_fixed_transitions": 0,
                "validation_items": 2,
                "generation_cells": 1,
                "generation_candidates_per_cell": 1,
            },
            "supplementary_scale": {"validation_adversarial_safety_items": 0},
            "replicates": {"normalisation": 2, "validation": 2, "generation": 1},
            "selection_rule": {
                "normalisation_margin": 0.05,
                "validation_margin": 0.05,
                "generation_margin": 0.05,
                "generation_coverage_tolerance_cells": 1,
            },
        },
    )
    _write_jsonl(
        output / "review_packets/validation_items.jsonl",
        [{"review_id": review_id} for review_id in review_ids],
    )
    _write_jsonl(
        output / "private_mappings/validation_review_map.jsonl",
        [
            {
                "review_id": review_id,
                "item_id": f"item_{index}",
                "adversarial_safety": False,
            }
            for index, review_id in enumerate(review_ids, 1)
        ],
    )
    frozen_reviews = [
        {
            "review_id": review_id,
            "decision": "accept",
            "critical_error": False,
            "failed_criteria": [],
            "confidence": "high",
            "rationale": "Clear and well formed.",
        }
        for review_id in review_ids
    ]
    _write_jsonl(reviews / "reviewer_a_validation.jsonl", frozen_reviews)
    _write_jsonl(reviews / "reviewer_b_validation.jsonl", frozen_reviews)
    result_rows = []
    for effort in analysis.EFFORTS:
        for item_id in ("item_1", "item_2"):
            for replicate in (1, 2):
                result_rows.append(
                    {
                        "item_id": item_id,
                        "effort": effort,
                        "replicate": replicate,
                        "success": True,
                        "accepted": True,
                        "adversarial_safety": False,
                        "tokens_used": 100,
                        "model_runtime_seconds": 1.0,
                    }
                )
    _write_jsonl(output / "validation/results.jsonl", result_rows)

    report = analysis.analyze_reviews(output, reviews, bootstrap_replicates=100)

    summary = report["modules"]["validation"]["by_effort"]["medium"]
    assert summary["quality_denominator_successful_calls"] == 4
    assert summary["quality_rate_lower"] == 1.0
    assert summary["repeat_accept_agreement_rate"] == 1.0
    recommendation = report["recommendations"]["validation"]
    assert recommendation["status"] == "selected_by_frozen_rule"
    assert recommendation["selected_effort"] == "medium"
    assert recommendation["superiority_claim"] is False

    # Identically ambiguous labels must not manufacture a medium-effort tie.
    uncertain_reviews = [
        {**row, "decision": "uncertain", "confidence": "low"}
        for row in frozen_reviews
    ]
    _write_jsonl(reviews / "reviewer_b_validation.jsonl", uncertain_reviews)
    uncertain_report = analysis.analyze_reviews(
        output, reviews, bootstrap_replicates=100
    )
    uncertain_recommendation = uncertain_report["recommendations"]["validation"]
    assert uncertain_recommendation["status"] == "inconclusive"
    assert uncertain_recommendation["selected_effort"] is None
