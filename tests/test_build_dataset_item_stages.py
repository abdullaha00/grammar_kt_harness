from __future__ import annotations

import json
from collections import Counter
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
