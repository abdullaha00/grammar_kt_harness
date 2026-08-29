from __future__ import annotations

import json

import pytest

from grammar_kt.io import read_jsonl, write_json, write_jsonl
from scripts import run_full_normalisation_stability as stability

from .helpers import ROOT


SCHEMA = ROOT / "modules/grammar/canonical/schema.yaml"
PROMPT = ROOT / "modules/grammar/resource/egp/normalisation/phase1.txt"
RULEBOOK = ROOT / "modules/grammar/resource/egp/normalisation/rulebook.md"
BACKENDS = ROOT / "modules/model_backends.yaml"


def _cell(tense: object = "present") -> dict[str, object]:
    return {
        "tense": tense,
        "aspect": "none",
        "voice": "active",
        "polarity": "positive",
        "clause": "declarative",
        "modal": "none",
    }


def _mapping(source_id: str, result: str) -> dict[str, object]:
    if result == "complete":
        cells, eligible = [_cell()], []
    elif result == "partial":
        cells, eligible = [_cell(["present", "past"])], ["tense"]
    else:
        cells, eligible = [], []
    return {
        "source_id": source_id,
        "result": result,
        "cells": cells,
        "phase2_eligible": eligible,
        "note": f"private model note for {source_id}",
    }


def _write_inputs(tmp_path, results: list[str], *, missing_cefr: bool = False):
    source = []
    primary = []
    levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    for index, result in enumerate(results):
        source_id = f"s{index:02d}"
        source.append(
            {
                "source_id": source_id,
                "supercategory": f"PRIVATE CATEGORY {index % 2}",
                "subcategory": f"private subcategory {index % 3}",
                "guideword": f"private guideword {index}",
                "can_do": f"private descriptor {index}",
                "examples": [f"Private example {index}."],
                "cefr": "" if missing_cefr and index == 0 else levels[index % len(levels)],
            }
        )
        primary.append(_mapping(source_id, result))
    source_path = tmp_path / "typed_source.jsonl"
    primary_path = tmp_path / "primary.jsonl"
    write_jsonl(source_path, source)
    write_jsonl(primary_path, primary)
    return source_path, primary_path, source, primary


def _paths(tmp_path, monkeypatch):
    monkeypatch.setattr(stability, "ROOT", tmp_path)
    return tmp_path / "runs/repeat-private", tmp_path / "public"


def _prepare(
    tmp_path,
    monkeypatch,
    results: list[str],
    *,
    target: int,
    missing_cefr: bool = False,
):
    source_path, primary_path, source, primary = _write_inputs(
        tmp_path, results, missing_cefr=missing_cefr
    )
    private, public = _paths(tmp_path, monkeypatch)
    cohort = stability.prepare_cohort(
        typed_source_path=source_path,
        primary_phase1_path=primary_path,
        schema_path=SCHEMA,
        prompt_path=PROMPT,
        rulebook_path=RULEBOOK,
        backends_path=BACKENDS,
        private_evidence_dir=private,
        public_output_dir=public,
        target=target,
        seed="fixture-cohort-seed",
        exact_command="fixture prepare command",
        code_revision="fixture-revision",
    )
    return cohort, source_path, primary_path, source, primary, private, public


