"""Stage 1: two-phase EGP normalisation into resource-neutral mappings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .io import ModelCall, call_model, read_text, read_yaml, render


RESULTS = {"complete", "partial", "out_of_scope", "unresolved"}
PHASE1_FIELDS = ("source_id", "supercategory", "subcategory", "guideword", "can_do")


def _validate_mapping(mapping: dict[str, Any], source_id: str, schema: dict[str, Any]) -> None:
    if set(mapping) != {"source_id", "result", "cells", "note"}:
        raise ValueError("NormalisedMapping must contain source_id, result, cells, and note")
    if mapping["source_id"] != source_id or mapping["result"] not in RESULTS:
        raise ValueError(f"invalid normalisation result for {source_id}")
    if mapping["result"] in {"out_of_scope", "unresolved"}:
        if mapping["cells"]:
            raise ValueError(f"{mapping['result']} mappings cannot contain cells")
        return

    dimensions = schema["dimensions"]
    has_uncertainty = False
    for cell in mapping["cells"]:
        if set(cell) != set(dimensions):
            raise ValueError(f"{source_id}: normalised cell has wrong dimensions")
        for name, value in cell.items():
            allowed = set(dimensions[name]["allowed_values"])
            if value is None:
                has_uncertainty = True
            elif isinstance(value, list):
                has_uncertainty = True
                if not value or not set(value) <= allowed:
                    raise ValueError(f"{source_id}: invalid bounded values for {name}")
            elif value not in allowed:
                raise ValueError(f"{source_id}: invalid {name}={value}")
    if mapping["result"] == "complete" and (has_uncertainty or not mapping["cells"]):
        raise ValueError(f"{source_id}: complete mapping must contain exact cells")
    if mapping["result"] == "partial":
        if not has_uncertainty:
            raise ValueError(f"{source_id}: partial mapping must retain uncertainty")
        if not isinstance(mapping["note"], str) or not mapping["note"].startswith("phase2 eligible: "):
            raise ValueError(f"{source_id}: partial mapping lacks Phase-2 eligibility note")


def _eligible_dimensions(mapping: dict[str, Any]) -> list[str]:
    note = mapping.get("note") or ""
    if not note.startswith("phase2 eligible: "):
        return []
    declaration = note.removeprefix("phase2 eligible: ").split(";", 1)[0]
    return [] if declaration == "none" else [value.strip() for value in declaration.split(",")]


def _field_evidence(cells: list[dict[str, Any]], field: str) -> set[str]:
    return {json.dumps(cell[field], sort_keys=True) for cell in cells}


def _validate_phase2_transition(first: dict[str, Any], second: dict[str, Any], dimensions: list[str]) -> None:
    eligible = set(_eligible_dimensions(first))
    for field in dimensions:
        if field not in eligible and _field_evidence(first["cells"], field) != _field_evidence(second["cells"], field):
            raise ValueError(f"Phase 2 changed ineligible dimension: {field}")


def normalise(
    resources: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    model_call: ModelCall = call_model,
    evidence_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Normalise typed descriptors in source order using the declared two phases."""

    schema = read_yaml(config["canonical_schema"])
    rulebook = read_text(config["rulebook"])
    phase1_template = read_text(config["phase1_prompt"])
    phase2_template = read_text(config["phase2_prompt"])
    schema_text = read_text(config["canonical_schema"])
    mappings = []

    for resource in resources:
        source_id = resource["source_id"]
        phase1_descriptor = {name: resource[name] for name in PHASE1_FIELDS}
        prompt = render(
            phase1_template,
            {"descriptor": phase1_descriptor, "canonical_schema": schema_text, "rulebook": rulebook},
        )
        first = model_call(
            prompt,
            {"descriptor": phase1_descriptor},
            config,
            "normalisation.phase1",
            source_id,
            evidence_dir / "calls" / f"{source_id}_phase1" if evidence_dir else None,
        )
        _validate_mapping(first, source_id, schema)

        final = first
        eligible = _eligible_dimensions(first)
        if first["result"] == "partial" and eligible and resource["examples"]:
            prompt = render(
                phase2_template,
                {
                    "descriptor": phase1_descriptor,
                    "phase1_mapping": first,
                    "examples": resource["examples"],
                    "canonical_schema": schema_text,
                    "rulebook": rulebook,
                },
            )
            final = model_call(
                prompt,
                {"descriptor": phase1_descriptor, "phase1_mapping": first, "examples": resource["examples"]},
                config,
                "normalisation.phase2",
                source_id,
                evidence_dir / "calls" / f"{source_id}_phase2" if evidence_dir else None,
            )
            _validate_mapping(final, source_id, schema)
            if final["result"] not in {"unresolved", "out_of_scope"}:
                _validate_phase2_transition(first, final, schema["dimension_order"])
        mappings.append(final)
    return mappings
