from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest

from grammar_kt.io import read_jsonl, read_yaml, write_json, write_jsonl
from scripts import build_dataset

from .helpers import ROOT


ORIGINAL_ASSERT_PRIVATE_DIR = build_dataset._assert_private_dir


def _cell(cell_id: str = "gc_fixture") -> dict:
    return {
        "cell_id": cell_id,
        "features": {
            "tense": "present",
            "aspect": "none",
            "voice": "active",
            "polarity": "positive",
            "clause": "declarative",
            "modal": "none",
        },
        "source_ids": ["opaque-source"],
    }


def _prepare_dataset(tmp_path: Path, *, with_kcs: bool = True):
    dataset_dir = tmp_path / "data"
    private_dir = tmp_path / "private"
    write_jsonl(dataset_dir / "grammar/cells.jsonl", [_cell()])
    if with_kcs:
        # Deliberately not valid JSON: generation may gate on this artifact but
        # must never parse or pass its contents.
        kcs_path = dataset_dir / "kcs.jsonl"
        kcs_path.parent.mkdir(parents=True, exist_ok=True)
        kcs_path.write_text("THIS MUST NOT BE READ\n", encoding="utf-8")
        write_json(
            dataset_dir / "provenance/kcs/construction.json",
            {"status": "frozen-fixture"},
        )
    return dataset_dir, private_dir


def _write_fake_evidence(
    evidence_dir: Path,
    *,
    prompt: str,
    input_data: dict,
    parsed: dict,
    model: str,
    reasoning_effort: str,
    stage: str,
    call_key: str,
) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=False)
    write_json(evidence_dir / "input.json", input_data)
    (evidence_dir / "rendered_prompt.txt").write_text(prompt, encoding="utf-8")
    write_json(
        evidence_dir / "model_settings.json",
        {
            "model": model,
            "reasoning_effort": reasoning_effort,
            "stage": stage,
            "call_key": call_key,
        },
    )
    write_json(evidence_dir / "parsed_result.json", parsed)
    (evidence_dir / "raw_output.txt").write_text(
        json.dumps(parsed) + "\n", encoding="utf-8"
    )


def _generation_payload(index: int, *, target_drift: bool = False) -> dict:
    contexts = {1: "Every morning", 2: "After lunch", 3: "Before dinner"}
    context = contexts[index]
    return {
        "prompt": f"{context}, Lina ___. (work)",
        "target_answer": (
            f"{context}, Lina sleeps."
            if target_drift
            else f"{context}, Lina works."
        ),
        "accepted_answers": ["works"],
    }


def _generation_model(*, drift_index: int | None = None, calls: list | None = None):
    def fake(prompt, **kwargs):
        index = kwargs["input_data"]["candidate_position"]["index"]
        if calls is not None:
            calls.append(kwargs["call_key"])
        parsed = _generation_payload(index, target_drift=index == drift_index)
        if kwargs["evidence_dir"] is not None:
            _write_fake_evidence(
                kwargs["evidence_dir"],
                prompt=prompt,
                input_data=kwargs["input_data"],
                parsed=parsed,
                model=kwargs["model"],
                reasoning_effort=kwargs["reasoning_effort"],
                stage=kwargs["stage"],
                call_key=kwargs["call_key"],
            )
        return parsed

    return fake


def _validator_model(*, failing: bool = False, calls: list | None = None):
    criteria = read_yaml(
        ROOT / "modules/items/validation/criteria.yaml"
    )["criteria"]

    def fake(prompt, **kwargs):
        if calls is not None:
            calls.append(kwargs["call_key"])
        parsed = {
            "judgments": {
                name: {
                    "passed": not failing,
                    "note": "Independent fixture judgment.",
                }
                for name in criteria
            }
        }
        if kwargs["evidence_dir"] is not None:
            _write_fake_evidence(
                kwargs["evidence_dir"],
                prompt=prompt,
                input_data=kwargs["input_data"],
                parsed=parsed,
                model=kwargs["model"],
                reasoning_effort=kwargs["reasoning_effort"],
                stage=kwargs["stage"],
                call_key=kwargs["call_key"],
            )
        return parsed

    return fake


@pytest.fixture(autouse=True)
def _allow_isolated_private_fixture(monkeypatch):
    # Production still enforces runs/. Tests use pytest's isolated filesystem
    # and inspect the same public/private separation there.
    monkeypatch.setattr(build_dataset, "_assert_private_dir", lambda _path: None)


def test_production_private_boundary_rejects_paths_outside_runs(tmp_path) -> None:
    with pytest.raises(ValueError, match="must stay under the ignored runs"):
        ORIGINAL_ASSERT_PRIVATE_DIR(tmp_path / "private")
    ORIGINAL_ASSERT_PRIVATE_DIR(ROOT / "runs/item-stage-fixture-private")


def test_generation_order_gate_precedes_model_calls(tmp_path) -> None:
    dataset_dir, private_dir = _prepare_dataset(tmp_path, with_kcs=False)

    def must_not_call(*args, **kwargs):
        raise AssertionError("generation ran before the K* ordering gate")

    with pytest.raises(FileNotFoundError, match=r"requires frozen K\*"):
        build_dataset.generate_items_full(
            dataset_dir,
            private_dir,
            workers=1,
            max_attempts=1,
            retry_failures=False,
            exact_command="fixture generation",
            model_call=must_not_call,
        )

    (dataset_dir / "kcs.jsonl").write_text("still not JSON\n", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match=r"requires frozen K\*"):
        build_dataset.generate_items_full(
            dataset_dir,
            private_dir,
            workers=1,
            max_attempts=1,
            retry_failures=False,
            exact_command="fixture generation",
            model_call=must_not_call,
        )


