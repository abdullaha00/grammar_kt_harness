from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from grammar_kt.io import read_jsonl, read_yaml, write_json, write_jsonl
from scripts.finalize_full_dataset import finalize_dataset


ROOT = Path(__file__).resolve().parents[1]
MEDIUM = ROOT / "data/grammar_kt_medium_v1"


def _read_jsonl_gzip(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _make_complete_temporary_bank(path: Path) -> None:
    cells = read_jsonl(MEDIUM / "canonical/cells.jsonl")
    criteria = read_yaml(
        ROOT / "modules/items/validation/criteria.yaml"
    )["criteria"]
    items = []
    judgments = []
    for index, cell in enumerate(cells, 1):
        item_id = f"temporary_item_{index:03d}"
        answer = f"Temporary response {index}."
        item = {
            "item_id": item_id,
            "cell_id": cell["cell_id"],
            "format": "controlled_production",
            "prompt": f"Temporary contract item {index}: ____",
            "target_answer": answer,
            "accepted_answers": [answer],
            "generation_metadata": {
                "candidate_index": 1,
                "candidate_count": 1,
                "model": "deterministic_test_fixture",
            },
            "selection_metadata": {
                "rank": 1,
                "rule": "earliest_valid",
                "token_set_distance_from_first": 0.0,
            },
        }
        items.append(item)
        judgments.append(
            {
                "item_id": item_id,
                "deterministic_checks": {
                    "answer_span_consistency": {
                        "passed": True,
                        "note": "Deterministic test fixture.",
                    }
                },
                "judgments": {
                    name: {
                        "passed": True,
                        "note": "Deterministic test fixture; not quality evidence.",
                    }
                    for name in criteria
                },
                "accepted": True,
                "rejection_stage": None,
            }
        )
    write_json(path / "manifest.json", {
        "dataset_id": "temporary_finalizer_contract",
        "status": "fixed_item_bank_complete",
    })
    write_jsonl(path / "canonical/cells.jsonl", cells)
    write_jsonl(path / "items/candidates.jsonl", items)
    write_jsonl(path / "items/validation.jsonl", judgments)
    write_jsonl(path / "items/validator_accepted.jsonl", items)
    write_jsonl(path / "items/selected_bank.jsonl", items)


def test_finalizer_refuses_incomplete_bank_before_writing(tmp_path: Path) -> None:
    write_json(
        tmp_path / "manifest.json",
        {"dataset_id": "incomplete", "status": "prepared_for_generation"},
    )
    with pytest.raises(ValueError, match="fixed_item_bank_complete"):
        finalize_dataset(tmp_path, learners=4, bootstrap_repeats=5)
    assert not (tmp_path / "fold").exists()


def test_temporary_complete_bank_runs_full_downstream_path(tmp_path: Path) -> None:
    _make_complete_temporary_bank(tmp_path)
    manifest = finalize_dataset(
        tmp_path,
        learners=8,
        seed=20260827,
        bootstrap_repeats=25,
        exact_command="pytest deterministic dry run",
    )

    assert manifest["status"] == "downstream_finalized"
    assert manifest["scale"]["cells"] == 24
    assert manifest["scale"]["selected_items"] == 24
    assert manifest["scale"]["learners"] == 8
    assert manifest["grammar_fold"]["cell_counts"] == {
        "compositional_holdout": 5,
        "development": 18,
        "novel_feature_holdout": 1,
    }
    assert manifest["simulation"]["events_are_identical_across_policies"] is True
    assert manifest["paired_logistic"] == {
        "repeats": 25,
        "seed": 20260827,
        "comparison_count": 12,
    }

    policies = {
        "factorized",
        "supported_interactions",
        "automated",
        "oracle_all_cell",
    }
    for name in policies:
        assert (tmp_path / f"kc/policies/{name}.yaml").is_file()
        assert (tmp_path / f"kc/projections/{name}.jsonl").is_file()
        assert (tmp_path / f"kc/q_matrices/{name}.csv").is_file()
        predictions = _read_jsonl_gzip(
            tmp_path / f"kt/{name}/predictions.jsonl.gz"
        )
        assert len(predictions) == manifest["scale"]["events"] * 3
        assert {row["technique"] for row in predictions} == {
            "empirical",
            "bkt",
            "logistic",
        }
        assert (tmp_path / f"evaluation/{name}/results.json").is_file()
    assert (tmp_path / "simulation/events.jsonl.gz").is_file()
    assert (tmp_path / "simulation/oracle_debug.json.gz").is_file()
    assert (tmp_path / "evaluation/paired_logistic.json").is_file()
    assert (tmp_path / "finalization_manifest.json").is_file()

    selection = read_yaml(tmp_path / "kc/policies/automated.yaml")
    assert selection["selection_metadata"]["held_out_grammar_read"] is False
    assert (
        selection["selection_metadata"]["reserved_or_holdout_outcomes_read"]
        is False
    )
