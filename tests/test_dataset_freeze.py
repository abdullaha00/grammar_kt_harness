from __future__ import annotations

import copy
import gzip
import json
from pathlib import Path

import pytest

from grammar_kt.baseline_simulation import iter_baseline_rows
from grammar_kt.dataset_freeze import (
    file_sha256,
    semantic_sha256,
    verify_artifact_inventory,
    verify_baseline_streams,
    write_baseline_streams,
)
from grammar_kt.grammar_regimes import design_grammar_regimes, recommended_regime_design
from grammar_kt.io import read_yaml, write_json, write_jsonl, write_yaml
from grammar_kt.kc import activation_matches
from grammar_kt.measurement_gate import (
    build_measurement_bundle,
    write_measurement_artifacts,
)
from scripts.freeze_baseline_dataset import freeze_full_v1_dataset

from .helpers import ROOT


def _stream_inputs() -> tuple[list[dict], list[dict], list[dict], dict[str, str], dict]:
    items = [
        {"item_id": "item_seen", "cell_id": "cell_plain_first"},
        {"item_id": "item_combination", "cell_id": "cell_marked_first"},
        {"item_id": "item_value", "cell_id": "cell_novel_third"},
    ]
    kcs = [
        {"id": "kc_form"},
        {"id": "kc_first"},
        {"id": "kc_third"},
    ]
    q_rows = [
        {
            "item_id": "item_seen",
            "cell_id": "cell_plain_first",
            "generator_kc_ids": ["kc_first", "kc_form"],
        },
        {
            "item_id": "item_combination",
            "cell_id": "cell_marked_first",
            "generator_kc_ids": ["kc_first", "kc_form"],
        },
        {
            "item_id": "item_value",
            "cell_id": "cell_novel_third",
            "generator_kc_ids": ["kc_form", "kc_third"],
        },
    ]
    regimes = {
        "cell_plain_first": "seen",
        "cell_marked_first": "unseen_combination",
        "cell_novel_third": "unseen_value",
    }
    config = read_yaml(ROOT / "modules/simulation/baseline.yaml")
    config["seed"] = 1701
    config["learners"] = 3
    config["schedule"]["acquisition"]["target_opportunities_per_seen_kc"] = 3
    return items, kcs, q_rows, regimes, config


def _write_stream_pair(
    directory: Path,
    *,
    config_override: dict | None = None,
) -> tuple[dict, Path, Path]:
    items, kcs, q_rows, regimes, config = _stream_inputs()
    if config_override is not None:
        config = config_override
    interactions = directory / "interactions.jsonl.gz"
    oracle = directory / "oracle/learner_truth.jsonl.gz"
    summary = write_baseline_streams(
        interactions,
        oracle,
        iter_baseline_rows(
            items, kcs, q_rows, regimes, config, seed=config["seed"]
        ),
        items=items,
        q_rows=q_rows,
        grammar_regime_by_cell=regimes,
        config=config,
    )
    return summary, interactions, oracle


def test_paired_streams_are_deterministic_canonical_and_oracle_separated(
    tmp_path: Path,
) -> None:
    first, first_interactions, first_oracle = _write_stream_pair(tmp_path / "first")
    second, second_interactions, second_oracle = _write_stream_pair(tmp_path / "second")

    assert first == second
    assert first_interactions.read_bytes() == second_interactions.read_bytes()
    assert first_oracle.read_bytes() == second_oracle.read_bytes()
    assert first["rows"] == 3 * (3 + 3)
    assert first["observable_has_oracle_fields"] is False
    assert first["paired_rows_verified"] is True

    # FLG has no original-filename bit, and bytes 4:8 hold the zero mtime.
    for path in (first_interactions, first_oracle):
        header = path.read_bytes()[:10]
        assert header[:3] == b"\x1f\x8b\x08"
        assert header[3] & 0x08 == 0
        assert header[4:8] == b"\x00\x00\x00\x00"

    with gzip.open(first_interactions, "rt", encoding="utf-8") as stream:
        observable = [json.loads(line) for line in stream]
    assert observable
    assert list(observable[0]) == [
        "learner_id",
        "item_id",
        "sequence_index",
        "correct",
        "phase",
        "pass_index",
        "grammar_regime",
    ]
    assert not any(
        name in row
        for row in observable
        for name in (
            "active_generator_kc_ids",
            "mastery_before",
            "mastery_after",
            "response_probability",
            "response_draw",
            "updates_mastery",
        )
    )

    items, _kcs, q_rows, regimes, config = _stream_inputs()
    assert verify_baseline_streams(
        first_interactions,
        first_oracle,
        items=items,
        q_rows=q_rows,
        grammar_regime_by_cell=regimes,
        config=config,
        expected_summary=first,
    ) == first


