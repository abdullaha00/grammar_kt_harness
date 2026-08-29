from __future__ import annotations

import json

import pytest

from grammar_kt.io import read_jsonl, read_text, read_yaml, render, write_json, write_jsonl
from grammar_kt.normalise import PHASE1_FIELDS
from scripts import build_dataset

from .helpers import ROOT


SCHEMA_PATH = ROOT / "modules/grammar/canonical/schema.yaml"
PHASE1_PROMPT_PATH = (
    ROOT / "modules/grammar/resource/egp/normalisation/phase1.txt"
)
PHASE2_PROMPT_PATH = (
    ROOT / "modules/grammar/resource/egp/normalisation/phase2.txt"
)
RULEBOOK_PATH = ROOT / "modules/grammar/resource/egp/normalisation/rulebook.md"


def _cell(tense: object) -> dict[str, object]:
    return {
        "tense": tense,
        "aspect": "none",
        "voice": "active",
        "polarity": "positive",
        "clause": "declarative",
        "modal": "none",
    }


def _mapping(
    source_id: str,
    result: str,
    *,
    note: str,
) -> dict[str, object]:
    if result == "partial":
        cells = [_cell(["present", "past"])]
        eligible = ["tense"]
    elif result == "complete":
        cells = [_cell("present"), _cell("past")]
        eligible = ["tense"]
    else:
        cells = []
        eligible = []
    return {
        "source_id": source_id,
        "result": result,
        "cells": cells,
        "phase2_eligible": eligible,
        "note": note,
    }


def _resource() -> dict[str, object]:
    return {
        "source_id": "s1",
        "supercategory": "private category",
        "subcategory": "private subcategory",
        "guideword": "private guideword",
        "can_do": "private descriptor",
        "examples": ["Private example."],
        "cefr": "B1",
    }


def _write_phase1_evidence(
    private_dir,
    resource,
    mapping,
    schema,
    backend,
) -> None:
    attempt = private_dir / "normalisation/phase1/s1/attempt-01"
    descriptor = {name: resource[name] for name in PHASE1_FIELDS}
    prompt = render(
        read_text(PHASE1_PROMPT_PATH),
        {
            "descriptor": descriptor,
            "canonical_schema": schema,
            "rulebook": read_text(RULEBOOK_PATH),
        },
    )
    write_json(attempt / "input.json", {"descriptor": descriptor})
    (attempt / "rendered_prompt.txt").write_text(prompt)
    write_json(
        attempt / "model_settings.json",
        {
            "model": backend["model"],
            "reasoning_effort": backend["reasoning_effort"],
            "stage": "normalisation.phase1",
            "call_key": "s1",
        },
    )
    write_json(attempt / "parsed_result.json", mapping)


def test_public_mapping_and_attempt_checkpoints_remove_free_text(tmp_path) -> None:
    private = _mapping("s1", "partial", note="private source-like explanation")
    legacy_public = dict(private)
    build_dataset._verify_public_normalisation_mapping(
        legacy_public, private, "s1"
    )
    mapping_path = tmp_path / "mappings.jsonl"
    build_dataset._write_public_normalisation_mappings(
        mapping_path, {"s1": private}, ["s1"]
    )
    published = read_jsonl(mapping_path)[0]
    assert published["note"] == build_dataset.PUBLIC_NORMALISATION_NOTE
    assert "source-like explanation" not in mapping_path.read_text()

    attempt = build_dataset._public_normalisation_attempt(
        {
            "source_id": "s1",
            "status": "technical_failure",
            "attempt_count": 1,
            "runtime_seconds": None,
            "errors": [
                {
                    "attempt": 1,
                    "error_type": "ValueError",
                    "error": "private descriptor was echoed in the exception",
                }
            ],
        }
    )
    assert attempt == {
        "source_id": "s1",
        "status": "technical_failure",
        "attempt_count": 1,
        "runtime_seconds": None,
        "errors": [{"error_type": "ValueError"}],
    }
    assert "private descriptor" not in json.dumps(attempt)

    tampered = {**published, "cells": [_cell("future")]}
    with pytest.raises(ValueError, match="does not match private evidence"):
        build_dataset._verify_public_normalisation_mapping(
            tampered, private, "s1"
        )


