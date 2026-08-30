from __future__ import annotations

import copy
import gzip
import json

import pytest

from scripts.experiments.collection_design import (
    DEFAULT_DATASET,
    REPRESENTATIONS,
    deterministic_learner_cohort,
    deterministic_train_validation,
    file_sha256,
    fixed_full_representations,
    load_acquisition_only,
    micro_designs,
    micro_hypotheses,
    micro_q_audit,
    run_items_per_kc_audit,
    simulate_micro_events,
)


def _write_gzip_rows(path, rows: list[dict[str, object]]) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row) + "\n")


def test_hash_cohorts_and_learner_disjoint_splits_are_deterministic() -> None:
    learners = [f"learner_{index:04d}" for index in range(100)]
    first = deterministic_learner_cohort(learners, count=60, replicate=3)
    second = deterministic_learner_cohort(
        list(reversed(learners)), count=60, replicate=3
    )
    assert first == second
    assert len(first) == len(set(first)) == 60
    train, validation = deterministic_train_validation(
        first, count=60, replicate=3
    )
    assert not train & validation
    assert train | validation == set(first)
    assert len(train) == 45
    assert len(validation) == 15
    larger = deterministic_learner_cohort(learners, count=80, replicate=3)
    assert set(first) <= set(larger)
    larger_train, larger_validation = deterministic_train_validation(
        larger, count=80, replicate=3
    )
    assert train <= larger_train
    assert validation <= larger_validation
    assert deterministic_learner_cohort(learners, count=100, replicate=0) == sorted(
        learners
    )
    with pytest.raises(ValueError, match="only one unique replicate"):
        deterministic_learner_cohort(learners, count=100, replicate=1)


def test_acquisition_loader_skips_probe_outcomes_and_rejects_oracle(tmp_path) -> None:
    rows = [
        {
            "learner_id": "l1",
            "item_id": "i1",
            "sequence_index": 1,
            "correct": 1,
            "phase": "acquisition",
            "pass_index": 1,
            "grammar_regime": "seen",
        },
        {
            "learner_id": "l1",
            "item_id": "i2",
            "sequence_index": 2,
            "correct": 0,
            "phase": "probe",
            "pass_index": 1,
            "grammar_regime": "unseen_value",
        },
    ]
    path = tmp_path / "events.jsonl.gz"
    _write_gzip_rows(path, rows)
    first, audit = load_acquisition_only(path)
    changed = copy.deepcopy(rows)
    changed[1]["correct"] = 1
    changed[1]["mastery_before"] = {"secret": 0.9}
    _write_gzip_rows(path, changed)
    second, changed_audit = load_acquisition_only(path)
    assert first == second
    assert audit == changed_audit
    assert audit["probe_outcomes_read"] is False
    assert audit["probe_rows_skipped_before_correct_access"] == 1

    leaked = copy.deepcopy(rows)
    leaked[0]["response_probability"] = 0.8
    _write_gzip_rows(path, leaked)
    with pytest.raises(ValueError, match="oracle fields"):
        load_acquisition_only(path)


def test_max_two_real_bank_adds_support_but_no_q_activation_geometry() -> None:
    projections = fixed_full_representations()
    result = run_items_per_kc_audit(DEFAULT_DATASET, projections["true_kstar"])
    one = result["max_one_per_cell"]
    two = result["max_two_per_cell"]
    comparison = result["comparison"]
    assert one["items"] == 75
    assert two["items"] == 113
    assert one["kcs"] == two["kcs"] == 18
    assert comparison["additional_items"] == 38
    assert comparison["additional_unique_q_rows"] == 0
    assert comparison["column_rank_change"] == 0
    assert comparison["second_variants_add_structural_activation_diversity"] is False
    assert two["item_support_per_kc"]["minimum"] >= one["item_support_per_kc"]["minimum"]


def test_micro_q_geometry_distinguishes_anchors_and_union_semantics() -> None:
    designs = micro_designs()
    factorized_all = micro_q_audit("factorized_ab", designs["all_ab_no_anchors"])
    factorized_sparse = micro_q_audit("factorized_ab", designs["sparse_anchors"])
    planted_all = micro_q_audit("planted_abi", designs["all_ab_no_anchors"])
    planted_sparse = micro_q_audit("planted_abi", designs["sparse_anchors"])
    assert factorized_all["rank"] == 1
    assert factorized_all["identical_q_column_groups"] == [["A", "B"]]
    assert factorized_sparse["rank"] == 2
    assert factorized_sparse["identical_q_column_groups"] == []
    assert planted_all["rank"] == 1
    assert planted_all["identical_q_column_groups"] == [["A", "B", "I"]]
    assert planted_sparse["rank"] == 3
    assert planted_sparse["identical_q_column_groups"] == []

    factorized = micro_hypotheses("factorized_ab")
    union = factorized["union_merge"]
    intersection = factorized["spurious_intersection"]
    assert union["a_only"] == union["b_only"] == union["a_plus_b"] == ("U",)
    assert "I" not in intersection["a_only"]
    assert "I" not in intersection["b_only"]
    assert "I" in intersection["a_plus_b"]


def test_micro_stream_is_deterministic_matched_volume_and_probes_do_not_update() -> None:
    design = micro_designs()["sparse_anchors"]
    first, first_digest = simulate_micro_events(
        world="planted_abi", design=design, learners=3, seed=20260840
    )
    second, second_digest = simulate_micro_events(
        world="planted_abi", design=design, learners=3, seed=20260840
    )
    assert first == second
    assert first_digest == second_digest
    acquisition = [row for row in first if row["phase"] == "acquisition"]
    probes = [row for row in first if row["phase"] == "probe"]
    assert len(acquisition) == 3 * 60
    assert len(probes) == 3 * 3
    assert all(row["updates_history"] for row in acquisition)
    assert all(not row["updates_history"] for row in probes)
    for learner in {row["learner_id"] for row in first}:
        learner_rows = [row for row in first if row["learner_id"] == learner]
        first_probe = next(
            index for index, row in enumerate(learner_rows) if row["phase"] == "probe"
        )
        assert all(row["phase"] == "probe" for row in learner_rows[first_probe:])


def test_collection_structural_checks_do_not_mutate_frozen_baseline() -> None:
    paths = [
        DEFAULT_DATASET / "manifest.json",
        DEFAULT_DATASET / "interactions.jsonl.gz",
        DEFAULT_DATASET / "items/items.jsonl",
        DEFAULT_DATASET / "q_matrix.csv",
    ]
    before = [file_sha256(path) for path in paths]
    projections = fixed_full_representations()
    assert tuple(projections) == REPRESENTATIONS
    run_items_per_kc_audit(DEFAULT_DATASET, projections["true_kstar"])
    micro_q_audit("factorized_ab", micro_designs()["balanced_anchors"])
    assert before == [file_sha256(path) for path in paths]