def test_generation_plan_is_public_safe_n3_and_private_calls_are_resumable(
    tmp_path,
) -> None:
    dataset_dir, private_dir = _prepare_dataset(tmp_path)
    calls = []
    build_dataset.generate_items_full(
        dataset_dir,
        private_dir,
        workers=2,
        max_attempts=2,
        retry_failures=False,
        exact_command="fixture generation",
        model_call=_generation_model(calls=calls),
    )
    assert len(calls) == 3

    plan = read_jsonl(dataset_dir / "provenance/items/generation_plan.jsonl")
    assert len(plan) == 3
    assert all(
        set(row)
        == {
            "candidate_id",
            "cell_id",
            "candidate_index",
            "input_sha256",
            "model",
            "reasoning_effort",
        }
        for row in plan
    )
    public_plan = json.dumps(plan)
    assert "Create one controlled-production" not in public_plan
    assert "target_cell" not in public_plan
    assert "opaque-source" not in public_plan
    candidates = read_jsonl(dataset_dir / "provenance/items/candidates.jsonl")
    assert len(candidates) == 3
    assert all(
        (private_dir / "items/generation" / row["item_id"] / "attempt-01/input.json")
        .is_file()
        for row in candidates
    )
    private_generation_input = json.loads(
        (
            private_dir
            / "items/generation"
            / candidates[0]["item_id"]
            / "attempt-01/input.json"
        ).read_text()
    )
    assert "opaque-source" not in json.dumps(private_generation_input)
    assert set(private_generation_input) == {
        "target_cell",
        "candidate_position",
        "item_format",
        "design",
    }
    audit = json.loads(
        (dataset_dir / "provenance/items/generation_audit.json").read_text()
    )
    assert audit["status"] == "PASS"
    assert audit["ordering_gate"]["kc_contents_read"] is False

    # Simulate a crash after all immutable private calls but before the public
    # candidate checkpoint. Exact-context recovery must avoid new calls.
    for name in (
        "candidates.jsonl",
        "generation_attempts.jsonl",
        "generation_audit.json",
    ):
        (dataset_dir / "provenance/items" / name).unlink()

    def must_not_call(*args, **kwargs):
        raise AssertionError("exact private evidence should recover the checkpoint")

    build_dataset.generate_items_full(
        dataset_dir,
        private_dir,
        workers=2,
        max_attempts=2,
        retry_failures=False,
        exact_command="fixture recovery",
        model_call=must_not_call,
    )
    attempts = read_jsonl(
        dataset_dir / "provenance/items/generation_attempts.jsonl"
    )
    assert all(row["recovered_from_private_evidence"] for row in attempts)
    assert read_jsonl(dataset_dir / "provenance/items/candidates.jsonl") == candidates

    # A context mismatch is not recoverable. Only that candidate receives a
    # fresh immutable attempt; the other two still recover without calls.
    for name in (
        "candidates.jsonl",
        "generation_attempts.jsonl",
        "generation_audit.json",
    ):
        (dataset_dir / "provenance/items" / name).unlink()
    first_id = plan[0]["candidate_id"]
    context_path = (
        private_dir / "items/generation" / first_id / "attempt-01/input.json"
    )
    context = json.loads(context_path.read_text())
    context["forbidden_drift"] = True
    write_json(context_path, context)
    replacement_calls = []
    build_dataset.generate_items_full(
        dataset_dir,
        private_dir,
        workers=2,
        max_attempts=2,
        retry_failures=False,
        exact_command="fixture mismatch recovery",
        model_call=_generation_model(calls=replacement_calls),
    )
    assert replacement_calls == [first_id]


