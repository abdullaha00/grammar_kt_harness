from __future__ import annotations

import csv
from pathlib import Path

from grammar_kt.io import read_yaml, write_json, write_jsonl, write_yaml
from grammar_kt.kc_candidates import make_kc_candidates
from scripts.analyze_full_dataset import analyse_dataset, candidate_cohort


ROOT = Path(__file__).resolve().parents[1]


def _item(
    cell_id: str,
    index: int,
    rank: int | None,
    *,
    provenance: dict | None = None,
) -> dict:
    row = {
        "item_id": f"candidate_{cell_id}_{index:02d}",
        "cell_id": cell_id,
        "format": "controlled_production",
        "prompt": f"Complete focused prompt {cell_id} {index}: ____",
        "target_answer": f"Target sentence {cell_id} {index}.",
        "accepted_answers": [f"Target sentence {cell_id} {index}."],
        "generation_metadata": {
            "candidate_index": index,
            "candidate_count": max(3, index),
            "model": "fixture",
            "provenance": provenance or {"status": "phase6_live_model_evidence"},
        },
    }
    if rank is not None:
        row["selection_metadata"] = {
            "rank": rank,
            "rule": "earliest_valid" if rank == 1 else "maximum_token_set_distance_from_first",
            "token_set_distance_from_first": 0.0 if rank == 1 else 0.75,
        }
    return row


def _judgment(item_id: str, accepted: bool, *, status: str) -> dict:
    criteria = {
        "target_fidelity": {"passed": True, "note": "fixture"},
        "grammaticality": {"passed": True, "note": "fixture"},
        "determinacy": {"passed": accepted, "note": "fixture"},
        "non_target_language_simplicity": {"passed": True, "note": "fixture"},
    }
    return {
        "item_id": item_id,
        "deterministic_checks": {
            "answer_span_consistency": {"passed": True, "note": "fixture"}
        },
        "judgments": criteria,
        "accepted": accepted,
        "rejection_stage": None if accepted else "independent_model_judgment",
        "validation_metadata": {
            "status": status,
            "model": "fixture",
            "runtime_seconds": 0.25,
        },
    }


def _make_analysis_fixture(path: Path) -> None:
    cells = [
        {
            "cell_id": "cell_dev",
            "features": {
                "tense": "present",
                "aspect": "progressive",
                "voice": "active",
                "polarity": "negative",
                "clause": "declarative",
                "modal": "none",
            },
            "source_ids": ["source_1"],
        },
        {
            "cell_id": "cell_comp",
            "features": {
                "tense": "past",
                "aspect": "progressive",
                "voice": "active",
                "polarity": "negative",
                "clause": "declarative",
                "modal": "none",
            },
            "source_ids": ["source_2"],
        },
        {
            "cell_id": "cell_novel",
            "features": {
                "tense": "NA",
                "aspect": "none",
                "voice": "active",
                "polarity": "positive",
                "clause": "declarative",
                "modal": "would",
            },
            "source_ids": ["source_3"],
        },
    ]
    default_one = _item("cell_dev", 1, 1)
    default_two = _item("cell_dev", 2, 2)
    rejected = _item("cell_comp", 1, None)
    rescue = _item(
        "cell_comp",
        4,
        1,
        provenance={
            "status": "phase6_conditional_rescue_live_model_evidence",
            "protocol": "conditional_zero_coverage_rescue_v1",
        },
    )
    intervention = _item(
        "cell_novel",
        6,
        1,
        provenance={
            "status": "phase6_determinacy_intervention_live_model_evidence",
            "protocol": "explicit_construction_determinacy_intervention_v1",
        },
    )
    candidates = [default_one, default_two, rejected, rescue, intervention]
    judgments = [
        _judgment(default_one["item_id"], True, status="phase6_live_model_evidence"),
        _judgment(default_two["item_id"], True, status="phase6_live_model_evidence"),
        _judgment(rejected["item_id"], False, status="phase6_live_model_evidence"),
        _judgment(
            rescue["item_id"],
            True,
            status="phase6_conditional_rescue_live_model_evidence",
        ),
        _judgment(
            intervention["item_id"],
            True,
            status="phase6_determinacy_intervention_live_model_evidence",
        ),
    ]
    accepted = [default_one, default_two, rescue, intervention]
    attempts = [
        {
            "candidate_id": row["item_id"],
            "cell_id": row["cell_id"],
            "candidate_index": row["generation_metadata"]["candidate_index"],
            "candidate_count": row["generation_metadata"]["candidate_count"],
            "structurally_valid": True,
            "structural_errors": [],
            "call_error": None,
            "runtime_seconds": 0.5,
            "model": "fixture",
            "provenance": row["generation_metadata"]["provenance"],
        }
        for row in candidates
    ]
    fold = [
        {
            "cell_id": cell["cell_id"],
            "grammar_split": split,
            "features": cell["features"],
            "accepted_item_ids": [
                row["item_id"] for row in accepted if row["cell_id"] == cell["cell_id"]
            ],
            "accepted_item_support": sum(
                row["cell_id"] == cell["cell_id"] for row in accepted
            ),
            "unseen_development_values": [],
            "selection_reason": "fixture",
        }
        for cell, split in zip(
            cells,
            ("development", "compositional_holdout", "novel_feature_holdout"),
        )
    ]
    schema = read_yaml(ROOT / "modules/grammar/canonical/schema.yaml")
    candidate_design = read_yaml(ROOT / "modules/kcs/candidate_design.yaml") | {
        "operation_declarations": read_yaml(
            ROOT / "modules/grammar/canonical/english_operations.yaml"
        )["operations"]
    }
    inventory = make_kc_candidates(
        schema, [cells[0]], [default_one, default_two], candidate_design
    )
    feature_kcs = [
        {
            "id": row["id"],
            "definition": row["definition"],
            "activation": row["activation"],
        }
        for row in inventory["candidates"]
        if row["family"] == "feature_value" and row["selection_eligible"]
    ]

    write_json(
        path / "finalization_manifest.json",
        {
            "status": "downstream_finalized",
            "scale": {"cells": 3, "selected_items": 4, "learners": 8},
        },
    )
    write_jsonl(
        path / "source/descriptors.jsonl",
        [
            {"source_id": "source_1"},
            {"source_id": "source_2"},
            {"source_id": "source_3"},
        ],
    )
    write_jsonl(
        path / "normalisation/mappings.jsonl",
        [
            {"source_id": "source_1", "result": "complete", "phase2_eligible": []},
            {"source_id": "source_2", "result": "partial", "phase2_eligible": ["tense"]},
            {"source_id": "source_3", "result": "unresolved", "phase2_eligible": []},
        ],
    )
    write_jsonl(path / "canonical/cells.jsonl", cells)
    write_jsonl(
        path / "canonical/source_cell_relations.jsonl",
        [
            {"source_id": f"source_{index}", "cell_id": cell["cell_id"]}
            for index, cell in enumerate(cells, 1)
        ],
    )
    write_jsonl(path / "items/generation_attempts.jsonl", attempts)
    write_jsonl(path / "items/candidates.jsonl", candidates)
    write_jsonl(path / "items/validation.jsonl", judgments)
    write_jsonl(path / "items/validator_accepted.jsonl", accepted)
    write_jsonl(path / "items/selected_bank.jsonl", accepted)
    write_jsonl(path / "fold/assignments.jsonl", fold)
    write_json(path / "kc/candidate_inventory.json", inventory)
    write_yaml(
        path / "kc/policies/automated.yaml",
        {
            "policy_id": "fixture_automated",
            "kcs": feature_kcs,
            "selection_metadata": {
                "initial_candidate_ids": [row["id"] for row in feature_kcs],
                "selected_candidate_ids": [row["id"] for row in feature_kcs],
                "selected_support": {},
            },
        },
    )
    representation = {
        "policy_id": "fixture_automated",
        "items": 4,
        "kcs": len(feature_kcs),
        "item_coverage": 1.0,
        "event_coverage": 1.0,
        "q_matrix_density": 0.5,
        "kcs_per_item": 1.0,
        "kc_support": {row["id"]: 2 for row in feature_kcs},
        "redundant_kcs": [],
        "compositional_coverage": 1.0,
    }
    metric = {
        "n": 8,
        "log_loss": 0.5,
        "brier_score": 0.16,
        "auc": 0.7,
        "ece": 0.1,
        "accuracy": 0.75,
    }
    write_json(
        path / "evaluation/automated/results.json",
        {
            "representation": representation,
            "kt": {
                "logistic": {
                    **metric,
                    "grammar_split_metrics": {
                        split: metric for split in (
                            "development",
                            "compositional_holdout",
                            "novel_feature_holdout",
                        )
                    },
                }
            },
        },
    )
    write_json(
        path / "evaluation/paired_logistic.json",
        {
            "comparisons": [
                {
                    "grammar_regime": "all_test",
                    "reference": "factorized",
                    "candidate": "automated",
                    "available": True,
                    "n_learners": 8,
                    "n_events": 8,
                    "delta_log_loss": {"point_estimate": -0.01, "interval_95": [-0.02, 0.0]},
                    "delta_brier_score": {"point_estimate": -0.005, "interval_95": [-0.01, 0.0]},
                    "sign_convention": "candidate_minus_reference; negative favours candidate",
                }
            ]
        },
    )


