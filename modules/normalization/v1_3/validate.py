#!/usr/bin/env python3
"""Mechanical validation for the frozen v1.3 pilot and its outputs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from _common import (
    INPUT,
    LOGS,
    OUTPUTS,
    execution_config,
    load_json,
    load_jsonl,
    sha256_path,
    verify_frozen_manifest,
    verify_prior_pilots,
    verify_source,
)


DIMENSION_ORDER = ("tense", "aspect", "voice", "polarity", "clause", "modal")
DIMENSIONS: dict[str, set[str]] = {
    "tense": {"present", "past", "NA"},
    "aspect": {"none", "progressive", "perfect", "perfect_progressive"},
    "voice": {"active", "passive"},
    "polarity": {"positive", "negative"},
    "clause": {
        "declarative",
        "polar_question",
        "subject_wh_question",
        "non_subject_wh_question",
        "imperative",
    },
    "modal": {
        "none",
        "can",
        "could",
        "may",
        "might",
        "must",
        "shall",
        "should",
        "will",
        "would",
    },
}
CENTRAL_MODALS = DIMENSIONS["modal"] - {"none"}
CENTRAL_MODAL_LIST = [
    "can",
    "could",
    "may",
    "might",
    "must",
    "shall",
    "should",
    "will",
    "would",
]
MORPHOLOGICAL_TENSES = {"present", "past"}
RESULTS = {"complete", "partial", "out_of_scope", "schema_failure", "unresolved"}
ZERO_RESULTS = {"out_of_scope", "schema_failure", "unresolved"}
ELIGIBILITY_PREFIX = "phase2 eligible: "
REALIZATION_PREFIX = "source realization condition: "
CONTRADICTION_RE = re.compile(
    r"^phase2 contradiction: ([a-z_]+)=([^;]+); evidence: (.+)$"
)


def parse_raw_mapping(text: str) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        value = json.loads(text.strip())
    except json.JSONDecodeError as exc:
        return None, [f"raw output is not exactly one JSON value: {exc}"]
    if not isinstance(value, dict):
        return None, ["top-level output is not an object"]
    return value, []


def parse_phase2_eligibility(note: Any) -> tuple[set[str], list[str]]:
    if not isinstance(note, str) or not note.startswith(ELIGIBILITY_PREFIX):
        return set(), ["partial note must begin with 'phase2 eligible: '"]
    head, separator, suffix = note.partition("; ")
    if separator and (
        not suffix.startswith(REALIZATION_PREFIX)
        or not suffix[len(REALIZATION_PREFIX) :].strip()
    ):
        return set(), [
            "partial note suffix must be a non-empty 'source realization condition: ...'"
        ]
    payload = head[len(ELIGIBILITY_PREFIX) :]
    if payload == "none":
        return set(), []
    parts = payload.split(", ")
    if not parts or any(part not in DIMENSIONS for part in parts):
        return set(), ["phase2 eligibility contains an unknown dimension"]
    if len(parts) != len(set(parts)):
        return set(), ["phase2 eligibility repeats a dimension"]
    expected_order = [dimension for dimension in DIMENSION_ORDER if dimension in parts]
    if parts != expected_order:
        return set(), ["phase2 eligibility dimensions are not in canonical order"]
    return set(parts), []


def validate_mapping(
    mapping: dict[str, Any],
    expected_id: str | None = None,
    *,
    phase: int = 1,
) -> list[str]:
    """Validate one mapping; only Phase 1 requires eligible dimensions to remain non-scalar."""
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
    result = mapping.get("result")
    if result not in RESULTS:
        errors.append(f"invalid result: {result!r}")
    note = mapping.get("note")
    if note is not None and not isinstance(note, str):
        errors.append("note must be a string or null")
    cells = mapping.get("cells")
    if not isinstance(cells, list):
        errors.append("cells must be a list")
        return errors

    has_non_scalar = False
    for cell_index, cell in enumerate(cells):
        prefix = f"cells[{cell_index}]"
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
                invalid = [
                    member
                    for member in value
                    if not isinstance(member, str) or member not in allowed
                ]
                if invalid:
                    errors.append(
                        f"{prefix}.{dimension} list has invalid members {invalid!r}"
                    )
                elif len(value) != len(set(value)):
                    errors.append(f"{prefix}.{dimension} list contains duplicates")
            else:
                errors.append(f"{prefix}.{dimension} must be scalar, list, or null")

        if set(cell) != set(DIMENSIONS):
            continue
        tense = cell["tense"]
        modal = cell["modal"]
        if cell["clause"] == "imperative":
            if tense != "NA":
                errors.append(f"{prefix}: imperative requires tense=NA")
            if modal != "none":
                errors.append(f"{prefix}: imperative requires modal=none")
        present_past_only = (
            isinstance(tense, str) and tense in MORPHOLOGICAL_TENSES
        ) or (
            isinstance(tense, list)
            and bool(tense)
            and set(tense).issubset(MORPHOLOGICAL_TENSES)
        )
        if present_past_only and modal != "none":
            errors.append(f"{prefix}: present/past-only tense requires modal=none")
        central_modal_only = (
            isinstance(modal, str) and modal in CENTRAL_MODALS
        ) or (
            isinstance(modal, list)
            and bool(modal)
            and set(modal).issubset(CENTRAL_MODALS)
        )
        if central_modal_only and tense != "NA":
            errors.append(f"{prefix}: central-modal-only constraint requires tense=NA")

    if result == "complete":
        if not cells:
            errors.append("complete requires non-empty cells")
        if has_non_scalar:
            errors.append("complete requires every dimension value to be scalar")
        for index, cell in enumerate(cells):
            if not isinstance(cell, dict) or set(cell) != set(DIMENSIONS):
                continue
            if cell["clause"] != "imperative":
                if cell["modal"] == "none" and cell["tense"] not in MORPHOLOGICAL_TENSES:
                    errors.append(
                        f"cells[{index}]: complete nonmodal cell requires present/past"
                    )
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
                if not any(
                    isinstance(cell, dict)
                    and (
                        cell.get(dimension) is None
                        or isinstance(cell.get(dimension), list)
                    )
                    for cell in cells
                ):
                    errors.append(
                        f"phase1 eligibility names scalar-only dimension {dimension}"
                    )
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
        if isinstance(child, str):
            return child in parent
        if isinstance(child, list):
            return bool(child) and set(child).issubset(set(parent))
        return False
    if parent is None:
        return child is None or isinstance(child, (str, list))
    return False


def _cell_refines(
    parent: dict[str, Any], child: dict[str, Any], eligible: set[str]
) -> bool:
    for dimension in DIMENSION_ORDER:
        if dimension in eligible:
            if not _value_refines(parent[dimension], child[dimension]):
                return False
        elif child[dimension] != parent[dimension]:
            return False
    return True


def validate_phase2_transition(
    phase1: dict[str, Any], phase2: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    if phase1.get("egp_id") != phase2.get("egp_id"):
        errors.append("Phase-2 egp_id differs from Phase 1")
        return errors

    if phase1.get("result") == "unresolved":
        if phase2 != phase1:
            errors.append("a zero-cell Phase-1 unresolved mapping cannot be refined")
        return errors

    if phase2.get("result") == "unresolved":
        note = phase2.get("note")
        match = CONTRADICTION_RE.fullmatch(note) if isinstance(note, str) else None
        if not match:
            errors.append("Phase-2 unresolved note does not follow contradiction convention")
            return errors
        dimension, value, _evidence = match.groups()
        if dimension not in DIMENSIONS or value not in DIMENSIONS.get(dimension, set()):
            errors.append("Phase-2 contradiction names an invalid dimension/value")
        elif not any(
            isinstance(cell, dict) and cell.get(dimension) == value
            for cell in phase1.get("cells", [])
        ):
            errors.append(
                "Phase-2 contradiction does not identify an exact Phase-1 scalar"
            )
        return errors

    if phase1.get("result") != "partial":
        if phase2 != phase1:
            errors.append("non-partial Phase-1 mapping changed without contradiction")
        return errors
    if phase2.get("result") not in {"partial", "complete"}:
        errors.append("Phase-2 refinement must remain partial or become complete")
        return errors

    eligible, note_errors = parse_phase2_eligibility(phase1.get("note"))
    errors.extend(note_errors)
    if phase2.get("note") != phase1.get("note"):
        errors.append("Phase-2 note changed outside the contradiction outcome")
    if note_errors:
        return errors
    if not eligible:
        if phase2 != phase1:
            errors.append("Phase-2 changed a mapping with phase2 eligible: none")
        return errors

    parents = phase1.get("cells", [])
    children = phase2.get("cells", [])
    if not all(
        isinstance(cell, dict) and set(cell) == set(DIMENSIONS)
        for cell in parents + children
    ):
        errors.append("cannot compare malformed Phase-1/Phase-2 cells")
        return errors
    for index, child in enumerate(children):
        if not any(_cell_refines(parent, child, eligible) for parent in parents):
            errors.append(
                f"Phase-2 cell {index} is not a licensed refinement of any Phase-1 cell"
            )
    for index, parent in enumerate(parents):
        if not any(_cell_refines(parent, child, eligible) for child in children):
            errors.append(f"Phase-1 cell {index} has no Phase-2 descendant")
    return errors


def validate_frozen() -> list[str]:
    errors = verify_frozen_manifest() + verify_prior_pilots()
    try:
        source = verify_source()
    except Exception as exc:
        errors.append(str(exc))
        return errors

    config = execution_config()
    ids = [
        line
        for line in (INPUT / "sample_ids.txt").read_text(encoding="utf-8").splitlines()
        if line
    ]
    sample = load_jsonl(INPUT / "sample.jsonl")
    metadata = load_jsonl(INPUT / "sample_metadata.jsonl")
    units = load_jsonl(INPUT / "annotation_units.jsonl")
    if len(ids) != len(set(ids)):
        errors.append("sample_ids.txt contains duplicates")
    if [row.get("egp_id") for row in sample] != ids:
        errors.append("sample.jsonl IDs/order do not match sample_ids.txt")
    if [row.get("egp_id") for row in metadata] != ids:
        errors.append("sample_metadata.jsonl IDs/order do not match sample_ids.txt")
    statuses = [row.get("status") for row in metadata]
    if set(statuses) != {"regression_control", "fresh"}:
        errors.append("sample status must be regression_control or fresh")
    if statuses.count("regression_control") != 20 or statuses.count("fresh") != 3:
        errors.append("sample must contain 20 regression controls and 3 fresh IDs")
    if len(ids) != config["unique_descriptor_count"]:
        errors.append("unique descriptor count differs from execution.json")

    allowed_fields = {"egp_id", "supercategory", "subcategory", "guideword", "can_do"}
    source_by_id = {row["egp_id"]: row for row in load_jsonl(source)}
    for index, row in enumerate(sample, 1):
        if set(row) != allowed_fields:
            errors.append(f"sample row {index} has fields outside the Phase-1 contract")
        source_row = source_by_id.get(row.get("egp_id"))
        if source_row is None:
            errors.append(f"selected ID missing from source: {row.get('egp_id')}")
        elif {field: source_row.get(field) for field in allowed_fields} != row:
            errors.append(f"sample projection differs from source: {row.get('egp_id')}")

    prior_ids: set[str] = set()
    for pilot_path in (
        Path(config["v1_pilot_path"]),
        Path(config["v1_1_pilot_path"]),
        Path(config["previous_pilot_path"]),
    ):
        prior_ids.update(
            line
            for line in (pilot_path / "input" / "sample_ids.txt")
            .read_text(encoding="utf-8")
            .splitlines()
            if line
        )
    for row in metadata:
        required = {
            "egp_id",
            "status",
            "strata",
            "selection_rationale",
            "previous_unit",
        }
        if set(row) != required:
            errors.append(f"sample metadata has unexpected keys: {row.get('egp_id')}")
        if not isinstance(row.get("strata"), list) or not row.get("strata"):
            errors.append(f"sample metadata requires non-empty strata: {row.get('egp_id')}")
        if not isinstance(row.get("selection_rationale"), str) or not row.get(
            "selection_rationale"
        ):
            errors.append(f"sample metadata requires rationale: {row.get('egp_id')}")
        if row.get("status") == "regression_control" and row.get("egp_id") not in prior_ids:
            errors.append(
                f"regression control was absent from earlier pilots: {row.get('egp_id')}"
            )
        if row.get("status") == "fresh" and row.get("egp_id") in prior_ids:
            errors.append(f"fresh ID appeared in an earlier pilot: {row.get('egp_id')}")

    if len(units) != config["annotation_unit_count"]:
        errors.append("annotation unit count differs from execution.json")
    unit_ids = [row.get("unit_id") for row in units]
    if len(unit_ids) != len(set(unit_ids)):
        errors.append("annotation unit IDs are not unique")
    if any(set(row) != {"unit_id", "egp_id", "duplicate_of"} for row in units):
        errors.append("annotation unit rows have unexpected keys")
    primary_by_unit = {
        row["unit_id"]: row for row in units if row.get("duplicate_of") is None
    }
    duplicates = [row for row in units if row.get("duplicate_of") is not None]
    if len(primary_by_unit) != len(ids):
        errors.append("primary annotation units do not match unique descriptor count")
    if len(duplicates) != config["duplicate_unit_count"]:
        errors.append("duplicate annotation unit count differs from execution.json")
    if [row["egp_id"] for row in units if row.get("duplicate_of") is None] != ids:
        errors.append("primary unit order/IDs do not match sample IDs")
    for row in duplicates:
        primary = primary_by_unit.get(row.get("duplicate_of"))
        if primary is None:
            errors.append(f"duplicate {row.get('unit_id')} refers to missing primary")
        elif primary["egp_id"] != row.get("egp_id"):
            errors.append(
                f"duplicate {row.get('unit_id')} has different egp_id from primary"
            )

    fixture_path = INPUT / "protocol_fixture.json"
    if not fixture_path.is_file():
        errors.append("protocol fixture is missing")
    else:
        fixture = load_json(fixture_path)
        expected_keys = {
            "fixture_id",
            "purpose",
            "descriptor",
            "phase1_mapping",
            "examples",
            "expected",
        }
        if set(fixture) != expected_keys:
            errors.append("protocol fixture has unexpected keys")
        descriptor = fixture.get("descriptor", {})
        if not isinstance(descriptor, dict) or set(descriptor) != allowed_fields:
            errors.append("protocol descriptor does not match the five-field contract")
        fixture_id = descriptor.get("egp_id") if isinstance(descriptor, dict) else None
        if fixture_id in source_by_id:
            errors.append("protocol fixture reuses a genuine EGP ID")
        mapping = fixture.get("phase1_mapping")
        if isinstance(mapping, dict):
            errors.extend(
                f"protocol Phase 1: {error}"
                for error in validate_mapping(mapping, fixture_id, phase=1)
            )
        else:
            errors.append("protocol Phase-1 mapping is not an object")
        if not isinstance(fixture.get("examples"), list) or not fixture.get("examples"):
            errors.append("protocol fixture requires contradictory examples")
    return errors


def expected_phase_units(
    phase: int,
) -> list[tuple[dict[str, Any], dict[str, Any] | None]]:
    units = load_jsonl(INPUT / "annotation_units.jsonl")
    if phase == 1:
        return [(unit, None) for unit in units]
    phase1_path = OUTPUTS / "phase1" / "mappings.jsonl"
    if not phase1_path.exists():
        return []
    phase1 = load_jsonl(phase1_path)
    if len(phase1) != len(units):
        return []
    return [
        (unit, mapping)
        for unit, mapping in zip(units, phase1, strict=True)
        if mapping["result"] in {"partial", "unresolved"}
    ]


def phase_completion_errors(
    *,
    phase: int,
    expected_ids: list[str],
    accepted_ids: list[str],
    rejected_reasons: dict[str, str],
    aggregate_present: bool,
    index_present: bool,
) -> list[str]:
    """Produce failure-safe completion diagnostics used by live audits and self-tests."""
    errors: list[str] = []
    expected_set = set(expected_ids)
    accepted_set = set(accepted_ids)
    unexpected = accepted_set - expected_set
    missing = [unit_id for unit_id in expected_ids if unit_id not in accepted_set]
    if unexpected:
        errors.append(f"phase {phase} has unexpected accepted units: {sorted(unexpected)}")
    if missing:
        errors.append(
            f"phase {phase} INCOMPLETE: routed={len(expected_ids)}, "
            f"accepted={len(accepted_set & expected_set)}, rejected/exhausted={len(missing)}"
        )
        for unit_id in missing:
            errors.append(
                f"phase {phase} INCOMPLETE unit {unit_id}: "
                f"{rejected_reasons.get(unit_id, 'no valid parsed output or recorded reason')}"
            )
        if aggregate_present or index_present:
            errors.append(
                f"phase {phase} incomplete run unexpectedly contains aggregate/index output"
            )
    elif not aggregate_present or not index_present:
        errors.append(
            f"phase {phase} COMPLETE unit inventory is missing aggregate or unit index"
        )
    return errors


def _attempt_reason(validation: dict[str, Any]) -> str:
    attempts = validation.get("attempt_errors")
    if not isinstance(attempts, list) or not attempts:
        return "invalid validation record without attempt reasons"
    rendered: list[str] = []
    for index, reasons in enumerate(attempts, 1):
        if isinstance(reasons, list) and reasons:
            rendered.append(f"attempt {index}: {' | '.join(str(reason) for reason in reasons)}")
        else:
            rendered.append(f"attempt {index}: no recorded validation reason")
    return "; ".join(rendered)


def _validate_failed_attempts(
    *,
    phase: int,
    unit_id: str,
    egp_id: str,
    phase1: dict[str, Any] | None,
    validation: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    attempt_count = validation.get("attempt_count")
    if not isinstance(attempt_count, int) or attempt_count < 1:
        return [f"{unit_id}: failed validation record has invalid attempt_count"]
    recorded_attempts = validation.get("attempt_errors")
    if not isinstance(recorded_attempts, list) or len(recorded_attempts) != attempt_count:
        errors.append(f"{unit_id}: failed validation attempt_errors length mismatch")
    for attempt in range(1, attempt_count + 1):
        stem = f"{unit_id}.attempt-{attempt:02d}"
        metadata_path = LOGS / f"phase{phase}" / f"{stem}.json"
        raw_path = OUTPUTS / f"phase{phase}" / "raw" / f"{stem}.txt"
        if not metadata_path.exists():
            errors.append(f"{unit_id}: missing metadata for failed attempt {attempt}")
            continue
        metadata = load_json(metadata_path)
        if metadata.get("valid") is not False:
            errors.append(f"{unit_id}: failed attempt {attempt} is not recorded invalid")
        computed: list[str] = []
        if metadata.get("returncode") != 0:
            computed.append(f"codex exited {metadata.get('returncode')}")
        elif not raw_path.exists():
            computed.append("Codex produced no final raw output file")
        else:
            mapping, computed = parse_raw_mapping(raw_path.read_text(encoding="utf-8"))
            if mapping is not None:
                computed.extend(validate_mapping(mapping, egp_id, phase=phase))
                if phase == 2 and phase1 is not None:
                    computed.extend(validate_phase2_transition(phase1, mapping))
        if metadata.get("validation_errors") != computed:
            errors.append(
                f"{unit_id}: failed attempt {attempt} recorded/computed errors differ"
            )
        if isinstance(recorded_attempts, list) and attempt <= len(recorded_attempts):
            if recorded_attempts[attempt - 1] != computed:
                errors.append(
                    f"{unit_id}: failed validation summary differs at attempt {attempt}"
                )
    return errors


def validate_phase(phase: int) -> list[str]:
    errors: list[str] = []
    if phase == 2 and not (OUTPUTS / "phase1" / "mappings.jsonl").exists():
        return ["phase 2 INCOMPLETE: Phase-1 aggregate is unavailable for routing"]
    expected = expected_phase_units(phase)
    phase_dir = OUTPUTS / f"phase{phase}"
    aggregate_path = phase_dir / "mappings.jsonl"
    index_path = phase_dir / "unit_index.jsonl"
    accepted: dict[str, dict[str, Any]] = {}
    rejected_reasons: dict[str, str] = {}

    for unit, phase1 in expected:
        unit_id = unit["unit_id"]
        egp_id = unit["egp_id"]
        parsed_path = phase_dir / "parsed" / f"{unit_id}.json"
        validation_path = LOGS / f"phase{phase}" / f"{unit_id}.validation.json"
        validation = load_json(validation_path) if validation_path.exists() else None
        if not parsed_path.exists():
            if validation is None:
                rejected_reasons[unit_id] = "validation record is missing"
            elif validation.get("valid") is not False:
                rejected_reasons[unit_id] = "parsed output missing but validation is not failed"
            else:
                rejected_reasons[unit_id] = _attempt_reason(validation)
                errors.extend(
                    _validate_failed_attempts(
                        phase=phase,
                        unit_id=unit_id,
                        egp_id=egp_id,
                        phase1=phase1,
                        validation=validation,
                    )
                )
            continue

        mapping = load_json(parsed_path)
        accepted[unit_id] = mapping
        errors.extend(
            f"{unit_id}: {error}"
            for error in validate_mapping(mapping, egp_id, phase=phase)
        )
        if phase == 2 and phase1 is not None:
            errors.extend(
                f"{unit_id}: {error}"
                for error in validate_phase2_transition(phase1, mapping)
            )
        if validation is None:
            errors.append(f"{unit_id}: missing validation record")
            continue
        attempt = validation.get("successful_attempt")
        if not validation.get("valid") or not isinstance(attempt, int):
            errors.append(f"{unit_id}: invalid successful validation outcome")
            continue
        if phase == 2 and validation.get("transition_valid") is not True:
            errors.append(f"{unit_id}: Phase-2 transition flag is not true")
        raw_path = phase_dir / "raw" / f"{unit_id}.attempt-{attempt:02d}.txt"
        if not raw_path.exists():
            errors.append(f"{unit_id}: missing successful raw output")
        else:
            raw, raw_errors = parse_raw_mapping(raw_path.read_text(encoding="utf-8"))
            errors.extend(f"{unit_id}: {error}" for error in raw_errors)
            if raw != mapping:
                errors.append(f"{unit_id}: successful raw output differs from parsed mapping")
        if validation.get("parent_rewrite_or_adjudication") is not False:
            errors.append(f"{unit_id}: parent rewrite/adjudication flag is not false")

    expected_ids = [unit["unit_id"] for unit, _ in expected]
    errors.extend(
        phase_completion_errors(
            phase=phase,
            expected_ids=expected_ids,
            accepted_ids=list(accepted),
            rejected_reasons=rejected_reasons,
            aggregate_present=aggregate_path.exists(),
            index_present=index_path.exists(),
        )
    )

    if len(accepted) == len(expected):
        aggregate = load_jsonl(aggregate_path) if aggregate_path.exists() else []
        index = load_jsonl(index_path) if index_path.exists() else []
        if len(aggregate) != len(expected) or len(index) != len(expected):
            errors.append(f"phase {phase} aggregate/index length differs from routing")
        else:
            for (unit, _phase1), mapping, index_row in zip(
                expected, aggregate, index, strict=True
            ):
                unit_id = unit["unit_id"]
                egp_id = unit["egp_id"]
                if index_row.get("unit_id") != unit_id or index_row.get("egp_id") != egp_id:
                    errors.append(f"phase {phase} index mismatch at {unit_id}")
                if accepted.get(unit_id) != mapping:
                    errors.append(f"phase {phase} aggregate differs at {unit_id}")
                parsed_path = phase_dir / "parsed" / f"{unit_id}.json"
                if parsed_path.exists() and sha256_path(parsed_path) != index_row.get(
                    "parsed_sha256"
                ):
                    errors.append(f"phase {phase} parsed hash differs at {unit_id}")
        if phase == 2:
            routed_path = phase_dir / "routed_units.jsonl"
            if not routed_path.exists():
                errors.append("Phase-2 routed-unit snapshot is missing")
            elif [row.get("unit_id") for row in load_jsonl(routed_path)] != expected_ids:
                errors.append("Phase-2 routed-unit snapshot differs from mechanical routing")
    return errors


def validate_protocol_fixture() -> list[str]:
    errors: list[str] = []
    fixture = load_json(INPUT / "protocol_fixture.json")
    fixture_id = fixture["fixture_id"]
    egp_id = fixture["descriptor"]["egp_id"]
    parsed_path = OUTPUTS / "protocol_fixture" / "parsed" / f"{fixture_id}.json"
    aggregate_path = OUTPUTS / "protocol_fixture" / "mappings.jsonl"
    validation_path = LOGS / "protocol_fixture" / f"{fixture_id}.validation.json"
    if not parsed_path.exists() or not aggregate_path.exists():
        return ["protocol fixture parsed output or aggregate is missing"]
    parsed = load_json(parsed_path)
    aggregate = load_jsonl(aggregate_path)
    if aggregate != [parsed]:
        errors.append("protocol fixture aggregate differs from parsed output")
    errors.extend(validate_mapping(parsed, egp_id, phase=2))
    errors.extend(validate_phase2_transition(fixture["phase1_mapping"], parsed))
    expected = fixture["expected"]
    if parsed.get("result") != expected.get("result"):
        errors.append("protocol fixture did not produce expected unresolved result")
    if parsed.get("cells") != expected.get("cells"):
        errors.append("protocol fixture did not produce expected empty cells")
    if not isinstance(parsed.get("note"), str) or not parsed["note"].startswith(
        expected.get("note_prefix", "")
    ):
        errors.append("protocol fixture note does not identify expected contradiction")
    if not validation_path.exists():
        errors.append("protocol fixture validation record is missing")
    else:
        validation = load_json(validation_path)
        attempt = validation.get("successful_attempt")
        if not validation.get("valid") or validation.get("transition_valid") is not True:
            errors.append("protocol fixture validation outcome is not valid")
        if isinstance(attempt, int):
            raw_path = (
                OUTPUTS
                / "protocol_fixture"
                / "raw"
                / f"{fixture_id}.attempt-{attempt:02d}.txt"
            )
            if not raw_path.exists():
                errors.append("protocol fixture successful raw output is missing")
            else:
                raw, raw_errors = parse_raw_mapping(raw_path.read_text(encoding="utf-8"))
                errors.extend(raw_errors)
                if raw != parsed:
                    errors.append("protocol fixture raw output differs from parsed output")
    return errors


def _phase_maps() -> tuple[
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    list[str],
]:
    errors: list[str] = []
    units = load_jsonl(INPUT / "annotation_units.jsonl")
    phase1_path = OUTPUTS / "phase1" / "mappings.jsonl"
    if not phase1_path.exists():
        return units, {}, {}, ["acceptance INCOMPLETE: Phase-1 aggregate is missing"]
    rows = load_jsonl(phase1_path)
    if len(rows) != len(units):
        return units, {}, {}, ["acceptance INCOMPLETE: Phase-1 aggregate length mismatch"]
    phase1 = {
        unit["unit_id"]: mapping
        for unit, mapping in zip(units, rows, strict=True)
    }
    phase2: dict[str, dict[str, Any]] = {}
    routed = [
        unit["unit_id"]
        for unit in units
        if phase1[unit["unit_id"]]["result"] in {"partial", "unresolved"}
    ]
    missing: list[str] = []
    for unit_id in routed:
        path = OUTPUTS / "phase2" / "parsed" / f"{unit_id}.json"
        if path.exists():
            phase2[unit_id] = load_json(path)
        else:
            missing.append(unit_id)
    if missing:
        errors.append(
            f"acceptance INCOMPLETE: Phase-2 accepted={len(phase2)}, "
            f"routed={len(routed)}, missing={','.join(missing)}"
        )
    return units, phase1, phase2, errors


def validate_acceptance() -> list[str]:
    """Evaluate frozen ID-specific assertions without assuming a complete aggregate."""
    units, phase1, phase2, errors = _phase_maps()
    if not phase1:
        return errors

    simple_units = {"u001", "u002", "u003", "u004", "u005"}
    for unit_id in simple_units:
        mapping = phase1[unit_id]
        if mapping["result"] != "partial" or len(mapping["cells"]) != 1:
            errors.append(f"{unit_id}: closed simple control is not one partial cell")
            continue
        cell = mapping["cells"][0]
        if not (
            cell["tense"] == ["present", "past"]
            and cell["aspect"] == "none"
            and cell["voice"] == "active"
            and cell["modal"] == "none"
        ):
            errors.append(f"{unit_id}: closed simple aspect/tense/modal expectation failed")
        eligible, _ = parse_phase2_eligibility(mapping["note"])
        if eligible != {"tense"}:
            errors.append(f"{unit_id}: expected exactly tense eligibility")

    imperative_polarity = {
        "u006": "positive",
        "u007": "negative",
        "u008": "positive",
        "u009": "positive",
        "u010": "negative",
        "u011": "positive",
        "u012": "positive",
    }
    for unit_id, polarity in imperative_polarity.items():
        mapping = phase1[unit_id]
        if mapping["result"] != "complete" or len(mapping["cells"]) != 1:
            errors.append(f"{unit_id}: imperative is not one complete cell")
            continue
        cell = mapping["cells"][0]
        expected = {
            "tense": "NA",
            "aspect": "none",
            "voice": "active",
            "polarity": polarity,
            "clause": "imperative",
            "modal": "none",
        }
        if cell != expected:
            errors.append(f"{unit_id}: imperative canonical cell expectation failed")
    for unit_id in ("u008", "u009", "u010", "u011", "u012"):
        note = phase1[unit_id]["note"]
        if not isinstance(note, str) or not note.startswith(REALIZATION_PREFIX):
            errors.append(f"{unit_id}: source-specific imperative realization note missing")

    question_aspects = {
        "u013": "progressive",
        "u014": "perfect",
        "u015": "perfect_progressive",
    }
    for unit_id, aspect in question_aspects.items():
        mapping = phase1[unit_id]
        if not mapping["cells"] or any(
            cell["clause"] is not None or cell["aspect"] != aspect
            for cell in mapping["cells"]
        ):
            errors.append(f"{unit_id}: generic-question clause/aspect expectation failed")
        eligible, _ = parse_phase2_eligibility(mapping["note"])
        if eligible:
            errors.append(f"{unit_id}: generic question-form superclass was made eligible")

    for unit_id in simple_units:
        mapping = phase2.get(unit_id)
        if mapping is None:
            errors.append(f"{unit_id}: expected licensed Phase-2 split is unavailable")
            continue
        tenses = {cell["tense"] for cell in mapping["cells"] if isinstance(cell["tense"], str)}
        if tenses != {"present", "past"}:
            errors.append(f"{unit_id}: licensed tense split did not yield present and past")
        if mapping.get("note") != phase1[unit_id].get("note"):
            errors.append(f"{unit_id}: Phase-2 eligibility provenance note changed")
        if validate_mapping(mapping, phase1[unit_id]["egp_id"], phase=2):
            errors.append(f"{unit_id}: licensed Phase-2 partial-to-partial mapping is invalid")

    unchanged_units = {
        "u013",
        "u014",
        "u015",
        "u016",
        "u017",
        "u018",
        "u019",
        "u020",
        "u021",
        "u022",
    }
    for unit_id in unchanged_units:
        if unit_id in phase2 and phase2[unit_id] != phase1[unit_id]:
            errors.append(f"{unit_id}: ineligible/non-exhaustive mapping changed in Phase 2")

    for unit_id in ("u017", "u018", "u020", "u021"):
        mapping = phase1[unit_id]
        if not mapping["cells"] or any(
            cell["modal"] != CENTRAL_MODAL_LIST for cell in mapping["cells"]
        ):
            errors.append(f"{unit_id}: generic modal superclass was not one list")
    for unit_id in ("u017", "u018", "u021"):
        if any(cell["aspect"] is not None for cell in phase1[unit_id]["cells"]):
            errors.append(f"{unit_id}: broad modal aspect should remain null")

    independent = phase1["u020"]
    if len(independent["cells"]) != 2 or {
        cell["polarity"] for cell in independent["cells"]
    } != {"positive", "negative"}:
        errors.append("u020: independently asserted polarity alternatives are not OR cells")
    generic_wh = ["subject_wh_question", "non_subject_wh_question"]
    if not phase1["u022"]["cells"] or any(
        cell["clause"] != generic_wh for cell in phase1["u022"]["cells"]
    ):
        errors.append("u022: generic-WH superclass was not preserved as a list")
    if phase1["u023"]["result"] != "out_of_scope" or phase1["u023"]["cells"] != []:
        errors.append("u023: question-tag control is not out_of_scope with empty cells")

    duplicate_pairs = (("u003", "u024"), ("u013", "u025"), ("u010", "u026"))
    for primary, duplicate in duplicate_pairs:
        if phase1[primary] != phase1[duplicate]:
            errors.append(f"{primary}/{duplicate}: Phase-1 duplicate objects differ")
        if primary in phase2 or duplicate in phase2:
            if primary not in phase2 or duplicate not in phase2:
                errors.append(f"{primary}/{duplicate}: duplicate routing/acceptance differs")
            elif phase2[primary] != phase2[duplicate]:
                errors.append(f"{primary}/{duplicate}: Phase-2 duplicate objects differ")

    schema_failures = [
        unit_id
        for unit_id, mapping in phase1.items()
        if mapping["result"] == "schema_failure"
    ]
    schema_failures.extend(
        unit_id
        for unit_id, mapping in phase2.items()
        if mapping["result"] == "schema_failure"
    )
    if schema_failures:
        errors.append(f"schema failures occurred: {sorted(set(schema_failures))}")
    return errors


def validate_self_test() -> list[str]:
    errors: list[str] = []
    base_cell = {
        "tense": "present",
        "aspect": "none",
        "voice": "active",
        "polarity": "positive",
        "clause": "declarative",
        "modal": "none",
    }
    bad_compatibility = {
        "egp_id": "self",
        "result": "partial",
        "cells": [{**base_cell, "modal": None}],
        "note": "phase2 eligible: modal",
    }
    if not any(
        "present/past-only tense" in error
        for error in validate_mapping(bad_compatibility, phase=1)
    ):
        errors.append("self-test failed to reject present tense with modal=null")

    phase1_none = {
        "egp_id": "self",
        "result": "partial",
        "cells": [{**base_cell, "polarity": None}],
        "note": "phase2 eligible: none",
    }
    phase2_changed = {
        "egp_id": "self",
        "result": "complete",
        "cells": [{**base_cell, "polarity": "positive"}],
        "note": "phase2 eligible: none",
    }
    if not validate_phase2_transition(phase1_none, phase2_changed):
        errors.append("self-test failed to reject an ineligible Phase-2 change")

    phase1_eligible = {
        "egp_id": "self",
        "result": "partial",
        "cells": [
            {
                **base_cell,
                "tense": ["present", "past"],
                "aspect": None,
            }
        ],
        "note": "phase2 eligible: tense",
    }
    phase2_split = {
        "egp_id": "self",
        "result": "partial",
        "cells": [
            {**base_cell, "tense": "present", "aspect": None},
            {**base_cell, "tense": "past", "aspect": None},
        ],
        "note": "phase2 eligible: tense",
    }
    if validate_mapping(phase1_eligible, phase=1):
        errors.append("self-test Phase-1 eligible fixture is invalid")
    if validate_mapping(phase2_split, phase=2):
        errors.append("self-test rejected phase-aware partial-to-partial refinement")
    if not any(
        "phase1 eligibility names scalar-only dimension tense" in error
        for error in validate_mapping(phase2_split, phase=1)
    ):
        errors.append("self-test failed to preserve the Phase-1-only eligibility check")
    if validate_phase2_transition(phase1_eligible, phase2_split):
        errors.append("self-test failed to accept a licensed partial-to-partial split")

    bad_split = {
        **phase2_split,
        "cells": [
            {**base_cell, "tense": "present", "aspect": None, "polarity": "negative"},
            {**base_cell, "tense": "past", "aspect": None},
        ],
    }
    if not validate_phase2_transition(phase1_eligible, bad_split):
        errors.append("self-test failed to reject an ineligible polarity change")

    contradiction = {
        "egp_id": "self",
        "result": "unresolved",
        "cells": [],
        "note": "phase2 contradiction: tense=present; evidence: past-form example",
    }
    phase1_complete = {
        "egp_id": "self",
        "result": "complete",
        "cells": [base_cell],
        "note": None,
    }
    if validate_mapping(contradiction, phase=2) or validate_phase2_transition(
        phase1_complete, contradiction
    ):
        errors.append("self-test failed to accept scalar contradiction outcome")

    complete_audit = phase_completion_errors(
        phase=2,
        expected_ids=["a", "b"],
        accepted_ids=["a", "b"],
        rejected_reasons={},
        aggregate_present=True,
        index_present=True,
    )
    if complete_audit:
        errors.append("self-test complete Phase-2 inventory did not audit cleanly")
    incomplete_audit = phase_completion_errors(
        phase=2,
        expected_ids=["a", "b"],
        accepted_ids=["a"],
        rejected_reasons={"b": "attempt 1: deliberate rejection"},
        aggregate_present=False,
        index_present=False,
    )
    if not incomplete_audit or not all("INCOMPLETE" in item for item in incomplete_audit):
        errors.append("self-test incomplete Phase-2 inventory was not reported safely")
    return errors


def report(errors: list[str]) -> int:
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--expected-id")
    parser.add_argument("--mapping-phase", type=int, choices=(1, 2), default=1)
    parser.add_argument("--frozen", action="store_true")
    parser.add_argument("--phase", type=int, choices=(1, 2))
    parser.add_argument("--protocol-fixture", action="store_true")
    parser.add_argument("--acceptance", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    if args.self_test:
        errors.extend(validate_self_test())
    if args.frozen or args.phase or args.protocol_fixture or args.acceptance or args.all:
        errors.extend(validate_frozen())
    if args.phase:
        errors.extend(validate_phase(args.phase))
    if args.protocol_fixture:
        errors.extend(validate_protocol_fixture())
    if args.acceptance:
        errors.extend(validate_acceptance())
    if args.all:
        errors.extend(validate_phase(1))
        errors.extend(validate_phase(2))
        errors.extend(validate_protocol_fixture())
        errors.extend(validate_acceptance())
    if args.path:
        mapping, parse_errors = parse_raw_mapping(args.path.read_text(encoding="utf-8"))
        errors.extend(parse_errors)
        if mapping is not None:
            errors.extend(
                validate_mapping(
                    mapping,
                    args.expected_id,
                    phase=args.mapping_phase,
                )
            )
    if not (
        args.path
        or args.frozen
        or args.phase
        or args.protocol_fixture
        or args.acceptance
        or args.self_test
        or args.all
    ):
        parser.error(
            "provide a mapping path, --frozen, --phase, --protocol-fixture, "
            "--acceptance, --self-test, or --all"
        )
    return report(errors)


if __name__ == "__main__":
    raise SystemExit(main())