def test_generation_retries_invalid_output_and_rejects_frozen_input_drift(
    tmp_path, monkeypatch
) -> None:
    dataset_dir, private_dir = _prepare_dataset(tmp_path)
    counts = Counter()

    def invalid_then_valid(prompt, **kwargs):
        call_key = kwargs["call_key"]
        counts[call_key] += 1
        index = kwargs["input_data"]["candidate_position"]["index"]
        parsed = (
            {"prompt": "invalid extra field", "extra": True}
            if counts[call_key] == 1
            else _generation_payload(index)
        )
        _write_fake_evidence(
            kwargs["evidence_dir"],
            prompt=prompt,
            input_data=kwargs["input_data"],
            parsed=parsed,
            model=kwargs["model"],
            reasoning_effort=kwargs["reasoning_effort"],
            stage=kwargs["stage"],
            call_key=call_key,
        )
        return parsed

    build_dataset.generate_items_full(
        dataset_dir,
        private_dir,
        workers=2,
        max_attempts=2,
        retry_failures=False,
        exact_command="fixture retry",
        model_call=invalid_then_valid,
    )
    assert set(counts.values()) == {2}
    attempts = read_jsonl(
        dataset_dir / "provenance/items/generation_attempts.jsonl"
    )
    assert {row["attempt_count"] for row in attempts} == {2}

    changed_prompt = tmp_path / "changed_generation_prompt.txt"
    changed_prompt.write_text(
        build_dataset.GENERATION_PROMPT_PATH.read_text().replace(
            "Create one", "Create exactly one", 1
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(build_dataset, "GENERATION_PROMPT_PATH", changed_prompt)
    with pytest.raises(ValueError, match="frozen generation plan changed"):
        build_dataset.generate_items_full(
            dataset_dir,
            private_dir,
            workers=1,
            max_attempts=2,
            retry_failures=False,
            exact_command="fixture drift",
            model_call=lambda *args, **kwargs: pytest.fail("must not call"),
        )


def test_public_candidate_checkpoint_cannot_diverge_from_private_evidence(
    tmp_path,
) -> None:
    dataset_dir, private_dir = _prepare_dataset(tmp_path)
    build_dataset.generate_items_full(
        dataset_dir,
        private_dir,
        workers=1,
        max_attempts=1,
        retry_failures=False,
        exact_command="fixture generation",
        model_call=_generation_model(),
    )
    path = dataset_dir / "provenance/items/candidates.jsonl"
    candidates = read_jsonl(path)
    candidates[0]["prompt"] = "Silently overwritten public prompt ___."
    write_jsonl(path, candidates)

    with pytest.raises(ValueError, match="checkpoint changed|immutable private"):
        build_dataset.generate_items_full(
            dataset_dir,
            private_dir,
            workers=1,
            max_attempts=1,
            retry_failures=False,
            exact_command="fixture immutable audit",
            model_call=lambda *args, **kwargs: pytest.fail("must not call"),
        )


def test_validation_prechecks_blinding_crash_recovery_and_curation_scale(
    tmp_path,
) -> None:
    dataset_dir, private_dir = _prepare_dataset(tmp_path)
    build_dataset.generate_items_full(
        dataset_dir,
        private_dir,
        workers=2,
        max_attempts=1,
        retry_failures=False,
        exact_command="fixture generation",
        model_call=_generation_model(),
    )
    validator_calls = []
    build_dataset.validate_items_full(
        dataset_dir,
        private_dir,
        workers=2,
        max_attempts=1,
        retry_failures=False,
        exact_command="fixture validation",
        model_call=_validator_model(calls=validator_calls),
    )
    assert len(validator_calls) == 3
    plan = read_jsonl(dataset_dir / "provenance/items/validation_plan.jsonl")
    assert all(row["validation_item_id"].startswith("validation_item_") for row in plan)
    assert all("candidate_gc_fixture" not in row["validation_item_id"] for row in plan)
    assert "Every morning" not in json.dumps(plan)

    # Recover all judgments after a checkpoint crash from exact private context.
    for name in (
        "validation_judgments.jsonl",
        "validation_attempts.jsonl",
        "validator_accepted_candidates.jsonl",
        "validation_audit.json",
    ):
        (dataset_dir / "provenance/items" / name).unlink()
    build_dataset.validate_items_full(
        dataset_dir,
        private_dir,
        workers=2,
        max_attempts=1,
        retry_failures=False,
        exact_command="fixture validation recovery",
        model_call=lambda *args, **kwargs: pytest.fail("must recover, not call"),
    )
    assert all(
        row["recovered_from_private_evidence"]
        for row in read_jsonl(
            dataset_dir / "provenance/items/validation_attempts.jsonl"
        )
    )

    # Validator settings drift likewise forces one new call rather than reuse.
    for name in (
        "validation_judgments.jsonl",
        "validation_attempts.jsonl",
        "validator_accepted_candidates.jsonl",
        "validation_audit.json",
    ):
        (dataset_dir / "provenance/items" / name).unlink()
    first_id = plan[0]["candidate_id"]
    settings_path = (
        private_dir
        / "items/validation"
        / first_id
        / "attempt-01/model_settings.json"
    )
    settings = json.loads(settings_path.read_text())
    settings["reasoning_effort"] = "drifted"
    write_json(settings_path, settings)
    replacement_calls = []
    build_dataset.validate_items_full(
        dataset_dir,
        private_dir,
        workers=2,
        max_attempts=2,
        retry_failures=False,
        exact_command="fixture validation mismatch recovery",
        model_call=_validator_model(calls=replacement_calls),
    )
    assert replacement_calls == [first_id]

    build_dataset.curate_items_full(dataset_dir, "fixture curation")
    items = read_jsonl(dataset_dir / "items/items.jsonl")
    assert len(items) == 2
    raw_candidates = read_jsonl(
        dataset_dir / "provenance/items/candidates.jsonl"
    )
    raw_judgments = read_jsonl(
        dataset_dir / "provenance/items/validation_judgments.jsonl"
    )
    assert len(raw_candidates) == len(raw_judgments) == 3
    comparison = json.loads(
        (
            dataset_dir
            / "provenance/items/curation_scale_comparison.json"
        ).read_text()
    )
    rows = comparison["comparison"]
    assert [(row["policy"], row["items"]) for row in rows] == [
        ("max_1", 1),
        ("max_2", 2),
        ("up_to_3", 3),
    ]
    assert [row["marginal_items"] for row in rows] == [1, 1, 1]
    assert all("support_distribution" in row for row in rows)
    assert comparison | {
        "uses_learner_data": False,
        "uses_kt_or_predictive_metrics": False,
        "uses_discovered_kcs": False,
        "uses_q_matrix": False,
    } == comparison


def test_validation_deterministic_rejection_skips_model_call(tmp_path) -> None:
    dataset_dir, private_dir = _prepare_dataset(tmp_path)
    build_dataset.generate_items_full(
        dataset_dir,
        private_dir,
        workers=1,
        max_attempts=1,
        retry_failures=False,
        exact_command="fixture generation with one packaging drift",
        model_call=_generation_model(drift_index=3),
    )
    validator_calls = []
    build_dataset.validate_items_full(
        dataset_dir,
        private_dir,
        workers=1,
        max_attempts=1,
        retry_failures=False,
        exact_command="fixture validation",
        model_call=_validator_model(calls=validator_calls),
    )
    assert len(validator_calls) == 2
    judgments = read_jsonl(
        dataset_dir / "provenance/items/validation_judgments.jsonl"
    )
    rejected = next(row for row in judgments if row["item_id"].endswith("_03"))
    assert rejected["rejection_stage"] == "deterministic_precheck"
    assert rejected["judgments"] == {}
    attempt = next(
        row
        for row in read_jsonl(
            dataset_dir / "provenance/items/validation_attempts.jsonl"
        )
        if row["candidate_id"].endswith("_03")
    )
    assert attempt["status"] == "deterministic_rejection"
    assert attempt["attempt_count"] == 0


def test_curation_fails_closed_for_zero_accepted_cell(tmp_path) -> None:
    dataset_dir, private_dir = _prepare_dataset(tmp_path)
    build_dataset.generate_items_full(
        dataset_dir,
        private_dir,
        workers=1,
        max_attempts=1,
        retry_failures=False,
        exact_command="fixture generation",
        model_call=_generation_model(),
    )
    build_dataset.validate_items_full(
        dataset_dir,
        private_dir,
        workers=1,
        max_attempts=1,
        retry_failures=False,
        exact_command="fixture rejecting validation",
        model_call=_validator_model(failing=True),
    )

    with pytest.raises(RuntimeError, match="zero accepted candidates"):
        build_dataset.curate_items_full(dataset_dir, "fixture blocked curation")
    blocker = json.loads(
        (dataset_dir / "provenance/items/curation_blockers.json").read_text()
    )
    assert blocker["zero_accepted_candidate_cell_ids"] == ["gc_fixture"]
    assert blocker["automatic_rescue_or_repair_performed"] is False
    assert not (dataset_dir / "items/items.jsonl").exists()


def test_two_campaign_rescue_freezes_cohorts_resumes_and_curates(tmp_path) -> None:
    dataset_dir, private_dir = _prepare_dataset(tmp_path)
    build_dataset.generate_items_full(
        dataset_dir,
        private_dir,
        workers=1,
        max_attempts=1,
        retry_failures=False,
        exact_command="fixture generation",
        model_call=_generation_model(),
    )
    build_dataset.validate_items_full(
        dataset_dir,
        private_dir,
        workers=1,
        max_attempts=1,
        retry_failures=False,
        exact_command="fixture rejecting baseline validation",
        model_call=_validator_model(failing=True),
    )

    criteria = read_yaml(
        ROOT / "modules/items/validation/criteria.yaml"
    )["criteria"]
    rescue_calls = []

    def rescue_model(prompt, **kwargs):
        rescue_calls.append((kwargs["stage"], kwargs["call_key"], prompt))
        if kwargs["stage"] == "generation":
            parsed = _generation_payload(
                kwargs["input_data"]["candidate_position"]["index"]
            )
        else:
            parsed = {
                "judgments": {
                    name: {
                        "passed": name != "determinacy",
                        "note": "Frozen rescue fixture judgment.",
                    }
                    for name in criteria
                }
            }
        _write_fake_evidence(
            kwargs["evidence_dir"],
            prompt=prompt,
            input_data=kwargs["input_data"],
            parsed=parsed,
            model=kwargs["model"],
            reasoning_effort=kwargs["reasoning_effort"],
            stage=kwargs["stage"],
            call_key=kwargs["call_key"],
        )
        return parsed

    build_dataset.run_item_campaign(
        dataset_dir,
        private_dir,
        build_dataset.UNCHANGED_RESCUE_ID,
        workers=2,
        max_attempts=1,
        retry_failures=False,
        exact_command="fixture unchanged rescue",
        model_call=rescue_model,
    )
    rescue_dir = (
        dataset_dir / "provenance/items/campaigns/unchanged_rescue"
    )
    rescue_plan = json.loads((rescue_dir / "plan.json").read_text())
    assert rescue_plan["cell_ids"] == ["gc_fixture"]
    assert rescue_plan["planned_generation_calls"] == 2
    assert rescue_plan["stops_after_early_acceptance"] is False
    assert len(read_jsonl(rescue_dir / "candidates.jsonl")) == 2
    assert len([row for row in rescue_calls if row[0] == "generation"]) == 2
    assert len([row for row in rescue_calls if row[0] == "validation"]) == 2
    effect = json.loads((rescue_dir / "coverage_effect.json").read_text())
    assert effect["newly_covered_cells"] == 0
    assert effect["remaining_zero_coverage_cell_ids"] == ["gc_fixture"]

    # Exact-context resume may not recall either backend and may not shrink the
    # already-frozen two-position cohort.
    build_dataset.run_item_campaign(
        dataset_dir,
        private_dir,
        build_dataset.UNCHANGED_RESCUE_ID,
        workers=1,
        max_attempts=1,
        retry_failures=False,
        exact_command="fixture unchanged rescue resume",
        model_call=lambda *args, **kwargs: pytest.fail("must resume without calls"),
    )
    assert json.loads((rescue_dir / "plan.json").read_text()) == rescue_plan

    intervention_calls = []

    def intervention_model(prompt, **kwargs):
        intervention_calls.append((kwargs["stage"], kwargs["call_key"], prompt))
        if kwargs["stage"] == "generation":
            parsed = _generation_payload(
                kwargs["input_data"]["candidate_position"]["index"]
            )
        else:
            parsed = {
                "judgments": {
                    name: {
                        "passed": True,
                        "note": "Frozen intervention fixture judgment.",
                    }
                    for name in criteria
                }
            }
        _write_fake_evidence(
            kwargs["evidence_dir"],
            prompt=prompt,
            input_data=kwargs["input_data"],
            parsed=parsed,
            model=kwargs["model"],
            reasoning_effort=kwargs["reasoning_effort"],
            stage=kwargs["stage"],
            call_key=kwargs["call_key"],
        )
        return parsed

    build_dataset.run_item_campaign(
        dataset_dir,
        private_dir,
        build_dataset.DETERMINACY_INTERVENTION_ID,
        workers=2,
        max_attempts=1,
        retry_failures=False,
        exact_command="fixture determinacy intervention",
        model_call=intervention_model,
    )
    intervention_dir = (
        dataset_dir
        / "provenance/items/campaigns/determinacy_intervention"
    )
    intervention_plan = json.loads((intervention_dir / "plan.json").read_text())
    assert intervention_plan["cell_ids"] == ["gc_fixture"]
    assert intervention_plan["eligibility"]["gc_fixture"]["eligible"] is True
    generation_prompts = [
        row[2] for row in intervention_calls if row[0] == "generation"
    ]
    assert len(generation_prompts) == 2
    assert all("DETERMINACY INTERVENTION" in prompt for prompt in generation_prompts)
    assert len([row for row in intervention_calls if row[0] == "validation"]) == 2
    effect = json.loads((intervention_dir / "coverage_effect.json").read_text())
    assert effect["newly_covered_cell_ids"] == ["gc_fixture"]
    assert effect["remaining_zero_coverage_cell_ids"] == []

    build_dataset.curate_items_full(dataset_dir, "fixture campaign curation")
    items = read_jsonl(dataset_dir / "items/items.jsonl")
    assert len(items) == 2
    assert all(
        row["generation_metadata"]["campaign"]
        == build_dataset.DETERMINACY_INTERVENTION_ID
        for row in items
    )
    curation = json.loads(
        (dataset_dir / "provenance/items/curation.json").read_text()
    )
    assert len(curation["declared_post_n3_campaigns"]) == 2
    assert curation["automatic_rescue_or_repair_performed"] is False


def test_packaging_correction_declaration_is_exactly_preregistered(
    tmp_path, monkeypatch
) -> None:
    config = read_yaml(build_dataset.PACKAGING_CORRECTIONS_PATH)
    assert build_dataset.sha256_file(build_dataset.PACKAGING_CORRECTIONS_PATH) == (
        build_dataset.EXPECTED_PACKAGING_CORRECTIONS_SHA256
    )
    assert {
        row["source_item_id"]: row["append_accepted_answers"]
        for row in config["corrections"]
    } == {
        "determinacy_intervention_gc_019f7fb10012b606_01": [
            "The children mustn't enter the kitchen."
        ],
        "determinacy_intervention_gc_04a854582c08aa84_02": [
            "Don't touch it.",
            "Do not touch it.",
            "Don't touch that wall.",
            "Do not touch that wall.",
        ],
        "determinacy_intervention_gc_bb4f472f992ab76b_01": [
            "Turn the light off."
        ],
    }

    changed = tmp_path / "changed_corrections.yaml"
    changed.write_text(
        build_dataset.PACKAGING_CORRECTIONS_PATH.read_text(encoding="utf-8")
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(build_dataset, "PACKAGING_CORRECTIONS_PATH", changed)
    with pytest.raises(ValueError, match="declaration hash changed"):
        build_dataset._packaging_correction_config()


def _packaging_correction_fixture() -> tuple[list[dict], list[dict], list[dict], dict]:
    specifications = [
        (
            "gc_019f7fb10012b606",
            "determinacy_intervention_gc_019f7fb10012b606_01",
            (
                "Use a negative declarative clause with must and the cue "
                "the children / enter the kitchen: ____"
            ),
            "The children must not enter the kitchen.",
            ["The children must not enter the kitchen."],
            ["The children mustn't enter the kitchen."],
            1,
        ),
        (
            "gc_04a854582c08aa84",
            "determinacy_intervention_gc_04a854582c08aa84_02",
            "The paint is wet. [____]",
            "Don't touch the wall.",
            ["Don't touch the wall.", "Do not touch the wall."],
            [
                "Don't touch it.",
                "Do not touch it.",
                "Don't touch that wall.",
                "Do not touch that wall.",
            ],
            2,
        ),
        (
            "gc_bb4f472f992ab76b",
            "determinacy_intervention_gc_bb4f472f992ab76b_01",
            "The light is on. ____",
            "Turn off the light.",
            ["Turn off the light."],
            ["Turn the light off."],
            1,
        ),
    ]
    cells = []
    candidates = []
    judgments = []
    criteria = read_yaml(
        ROOT / "modules/items/validation/criteria.yaml"
    )["criteria"]
    for cell_id, item_id, prompt, target, answers, _additions, index in specifications:
        cells.append(_cell(cell_id))
        candidates.append(
            {
                "item_id": item_id,
                "cell_id": cell_id,
                "format": "controlled_production",
                "prompt": prompt,
                "target_answer": target,
                "accepted_answers": answers,
                "generation_metadata": {
                    "candidate_index": 5 + index,
                    "candidate_count": 7,
                    "campaign": build_dataset.DETERMINACY_INTERVENTION_ID,
                    "campaign_candidate_index": index,
                    "model": "fixture-generator",
                    "reasoning_effort": "medium",
                    "input_sha256": str(index) * 64,
                },
            }
        )
        judgments.append(
            {
                "item_id": item_id,
                "deterministic_checks": {},
                "judgments": {
                    name: {
                        "passed": name != "determinacy",
                        "note": "Fixture source judgment.",
                    }
                    for name in criteria
                },
                "accepted": False,
                "rejection_stage": "independent_model_judgment",
                "validation_metadata": {
                    "policy_id": "independent_item_judgment_v1",
                    "model": "fixture-validator",
                    "reasoning_effort": "medium",
                    "input_sha256": str(index + 2) * 64,
                },
            }
        )
    candidates.sort(key=lambda row: row["item_id"])
    judgments.sort(key=lambda row: row["item_id"])
    additions = {row[1]: row[5] for row in specifications}
    config = {
        "protocol_id": build_dataset.PACKAGING_CORRECTION_ID,
        "scope": "append_only_validator_named_accepted_answers",
        "source_campaign": build_dataset.DETERMINACY_INTERVENTION_ID,
        "validation": {
            "reuse_baseline_prompt": True,
            "reuse_baseline_criteria": True,
            "independent_and_blinded": True,
        },
        "corrections": [
            {
                "correction_id": f"fixture_{index}",
                "source_item_id": candidate["item_id"],
                "corrected_item_id": f"packaging_correction_{candidate['item_id']}",
                "source_candidate_sha256": build_dataset._json_sha256(candidate),
                "source_judgment_sha256": build_dataset._json_sha256(
                    next(
                        row
                        for row in judgments
                        if row["item_id"] == candidate["item_id"]
                    )
                ),
                "append_accepted_answers": additions[candidate["item_id"]],
            }
            for index, candidate in enumerate(candidates, 1)
        ],
    }
    return cells, candidates, judgments, config


def test_packaging_correction_freezes_resumes_and_curates_without_raw_mutation(
    tmp_path, monkeypatch
) -> None:
    dataset_dir, private_dir = _prepare_dataset(tmp_path)
    cells, source_candidates, source_judgments, config = (
        _packaging_correction_fixture()
    )
    config_path = tmp_path / "fixture-corrections.yaml"
    config_path.write_text("frozen fixture correction declaration\n", encoding="utf-8")
    monkeypatch.setattr(build_dataset, "PACKAGING_CORRECTIONS_PATH", config_path)
    monkeypatch.setattr(build_dataset, "_packaging_correction_config", lambda: config)
    monkeypatch.setattr(
        build_dataset,
        "_load_complete_pre_correction_evidence",
        lambda _dataset_dir: (cells, source_candidates, source_judgments),
    )
    monkeypatch.setattr(build_dataset, "_git_revision", lambda: "fixture-revision")
    raw_candidates_before = deepcopy(source_candidates)
    raw_judgments_before = deepcopy(source_judgments)
    calls = []

    def passing_validator(prompt, **kwargs):
        calls.append(kwargs["call_key"])
        public_dir = dataset_dir / "provenance/items/packaging_corrections"
        assert (public_dir / "plan.json").is_file()
        assert (public_dir / "corrected_candidates.jsonl").is_file()
        parsed = {
            "judgments": {
                name: {"passed": True, "note": "Independent correction fixture."}
                for name in read_yaml(
                    ROOT / "modules/items/validation/criteria.yaml"
                )["criteria"]
            }
        }
        _write_fake_evidence(
            kwargs["evidence_dir"],
            prompt=prompt,
            input_data=kwargs["input_data"],
            parsed=parsed,
            model=kwargs["model"],
            reasoning_effort=kwargs["reasoning_effort"],
            stage=kwargs["stage"],
            call_key=kwargs["call_key"],
        )
        return parsed

    build_dataset.correct_items_full(
        dataset_dir,
        private_dir,
        workers=3,
        max_attempts=1,
        retry_failures=False,
        exact_command="fixture correct-items",
        model_call=passing_validator,
    )
    assert len(calls) == 3
    assert source_candidates == raw_candidates_before
    assert source_judgments == raw_judgments_before
    correction_dir = dataset_dir / "provenance/items/packaging_corrections"
    corrected = read_jsonl(correction_dir / "corrected_candidates.jsonl")
    assert len(corrected) == 3
    assert all(row["item_id"].startswith("packaging_correction_") for row in corrected)
    assert all(
        row["generation_metadata"]["campaign"]
        == build_dataset.PACKAGING_CORRECTION_ID
        for row in corrected
    )
    assert len(read_jsonl(correction_dir / "validation_judgments.jsonl")) == 3

    build_dataset.correct_items_full(
        dataset_dir,
        private_dir,
        workers=1,
        max_attempts=1,
        retry_failures=False,
        exact_command="fixture correct-items resume",
        model_call=lambda *args, **kwargs: pytest.fail("resume must make no call"),
    )

    drifted = deepcopy(config)
    drifted["corrections"][0]["append_accepted_answers"] = ["Changed answer."]
    monkeypatch.setattr(
        build_dataset, "_packaging_correction_config", lambda: drifted
    )
    with pytest.raises(ValueError, match="frozen packaging-correction plan changed"):
        build_dataset.correct_items_full(
            dataset_dir,
            private_dir,
            workers=1,
            max_attempts=1,
            retry_failures=False,
            exact_command="fixture correction drift",
            model_call=lambda *args, **kwargs: pytest.fail("drift must precede calls"),
        )
    monkeypatch.setattr(build_dataset, "_packaging_correction_config", lambda: config)

    # Curation consumes accepted copies while the raw campaign remains a
    # separate immutable input.
    write_json(
        dataset_dir / "provenance/items/campaigns/unchanged_rescue/plan.json", {}
    )
    write_json(
        dataset_dir
        / "provenance/items/campaigns/determinacy_intervention/plan.json",
        {},
    )
    monkeypatch.setattr(
        build_dataset,
        "_load_complete_baseline_item_evidence",
        lambda _dataset_dir: (cells, [], []),
    )

    def campaign_loader(_dataset_dir, _cells, campaign_id, _prior_c, _prior_j):
        if campaign_id == build_dataset.UNCHANGED_RESCUE_ID:
            return [], []
        return source_candidates, source_judgments

    monkeypatch.setattr(build_dataset, "_load_complete_campaign", campaign_loader)
    build_dataset.curate_items_full(dataset_dir, "fixture corrected curation")
    items = read_jsonl(dataset_dir / "items/items.jsonl")
    assert len(items) == 3
    assert all(row["item_id"].startswith("packaging_correction_") for row in items)
    curation = json.loads(
        (dataset_dir / "provenance/items/curation.json").read_text()
    )
    assert curation["declared_packaging_corrections"] == [
        {
            "protocol_id": build_dataset.PACKAGING_CORRECTION_ID,
            "corrected_candidates": 3,
            "accepted": 3,
        }
    ]


def test_packaging_correction_requires_determinacy_as_sole_failure(
    tmp_path, monkeypatch
) -> None:
    cells, candidates, judgments, config = _packaging_correction_fixture()
    judgments = deepcopy(judgments)
    judgments[0]["judgments"]["naturalness"]["passed"] = False
    source_id = judgments[0]["item_id"]
    declaration = next(
        row for row in config["corrections"] if row["source_item_id"] == source_id
    )
    declaration["source_judgment_sha256"] = build_dataset._json_sha256(
        judgments[0]
    )
    config_path = tmp_path / "fixture-corrections.yaml"
    config_path.write_text("frozen fixture correction declaration\n", encoding="utf-8")
    monkeypatch.setattr(build_dataset, "PACKAGING_CORRECTIONS_PATH", config_path)
    monkeypatch.setattr(build_dataset, "_packaging_correction_config", lambda: config)
    with pytest.raises(ValueError, match="sole failed required criterion"):
        build_dataset._expected_packaging_correction(cells, candidates, judgments)


def _cue_bounded_fixture() -> tuple[list[dict], list[dict], list[dict]]:
    negative = _cell("gc_04a854582c08aa84")
    negative["features"]["clause"] = "imperative"
    negative["features"]["polarity"] = "negative"
    positive = _cell("gc_bb4f472f992ab76b")
    positive["features"]["clause"] = "imperative"
    positive["features"]["polarity"] = "positive"
    candidates = [
        {"item_id": f"prior_{index:03d}", "cell_id": "historical_cell"}
        for index in range(282)
    ]
    judgments = [
        {"item_id": row["item_id"], "accepted": False}
        for row in candidates
    ]
    return [negative, positive], candidates, judgments


def test_cue_bounded_protocol_and_prompt_hashes_are_frozen(
    tmp_path, monkeypatch
) -> None:
    protocol = build_dataset._cue_bounded_imperative_protocol()
    assert protocol["campaign"]["cell_ids"] == [
        "gc_04a854582c08aa84",
        "gc_bb4f472f992ab76b",
    ]
    assert protocol["decision_rule"] == {
        "minimum_accepted_per_cell": 1,
        "minimum_accepted_overall": 2,
        "early_stopping": False,
        "post_call_repair": "forbidden",
    }
    assert build_dataset.sha256_file(
        build_dataset.CUE_BOUNDED_IMPERATIVE_PROTOCOL_PATH
    ) == build_dataset.EXPECTED_CUE_BOUNDED_IMPERATIVE_PROTOCOL_SHA256
    assert build_dataset.sha256_file(
        build_dataset.CUE_BOUNDED_IMPERATIVE_PROMPT_PATH
    ) == build_dataset.EXPECTED_CUE_BOUNDED_IMPERATIVE_PROMPT_SHA256

    changed = tmp_path / "changed-cue-prompt.txt"
    changed.write_text(
        build_dataset.CUE_BOUNDED_IMPERATIVE_PROMPT_PATH.read_text(
            encoding="utf-8"
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(build_dataset, "CUE_BOUNDED_IMPERATIVE_PROMPT_PATH", changed)
    with pytest.raises(ValueError, match="prompt hash changed"):
        build_dataset._cue_bounded_imperative_protocol()


def test_cue_bounded_campaign_freezes_resumes_rejects_drift_and_curates(
    tmp_path, monkeypatch
) -> None:
    dataset_dir, private_dir = _prepare_dataset(tmp_path)
    cells, prior_candidates, prior_judgments = _cue_bounded_fixture()
    monkeypatch.setattr(
        build_dataset,
        "_load_complete_pre_imperative_constraint_evidence",
        lambda _dataset_dir: (cells, prior_candidates, prior_judgments),
    )
    monkeypatch.setattr(build_dataset, "_git_revision", lambda: "fixture-revision")
    criteria = read_yaml(
        ROOT / "modules/items/validation/criteria.yaml"
    )["criteria"]
    calls = []
    visible_validation_inputs = []

    def campaign_model(prompt, **kwargs):
        calls.append((kwargs["stage"], kwargs["call_key"]))
        campaign_dir = (
            dataset_dir
            / "provenance/items/campaigns/cue_bounded_imperative"
        )
        assert (campaign_dir / "plan.json").is_file()
        assert (campaign_dir / "generation_plan.jsonl").is_file()
        if kwargs["stage"] == "generation":
            features = kwargs["input_data"]["target_cell"]["features"]
            if features["polarity"] == "negative":
                parsed = {
                    "prompt": (
                        "The paint is wet. Use all and only the chunks exactly "
                        "once; add no politeness, vocatives, pronouns, or adverbs. "
                        "Chunks (unordered): the wall | touch. Begin with a "
                        "capital letter and add only uncontracted negative "
                        "DO-support: [____]."
                    ),
                    "target_answer": "Do not touch the wall.",
                    "accepted_answers": ["Do not touch the wall"],
                }
            else:
                parsed = {
                    "prompt": (
                        "The light is on. Use all and only the chunks exactly "
                        "once; add no politeness, vocatives, pronouns, or adverbs. "
                        "Chunks (unordered): the light | turn off. Begin with "
                        "a capital letter: [____]."
                    ),
                    "target_answer": "Turn off the light.",
                    "accepted_answers": ["Turn off the light"],
                }
        else:
            visible_validation_inputs.append(kwargs["input_data"])
            parsed = {
                "judgments": {
                    name: {
                        "passed": True,
                        "note": "Independent cue-bounded fixture judgment.",
                    }
                    for name in criteria
                }
            }
        _write_fake_evidence(
            kwargs["evidence_dir"],
            prompt=prompt,
            input_data=kwargs["input_data"],
            parsed=parsed,
            model=kwargs["model"],
            reasoning_effort=kwargs["reasoning_effort"],
            stage=kwargs["stage"],
            call_key=kwargs["call_key"],
        )
        return parsed

    build_dataset.constrain_imperatives_full(
        dataset_dir,
        private_dir,
        workers=4,
        max_attempts=1,
        retry_failures=False,
        exact_command="fixture constrain-imperatives",
        model_call=campaign_model,
    )
    assert len([row for row in calls if row[0] == "generation"]) == 4
    assert len([row for row in calls if row[0] == "validation"]) == 4
    campaign_dir = (
        dataset_dir / "provenance/items/campaigns/cue_bounded_imperative"
    )
    plan = json.loads((campaign_dir / "plan.json").read_text())
    assert plan["cell_ids"] == [
        "gc_04a854582c08aa84",
        "gc_bb4f472f992ab76b",
    ]
    assert plan["planned_generation_calls"] == 4
    assert plan["prior_candidates"] == plan["prior_judgments"] == 282
    assert plan["stops_after_early_acceptance"] is False
    candidates = read_jsonl(campaign_dir / "candidates.jsonl")
    assert len(candidates) == 4
    assert {row["generation_metadata"]["candidate_index"] for row in candidates} == {
        8,
        9,
    }
    assert {row["generation_metadata"]["candidate_count"] for row in candidates} == {
        9
    }
    negative_prompts = [
        row["prompt"]
        for row in candidates
        if row["cell_id"] == "gc_04a854582c08aa84"
    ]
    assert len(negative_prompts) == 2
    for prompt in negative_prompts:
        cue_text = prompt.split("Chunks (unordered):", 1)[1].split(".", 1)[0]
        assert " do " not in f" {cue_text.casefold()} "
        assert " not " not in f" {cue_text.casefold()} "
        assert "the wall" in cue_text and "touch" in cue_text
    assert all(
        set(row) == {"visible_item", "target_cell", "criteria"}
        and "generation_metadata" not in str(row)
        and "campaign" not in str(row)
        for row in visible_validation_inputs
    )
    effect = json.loads((campaign_dir / "coverage_effect.json").read_text())
    assert effect["decision_rule_passed"] is True
    assert effect["accepted_candidates_by_cell"] == {
        "gc_04a854582c08aa84": 2,
        "gc_bb4f472f992ab76b": 2,
    }

    # Exact-context resume neither recalls a backend nor shrinks the cohort.
    build_dataset.constrain_imperatives_full(
        dataset_dir,
        private_dir,
        workers=1,
        max_attempts=1,
        retry_failures=False,
        exact_command="fixture constrain-imperatives resume",
        model_call=lambda *args, **kwargs: pytest.fail("resume must not call"),
    )
    assert json.loads((campaign_dir / "plan.json").read_text()) == plan

    # An upstream coverage change invalidates the frozen exact cohort before a
    # generation or validation call can occur.
    drift_candidates = deepcopy(prior_candidates)
    drift_judgments = deepcopy(prior_judgments)
    drift_candidates[0]["cell_id"] = "gc_04a854582c08aa84"
    drift_judgments[0]["accepted"] = True
    monkeypatch.setattr(
        build_dataset,
        "_load_complete_pre_imperative_constraint_evidence",
        lambda _dataset_dir: (cells, drift_candidates, drift_judgments),
    )
    with pytest.raises(ValueError, match="frozen residual cells"):
        build_dataset.constrain_imperatives_full(
            dataset_dir,
            private_dir,
            workers=1,
            max_attempts=1,
            retry_failures=False,
            exact_command="fixture cohort drift",
            model_call=lambda *args, **kwargs: pytest.fail("drift must not call"),
        )
    monkeypatch.setattr(
        build_dataset,
        "_load_complete_pre_imperative_constraint_evidence",
        lambda _dataset_dir: (cells, prior_candidates, prior_judgments),
    )

    # Curation sees the cue-bounded campaign only after the correction layer,
    # and consumes it only because the frozen coverage rule passed.
    for path in (
        dataset_dir / "provenance/items/campaigns/unchanged_rescue/plan.json",
        dataset_dir
        / "provenance/items/campaigns/determinacy_intervention/plan.json",
        dataset_dir / "provenance/items/packaging_corrections/plan.json",
    ):
        write_json(path, {})
    monkeypatch.setattr(
        build_dataset,
        "_load_complete_baseline_item_evidence",
        lambda _dataset_dir: (cells, prior_candidates, prior_judgments),
    )
    real_campaign_loader = build_dataset._load_complete_campaign

    def campaign_loader(_dataset_dir, _cells, campaign_id, prior_c, prior_j):
        if campaign_id in {
            build_dataset.UNCHANGED_RESCUE_ID,
            build_dataset.DETERMINACY_INTERVENTION_ID,
        }:
            return [], []
        return real_campaign_loader(
            _dataset_dir, _cells, campaign_id, prior_c, prior_j
        )

    monkeypatch.setattr(build_dataset, "_load_complete_campaign", campaign_loader)
    monkeypatch.setattr(
        build_dataset,
        "_load_complete_packaging_corrections",
        lambda _dataset_dir, _cells, _prior_c, _prior_j: ([], []),
    )
    build_dataset.curate_items_full(dataset_dir, "fixture cue-bounded curation")
    items = read_jsonl(dataset_dir / "items/items.jsonl")
    assert len(items) == 4
    assert all(
        row["generation_metadata"]["campaign"]
        == build_dataset.CUE_BOUNDED_IMPERATIVE_ID
        for row in items
    )
    curation = json.loads(
        (dataset_dir / "provenance/items/curation.json").read_text()
    )
    assert curation["declared_post_n3_campaigns"][-1] == {
        "campaign_id": build_dataset.CUE_BOUNDED_IMPERATIVE_ID,
        "candidates": 4,
        "accepted": 4,
        "decision_rule_passed": True,
    }
