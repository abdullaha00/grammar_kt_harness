"""Construct one ontology-independent bank of controlled grammar items."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .io import read_json, read_jsonl, read_yaml, repo_path, stable_id, write_json, write_jsonl
from .realisation import LEXICON, imperative_subtype, realise, validate_spec


ITEM_FAMILY = "controlled_transformation"
BASE_SUBJECT = {"text": "the technician", "person": 3, "number": "singular"}
AGREEMENT_SUBJECTS = (
    {"text": "I", "person": 1, "number": "singular"},
    {"text": "the technicians", "person": 3, "number": "plural"},
)


# Item form and stable ontology-independent identity

def render_prompt(
    template: str,
    cell: dict[str, str],
    spec: dict[str, Any],
    frame: dict[str, Any],
) -> str:
    passive = cell["voice"] == "passive"
    imperative = cell["clause"] == "imperative"
    values = {
        **cell,
        "imperative_subtype": spec["imperative_subtype"] or "NONE",
        "subject": "IMPLICIT YOU" if imperative else spec["subject"]["text"],
        "lemma": frame["lemma"].upper(),
        "object": "NONE" if passive or frame["object"] is None else frame["object"],
        "complement": frame["complement"] or "NONE",
        "wh_phrase": spec["wh"]["phrase"] if spec["wh"] else "NONE",
        "let_pronoun": spec["let_pronoun"] or "NONE",
        "punctuation_name": (
            "a question mark (?)" if cell["clause"].endswith("question") else "a period (.)"
        ),
    }
    return template.format(**values).strip()


def nuisance_signature(spec: dict[str, Any]) -> tuple[Any, ...]:
    """Conditions that must be equal for a controlled cell contrast."""

    return (
        spec["predicate_frame_id"],
        spec["subject"]["text"],
        spec["subject"]["person"],
        spec["subject"]["number"],
        json.dumps(spec["wh"], sort_keys=True),
        spec["imperative_subtype"],
        spec["let_pronoun"],
    )


def item_identity(item: dict[str, Any]) -> str:
    """Hash only grammatical/item content, never a KC or policy label."""

    return stable_id(
        "ITEM",
        ITEM_FAMILY,
        item["item_opportunity_id"],
        item["canonical_cell_id"],
        item["realization_spec"],
        item["prompt"],
        item["target_answer"],
    )


def item_bank_record(item: dict[str, Any]) -> dict[str, Any]:
    """Return bank content shared by every ontology projection."""

    fields = (
        "item_id",
        "item_opportunity_id",
        "source_descriptor_ids",
        "canonical_cell_id",
        "realization_spec",
        "realization_evidence",
        "item_family",
        "prompt",
        "target_answer",
        "accepted_answers",
        "contrast_set_id",
        "generation_metadata",
    )
    return {field: item[field] for field in fields}


def item_bank_fingerprint(items: list[dict[str, Any]]) -> str:
    """SHA-256 of sorted ontology-independent records, excluding validator evidence."""

    records = [item_bank_record(row) for row in sorted(items, key=lambda value: value["item_id"])]
    payload = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# Opportunity construction

def _wh_conditions(cell: dict[str, str]) -> list[dict[str, str] | None]:
    if cell["clause"] == "subject_wh_question":
        return [{"phrase": "who", "role": "subject"}]
    if cell["clause"] == "non_subject_wh_question":
        return [
            {"phrase": "what", "role": "object"},
            {"phrase": "when", "role": "adjunct"},
        ]
    return [None]


def _base_frame_id(cell: dict[str, str], config: dict[str, Any]) -> str:
    if cell["modal"] == "would":
        return config["would_frame_id"]
    return config["baseline_frame_id"]


def _base_subject(
    cell: dict[str, str], frame: dict[str, Any], wh: dict[str, str] | None
) -> dict[str, Any]:
    if cell["voice"] == "passive":
        return {"text": frame["object"], "person": 3, "number": "singular"}
    if cell["clause"] == "imperative":
        return {"text": "you", "person": 2, "number": "singular"}
    if wh and wh["role"] == "subject":
        return {"text": wh["phrase"], "person": 3, "number": "singular"}
    return dict(BASE_SUBJECT)


def _make_opportunity(
    cell_row: dict[str, Any],
    split: str,
    source_id: str,
    source_note: str | None,
    frame_id: str,
    subject: dict[str, Any],
    wh: dict[str, str] | None,
    subtype: str | None,
    coverage_reasons: list[str],
    frames: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    cell_id = cell_row["canonical_cell_id"]
    cell = cell_row["cell"]
    frame = frames[frame_id]
    realization_id = stable_id(
        "REAL", "item_bank_v0", cell_id, source_id, frame_id, subject, wh, subtype
    )
    spec = {
        "realization_id": realization_id,
        "canonical_cell_id": cell_id,
        "source_descriptor_id": source_id,
        "predicate_frame_id": frame_id,
        "subject": subject,
        "wh": wh,
        "imperative_subtype": subtype,
        "let_pronoun": "them" if subtype == "let_pronoun" else None,
    }
    errors = validate_spec(spec, cell, frame, source_note)
    if errors:
        raise RuntimeError(f"invalid item opportunity {realization_id}: {'; '.join(errors)}")
    derivation = realise(spec, cell, frame)
    coverage_tags = sorted(
        {
            f"frame_type:{frame['frame_type']}",
            f"agreement_site:{derivation['agreement_site']}",
            f"auxiliary_count:{len(derivation['auxiliary_chain'])}",
            f"subject:{subject['person']}:{subject['number']}",
            *(f"operation:{operation}" for operation in derivation["operations"]),
        }
    )
    opportunity_id = stable_id(
        "ITEMOPP", cell_id, frame_id, subject, wh, subtype, source_id
    )
    return {
        "item_opportunity_id": opportunity_id,
        "canonical_cell_id": cell_id,
        "cell": cell,
        "canonical_split": split,
        "source_descriptor_ids": cell_row["source_descriptor_ids"],
        "source_mapping_notes": cell_row["source_mapping_notes"],
        "realization_spec": spec,
        "realization_evidence": {
            "operations": derivation["operations"],
            "agreement_site": derivation["agreement_site"],
            "auxiliary_chain": derivation["auxiliary_chain"],
            "coverage_tags": coverage_tags,
        },
        "coverage_reasons": sorted(set(coverage_reasons)),
        "target_answer": derivation["surface"],
    }


def _source_cases(cell_row: dict[str, Any]) -> list[tuple[str, str | None, str | None]]:
    """Select one source normally and one per licensed imperative subtype."""

    notes = cell_row["source_mapping_notes"]
    if cell_row["cell"]["clause"] != "imperative":
        source_id = sorted(cell_row["source_descriptor_ids"])[0]
        return [(source_id, notes[source_id], None)]
    by_subtype: dict[str, tuple[str, str | None]] = {}
    for source_id in sorted(cell_row["source_descriptor_ids"]):
        note = notes[source_id]
        subtype = imperative_subtype(note)
        by_subtype.setdefault(subtype, (source_id, note))
    return [
        (source_id, note, subtype)
        for subtype, (source_id, note) in sorted(by_subtype.items())
    ]


def build_item_opportunities(
    cells: list[dict[str, Any]],
    split_rows: list[dict[str, Any]],
    frames: dict[str, dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Cover cells and important realization conditions without consulting a KC policy."""

    split_by_cell = {row["canonical_cell_id"]: row["split"] for row in split_rows}
    cell_by_id = {row["canonical_cell_id"]: row for row in cells}
    if set(split_by_cell) != set(cell_by_id):
        raise RuntimeError("item-bank splits must exactly cover the canonical inventory")

    opportunities: dict[str, dict[str, Any]] = {}

    def add(
        cell_row: dict[str, Any],
        source_id: str,
        source_note: str | None,
        subtype: str | None,
        frame_id: str,
        subject: dict[str, Any],
        wh: dict[str, str] | None,
        reason: str,
    ) -> dict[str, Any]:
        row = _make_opportunity(
            cell_row,
            split_by_cell[cell_row["canonical_cell_id"]],
            source_id,
            source_note,
            frame_id,
            subject,
            wh,
            subtype,
            [reason],
            frames,
        )
        existing = opportunities.get(row["item_opportunity_id"])
        if existing:
            existing["coverage_reasons"] = sorted(
                set(existing["coverage_reasons"]) | set(row["coverage_reasons"])
            )
            return existing
        opportunities[row["item_opportunity_id"]] = row
        return row

    # First, every cell; imperative subtypes and WH roles are separate conditions.
    for cell_row in sorted(cells, key=lambda row: row["canonical_cell_id"]):
        cell = cell_row["cell"]
        frame_id = _base_frame_id(cell, config)
        frame = frames[frame_id]
        for source_id, source_note, subtype in _source_cases(cell_row):
            for wh in _wh_conditions(cell):
                reason = (
                    f"imperative_subtype:{subtype}"
                    if subtype is not None
                    else f"wh_role:{wh['role']}" if wh is not None
                    else "canonical_cell_baseline"
                )
                add(
                    cell_row,
                    source_id,
                    source_note,
                    subtype,
                    frame_id,
                    _base_subject(cell, frame, wh),
                    wh,
                    reason,
                )

    # Contrast a lexical predicate (DO-support where required) with inherent BE.
    if config.get("include_operator_source_contrasts", True):
        copular_id = config["operator_contrast_frame_id"]
        copular = frames[copular_id]
        for cell_row in sorted(cells, key=lambda row: row["canonical_cell_id"]):
            cell = cell_row["cell"]
            eligible = (
                cell["voice"] == "active"
                and cell["aspect"] == "none"
                and cell["modal"] == "none"
                and cell["tense"] in {"present", "past"}
                and (
                    cell["polarity"] == "negative"
                    or cell["clause"] in {"polar_question", "non_subject_wh_question"}
                )
            )
            if not eligible:
                continue
            source_id, source_note, subtype = _source_cases(cell_row)[0]
            for wh in _wh_conditions(cell):
                add(
                    cell_row,
                    source_id,
                    source_note,
                    subtype,
                    copular_id,
                    _base_subject(cell, copular, wh),
                    wh,
                    "operator_source_contrast",
                )

    # Sample subject agreement by observed realization profile, not per cell.
    if config.get("include_agreement_variants", True):
        representatives: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for row in sorted(
            opportunities.values(),
            key=lambda value: (
                value["canonical_cell_id"],
                value["realization_spec"]["predicate_frame_id"],
                json.dumps(value["realization_spec"]["wh"], sort_keys=True),
                value["realization_spec"]["imperative_subtype"] or "",
                value["realization_spec"]["source_descriptor_id"],
            ),
        ):
            cell = row["cell"]
            site = row["realization_evidence"]["agreement_site"]
            frame_type = frames[row["realization_spec"]["predicate_frame_id"]]["frame_type"]
            if (
                site in {"none", "modal"}
                or cell["voice"] == "passive"
                or cell["clause"] in {"imperative", "subject_wh_question"}
            ):
                continue
            # Keep nuisance coverage in each canonical split rather than letting
            # one arbitrary cell supply agreement evidence for every split.
            profile = (row["canonical_split"], site, cell["tense"], frame_type)
            representatives.setdefault(profile, row)
        for profile, representative in sorted(representatives.items()):
            cell_row = cell_by_id[representative["canonical_cell_id"]]
            spec = representative["realization_spec"]
            note = cell_row["source_mapping_notes"][spec["source_descriptor_id"]]
            for subject in AGREEMENT_SUBJECTS:
                add(
                    cell_row,
                    spec["source_descriptor_id"],
                    note,
                    spec["imperative_subtype"],
                    spec["predicate_frame_id"],
                    dict(subject),
                    spec["wh"],
                    f"agreement_profile:{':'.join(profile)}",
                )

    ordered = sorted(opportunities.values(), key=lambda row: row["item_opportunity_id"])
    covered_cells = {row["canonical_cell_id"] for row in ordered}
    if covered_cells != set(cell_by_id):
        raise RuntimeError(f"item bank lost canonical cells: {sorted(set(cell_by_id) - covered_cells)}")
    return ordered


