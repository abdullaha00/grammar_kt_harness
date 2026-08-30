from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

import jsonschema
import pytest

from scripts.experiments.measurement_realism_worlds import (
    CANONICAL_FORMATS,
    DEFAULT_CONFIG,
    ROOT,
    _validate_retained_claim_boundary,
    create_run_plan,
    load_executable_config,
    load_selected_cells,
    read_jsonl,
    run_planned_world,
    validate_controlled_instrument,
    validate_curated_bank,
    validate_run_plan,
)


HERE = (
    ROOT
    / "experiments/measurement_realism/design/controlled_instrument_v1"
)
CONFIG = HERE / "scenario_config.yaml"
ROWS = HERE / "instrument.jsonl"
SCHEMA = HERE / "controlled_instrument.schema.json"
MANIFEST = HERE / "manifest.json"
FAILED_RUN = (
    ROOT
    / "experiments/measurement_realism/design/bank_protocol/runs/"
    "matched_bank_v0_2_20260830"
)


@pytest.fixture(scope="module")
def controlled_inputs():
    config = load_executable_config(CONFIG)
    selected = load_selected_cells(config)
    rows = read_jsonl(ROWS)
    return config, selected, rows


def _load_builder_module():
    path = HERE / "build_scaffold.py"
    spec = importlib.util.spec_from_file_location("controlled_scaffold_builder", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scaffold_replays_and_contains_only_structural_placeholders(
    controlled_inputs,
):
    config, selected, rows = controlled_inputs
    audit = validate_controlled_instrument(
        rows, selected, config, schema_path=SCHEMA
    )
    assert audit["item_count"] == 152
    assert audit["families"] == 38
    assert audit["seen_items"] == 144
    assert audit["probe_only_items"] == 8
    assert audit["seen_cell_q_rank"] == 18
    assert audit["formats"] == {label: 38 for label in CANONICAL_FORMATS}
    assert audit["release_eligible"] is False
    assert audit["learner_facing_content_present"] is False

    forbidden = {
        "learner_view",
        "instruction",
        "context",
        "canonical_target_sentence",
        "semantic_frame",
        "target_answer",
        "scoring",
        "accepted_responses",
        "candidate_id",
        "source_candidate_item_id",
        "validation_status",
    }
    assert all(not (forbidden & set(row)) for row in rows)
    assert all(not row["slot_id"].startswith("mb0_") for row in rows)
    assert all(row["instrument_status"] == "STRUCTURAL_PLACEHOLDER_ONLY" for row in rows)
    assert all(row["release_eligible"] is False for row in rows)
    assert all(row["placeholder_metadata"]["format_is_label_only"] for row in rows)

    builder = _load_builder_module()
    replay = builder.build_rows(selected)
    replay_payload = "".join(builder.canonical_json(row) + "\n" for row in replay)
    assert replay_payload == ROWS.read_text(encoding="utf-8")
    assert builder.semantic_hash(replay) == audit["raw_semantic_sha256"]


def test_scaffold_and_curated_schemas_are_mechanically_disjoint(controlled_inputs):
    config, selected, rows = controlled_inputs
    curated_schema_path = (
        ROOT
        / config["frozen_overlay"]["curated_bank_contract"]["schema_path"]
    )
    curated_schema = json.loads(curated_schema_path.read_text(encoding="utf-8"))
    controlled_schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert list(jsonschema.Draft202012Validator(curated_schema).iter_errors(rows[0]))

    standard = load_executable_config(DEFAULT_CONFIG)
    standard_selected = load_selected_cells(standard)
    from scripts.experiments.measurement_realism_worlds import (
        build_synthetic_bank_fixture,
    )

    fixture = build_synthetic_bank_fixture(standard_selected, standard)
    assert list(
        jsonschema.Draft202012Validator(controlled_schema).iter_errors(fixture[0])
    )
    with pytest.raises(ValueError, match="missing"):
        validate_curated_bank(
            rows,
            selected,
            config,
            schema_path=None,
            fixture=False,
        )


def test_failed_live_bank_is_recorded_as_incomplete_without_reusing_content():
    decisions = read_jsonl(FAILED_RUN / "curation/family_decisions.jsonl")
    by_round = Counter(row["candidate_round"] for row in decisions)
    accepted = {row["family_id"] for row in decisions if row["decision"] == "accept"}
    attempted = {row["family_id"] for row in decisions}
    unresolved = attempted - accepted
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert len(decisions) == 106
    assert by_round == {1: 38, 2: 35, 3: 33}
    assert len(attempted) == 38
    assert len(accepted) == 5
    assert len(unresolved) == 33
    assert not (FAILED_RUN / "bank").exists()
    assert manifest["curated_bank_failure_evidence"]["accepted_families"] == 5
    assert manifest["construction_uses_generated_candidate_content"] is False
    assert manifest["learner_facing_item_bank"] is False
    assert manifest["release_eligible"] is False


def test_controlled_plan_requires_explicit_mode_and_freezes_every_input(
    controlled_inputs, tmp_path: Path
):
    output = tmp_path / "controlled_plan"
    with pytest.raises(ValueError, match="explicit --controlled-scenario"):
        create_run_plan(
            config_path=CONFIG,
            bank_path=ROWS,
            output_dir=output,
            controlled_scenario=False,
        )
    plan = create_run_plan(
        config_path=CONFIG,
        bank_path=ROWS,
        output_dir=output,
        controlled_scenario=True,
    )
    assert plan["status"] == "PREREGISTERED_CONTROLLED_SCENARIO_BEFORE_RESPONSES"
    assert plan["scenario_kind"] == "controlled_instrument_scaffold"
    assert plan["controlled_scenario"] is True
    assert plan["release_eligible"] is False
    assert plan["production_curated_bank_evidence"] is None
    assert plan["frozen_acquisition_budget"] == 188
    assert len(plan["run_matrix"]) == 27
    for stage_command in plan["commands"].values():
        assert "--controlled-scenario" in stage_command
        assert "--config experiments/measurement_realism/design/controlled_instrument_v1/scenario_config.yaml" in stage_command
    assert {
        "executable_config",
        "base_executable_config",
        "selected_cells",
        "controlled_instrument",
        "controlled_instrument_schema",
        "controlled_instrument_manifest",
        "controlled_instrument_builder",
        "controlled_instrument_protocol",
        "controlled_instrument_execution_plan",
        "failed_curated_decision_ledger",
        "implementation_script",
        "schedule_dependency",
        "dependency_declaration",
    } == set(plan["inputs"])
    validate_run_plan(output, controlled_scenario=True)
    with pytest.raises(ValueError, match="explicit --controlled-scenario"):
        validate_run_plan(output, controlled_scenario=False)

    # External paths are available for plan-only unit tests, but can never
    # become controlled scientific response locations.
    with pytest.raises(ValueError, match="isolated canonical"):
        run_planned_world(
            output,
            world_id="clean_zero",
            seed=20260829,
            policy_id="q_balanced_lab",
            learner_count=2,
            controlled_scenario=True,
        )
    assert not (output / "runs").exists()


def test_controlled_plan_claim_boundary_is_revalidated(controlled_inputs, tmp_path: Path):
    output = tmp_path / "controlled_plan"
    create_run_plan(
        config_path=CONFIG,
        bank_path=ROWS,
        output_dir=output,
        controlled_scenario=True,
    )
    plan_path = output / "study_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["release_eligible"] = True
    plan_path.write_text(json.dumps(plan, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="claim boundary"):
        validate_run_plan(output, controlled_scenario=True)


def test_controlled_plan_rejects_protected_and_unpreregistered_paths(controlled_inputs, tmp_path: Path):
    with pytest.raises(ValueError, match="protected tree"):
        create_run_plan(
            config_path=CONFIG,
            bank_path=ROWS,
            output_dir=ROOT / "data/grammar_kt_full_v1",
            controlled_scenario=True,
        )

    output = tmp_path / "controlled_plan"
    create_run_plan(
        config_path=CONFIG,
        bank_path=ROWS,
        output_dir=output,
        controlled_scenario=True,
    )
    plan_path = output / "study_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["run_matrix"].append(
        {"world_id": "unplanned", "policy_id": "q_balanced_lab", "seed": 1}
    )
    plan_path.write_text(json.dumps(plan, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="run_matrix"):
        validate_run_plan(output, controlled_scenario=True)


def test_controlled_run_manifest_claims_fail_closed():
    valid = {
        "controlled_scenario": True,
        "release_eligible": False,
        "learner_facing_measurement_validity": "NOT_ASSESSED",
        "platform_plausibility": "NOT_ASSESSED",
    }
    _validate_retained_claim_boundary(
        valid, controlled_scenario=True, artifact="response"
    )
    for field, weakened in (
        ("release_eligible", True),
        ("learner_facing_measurement_validity", "VALIDATED"),
        ("platform_plausibility", "VALIDATED"),
    ):
        tampered = {**valid, field: weakened}
        with pytest.raises(ValueError, match="claim boundary"):
            _validate_retained_claim_boundary(
                tampered, controlled_scenario=True, artifact="response"
            )
