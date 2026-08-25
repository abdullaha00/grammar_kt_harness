"""Construct stable generator-independent MeasurementOpportunities."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..io import read_json, read_jsonl, repo_path, stable_id, write_json, write_jsonl
from ..records import grammar_cell, measurement_opportunity
from .operations import derive_agreement_site, derive_operations


DEFAULT_CONFIG = "modules/measurement/opportunities/default.json"


def _imperative_subtype(note: str | None) -> str:
    text = note or ""
    if "LET'S NOT" in text:
        return "lets_not"
    if "LET'S" in text:
        return "lets"
    if "emphatic-DO" in text:
        return "emphatic_do"
    if "LET + third-person pronoun" in text:
        return "let_pronoun"
    return "ordinary"


def _source_cases(cell_row: dict[str, Any]) -> list[tuple[str | None, list[str]]]:
    source_ids = sorted(cell_row.get("source_descriptor_ids", []))
    if cell_row["cell"]["clause"] != "imperative":
        return [(None, source_ids)]
    notes = cell_row.get("source_mapping_notes", {})
    grouped: dict[str, list[str]] = {}
    for source_id in source_ids or ["SOURCE_FIXTURE"]:
        grouped.setdefault(_imperative_subtype(notes.get(source_id)), []).append(source_id)
    return [(subtype, sorted(ids)) for subtype, ids in sorted(grouped.items())]


def _roles(cell: dict[str, str], predicate_class: str) -> list[str | None]:
    if cell["clause"] == "subject_wh_question":
        return ["subject"]
    if cell["clause"] == "non_subject_wh_question":
        return (["object", "adjunct"] if predicate_class == "lexical_transitive" and cell["voice"] == "active" else ["adjunct"])
    return [None]


def _conditions(
    cell: dict[str, str], predicate_class: str, wh_role: str | None,
    imperative_subtype: str | None, person: int = 3, number: str = "singular",
) -> dict[str, Any]:
    if cell["clause"] == "imperative":
        person, number = 2, "singular"
    return {
        "predicate_class": predicate_class,
        "subject_person": person,
        "subject_number": number,
        "wh_role": wh_role,
        "imperative_subtype": imperative_subtype,
    }


def _make(
    cell_row: dict[str, Any], conditions: dict[str, Any], source_ids: list[str], reason: str
) -> dict[str, Any]:
    cell_id = cell_row["canonical_cell_id"]
    cell = dict(grammar_cell(cell_row["cell"]))
    operations = derive_operations(cell, conditions)
    row = {
        "measurement_opportunity_id": stable_id(
            "OPP", "measurement_v1", cell_id, conditions
        ),
        "canonical_cell_id": cell_id,
        "cell": cell,
        "structural_conditions": conditions,
        "expected_operations": operations,
        "source_descriptor_ids": sorted(set(source_ids)),
        "coverage_reasons": [reason],
    }
    return measurement_opportunity(row)


def build_measurement_opportunities(
    cells: list[dict[str, Any]], config: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Build a structural bank without lexical content, folds, or KC labels."""

    selected = config or read_json(DEFAULT_CONFIG)
    opportunities: dict[str, dict[str, Any]] = {}

    def add(row: dict[str, Any]) -> None:
        key = row["measurement_opportunity_id"]
        if key in opportunities:
            existing = opportunities[key]
            existing["source_descriptor_ids"] = sorted(
                set(existing["source_descriptor_ids"]) | set(row["source_descriptor_ids"])
            )
            existing["coverage_reasons"] = sorted(
                set(existing["coverage_reasons"]) | set(row["coverage_reasons"])
            )
        else:
            opportunities[key] = row

    for cell_row in sorted(cells, key=lambda row: row["canonical_cell_id"]):
        cell = grammar_cell(cell_row["cell"])
        baseline_class = "lexical_transitive"
        for subtype, source_ids in _source_cases(cell_row):
            for role in _roles(cell, baseline_class):
                reason = (
                    f"imperative_subtype:{subtype}" if subtype is not None
                    else f"wh_role:{role}" if role is not None
                    else "canonical_cell_baseline"
                )
                conditions = _conditions(cell, baseline_class, role, subtype)
                add(_make(cell_row, conditions, source_ids, reason))

        contrast_eligible = (
            selected.get("include_predicate_class_contrasts", True)
            and cell["voice"] == "active"
            and cell["aspect"] == "none"
            and cell["modal"] == "none"
            and cell["tense"] in {"present", "past"}
            and (
                cell["polarity"] == "negative"
                or cell["clause"] in {"polar_question", "non_subject_wh_question"}
            )
        )
        if contrast_eligible:
            for subtype, source_ids in _source_cases(cell_row):
                for role in _roles(cell, "copular"):
                    conditions = _conditions(cell, "copular", role, subtype)
                    add(_make(cell_row, conditions, source_ids, "predicate_class_contrast"))

    if selected.get("include_agreement_variants", True):
        baselines = list(opportunities.values())
        for row in baselines:
            cell = row["cell"]
            conditions = row["structural_conditions"]
            site = derive_agreement_site(cell, conditions)
            if (
                site in {"none", "modal"}
                or cell["voice"] == "passive"
                or conditions["wh_role"] is not None
            ):
                continue
            for person, number in ((1, "singular"), (3, "plural")):
                varied = {**conditions, "subject_person": person, "subject_number": number}
                add(
                    _make(
                        {
                            "canonical_cell_id": row["canonical_cell_id"],
                            "cell": cell,
                        },
                        varied,
                        row["source_descriptor_ids"],
                        f"agreement_measurement:{site}",
                    )
                )

    ordered = sorted(opportunities.values(), key=lambda row: row["measurement_opportunity_id"])
    expected_cells = {row["canonical_cell_id"] for row in cells}
    actual_cells = {row["canonical_cell_id"] for row in ordered}
    if actual_cells != expected_cells:
        raise RuntimeError(f"measurement bank lost cells: {sorted(expected_cells - actual_cells)}")
    return ordered


def opportunity_bank_fingerprint(opportunities: list[dict[str, Any]]) -> str:
    payload = json.dumps(
        sorted(opportunities, key=lambda row: row["measurement_opportunity_id"]),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run(run_dir: Path, settings: dict[str, Any]) -> dict[str, Any]:
    output = run_dir / "measurement"
    output.mkdir(parents=True, exist_ok=False)
    cells = read_jsonl(run_dir / "canonical" / "canonical_cells.jsonl")
    config_path = repo_path(settings.get("config", DEFAULT_CONFIG))
    config = read_json(config_path)
    opportunities = build_measurement_opportunities(cells, config)
    fingerprint = opportunity_bank_fingerprint(opportunities)
    write_jsonl(output / "measurement_opportunities.jsonl", opportunities, sort_keys=False)
    write_json(
        output / "audit.json",
        {
            "status": "PASS",
            "opportunities": len(opportunities),
            "canonical_cells": len({row["canonical_cell_id"] for row in opportunities}),
            "opportunity_bank_sha256": fingerprint,
            "generator_fields_present": False,
            "kc_fields_present": False,
            "fold_fields_present": False,
            "config": str(config_path),
        },
    )
    return {"opportunities": len(opportunities), "opportunity_bank_sha256": fingerprint}