# Deterministic item construction and saved generation evidence

def construct_items(
    opportunities: list[dict[str, Any]],
    frames: dict[str, dict[str, Any]],
    template: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for opportunity in opportunities:
        cell = opportunity["cell"]
        spec = opportunity["realization_spec"]
        frame = frames[spec["predicate_frame_id"]]
        prompt = render_prompt(template, cell, spec, frame)
        item = {
            "item_id": "",
            "item_opportunity_id": opportunity["item_opportunity_id"],
            "source_descriptor_ids": opportunity["source_descriptor_ids"],
            "canonical_cell_id": opportunity["canonical_cell_id"],
            "realization_spec": spec,
            "realization_evidence": opportunity["realization_evidence"],
            "item_family": ITEM_FAMILY,
            "prompt": prompt,
            "target_answer": opportunity["target_answer"],
            "accepted_answers": [opportunity["target_answer"]],
            "contrast_set_id": None,
            "generation_metadata": {
                "canonical_split": opportunity["canonical_split"],
                "coverage_reasons": opportunity["coverage_reasons"],
                "deterministic": True,
            },
        }
        item["item_id"] = item_identity(item)
        candidates.append(item)

    assigned: set[str] = set()
    contrast_serial = 0
    cells = {row["canonical_cell_id"]: row["cell"] for row in opportunities}
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

    item_ids = [row["item_id"] for row in candidates]
    opportunity_ids = [row["item_opportunity_id"] for row in candidates]
    if len(item_ids) != len(set(item_ids)) or len(opportunity_ids) != len(set(opportunity_ids)):
        raise RuntimeError("generated item or opportunity IDs are not unique")
    if len({row["prompt"] for row in candidates}) != len(candidates):
        raise RuntimeError("ontology-independent opportunities produced duplicate prompts")
    return sorted(candidates, key=lambda row: row["item_id"])


def generate_items(
    items_dir: Path,
    run_dir: Path,
    *,
    family_prompt_path: str | Path,
    bank_config_path: str | Path,
    repeated_diagnostics: int,
) -> dict[str, Any]:
    output = items_dir / "generation"
    output.mkdir(parents=True, exist_ok=False)
    cells = read_jsonl(run_dir / "canonical" / "canonical_cells.jsonl")
    split_rows = read_jsonl(run_dir / "realisation" / "cell_splits.jsonl")
    frames = {row["predicate_frame_id"]: row for row in read_jsonl(LEXICON)}
    template_path = repo_path(family_prompt_path)
    template = template_path.read_text(encoding="utf-8")
    config = read_json(repo_path(bank_config_path))

    opportunities = build_item_opportunities(cells, split_rows, frames, config)
    candidates = construct_items(opportunities, frames, template)
    write_jsonl(output / "item_opportunities.jsonl", opportunities)
    write_jsonl(output / "candidate_items.jsonl", candidates)

    units = [
        {"validation_unit_id": f"IV1{index:03d}", "item_id": row["item_id"], "duplicate_of": None}
        for index, row in enumerate(candidates, 1)
    ]
    repeated = [
        row for row in candidates
        if row["generation_metadata"]["canonical_split"] != "development"
    ][:repeated_diagnostics]
    originals = {unit["item_id"]: unit["validation_unit_id"] for unit in units}
    for index, row in enumerate(repeated, len(units) + 1):
        units.append(
            {
                "validation_unit_id": f"IV1{index:03d}",
                "item_id": row["item_id"],
                "duplicate_of": originals[row["item_id"]],
            }
        )
    write_jsonl(output / "validation_units.jsonl", units)

    opportunity_by_id = {row["item_opportunity_id"]: row for row in opportunities}
    for item in candidates:
        unit_dir = output / "units" / item["item_id"]
        unit_dir.mkdir(parents=True, exist_ok=False)
        write_json(unit_dir / "input.json", opportunity_by_id[item["item_opportunity_id"]])
        write_json(
            unit_dir / "procedure.json",
            {
                "implementation": "deterministic ontology-independent item bank v0",
                "bank_config": str(repo_path(bank_config_path)),
                "template": str(template_path),
                "lexicon": str(LEXICON),
                "model_invoked": False,
                "kc_policy_consulted": False,
            },
        )
        write_json(unit_dir / "generated_item.json", item)

    tags = Counter(
        tag for row in candidates for tag in row["realization_evidence"]["coverage_tags"]
    )
    splits = Counter(row["generation_metadata"]["canonical_split"] for row in candidates)
    report = {
        "bank_version": config["bank_version"],
        "item_bank_sha256": item_bank_fingerprint(candidates),
        "canonical_cells": len(cells),
        "opportunities": len(opportunities),
        "items": len(candidates),
        "items_by_canonical_split": dict(sorted(splits.items())),
        "coverage_tag_support": dict(sorted(tags.items())),
        "ontology_fields_present": [],
    }
    write_json(output / "bank_report.json", report)
    return {
        "candidate_items": len(candidates),
        "diagnostic_units": len(units),
        "item_bank_sha256": report["item_bank_sha256"],
    }


# One-fixture boundary

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
    if frame["complement"] is not None and frame["frame_type"] != "copular":
        errors.append("free non-copular complement/adjunct frame is prohibited")
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


# Full stage

def run(run_dir: Path, settings: dict[str, Any]) -> dict[str, Any]:
    from .item_validation import run_validation

    output = run_dir / "items"
    output.mkdir(parents=True, exist_ok=False)
    validation_settings = settings["validation"]
    generation = generate_items(
        output,
        run_dir,
        family_prompt_path=settings["family_prompt"],
        bank_config_path=settings["bank_config"],
        repeated_diagnostics=int(validation_settings.get("repeated_diagnostics", 5)),
    )
    validation = run_validation(
        output,
        run_dir,
        family_template=repo_path(settings["family_prompt"]).read_text(encoding="utf-8"),
        acceptance=read_json(validation_settings["acceptance"]),
        backend_config=read_yaml(validation_settings["backend_config"]),
        workers=int(validation_settings.get("workers", 6)),
        max_attempts=int(validation_settings.get("max_attempts", 2)),
    )
    return {**generation, **validation}
