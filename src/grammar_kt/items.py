"""Construct deterministic controlled-transformation items from KC opportunities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .io import read_jsonl, repo_path, stable_id, write_json, write_jsonl
from .realisation import LEXICON, imperative_subtype, realise, validate_spec


ITEM_FAMILY = "controlled_transformation"
TRANSITIVE_FRAMES = (
    "FRAME_INSPECT",
    "FRAME_WRITE",
    "FRAME_REPAIR",
    "FRAME_APPROVE",
    "FRAME_REVIEW",
    "FRAME_COMPLETE",
    "FRAME_PROCESS",
)
SUBJECTS = (
    {"text": "the technician", "person": 3, "number": "singular"},
    {"text": "the technicians", "person": 3, "number": "plural"},
    {"text": "I", "person": 1, "number": "singular"},
    {"text": "we", "person": 1, "number": "plural"},
    {"text": "she", "person": 3, "number": "singular"},
)


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
    return stable_id("ITEM", ITEM_FAMILY, primary_kc_id, spec["realization_id"], replicate)


def _wh_conditions(clause: str) -> dict[str, str] | None:
    if clause == "subject_wh_question":
        return {"phrase": "who", "role": "subject"}
    if clause == "non_subject_wh_question":
        return {"phrase": "what", "role": "object"}
    return None


def _construct_spec(
    primary_kc_id: str,
    opportunity: dict[str, Any],
    replicate: int,
    choice: int,
    frames: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    cell = opportunity["cell"]
    source_ids = opportunity["source_descriptor_ids"]
    source_id = source_ids[(replicate + choice) % len(source_ids)]
    note = opportunity["source_mapping_notes"].get(source_id)
    subtype = imperative_subtype(note) if cell["clause"] == "imperative" else None

    frame_ids = ("FRAME_LIKE",) if cell["modal"] == "would" and cell["voice"] == "active" else TRANSITIVE_FRAMES
    frame_id = frame_ids[choice % len(frame_ids)]
    if cell["voice"] == "passive":
        subject = {"text": frames[frame_id]["object"], "person": 3, "number": "singular"}
    elif cell["clause"] == "imperative":
        subject = {"text": "you", "person": 2, "number": "singular"}
    elif cell["clause"] == "subject_wh_question":
        subject = {"text": "who", "person": 3, "number": "singular"}
    else:
        subject = dict(SUBJECTS[(choice // len(frame_ids)) % len(SUBJECTS)])

    realization_id = stable_id(
        "REAL",
        "item",
        primary_kc_id,
        opportunity["canonical_cell_id"],
        source_id,
        frame_id,
        subject,
        _wh_conditions(cell["clause"]),
        subtype,
        replicate,
    )
    return {
        "realization_id": realization_id,
        "canonical_cell_id": opportunity["canonical_cell_id"],
        "source_descriptor_id": source_id,
        "predicate_frame_id": frame_id,
        "subject": subject,
        "wh": _wh_conditions(cell["clause"]),
        "imperative_subtype": subtype,
        "let_pronoun": "them" if subtype == "let_pronoun" else None,
    }


def construct_items(
    projections: list[dict[str, Any]],
    cards: list[dict[str, Any]],
    frames: dict[str, dict[str, Any]],
    template: str,
    *,
    replicates_per_kc: int,
    development_replicates: int,
) -> list[dict[str, Any]]:
    """Select opportunities and construct unique deterministic exercises."""

    opportunities_by_kc = {
        card["kc_id"]: [row for row in projections if card["kc_id"] in row["kc_ids"]]
        for card in cards
    }
    candidates: list[dict[str, Any]] = []
    used_prompts: set[str] = set()
    used_answers: set[str] = set()

    for kc_offset, primary_kc_id in enumerate(sorted(opportunities_by_kc)):
        domain = sorted(opportunities_by_kc[primary_kc_id], key=lambda row: row["canonical_cell_id"])
        if not domain:
            raise RuntimeError(f"KC has no item-generation opportunities: {primary_kc_id}")
        for replicate in range(replicates_per_kc):
            selected = None
            for opportunity_offset in range(len(domain)):
                opportunity = domain[(replicate + kc_offset + opportunity_offset) % len(domain)]
                cell = opportunity["cell"]
                for lexical_offset in range(len(TRANSITIVE_FRAMES) * len(SUBJECTS)):
                    choice = replicate + kc_offset + lexical_offset
                    spec = _construct_spec(primary_kc_id, opportunity, replicate, choice, frames)
                    frame = frames[spec["predicate_frame_id"]]
                    errors = validate_spec(
                        spec,
                        cell,
                        frame,
                        opportunity["source_mapping_notes"].get(spec["source_descriptor_id"]),
                    )
                    if errors:
                        continue
                    derivation = realise(spec, cell, frame)
                    prompt = render_prompt(template, cell, spec, frame)
                    if prompt not in used_prompts and derivation["surface"] not in used_answers:
                        selected = (opportunity, cell, spec, derivation, prompt, opportunity_offset, lexical_offset)
                        break
                if selected is not None:
                    break
            if selected is None:
                raise RuntimeError(
                    f"could not construct a unique item for {primary_kc_id} replicate {replicate}"
                )
            opportunity, cell, spec, derivation, prompt, opportunity_offset, lexical_offset = selected

            used_prompts.add(prompt)
            used_answers.add(derivation["surface"])
            candidates.append(
                {
                    "item_id": item_id(primary_kc_id, spec, replicate),
                    "source_descriptor_ids": opportunity["source_descriptor_ids"],
                    "canonical_cell_id": opportunity["canonical_cell_id"],
                    "realization_spec": spec,
                    "item_family": ITEM_FAMILY,
                    "primary_kc_id": primary_kc_id,
                    "all_kc_ids": opportunity["kc_ids"],
                    "prompt": prompt,
                    "target_answer": derivation["surface"],
                    "accepted_answers": [derivation["surface"]],
                    "contrast_set_id": None,
                    "generation_metadata": {
                        "opportunity_id": opportunity["opportunity_id"],
                        "replicate": replicate,
                        "split": "development" if replicate < development_replicates else "held_out",
                        "deterministic": True,
                        "opportunity_search_offset": opportunity_offset,
                        "lexical_search_offset": lexical_offset,
                    },
                }
            )

    assigned: set[str] = set()
    contrast_serial = 0
    cells = {row["canonical_cell_id"]: row["cell"] for row in projections}
    for index, left in enumerate(candidates):
        for right in candidates[index + 1 :]:
            if left["item_id"] in assigned or right["item_id"] in assigned:
                continue
            if nuisance_signature(left["realization_spec"]) != nuisance_signature(right["realization_spec"]):
                continue
            left_cell = cells[left["canonical_cell_id"]]
            right_cell = cells[right["canonical_cell_id"]]
            if sum(left_cell[key] != right_cell[key] for key in left_cell) == 1:
                contrast_serial += 1
                contrast_id = f"CONTRAST_{contrast_serial:03d}"
                left["contrast_set_id"] = right["contrast_set_id"] = contrast_id
                assigned.update((left["item_id"], right["item_id"]))
                break

    if len({row["item_id"] for row in candidates}) != len(candidates):
        raise RuntimeError("generated item IDs are not unique")
    return candidates


def generate_items(items_dir: Path, run_dir: Path, settings: dict[str, Any]) -> dict[str, Any]:
    output = items_dir / "generation"
    output.mkdir(parents=True, exist_ok=False)
    projections = read_jsonl(run_dir / "kc" / "cell_kc_projection.jsonl")
    cards = read_jsonl(run_dir / "kc" / "kc_inventory.jsonl")
    frames = {row["predicate_frame_id"]: row for row in read_jsonl(LEXICON)}
    template_path = repo_path(settings["family_prompt"])
    template = template_path.read_text(encoding="utf-8")

    candidates = construct_items(
        projections,
        cards,
        frames,
        template,
        replicates_per_kc=int(settings["replicates_per_kc"]),
        development_replicates=int(settings["development_replicates"]),
    )
    ordered = sorted(candidates, key=lambda row: row["item_id"])
    write_jsonl(output / "candidate_items.jsonl", ordered)

    units = [
        {"validation_unit_id": f"IV1{index:02d}", "item_id": row["item_id"], "duplicate_of": None}
        for index, row in enumerate(ordered, 1)
    ]
    repeated = [row for row in ordered if row["generation_metadata"]["split"] == "held_out"][
        : int(settings["validation"].get("repeated_diagnostics", 5))
    ]
    originals = {unit["item_id"]: unit["validation_unit_id"] for unit in units}
    for index, row in enumerate(repeated, len(units) + 1):
        units.append(
            {
                "validation_unit_id": f"IV1{index:02d}",
                "item_id": row["item_id"],
                "duplicate_of": originals[row["item_id"]],
            }
        )
    write_jsonl(output / "validation_units.jsonl", units)

    opportunities = {row["opportunity_id"]: row for row in projections}
    cards_by_id = {row["kc_id"]: row for row in cards}
    for item in ordered:
        unit_dir = output / "units" / item["item_id"]
        unit_dir.mkdir(parents=True, exist_ok=False)
        write_json(
            unit_dir / "input.json",
            {
                "opportunity": opportunities[item["generation_metadata"]["opportunity_id"]],
                "primary_kc": cards_by_id[item["primary_kc_id"]],
            },
        )
        write_json(
            unit_dir / "procedure.json",
            {
                "implementation": "deterministic controlled transformation",
                "template": str(template_path),
                "lexicon": str(LEXICON),
                "model_invoked": False,
            },
        )
        write_json(unit_dir / "generated_item.json", item)
    return {"candidate_items": len(ordered), "diagnostic_units": len(units)}


def evaluate_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    frames = {row["predicate_frame_id"]: row for row in read_jsonl(LEXICON)}
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
    return {
        "input": fixture,
        "output": derivation,
        "valid": valid,
        "expected_valid": fixture.get("expected_valid"),
        "expectation_met": valid == fixture.get("expected_valid"),
        "errors": errors,
    }


def run(run_dir: Path, settings: dict[str, Any]) -> dict[str, Any]:
    from .item_validation import run_validation

    output = run_dir / "items"
    output.mkdir(parents=True, exist_ok=False)
    generation = generate_items(output, run_dir, settings)
    validation = run_validation(output, run_dir, settings)
    return {**generation, **validation}
