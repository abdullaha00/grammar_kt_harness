"""Materialize the accepted source-linked RealizationSpec v0 cases."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from modules.realization.engine import realize, validate_spec
from shared.utils.io import ROOT, read_json, read_jsonl, repo_path, require_new_directory, utc_now, write_jsonl
from shared.utils.manifests import write_stage_manifest


def imperative_subtype(note: str | None) -> str:
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


def _case(cell_row: dict[str, Any], edge: dict[str, Any], note: str | None, serial: int, held_out: set[str]) -> dict[str, Any]:
    cell = cell_row["cell"]
    if cell["modal"] == "would":
        frame = "FRAME_LIKE"
    elif cell["voice"] == "passive":
        frame = "FRAME_REPAIR"
    elif cell["aspect"] in {"progressive", "perfect_progressive"}:
        frame = "FRAME_WORK"
    else:
        frame = "FRAME_WRITE" if serial % 2 else "FRAME_INSPECT"
    subject = (
        {"text": "The machine", "person": 3, "number": "singular"}
        if cell["voice"] == "passive"
        else (
            {"text": "The technician", "person": 3, "number": "singular"}
            if serial % 2
            else {"text": "The technicians", "person": 3, "number": "plural"}
        )
    )
    subtype = imperative_subtype(note) if cell["clause"] == "imperative" else None
    basis = f"{cell_row['canonical_cell_id']}|{edge['egp_id']}|{frame}|{subtype}|{serial}"
    return {
        "split": "held_out" if cell_row["canonical_cell_id"] in held_out else "development",
        "spec": {
            "realization_id": "REAL_" + hashlib.sha256(basis.encode()).hexdigest()[:16].upper(),
            "canonical_cell_id": cell_row["canonical_cell_id"],
            "source_descriptor_id": edge["egp_id"],
            "predicate_frame_id": frame,
            "subject": subject,
            "wh": None,
            "imperative_subtype": subtype,
            "let_pronoun": "them" if subtype == "let_pronoun" else None,
        },
    }


def run_stage(run_dir: Path, config: dict[str, Any], experiment_manifest: Path, command: list[str]) -> None:
    started = utc_now()
    output = run_dir / "realization"
    require_new_directory(output)
    cells_path = run_dir / "canonical" / "canonical_cells.jsonl"
    edges_path = run_dir / "canonical" / "source_cell_edges.jsonl"
    mappings_path = run_dir / "normalization" / "final_mappings.jsonl"
    realization_config_path = repo_path(config["config"])
    lexicon_path = repo_path(config["lexicon"])
    schema_path = repo_path(config["schema"])
    rules_path = repo_path(config["rules"])
    realization_config = read_json(realization_config_path)
    held_out = set(realization_config["held_out_cell_ids"])
    cells = read_jsonl(cells_path)
    cell_ids = {row["canonical_cell_id"] for row in cells}
    missing_held_out = held_out - cell_ids
    if missing_held_out:
        raise RuntimeError(f"frozen realization split IDs absent from canonical inventory: {sorted(missing_held_out)}")
    edges = read_jsonl(edges_path)
    mappings = {row["egp_id"]: row for row in read_jsonl(mappings_path)}
    frames = {row["predicate_frame_id"]: row for row in read_jsonl(lexicon_path)}
    by_cell: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        by_cell.setdefault(edge["canonical_cell_id"], []).append(edge)
    cases: list[dict[str, Any]] = []
    serial = 0
    for cell_row in sorted(cells, key=lambda row: row["canonical_cell_id"]):
        edge = sorted(by_cell[cell_row["canonical_cell_id"]], key=lambda row: row["egp_id"])[0]
        serial += 1
        cases.append(_case(cell_row, edge, mappings[edge["egp_id"]].get("note"), serial, held_out))
    existing = {(row["spec"]["canonical_cell_id"], row["spec"]["source_descriptor_id"]) for row in cases}
    for cell_row in cells:
        if cell_row["cell"]["clause"] != "imperative":
            continue
        for edge in sorted(by_cell[cell_row["canonical_cell_id"]], key=lambda row: row["egp_id"]):
            note = mappings[edge["egp_id"]].get("note")
            key = (cell_row["canonical_cell_id"], edge["egp_id"])
            if note and key not in existing:
                serial += 1
                cases.append(_case(cell_row, edge, note, serial, held_out))

    cell_by_id = {row["canonical_cell_id"]: row["cell"] for row in cells}
    spec_validator = Draft202012Validator(read_json(schema_path))
    realized = []
    for row in sorted(cases, key=lambda item: item["spec"]["realization_id"]):
        spec = row["spec"]
        cell = cell_by_id[spec["canonical_cell_id"]]
        frame = frames[spec["predicate_frame_id"]]
        schema_errors = list(spec_validator.iter_errors(spec))
        errors = validate_spec(spec, cell, frame, mappings[spec["source_descriptor_id"]].get("note"))
        if schema_errors or errors:
            message = schema_errors[0].message if schema_errors else "; ".join(errors)
            raise RuntimeError(f"invalid realization {spec['realization_id']}: {message}")
        realized.append({"spec": spec, "cell": cell, "derivation": realize(spec, cell, frame)})
    if {row["spec"]["canonical_cell_id"] for row in realized} != cell_ids:
        raise RuntimeError("realizations do not cover every canonical cell")

    realizations_path = output / "realizations.jsonl"
    splits_path = output / "cell_splits.jsonl"
    write_jsonl(realizations_path, realized)
    write_jsonl(
        splits_path,
        [
            {"canonical_cell_id": cell_id, "split": "held_out" if cell_id in held_out else "development"}
            for cell_id in sorted(cell_ids)
        ],
    )
    write_stage_manifest(
        output,
        module="realization",
        version=config["version"],
        started_utc=started,
        command=command,
        inputs=[cells_path, edges_path, mappings_path],
        configs=[experiment_manifest, realization_config_path, rules_path, schema_path, lexicon_path],
        code=[Path(__file__), ROOT / "modules" / "realization" / "engine.py"],
        outputs=[realizations_path, splits_path],
        details={
            "canonical_cells": len(cell_ids),
            "realization_specs": len(realized),
            "held_out_cells": len(held_out),
            "grammar_cell_fields_modified": False,
        },
    )