def test_prepare_balances_groups_reallocates_shortfall_and_is_source_text_free(
    tmp_path, monkeypatch
) -> None:
    results = ["complete"] * 5 + ["partial"] * 3 + ["unresolved"] * 2 + ["out_of_scope"]
    cohort, source_path, primary_path, _source, _primary, private, public = _prepare(
        tmp_path,
        monkeypatch,
        results,
        target=9,
        missing_cefr=True,
    )

    assert cohort["balance_strategy"] == "category_hash"
    assert cohort["initial_group_quotas"] == {
        "complete": 3,
        "partial_or_unresolved": 3,
        "out_of_scope": 3,
    }
    assert cohort["final_group_quotas"] == {
        "complete": 4,
        "partial_or_unresolved": 4,
        "out_of_scope": 1,
    }
    assert cohort["quota_reallocation"] == {
        "complete": 1,
        "partial_or_unresolved": 1,
        "out_of_scope": -2,
    }
    assert all(
        row["balance_stratum"].startswith("category_sha256:")
        for row in cohort["selected"]
    )
    published = "\n".join(path.read_text() for path in public.iterdir())
    assert "private guideword" not in published
    assert "PRIVATE CATEGORY" not in published
    assert json.loads((public / "prepare_summary.json").read_text())[
        "provider_sampling_seed"
    ]["available"] is False

    # Preparing again with identical inputs is idempotent, while input drift is
    # rejected instead of silently replacing the frozen cohort.
    repeated = stability.prepare_cohort(
        typed_source_path=source_path,
        primary_phase1_path=primary_path,
        schema_path=SCHEMA,
        prompt_path=PROMPT,
        rulebook_path=RULEBOOK,
        backends_path=BACKENDS,
        private_evidence_dir=private,
        public_output_dir=public,
        target=9,
        seed="fixture-cohort-seed",
        exact_command="fixture prepare command",
        code_revision="fixture-revision",
    )
    assert repeated == cohort
    rows = read_jsonl(primary_path)
    rows[0] = _mapping(rows[0]["source_id"], "out_of_scope")
    write_jsonl(primary_path, rows)
    with pytest.raises(ValueError, match="frozen repeated-annotation cohort"):
        stability.prepare_cohort(
            typed_source_path=source_path,
            primary_phase1_path=primary_path,
            schema_path=SCHEMA,
            prompt_path=PROMPT,
            rulebook_path=RULEBOOK,
            backends_path=BACKENDS,
            private_evidence_dir=private,
            public_output_dir=public,
            target=9,
            seed="fixture-cohort-seed",
            exact_command="fixture prepare command",
            code_revision="fixture-revision",
        )


def test_run_uses_fresh_distinct_repeat_evidence_retries_and_resumes(
    tmp_path, monkeypatch
) -> None:
    cohort, source_path, primary_path, source, _primary, private, public = _prepare(
        tmp_path,
        monkeypatch,
        ["complete", "partial", "out_of_scope"],
        target=3,
    )
    source_by_id = {row["source_id"]: row for row in source}
    calls: list[tuple[str, str]] = []

    def fake_audited_call(
        prompt,
        *,
        model,
        reasoning_effort,
        input_data,
        stage,
        call_key,
        evidence_dir,
    ):
        calls.append((call_key, stage))
        evidence_dir.mkdir(parents=True, exist_ok=False)
        write_json(evidence_dir / "input.json", input_data)
        (evidence_dir / "rendered_prompt.txt").write_text(prompt)
        write_json(
            evidence_dir / "model_settings.json",
            {
                "model": model,
                "reasoning_effort": reasoning_effort,
                "stage": stage,
                "call_key": call_key,
            },
        )
        # One schema-contract failure exercises a technical retry.  No valid
        # semantic disagreement is ever retried.
        attempt = int(evidence_dir.name.split("-")[-1])
        if call_key == cohort["selected"][0]["source_id"] and attempt == 1:
            invalid = {"source_id": call_key}
            write_json(evidence_dir / "parsed_result.json", invalid)
            return invalid
        result = _mapping(call_key, "complete")
        result["note"] = f"private repeated note and {source_by_id[call_key]['can_do']}"
        write_json(evidence_dir / "parsed_result.json", result)
        return result

    summary = stability.run_repeat(
        typed_source_path=source_path,
        primary_phase1_path=primary_path,
        schema_path=SCHEMA,
        prompt_path=PROMPT,
        rulebook_path=RULEBOOK,
        backends_path=BACKENDS,
        private_evidence_dir=private,
        public_output_dir=public,
        workers=2,
        max_attempts=2,
        exact_command="fixture run command",
        model_call=fake_audited_call,
        code_revision="fixture-revision",
    )
    assert summary["status"] == "complete"
    assert len(calls) == 4
    assert {stage for _, stage in calls} == {stability.REPEAT_STAGE}
    assert all(
        "normalisation_stability/phase1_repeat" in str(path)
        for path in private.rglob("parsed_result.json")
    )
    public_mappings = read_jsonl(public / "repeat_mappings.jsonl")
    assert len(public_mappings) == 3
    assert all(set(row) == {"source_id", "result", "cells", "phase2_eligible", "note"} for row in public_mappings)
    assert all(row["note"] == stability.PUBLIC_NOTE for row in public_mappings)
    published = "\n".join(path.read_text() for path in public.iterdir())
    assert "private repeated note" not in published
    assert "private descriptor" not in published

    def must_not_call(*_args, **_kwargs):  # pragma: no cover - failure assertion
        raise AssertionError("completed repeat checkpoint made another model call")

    rerun = stability.run_repeat(
        typed_source_path=source_path,
        primary_phase1_path=primary_path,
        schema_path=SCHEMA,
        prompt_path=PROMPT,
        rulebook_path=RULEBOOK,
        backends_path=BACKENDS,
        private_evidence_dir=private,
        public_output_dir=public,
        workers=1,
        max_attempts=2,
        exact_command="fixture resume command",
        model_call=must_not_call,
        code_revision="fixture-revision",
    )
    assert rerun["valid_repeat_mappings"] == 3

    # Simulate a crash after immutable evidence but before a checkpoint write.
    write_jsonl(public / "repeat_mappings.jsonl", public_mappings[1:])
    recovered = stability.run_repeat(
        typed_source_path=source_path,
        primary_phase1_path=primary_path,
        schema_path=SCHEMA,
        prompt_path=PROMPT,
        rulebook_path=RULEBOOK,
        backends_path=BACKENDS,
        private_evidence_dir=private,
        public_output_dir=public,
        workers=1,
        max_attempts=2,
        exact_command="fixture recover command",
        model_call=must_not_call,
        code_revision="fixture-revision",
    )
    assert recovered["valid_repeat_mappings"] == 3