def test_candidate_cohort_recognizes_all_frozen_construction_stages() -> None:
    assert candidate_cohort(_item("cell", 1, None)) == "default_n3"
    assert (
        candidate_cohort(
            _item(
                "cell",
                4,
                None,
                provenance={"protocol": "conditional_zero_coverage_rescue_v1"},
            )
        )
        == "conditional_rescue"
    )
    assert (
        candidate_cohort(
            _item(
                "cell",
                6,
                None,
                provenance={"protocol": "explicit_construction_determinacy_intervention_v1"},
            )
        )
        == "determinacy_intervention"
    )


def test_analysis_writes_grounded_tables_and_structural_sensitivity(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "dataset"
    output = tmp_path / "analysis"
    _make_analysis_fixture(dataset)

    summary = analyse_dataset(
        dataset, output, exact_command="pytest retained-artifact fixture"
    )

    assert summary["model_calls_made"] is False
    assert summary["learner_outcomes_recomputed"] is False
    assert summary["source_normalisation"]["descriptors"] == 3
    assert summary["items"]["selected_cells"] == 3
    assert summary["one_vs_two_variant_structural_sensitivity"][
        "outcomes_read"
    ] is False
    expected = {
        "summary.json",
        "tables.md",
        "item_generation_stages.csv",
        "criterion_failures.csv",
        "kc_candidate_families.csv",
        "policy_granularity.csv",
        "kt_metrics.csv",
        "paired_logistic.csv",
        "one_vs_two_variant_sensitivity.csv",
        "rq_evidence.csv",
    }
    assert expected <= {row.name for row in output.iterdir()}

    with (output / "item_generation_stages.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        stages = {row["stage"]: row for row in csv.DictReader(stream)}
    assert stages["default_prefix_n1"]["validator_covered_cells"] == "1"
    assert stages["cumulative_through_rescue"]["validator_covered_cells"] == "2"
    assert stages["final_cumulative"]["validator_covered_cells"] == "3"

    markdown = (output / "tables.md").read_text(encoding="utf-8")
    assert "Fixed-logistic primary comparison" in markdown
    assert "does not read outcomes" in markdown