def test_phase2_uses_private_phase1_note_but_publishes_only_sanitised_notes(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(build_dataset, "ROOT", tmp_path)
    monkeypatch.setattr(build_dataset, "_git_revision", lambda: "fixture-revision")
    resource = _resource()
    schema = read_yaml(SCHEMA_PATH)
    backend = read_yaml(ROOT / "modules/model_backends.yaml")["normalisation"]
    phase1 = _mapping(
        "s1", "partial", note="ORIGINAL PRIVATE PHASE-1 LINGUISTIC NOTE"
    )
    phase2 = _mapping("s1", "complete", note="PRIVATE PHASE-2 NOTE")
    private_dir = tmp_path / "runs/private"
    dataset_dir = tmp_path / "dataset"
    output = dataset_dir / "provenance/normalisation"
    write_jsonl(
        output / "phase1_mappings.jsonl",
        [build_dataset._public_normalisation_mapping(phase1)],
    )
    _write_phase1_evidence(private_dir, resource, phase1, schema, backend)
    monkeypatch.setattr(
        build_dataset,
        "_load_and_verify_source",
        lambda _path: ([resource], {"raw_source_sha256": "fixture"}),
    )
    captured_phase1_notes: list[str] = []

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
        captured_phase1_notes.append(input_data["phase1_mapping"]["note"])
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
        write_json(evidence_dir / "parsed_result.json", phase2)
        return phase2

    monkeypatch.setattr(build_dataset, "audited_model_call", fake_audited_call)
    build_dataset.run_phase2(
        tmp_path / "unused-source.jsonl",
        dataset_dir,
        private_dir,
        workers=1,
        max_attempts=1,
        retry_failures=False,
        exact_command="fixture phase2 command",
    )
    assert captured_phase1_notes == ["ORIGINAL PRIVATE PHASE-1 LINGUISTIC NOTE"]
    assert read_jsonl(output / "phase2_mappings.jsonl")[0][
        "note"
    ] == build_dataset.PUBLIC_NORMALISATION_NOTE
    assert read_jsonl(output / "final_mappings.jsonl")[0][
        "note"
    ] == build_dataset.PUBLIC_NORMALISATION_NOTE
    attempts = read_jsonl(output / "phase2_attempts.jsonl")
    assert set(attempts[0]) == {
        "source_id",
        "status",
        "attempt_count",
        "runtime_seconds",
        "errors",
    }
    public_text = "\n".join(path.read_text() for path in output.iterdir())
    assert "ORIGINAL PRIVATE PHASE-1 LINGUISTIC NOTE" not in public_text
    assert "PRIVATE PHASE-2 NOTE" not in public_text

    def forbidden(*_args, **_kwargs):  # pragma: no cover - assertion helper
        raise AssertionError("resume should recover immutable private evidence")

    monkeypatch.setattr(build_dataset, "audited_model_call", forbidden)
    build_dataset.run_phase2(
        tmp_path / "unused-source.jsonl",
        dataset_dir,
        private_dir,
        workers=1,
        max_attempts=1,
        retry_failures=False,
        exact_command="fixture phase2 resume command",
    )


def test_private_evidence_context_drift_is_rejected(tmp_path) -> None:
    resource = _resource()
    schema = read_yaml(SCHEMA_PATH)
    backend = read_yaml(ROOT / "modules/model_backends.yaml")["normalisation"]
    mapping = _mapping("s1", "partial", note="private note")
    private_dir = tmp_path / "private"
    _write_phase1_evidence(private_dir, resource, mapping, schema, backend)
    prompt_path = private_dir / "normalisation/phase1/s1/attempt-01/rendered_prompt.txt"
    prompt_path.write_text(prompt_path.read_text() + "\ndrift")

    with pytest.raises(ValueError, match="rendered-prompt drift"):
        build_dataset._recover_phase1(
            resource,
            private_dir / "normalisation/phase1/s1",
            schema,
            phase1_prompt=read_text(PHASE1_PROMPT_PATH),
            rulebook=read_text(RULEBOOK_PATH),
            backend=backend,
        )