def test_run_rejects_configuration_drift_before_any_model_call(
    tmp_path, monkeypatch
) -> None:
    cohort, source_path, primary_path, _source, _primary, private, public = _prepare(
        tmp_path,
        monkeypatch,
        ["complete", "partial", "out_of_scope"],
        target=3,
    )
    changed_prompt = tmp_path / "changed_phase1.txt"
    changed_prompt.write_text(PROMPT.read_text() + "\nmaterial change\n")
    called = False

    def forbidden(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("drift should be detected before calls")

    with pytest.raises(ValueError, match="cohort or its inputs drifted"):
        stability.run_repeat(
            typed_source_path=source_path,
            primary_phase1_path=primary_path,
            schema_path=SCHEMA,
            prompt_path=changed_prompt,
            rulebook_path=RULEBOOK,
            backends_path=BACKENDS,
            private_evidence_dir=private,
            public_output_dir=public,
            workers=1,
            max_attempts=2,
            exact_command="fixture drift command",
            model_call=forbidden,
            code_revision="fixture-revision",
        )
    assert cohort["frozen_before_repeat_calls"] is True
    assert called is False


def test_run_rejects_a_checkpoint_copied_without_repeat_call_evidence(
    tmp_path, monkeypatch
) -> None:
    cohort, source_path, primary_path, _source, _primary, private, public = _prepare(
        tmp_path,
        monkeypatch,
        ["complete", "partial", "out_of_scope"],
        target=3,
    )
    source_id = cohort["selected"][0]["source_id"]
    copied = _mapping(source_id, "complete")
    copied["note"] = stability.PUBLIC_NOTE
    write_jsonl(public / "repeat_mappings.jsonl", [copied])
    called = False

    def forbidden(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("unproven checkpoint must be rejected before calls")

    with pytest.raises(ValueError, match="lacks matching restricted repeat evidence"):
        stability.run_repeat(
            typed_source_path=source_path,
            primary_phase1_path=primary_path,
            schema_path=SCHEMA,
            prompt_path=PROMPT,
            rulebook_path=RULEBOOK,
            backends_path=BACKENDS,
            private_evidence_dir=private,
            public_output_dir=public,
            workers=1,
            max_attempts=2,
            exact_command="fixture copied-checkpoint command",
            model_call=forbidden,
            code_revision="fixture-revision",
        )
    assert called is False


def test_prepare_refuses_orphan_repeat_calls_without_a_frozen_cohort(
    tmp_path, monkeypatch
) -> None:
    source_path, primary_path, _source, _primary = _write_inputs(
        tmp_path, ["complete", "partial", "out_of_scope"]
    )
    private, public = _paths(tmp_path, monkeypatch)
    orphan = private / "normalisation_stability/phase1_repeat/orphan"
    orphan.mkdir(parents=True)
    with pytest.raises(ValueError, match="cohort was not frozen first"):
        stability.prepare_cohort(
            typed_source_path=source_path,
            primary_phase1_path=primary_path,
            schema_path=SCHEMA,
            prompt_path=PROMPT,
            rulebook_path=RULEBOOK,
            backends_path=BACKENDS,
            private_evidence_dir=private,
            public_output_dir=public,
            target=3,
            seed="fixture-cohort-seed",
            exact_command="fixture prepare command",
            code_revision="fixture-revision",
        )
