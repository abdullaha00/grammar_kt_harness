"""Accepted mechanical rules for two-phase EGP normalisation."""

from __future__ import annotations

import json
import re
from typing import Any

from .records import CENTRAL_MODALS, DIMENSIONS as DIMENSION_ORDER, GRAMMAR_VALUES as DIMENSIONS, MORPHOLOGICAL_TENSES

RESULTS = {"complete", "partial", "out_of_scope", "schema_failure", "unresolved"}
ZERO_RESULTS = {"out_of_scope", "schema_failure", "unresolved"}
ELIGIBILITY_PREFIX = "phase2 eligible: "
REALIZATION_PREFIX = "source realization condition: "
CONTRADICTION_RE = re.compile(r"^phase2 contradiction: ([a-z_]+)=([^;]+); evidence: (.+)$")


def parse_raw_mapping(text: str) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        value = json.loads(text.strip())
    except json.JSONDecodeError as error:
        return None, [f"raw output is not exactly one JSON value: {error}"]
    return (value, []) if isinstance(value, dict) else (None, ["top-level output is not an object"])


def parse_phase2_eligibility(note: Any) -> tuple[set[str], list[str]]:
    if not isinstance(note, str) or not note.startswith(ELIGIBILITY_PREFIX):
        return set(), ["partial note must begin with 'phase2 eligible: '"]
    head, separator, suffix = note.partition("; ")
    if separator and (not suffix.startswith(REALIZATION_PREFIX) or not suffix[len(REALIZATION_PREFIX):].strip()):
        return set(), ["partial note suffix must be a non-empty 'source realization condition: ...'"]
    payload = head[len(ELIGIBILITY_PREFIX):]
    if payload == "none":
        return set(), []
    parts = payload.split(", ")
    if not parts or any(part not in DIMENSIONS for part in parts):
        return set(), ["phase2 eligibility contains an unknown dimension"]
    if len(parts) != len(set(parts)):
        return set(), ["phase2 eligibility repeats a dimension"]
    if parts != [dimension for dimension in DIMENSION_ORDER if dimension in parts]:
        return set(), ["phase2 eligibility dimensions are not in canonical order"]
    return set(parts), []