def test_stream_freeze_resumes_one_missing_file_and_refuses_drift(
    tmp_path: Path,
) -> None:
    summary, interactions, oracle = _write_stream_pair(tmp_path / "resume")
    retained_interactions = interactions.read_bytes()
    oracle.unlink()
    replay, replay_interactions, replay_oracle = _write_stream_pair(tmp_path / "resume")
    assert replay == summary
    assert replay_interactions.read_bytes() == retained_interactions
    assert replay_oracle.is_file()
    assert not list((tmp_path / "resume").rglob("*.partial"))

    _items, _kcs, _q_rows, _regimes, changed = _stream_inputs()
    changed = copy.deepcopy(changed)
    changed["seed"] += 1
    with pytest.raises(ValueError, match="refusing to overwrite changed frozen"):
        _write_stream_pair(tmp_path / "resume", config_override=changed)
    assert interactions.read_bytes() == retained_interactions


def test_stream_verifier_rejects_public_outcome_tampering(tmp_path: Path) -> None:
    summary, interactions, oracle = _write_stream_pair(tmp_path / "tamper")
    with gzip.open(interactions, "rt", encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream]
    rows[0]["correct"] = 1 - rows[0]["correct"]
    with interactions.open("wb") as raw:
        with gzip.GzipFile(
            filename="", fileobj=raw, mode="wb", compresslevel=9, mtime=0
        ) as compressed:
            for row in rows:
                compressed.write(
                    (
                        json.dumps(
                            row,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                        + "\n"
                    ).encode("utf-8")
                )

    items, _kcs, q_rows, regimes, config = _stream_inputs()
    with pytest.raises(ValueError, match="disagree on correct"):
        verify_baseline_streams(
            interactions,
            oracle,
            items=items,
            q_rows=q_rows,
            grammar_regime_by_cell=regimes,
            config=config,
            expected_summary=summary,
        )


def test_stream_verifier_can_require_exact_deterministic_replay(
    tmp_path: Path,
) -> None:
    summary, interactions, oracle = _write_stream_pair(tmp_path / "replay")
    items, kcs, q_rows, regimes, config = _stream_inputs()
    expected = list(
        iter_baseline_rows(
            items, kcs, q_rows, regimes, config, seed=config["seed"]
        )
    )
    changed_interaction = copy.deepcopy(expected[0][0])
    changed_oracle = copy.deepcopy(expected[0][1])
    changed_oracle["response_draw"] = (
        changed_oracle["response_draw"] + 0.25
    ) % 1.0
    expected[0] = (changed_interaction, changed_oracle)

    with pytest.raises(ValueError, match="differs from deterministic replay"):
        verify_baseline_streams(
            interactions,
            oracle,
            items=items,
            q_rows=q_rows,
            grammar_regime_by_cell=regimes,
            config=config,
            expected_summary=summary,
            expected_row_pairs=expected,
        )


def _schema() -> dict:
    return {
        "schema_id": "toy_mood_person_polarity_v1",
        "dimension_order": ["mood", "person", "polarity"],
        "dimensions": {
            "mood": {
                "allowed_values": ["indicative", "subjunctive", "irrealis"]
            },
            "person": {"allowed_values": ["first", "third"]},
            "polarity": {"allowed_values": ["affirmative", "negative"]},
        },
    }


def _cells() -> list[dict]:
    rows = []
    for mood in ("indicative", "subjunctive"):
        for person in ("first", "third"):
            for polarity in ("affirmative", "negative"):
                rows.append(
                    {
                        "cell_id": f"cell_{mood}_{person}_{polarity}",
                        "features": {
                            "mood": mood,
                            "person": person,
                            "polarity": polarity,
                        },
                    }
                )
    rows.append(
        {
            "cell_id": "cell_irrealis_first_affirmative",
            "features": {
                "mood": "irrealis",
                "person": "first",
                "polarity": "affirmative",
            },
        }
    )
    return rows


def _generator_kcs(cells: list[dict]) -> list[dict]:
    declarations = [
        (
            "kc_clause_form",
            {
                "cell": {
                    "mood": ["indicative", "subjunctive", "irrealis"]
                }
            },
        ),
        ("kc_subjunctive", {"cell": {"mood": "subjunctive"}}),
        ("kc_third_person", {"cell": {"person": "third"}}),
    ]
    rows = []
    for kc_id, rule in declarations:
        support = sorted(
            row["cell_id"]
            for row in cells
            if activation_matches(row["features"], rule)
        )
        rows.append(
            {
                "id": kc_id,
                "name": kc_id,
                "description": "Language-neutral test generator KC.",
                "activation_rule": rule,
                "supporting_cell_ids": support,
                "cell_support": len(support),
            }
        )
    return rows


def _regime_design() -> dict:
    design = recommended_regime_design()
    design["unseen_value"].update(
        {
            "target_cells": 1,
            "minimum_cells": 1,
            "maximum_cells": 1,
            "maximum_unseen_value_only_kcs": 0,
        }
    )
    design["unseen_combination"].update(
        {"target_cells": 2, "minimum_cells": 2, "beam_width": 32}
    )
    return design


def _prepare_runner_fixture(tmp_path: Path) -> dict[str, Path]:
    dataset = tmp_path / "dataset"
    declarations = tmp_path / "declarations"
    cells = _cells()
    kcs = _generator_kcs(cells)
    items = [
        {
            "item_id": f"item_{cell['cell_id']}",
            "cell_id": cell["cell_id"],
            "format": "controlled_production",
            "prompt": f"Produce test form {index}: ____",
            "target_answer": f"form {index}",
            "accepted_answers": [f"form {index}"],
        }
        for index, cell in enumerate(cells, 1)
    ]
    schema = _schema()
    regime_design = _regime_design()
    regimes = design_grammar_regimes(
        schema,
        cells,
        generator_kcs=kcs,
        items=items,
        design=regime_design,
    )
    measurement_design = {
        "design_id": "toy_generator_measurement_v1",
        "support": {
            "minimum_items_per_kc_before_simulation": 1,
            "rare_kc_cell_threshold": 1,
            "rare_kc_item_threshold": 1,
        },
        "identifiability": {
            "require_nonempty_item_projection": True,
            "require_unique_q_columns": True,
            "require_full_column_rank": True,
        },
    }
    bundle = build_measurement_bundle(
        cells,
        items,
        kcs,
        measurement_design,
        grammar_regime_by_cell=regimes["assignments"],
    )
    assert bundle["audit"]["status"] == "PASS"

    write_jsonl(dataset / "grammar/cells.jsonl", cells)
    write_jsonl(
        dataset / "grammar/source_cell_relations.jsonl",
        [
            {"source_id": f"source_{index}", "cell_id": cell["cell_id"]}
            for index, cell in enumerate(cells, 1)
        ],
    )
    write_jsonl(dataset / "kcs.jsonl", kcs)
    write_jsonl(dataset / "items/items.jsonl", items)
    write_json(
        dataset / "provenance/items/curation.json",
        {
            "status": "PASS",
            "selected_items": len(items),
            "covered_cells": len(cells),
            "final_bank_sha256": semantic_sha256(items),
        },
    )
    write_jsonl(dataset / "grammar/regime_assignments.jsonl", regimes["assignments"])
    write_json(dataset / "provenance/grammar_regimes/audit.json", regimes["audit"])
    write_measurement_artifacts(
        bundle,
        dense_q_matrix_path=dataset / "q_matrix.csv",
        sparse_q_matrix_path=dataset / "oracle/q_matrix_sparse.jsonl",
        audit_path=dataset / "provenance/measurement/audit.json",
        manifest_path=dataset / "provenance/measurement/manifest.json",
    )

    schema_path = declarations / "schema.yaml"
    regime_design_path = declarations / "regimes.yaml"
    measurement_design_path = declarations / "measurement.yaml"
    config_path = declarations / "baseline.yaml"
    write_yaml(schema_path, schema)
    write_yaml(regime_design_path, regime_design)
    write_yaml(measurement_design_path, measurement_design)
    config = read_yaml(ROOT / "modules/simulation/baseline.yaml")
    config["seed"] = 1801
    config["learners"] = 2
    config["schedule"]["acquisition"]["target_opportunities_per_seen_kc"] = 12
    write_yaml(config_path, config)

    condition = {
        "aggregation": "minimum",
        "learning_rule": "all_active_opportunity",
        "schedule_mode": "q_balanced",
        "target_opportunities_per_seen_kc": 12,
        "exhaustive_passes": None,
        "learning_rate": 0.02,
        "beta_alpha": 2.0,
        "beta_beta": 2.0,
        "guess": 0.1,
        "slip": 0.1,
        "condition_id": "toy_admissible_baseline",
        "admissible": True,
        "analytical_aggregation_gates_passed": True,
        "simulation_gates": {"passed": True, "failures": []},
    }
    pilot_path = declarations / "pilot.json"
    write_json(
        pilot_path,
        {
            "pilot_id": "baseline_simulator_assumptions_v1",
            "scientific_boundary": {
                "prediction_or_kc_recovery_used": False,
                "inputs_not_accepted": ["k_hat", "learner_outcomes", "kt_predictions"],
            },
            "protocol": {"learners": 8, "seed": 1801},
            "inputs": {
                "items_file_sha256": file_sha256(dataset / "items/items.jsonl"),
                "generator_kcs_file_sha256": file_sha256(dataset / "kcs.jsonl"),
                "q_matrix_file_sha256": file_sha256(dataset / "q_matrix.csv"),
                "grammar_regimes_file_sha256": file_sha256(
                    dataset / "grammar/regime_assignments.jsonl"
                ),
                "item_count": len(items),
                "generator_kc_count": len(kcs),
            },
            "conditions": [condition],
            "admissible_condition_ids": [condition["condition_id"]],
        },
    )
    return {
        "dataset": dataset,
        "pilot": pilot_path,
        "config": config_path,
        "schema": schema_path,
        "regime_design": regime_design_path,
        "measurement_design": measurement_design_path,
    }


def _freeze_fixture(paths: dict[str, Path], *, verify_only: bool = False) -> dict:
    return freeze_full_v1_dataset(
        paths["dataset"],
        pilot_path=paths["pilot"],
        simulation_config_path=paths["config"],
        grammar_schema_path=paths["schema"],
        regime_design_path=paths["regime_design"],
        measurement_design_path=paths["measurement_design"],
        verify_only=verify_only,
        exact_command="pytest toy full-v1 freeze",
    )


def test_full_freeze_runner_plans_first_inventories_and_verifies_without_writes(
    tmp_path: Path,
) -> None:
    paths = _prepare_runner_fixture(tmp_path)
    manifest = _freeze_fixture(paths)
    dataset = paths["dataset"]

    assert manifest["status"] == "FROZEN_BASELINE_COMPLETE"
    assert manifest["scale"] | {
        "canonical_grammar_cells": 9,
        "generator_kcs": 3,
        "items": 9,
        "learners": 2,
    } == manifest["scale"]
    assert (dataset / "provenance/simulation/freeze_plan.json").is_file()
    assert (dataset / "provenance/simulation/baseline.yaml").is_file()
    assert (dataset / "provenance/simulation/pilot.json").is_file()
    assert (dataset / "interactions.jsonl.gz").is_file()
    assert (dataset / "oracle/learner_truth.jsonl.gz").is_file()
    assert "oracle/q_matrix_sparse.jsonl" in manifest["artifact_inventory"]
    assert "README.md" in manifest["artifact_inventory"]
    assert "manifest.json" not in manifest["artifact_inventory"]
    verify_artifact_inventory(dataset, manifest["artifact_inventory"])

    before = {
        relative: file_sha256(dataset / relative)
        for relative in [*manifest["artifact_inventory"], "manifest.json"]
    }
    assert _freeze_fixture(paths, verify_only=True) == manifest
    after = {
        relative: file_sha256(dataset / relative)
        for relative in [*manifest["artifact_inventory"], "manifest.json"]
    }
    assert after == before


def test_full_freeze_preflight_rejects_pilot_hash_drift_before_plan(
    tmp_path: Path,
) -> None:
    paths = _prepare_runner_fixture(tmp_path)
    pilot = json.loads(paths["pilot"].read_text(encoding="utf-8"))
    pilot["inputs"]["q_matrix_file_sha256"] = "0" * 64
    write_json(paths["pilot"], pilot)

    with pytest.raises(ValueError, match="pilot input hash differs"):
        _freeze_fixture(paths)
    assert not (paths["dataset"] / "provenance/simulation/freeze_plan.json").exists()
    assert not (paths["dataset"] / "interactions.jsonl.gz").exists()


def test_full_freeze_refuses_outcomes_that_predate_the_plan(tmp_path: Path) -> None:
    paths = _prepare_runner_fixture(tmp_path)
    interactions = paths["dataset"] / "interactions.jsonl.gz"
    interactions.write_bytes(b"outcomes must not predate K*/Q*/simulation freeze")

    with pytest.raises(ValueError, match="outputs exist before the freeze plan"):
        _freeze_fixture(paths)
    assert not (paths["dataset"] / "provenance/simulation/freeze_plan.json").exists()


def test_complete_freeze_rejects_stream_neutral_config_drift(tmp_path: Path) -> None:
    paths = _prepare_runner_fixture(tmp_path)
    _freeze_fixture(paths)
    config = read_yaml(paths["config"])
    config["description"] += " Changed after freezing."
    write_yaml(paths["config"], config)

    with pytest.raises(ValueError, match="frozen baseline simulation plan changed"):
        _freeze_fixture(paths, verify_only=True)


def test_complete_freeze_rejects_manifest_claim_tampering(tmp_path: Path) -> None:
    paths = _prepare_runner_fixture(tmp_path)
    _freeze_fixture(paths)
    manifest_path = paths["dataset"] / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["scale"]["items"] += 1
    write_json(manifest_path, manifest)

    with pytest.raises(ValueError, match="manifest claims differ"):
        _freeze_fixture(paths, verify_only=True)


def test_frozen_dataset_inventory_rejects_added_downstream_artifact(
    tmp_path: Path,
) -> None:
    paths = _prepare_runner_fixture(tmp_path)
    manifest = _freeze_fixture(paths)
    write_json(paths["dataset"] / "downstream_result.json", {"must_not": "mutate"})

    with pytest.raises(ValueError, match="artifact inventory changed"):
        verify_artifact_inventory(paths["dataset"], manifest["artifact_inventory"])
    with pytest.raises(ValueError, match="artifact inventory changed"):
        _freeze_fixture(paths, verify_only=True)
