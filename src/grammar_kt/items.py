"""Current controlled-transformation prompt rendering and stable IDs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .io import read_jsonl, resource


def render_prompt(template: str, cell: dict[str, str], spec: dict[str, Any], frame: dict[str, Any]) -> str:
    passive = cell["voice"] == "passive"
    imperative = cell["clause"] == "imperative"
    values = {
        **cell,
        "imperative_subtype": spec["imperative_subtype"] or "NONE",
        "subject": "IMPLICIT YOU" if imperative else spec["subject"]["text"],
        "lemma": frame["lemma"].upper(),
        "object": "NONE" if passive or frame["object"] is None else frame["object"],
        "complement": "NONE",
        "wh_phrase": spec["wh"]["phrase"] if spec["wh"] else "NONE",
        "let_pronoun": spec["let_pronoun"] or "NONE",
        "punctuation_name": "a question mark (?)" if cell["clause"].endswith("question") else "a period (.)",
    }
    return template.format(**values).strip()


def nuisance_signature(spec: dict[str, Any]) -> tuple[Any, ...]:
    return (
        spec["predicate_frame_id"],
        spec["subject"]["text"],
        spec["subject"]["person"],
        spec["subject"]["number"],
        json.dumps(spec["wh"], sort_keys=True),
        spec["imperative_subtype"],
        spec["let_pronoun"],
    )


def item_id(primary_kc_id: str, spec: dict[str, Any], replicate: int) -> str:
    basis = "|".join(
        (
            "CONTROLLED_TRANSFORMATION_v0_1",
            primary_kc_id,
            spec["canonical_cell_id"],
            spec["source_descriptor_id"],
            spec["predicate_frame_id"],
            json.dumps(spec["subject"], sort_keys=True),
            str(spec["imperative_subtype"]),
            str(replicate),
        )
    )
    return "ITEM_" + hashlib.sha256(basis.encode()).hexdigest()[:16].upper()


def evaluate_fixture(fixture: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    from .realisation import realise, validate_spec

    frames = {row["predicate_frame_id"]: row for row in read_jsonl(resource("realisation", "lexicons", config["realisation_lexicon"], ".jsonl"))}
    cell, spec = fixture["cell"], fixture["spec"]
    frame = frames[spec["predicate_frame_id"]]
    errors = validate_spec(spec, cell, frame, None)
    derivation = realise(spec, cell, frame) if not errors else None
    punctuation = "?" if cell["clause"].endswith("question") else "."
    if not fixture["target_answer"].endswith(punctuation):
        errors.append("target punctuation does not match clause type")
    if fixture["accepted_answers"] != [fixture["target_answer"]]:
        errors.append("accepted answer set is not a deterministic singleton")
    if derivation and derivation["surface"] != fixture["target_answer"]:
        errors.append("target differs from deterministic realisation")
    if frame["complement"] is not None:
        errors.append("movable complement/adjunct frame is prohibited")
    if cell["voice"] == "passive" and spec["subject"]["text"] != frame["object"]:
        errors.append("passive subject is not the frame patient")
    valid = not errors
    return {"input": fixture, "output": derivation, "valid": valid, "expected_valid": fixture.get("expected_valid"), "expectation_met": valid == fixture.get("expected_valid"), "errors": errors}


def run(run_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    from .item_generation import run_generation
    from .item_validation import run_validation

    output = run_dir / "items"
    output.mkdir(parents=True, exist_ok=False)
    generation = run_generation(output, run_dir, config)
    validation = run_validation(output, run_dir, config)
    return {**generation, **validation}