def validate_mapping(mapping: dict[str, Any], expected_id: str | None = None, *, phase: int = 1) -> list[str]:
    if phase not in {1, 2}:
        return [f"invalid validation phase: {phase}"]
    errors: list[str] = []
    if set(mapping) != {"egp_id", "result", "cells", "note"}:
        errors.append("top-level keys must be exactly egp_id, result, cells, note")
    egp_id = mapping.get("egp_id")
    if not isinstance(egp_id, str) or not egp_id:
        errors.append("egp_id must be a non-empty string")
    elif expected_id is not None and egp_id != expected_id:
        errors.append(f"egp_id mismatch: expected {expected_id}, got {egp_id}")
    result, note, cells = mapping.get("result"), mapping.get("note"), mapping.get("cells")
    if result not in RESULTS:
        errors.append(f"invalid result: {result!r}")
    if note is not None and not isinstance(note, str):
        errors.append("note must be a string or null")
    if not isinstance(cells, list):
        return errors + ["cells must be a list"]
    has_non_scalar = False
    for index, cell in enumerate(cells):
        prefix = f"cells[{index}]"
        if not isinstance(cell, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if set(cell) != set(DIMENSIONS):
            errors.append(f"{prefix} has incorrect dimension keys")
        for dimension, allowed in DIMENSIONS.items():
            value = cell.get(dimension)
            if value is None:
                has_non_scalar = True
            elif isinstance(value, str):
                if value not in allowed:
                    errors.append(f"{prefix}.{dimension} has invalid scalar {value!r}")
            elif isinstance(value, list):
                has_non_scalar = True
                if not value:
                    errors.append(f"{prefix}.{dimension} list must be non-empty")
                elif any(not isinstance(member, str) or member not in allowed for member in value):
                    errors.append(f"{prefix}.{dimension} list has invalid members")
                elif len(value) != len(set(value)):
                    errors.append(f"{prefix}.{dimension} list contains duplicates")
            else:
                errors.append(f"{prefix}.{dimension} must be scalar, list, or null")
        if set(cell) != set(DIMENSIONS):
            continue
        tense, modal = cell["tense"], cell["modal"]
        if cell["clause"] == "imperative" and (tense != "NA" or modal != "none"):
            errors.append(f"{prefix}: imperative requires tense=NA and modal=none")
        present_past_only = (isinstance(tense, str) and tense in MORPHOLOGICAL_TENSES) or (isinstance(tense, list) and bool(tense) and set(tense) <= MORPHOLOGICAL_TENSES)
        if present_past_only and modal != "none":
            errors.append(f"{prefix}: present/past-only tense requires modal=none")
        central_modal_only = (isinstance(modal, str) and modal in CENTRAL_MODALS) or (isinstance(modal, list) and bool(modal) and set(modal) <= CENTRAL_MODALS)
        if central_modal_only and tense != "NA":
            errors.append(f"{prefix}: central-modal-only constraint requires tense=NA")
    if result == "complete":
        if not cells:
            errors.append("complete requires non-empty cells")
        if has_non_scalar:
            errors.append("complete requires every dimension value to be scalar")
        for index, cell in enumerate(cells):
            if not isinstance(cell, dict) or set(cell) != set(DIMENSIONS) or cell["clause"] == "imperative":
                continue
            if cell["modal"] == "none" and cell["tense"] not in MORPHOLOGICAL_TENSES:
                errors.append(f"cells[{index}]: complete nonmodal cell requires present/past")
            if cell["modal"] != "none" and cell["tense"] != "NA":
                errors.append(f"cells[{index}]: complete modal cell requires tense=NA")
    elif result == "partial":
        if not cells:
            errors.append("partial requires non-empty cells")
        if not has_non_scalar:
            errors.append("partial requires at least one list or null")
        eligible, note_errors = parse_phase2_eligibility(note)
        errors.extend(note_errors)
        if phase == 1:
            for dimension in eligible:
                if not any(isinstance(cell, dict) and (cell.get(dimension) is None or isinstance(cell.get(dimension), list)) for cell in cells):
                    errors.append(f"phase1 eligibility names scalar-only dimension {dimension}")
    elif result in ZERO_RESULTS:
        if cells:
            errors.append(f"{result} requires cells=[]")
        if not isinstance(note, str) or not note.strip():
            errors.append(f"{result} requires a brief non-empty note")
    return errors


def _value_refines(parent: Any, child: Any) -> bool:
    if isinstance(parent, str):
        return child == parent
    if isinstance(parent, list):
        return child in parent if isinstance(child, str) else isinstance(child, list) and bool(child) and set(child) <= set(parent)
    return parent is None and (child is None or isinstance(child, (str, list)))


def _cell_refines(parent: dict[str, Any], child: dict[str, Any], eligible: set[str]) -> bool:
    return all(_value_refines(parent[field], child[field]) if field in eligible else child[field] == parent[field] for field in DIMENSION_ORDER)


def validate_phase2_transition(phase1: dict[str, Any], phase2: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if phase1.get("egp_id") != phase2.get("egp_id"):
        return ["Phase-2 egp_id differs from Phase 1"]
    if phase1.get("result") == "unresolved":
        return [] if phase2 == phase1 else ["a zero-cell Phase-1 unresolved mapping cannot be refined"]
    if phase2.get("result") == "unresolved":
        note = phase2.get("note")
        match = CONTRADICTION_RE.fullmatch(note) if isinstance(note, str) else None
        if not match:
            return ["Phase-2 unresolved note does not follow contradiction convention"]
        dimension, value, _evidence = match.groups()
        if dimension not in DIMENSIONS or value not in DIMENSIONS.get(dimension, set()):
            errors.append("Phase-2 contradiction names an invalid dimension/value")
        elif not any(isinstance(cell, dict) and cell.get(dimension) == value for cell in phase1.get("cells", [])):
            errors.append("Phase-2 contradiction does not identify an exact Phase-1 scalar")
        return errors
    if phase1.get("result") != "partial":
        return [] if phase2 == phase1 else ["non-partial Phase-1 mapping changed without contradiction"]
    if phase2.get("result") not in {"partial", "complete"}:
        return ["Phase-2 refinement must remain partial or become complete"]
    eligible, note_errors = parse_phase2_eligibility(phase1.get("note"))
    errors.extend(note_errors)
    if phase2.get("note") != phase1.get("note"):
        errors.append("Phase-2 note changed outside the contradiction outcome")
    if note_errors:
        return errors
    if not eligible:
        return errors if phase2 == phase1 else errors + ["Phase-2 changed a mapping with phase2 eligible: none"]
    parents, children = phase1.get("cells", []), phase2.get("cells", [])
    if not all(isinstance(cell, dict) and set(cell) == set(DIMENSIONS) for cell in parents + children):
        return errors + ["cannot compare malformed Phase-1/Phase-2 cells"]
    for index, child in enumerate(children):
        if not any(_cell_refines(parent, child, eligible) for parent in parents):
            errors.append(f"Phase-2 cell {index} is not a licensed refinement of any Phase-1 cell")
    for index, parent in enumerate(parents):
        if not any(_cell_refines(parent, child, eligible) for child in children):
            errors.append(f"Phase-1 cell {index} has no Phase-2 descendant")
    return errors
