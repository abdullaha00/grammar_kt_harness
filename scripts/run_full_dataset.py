#!/usr/bin/env python3
"""Prepare and extend the retained medium-scale grammar item bank.

This script deliberately has four explicit modes:

1. ``--prepare-only`` converts the retained 139-descriptor normalization run
   to the current source/mapping contracts, canonicalizes it with the active
   schema, and reuses only the N=3 model-selected arm of the Phase-4 live item
   pilot.  It makes no model calls.
2. ``--generate-missing`` makes three active generation calls for each of the
   16 cells not covered by that pilot, independently validates every new
   candidate, and selects at most two valid variants per cell.
3. ``--rescue-uncovered`` is a preregistered conditional continuation.  It is
   available only after every default N=3 position has a terminal attempt and
   validation is complete, and only when at least one cell has no accepted
   item.  It freezes that cohort, then independently generates and validates
   exactly positions 4 and 5 for each uncovered cell.
4. ``--determinacy-intervention`` is available only after that frozen rescue
   is complete.  It freezes the cells still uncovered because of repeated
   determinacy failures, then generates and validates exactly positions 6 and
   7 with a separately declared prompt that may name the target construction.

The script stops at the fixed item-bank boundary.  Grammar folds, simulated
learner evidence, KC selection, KT, and evaluation are run only after the
Phase-5 methodology is frozen; none of them can influence item construction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.canonicalise import canonicalise
from grammar_kt.generate import generate_item_candidate
from grammar_kt.io import (
    ModelCall,
    call_model,
    load_typed_resource,
    read_jsonl,
    read_text,
    read_yaml,
    write_json,
    write_jsonl,
)
from grammar_kt.normalise import _validate_mapping
from grammar_kt.validate_items import (
    answer_span_consistency,
    bank_summary,
    select_item_bank,
    validate_items,
)


DATASET_ID = "grammar_kt_medium_v1"
PILOT_N = 3
RESCUE_INDICES = (4, 5)
RESCUE_PROTOCOL = "conditional_zero_coverage_rescue_v1"
RESCUE_STATUS = "phase6_conditional_rescue_live_model_evidence"
INTERVENTION_INDICES = (6, 7)
INTERVENTION_PROTOCOL = "explicit_construction_determinacy_intervention_v1"
INTERVENTION_STATUS = "phase6_determinacy_intervention_live_model_evidence"

GRAMMAR_SCHEMA_PATH = ROOT / "modules/grammar/canonical/schema.yaml"
RESOURCE_SCHEMA_PATH = ROOT / "modules/grammar/resource/egp/schema.yaml"
GENERATION_PROMPT_PATH = ROOT / "modules/items/generation/prompt.txt"
INTERVENTION_PROMPT_PATH = (
    ROOT
    / "modules/items/generation/ablations/"
    "determinacy_explicit_construction_prompt.txt"
)
GENERATION_RULEBOOK_PATH = ROOT / "modules/items/generation/rulebook.md"
GENERATION_DESIGN_PATH = ROOT / "modules/items/generation/design.yaml"
ITEM_FORMAT_PATH = (
    ROOT / "modules/items/generation/formats/controlled_production.yaml"
)
VALIDATION_PROMPT_PATH = ROOT / "modules/items/validation/prompt.txt"
VALIDATION_CRITERIA_PATH = ROOT / "modules/items/validation/criteria.yaml"

PILOT_DIR = ROOT / "reports/phase4/artifacts/item_audit/live_pilot"

GENERATION_MODEL = "gpt-5.6-sol"
VALIDATION_MODEL = "gpt-5.6-terra"
REASONING_EFFORT = "medium"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _feature_key(features: dict[str, str], schema: dict[str, Any]) -> tuple[str, ...]:
    return tuple(features[name] for name in schema["dimension_order"])


def adapt_legacy_sources(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only fields declared by the active typed EGP resource schema."""

    return [
        {
            "source_id": row["egp_id"],
            "supercategory": row["supercategory"],
            "subcategory": row["subcategory"],
            "guideword": row["guideword"],
            "can_do": row["can_do"],
            "examples": row["examples"],
            "cefr": row["cefr_band"],
        }
        for row in rows
    ]


def _declared_phase2_eligibility(
    note: str | None, schema: dict[str, Any]
) -> list[str]:
    """Recover the old run's explicit eligibility declaration from its note.

    This is a provenance adapter, not a new linguistic inference.  The Phase-4
    replay established that exactly nine retained primary annotations made
    this declaration; the other legacy Phase-2 calls remain documented as
    unnecessary calls under the active protocol.
    """

    if not note or "phase2 eligible:" not in note.casefold():
        return []
    suffix = note.casefold().split("phase2 eligible:", 1)[1].split(";", 1)[0]
    named = set(re.findall(r"[a-z_]+", suffix))
    return [name for name in schema["dimension_order"] if name in named]


def adapt_legacy_mappings(
    rows: list[dict[str, Any]], schema: dict[str, Any]
) -> list[dict[str, Any]]:
    """Translate retained final mappings to the active five-field contract."""

    mappings = []
    for row in rows:
        mapping = {
            "source_id": row["egp_id"],
            "result": row["result"],
            "cells": row["cells"],
            "phase2_eligible": _declared_phase2_eligibility(row.get("note"), schema),
            "note": row.get("note"),
        }
        _validate_mapping(
            mapping,
            mapping["source_id"],
            schema,
            allow_resolved_eligibility=True,
        )
        mappings.append(mapping)
    return mappings


def make_source_cell_relations(
    mappings: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    schema: dict[str, Any],
) -> list[dict[str, Any]]:
    """Make the inspectable many-to-many source-to-canonical relation."""

    cell_id_by_features = {
        _feature_key(cell["features"], schema): cell["cell_id"] for cell in cells
    }
    relations = []
    for mapping in mappings:
        if mapping["result"] != "complete":
            continue
        for index, features in enumerate(mapping["cells"]):
            relations.append(
                {
                    "source_id": mapping["source_id"],
                    "source_cell_index": index,
                    "cell_id": cell_id_by_features[_feature_key(features, schema)],
                    "normalisation_note": mapping["note"],
                }
            )
    return relations


def verify_legacy_inventory(
    cells: list[dict[str, Any]], legacy_cells_path: Path, schema: dict[str, Any]
) -> dict[str, Any]:
    """Verify that current canonicalization preserves the retained structure."""

    legacy = read_jsonl(legacy_cells_path)
    current_by_features = {
        _feature_key(row["features"], schema): set(row["source_ids"])
        for row in cells
    }
    legacy_by_features = {
        _feature_key(row["cell"], schema): set(row["source_descriptor_ids"])
        for row in legacy
    }
    return {
        "legacy_cell_count": len(legacy),
        "current_cell_count": len(cells),
        "feature_inventory_exact_match": set(current_by_features)
        == set(legacy_by_features),
        "source_memberships_exact_match": current_by_features == legacy_by_features,
    }


def _write_or_verify_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if path.exists():
        if read_jsonl(path) != rows:
            raise ValueError(f"prepared artifact differs from retained input: {path}")
        return
    write_jsonl(path, rows)


def prepare_static_inputs(output_dir: Path, legacy_run: Path) -> dict[str, Any]:
    """Retain source, normalization, and canonical artifacts without model calls."""

    source_path = output_dir / "source/descriptors.jsonl"
    mappings_path = output_dir / "normalisation/mappings.jsonl"
    cells_path = output_dir / "canonical/cells.jsonl"
    relations_path = output_dir / "canonical/source_cell_relations.jsonl"

    if source_path.exists() and mappings_path.exists():
        sources = read_jsonl(source_path)
        mappings = read_jsonl(mappings_path)
    else:
        legacy_source_path = legacy_run / "source/source_subset.jsonl"
        legacy_mapping_path = legacy_run / "normalisation/final_mappings.jsonl"
        if not legacy_source_path.is_file() or not legacy_mapping_path.is_file():
            raise FileNotFoundError(
                "the retained prepared artifacts do not yet exist and the legacy "
                f"handoff is unavailable under {legacy_run}"
            )
        schema = read_yaml(GRAMMAR_SCHEMA_PATH)
        sources = adapt_legacy_sources(read_jsonl(legacy_source_path))
        mappings = adapt_legacy_mappings(read_jsonl(legacy_mapping_path), schema)
        if [row["source_id"] for row in sources] != [
            row["source_id"] for row in mappings
        ]:
            raise ValueError("source and retained mapping orders differ")
        _write_or_verify_jsonl(source_path, sources)
        _write_or_verify_jsonl(mappings_path, mappings)

    # Validate the retained files through the active contracts on every run.
    resource_schema = read_yaml(RESOURCE_SCHEMA_PATH)
    loaded_sources = load_typed_resource(source_path, resource_schema)
    if loaded_sources != sources:
        raise ValueError("typed source reload changed row content")
    grammar_schema = read_yaml(GRAMMAR_SCHEMA_PATH)
    for mapping in mappings:
        _validate_mapping(
            mapping,
            mapping["source_id"],
            grammar_schema,
            allow_resolved_eligibility=True,
        )
    cells = canonicalise(mappings, grammar_schema)
    relations = make_source_cell_relations(mappings, cells, grammar_schema)
    _write_or_verify_jsonl(cells_path, cells)
    _write_or_verify_jsonl(relations_path, relations)

    legacy_inventory_path = legacy_run / "canonical/canonical_cells.jsonl"
    equivalence = (
        verify_legacy_inventory(cells, legacy_inventory_path, grammar_schema)
        if legacy_inventory_path.is_file()
        else {
            "legacy_cell_count": None,
            "current_cell_count": len(cells),
            "feature_inventory_exact_match": None,
            "source_memberships_exact_match": None,
        }
    )
    summary = {
        "descriptors": len(sources),
        "unique_source_ids": len({row["source_id"] for row in sources}),
        "normalisation_results": dict(
            sorted(Counter(row["result"] for row in mappings).items())
        ),
        "explicit_phase2_eligible": sum(
            bool(row["phase2_eligible"]) for row in mappings
        ),
        "canonical_cells": len(cells),
        "source_cell_relations": len(relations),
        "descriptors_contributing_cells": len(
            {row["source_id"] for row in relations}
        ),
        "complete_descriptors_per_cell": (
            sum(row["result"] == "complete" for row in mappings) / len(cells)
            if cells
            else None
        ),
        "source_cell_relations_per_cell": (
            len(relations) / len(cells) if cells else None
        ),
        "legacy_equivalence": equivalence,
    }
    write_json(output_dir / "source/manifest.json", {
        "dataset_id": DATASET_ID,
        "resource": "English Grammar Profile retained 139-descriptor sample",
        "descriptor_count": len(sources),
        "schema": str(RESOURCE_SCHEMA_PATH.relative_to(ROOT)),
        "descriptors_sha256": _sha256(source_path),
        "claim_boundary": (
            "The source sample and model normalization outputs are retained from "
            "the 2026-08-20 run; Phase 6 does not relabel them."
        ),
    })
    write_json(output_dir / "normalisation/summary.json", summary)
    return summary


def _pilot_cell_translation(
    cells: list[dict[str, Any]], schema: dict[str, Any]
) -> dict[str, str]:
    active_by_features = {
        _feature_key(row["features"], schema): row["cell_id"] for row in cells
    }
    translation = {}
    for row in read_jsonl(PILOT_DIR / "frozen_cells.jsonl"):
        key = _feature_key(row["features"], schema)
        if key not in active_by_features:
            raise ValueError(f"pilot cell absent from current inventory: {row['cell_id']}")
        translation[row["cell_id"]] = active_by_features[key]
    if len(translation) != 8 or len(set(translation.values())) != 8:
        raise ValueError("expected a one-to-one eight-cell pilot translation")
    return translation


def _current_candidate_id(cell_id: str, index: int) -> str:
    return f"candidate_{cell_id}_{index:02d}"


def _rescue_provenance() -> dict[str, Any]:
    return {
        "status": RESCUE_STATUS,
        "protocol": RESCUE_PROTOCOL,
        "trigger": "zero_validator_accepted_after_default_n3",
        "default_candidates_per_cell": PILOT_N,
        "rescue_candidate_indices": list(RESCUE_INDICES),
    }


def _intervention_provenance() -> dict[str, Any]:
    return {
        "status": INTERVENTION_STATUS,
        "protocol": INTERVENTION_PROTOCOL,
        "trigger": "zero_coverage_after_rescue_with_repeated_determinacy_failure",
        "candidate_indices": list(INTERVENTION_INDICES),
        "generation_prompt": str(INTERVENTION_PROMPT_PATH.relative_to(ROOT)),
        "generation_prompt_sha256": _sha256(INTERVENTION_PROMPT_PATH),
    }


def _is_declared_rescue_attempt(row: dict[str, Any]) -> bool:
    provenance = row.get("provenance", {})
    return (
        provenance.get("status") == RESCUE_STATUS
        and provenance.get("protocol") == RESCUE_PROTOCOL
    )


def _is_declared_intervention_attempt(row: dict[str, Any]) -> bool:
    provenance = row.get("provenance", {})
    return (
        provenance.get("status") == INTERVENTION_STATUS
        and provenance.get("protocol") == INTERVENTION_PROTOCOL
    )


def reuse_phase4_pilot(
    cells: list[dict[str, Any]], schema: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Translate only the frozen model-selected N=3 pilot to active IDs."""

    translation = _pilot_cell_translation(cells, schema)
    pilot_attempts = [
        row
        for row in read_jsonl(PILOT_DIR / "generation_attempts.jsonl")
        if row["condition"] == "model_selected"
        and row["candidate_index"] <= PILOT_N
    ]
    attempts = []
    original_to_current = {}
    for row in pilot_attempts:
        current_cell = translation[row["cell_id"]]
        current_id = _current_candidate_id(current_cell, row["candidate_index"])
        original_to_current[row["candidate_id"]] = current_id
        attempts.append(
            {
                "candidate_id": current_id,
                "cell_id": current_cell,
                "candidate_index": row["candidate_index"],
                "candidate_count": PILOT_N,
                "structurally_valid": row["structurally_valid"],
                "structural_errors": row["structural_errors"],
                "call_error": row["call_error"],
                "runtime_seconds": row["runtime_seconds"],
                "model": GENERATION_MODEL,
                "provenance": {
                    "status": "reused_live_model_evidence",
                    "artifact": str(PILOT_DIR.relative_to(ROOT)),
                    "original_candidate_id": row["candidate_id"],
                    "original_maximum_n": row["candidate_count"],
                    "active_prefix_n": PILOT_N,
                },
            }
        )

    candidates = []
    for row in read_jsonl(PILOT_DIR / "candidates.jsonl"):
        metadata = row["generation_metadata"]
        if (
            metadata["condition"] != "model_selected"
            or metadata["candidate_index"] > PILOT_N
        ):
            continue
        current_cell = translation[row["cell_id"]]
        current_id = _current_candidate_id(current_cell, metadata["candidate_index"])
        candidates.append(
            {
                "item_id": current_id,
                "cell_id": current_cell,
                "format": row["format"],
                "prompt": row["prompt"],
                "target_answer": row["target_answer"],
                "accepted_answers": row["accepted_answers"],
                "generation_metadata": {
                    "candidate_index": metadata["candidate_index"],
                    "candidate_count": PILOT_N,
                    "model": metadata["model"],
                    "provenance": {
                        "status": "reused_live_model_evidence",
                        "artifact": str(PILOT_DIR.relative_to(ROOT)),
                        "original_candidate_id": row["item_id"],
                        "original_maximum_n": metadata["candidate_count"],
                    },
                },
            }
        )

    validation_by_original = {
        row["candidate_id"]: row
        for row in read_jsonl(PILOT_DIR / "validation.jsonl")
    }
    judgments = []
    for candidate in candidates:
        original_id = candidate["generation_metadata"]["provenance"][
            "original_candidate_id"
        ]
        retained = validation_by_original[original_id]
        span_passed, span_note = answer_span_consistency(candidate)
        model_accepted = bool(
            retained["validator_output_valid"] and retained["accepted"]
        )
        accepted = model_accepted and span_passed
        if not span_passed:
            rejection_stage = "deterministic_precheck_reapplied"
        elif not retained["validator_output_valid"]:
            rejection_stage = "invalid_validator_output"
        elif not retained["accepted"]:
            rejection_stage = "independent_model_judgment"
        else:
            rejection_stage = None
        judgments.append(
            {
                "item_id": candidate["item_id"],
                "deterministic_checks": {
                    "answer_span_consistency": {
                        "passed": span_passed,
                        "note": span_note,
                    }
                },
                "judgments": retained["judgments"],
                "accepted": accepted,
                "rejection_stage": rejection_stage,
                "validation_metadata": {
                    "status": "reused_live_model_evidence",
                    "artifact": str(PILOT_DIR.relative_to(ROOT)),
                    "original_candidate_id": original_id,
                    "blind_item_id": retained["blind_item_id"],
                    "model": VALIDATION_MODEL,
                    "historical_model_accepted": model_accepted,
                    "active_precheck_reapplied": True,
                },
            }
        )
    return (
        sorted(attempts, key=lambda row: row["candidate_id"]),
        sorted(candidates, key=lambda row: row["item_id"]),
        sorted(judgments, key=lambda row: row["item_id"]),
    )


def _merge_unique(
    current: list[dict[str, Any]], additions: list[dict[str, Any]], id_field: str
) -> list[dict[str, Any]]:
    by_id = {row[id_field]: row for row in current}
    for row in additions:
        previous = by_id.get(row[id_field])
        if previous is not None and previous != row:
            raise ValueError(f"conflicting retained rows for {id_field}={row[id_field]}")
        by_id[row[id_field]] = row
    return [by_id[key] for key in sorted(by_id)]


def _write_item_state(
    output_dir: Path,
    attempts: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    design: dict[str, Any],
) -> dict[str, Any]:
    judgment_by_id = {row["item_id"]: row for row in judgments}
    validator_accepted = [
        row
        for row in candidates
        if row["item_id"] in judgment_by_id
        and judgment_by_id[row["item_id"]]["accepted"]
    ]
    selected = select_item_bank(validator_accepted, design)
    write_jsonl(output_dir / "items/generation_attempts.jsonl", attempts)
    write_jsonl(output_dir / "items/candidates.jsonl", candidates)
    write_jsonl(output_dir / "items/validation.jsonl", judgments)
    write_jsonl(output_dir / "items/validator_accepted.jsonl", validator_accepted)
    write_jsonl(output_dir / "items/selected_bank.jsonl", selected)
    summary = bank_summary(
        candidates,
        validator_accepted,
        judgments,
        cells,
        selected_items=selected,
    )
    summary.update(
        {
            "generation_attempts": len(attempts),
            "structurally_invalid_attempts": sum(
                not row["structurally_valid"] for row in attempts
            ),
            "attempted_cells": len({row["cell_id"] for row in attempts}),
            "deterministic_precheck_rejections": sum(
                str(row.get("rejection_stage", "")).startswith(
                    "deterministic_precheck"
                )
                for row in judgments
            ),
        }
    )
    write_json(output_dir / "items/bank_summary.json", summary)
    return summary


def prepare_pilot_items(
    output_dir: Path, cells: list[dict[str, Any]], schema: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Initialize or verify the item tree with retained Phase-4 evidence."""

    reused_attempts, reused_candidates, reused_judgments = reuse_phase4_pilot(
        cells, schema
    )
    attempts_path = output_dir / "items/generation_attempts.jsonl"
    candidates_path = output_dir / "items/candidates.jsonl"
    judgments_path = output_dir / "items/validation.jsonl"
    attempts = _merge_unique(
        read_jsonl(attempts_path) if attempts_path.exists() else [],
        reused_attempts,
        "candidate_id",
    )
    candidates = _merge_unique(
        read_jsonl(candidates_path) if candidates_path.exists() else [],
        reused_candidates,
        "item_id",
    )
    judgments = _merge_unique(
        read_jsonl(judgments_path) if judgments_path.exists() else [],
        reused_judgments,
        "item_id",
    )
    return attempts, candidates, judgments


def cells_missing_generation_attempts(
    cells: list[dict[str, Any]], attempts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return cells with at least one unattempted N=3 candidate position."""

    missing_cell_ids = {
        cell["cell_id"] for cell, _ in missing_generation_positions(cells, attempts)
    }
    return [row for row in cells if row["cell_id"] in missing_cell_ids]


def missing_generation_positions(
    cells: list[dict[str, Any]], attempts: list[dict[str, Any]]
) -> list[tuple[dict[str, Any], int]]:
    """List unattempted default N=3 positions, ignoring declared later cohorts."""

    cells_by_id = {row["cell_id"]: row for row in cells}
    if len(cells_by_id) != len(cells):
        raise ValueError("GrammarCell IDs must be unique")
    attempted: set[tuple[str, int]] = set()
    for row in attempts:
        cell_id = row["cell_id"]
        index = int(row["candidate_index"])
        if cell_id not in cells_by_id:
            raise ValueError(f"invalid retained generation attempt: {row}")
        if index in RESCUE_INDICES:
            if not _is_declared_rescue_attempt(row):
                raise ValueError(
                    "post-N=3 attempt lacks declared rescue provenance: "
                    f"{row}"
                )
            expected_id = _current_candidate_id(cell_id, index)
            if row["candidate_id"] != expected_id:
                raise ValueError(
                    f"attempt ID does not match its fixed rescue position: {row}"
                )
            continue
        if index in INTERVENTION_INDICES:
            if not _is_declared_intervention_attempt(row):
                raise ValueError(
                    "post-rescue attempt lacks declared intervention provenance: "
                    f"{row}"
                )
            expected_id = _current_candidate_id(cell_id, index)
            if row["candidate_id"] != expected_id:
                raise ValueError(
                    "attempt ID does not match its fixed intervention position: "
                    f"{row}"
                )
            continue
        if (
            not 1 <= index <= PILOT_N
            or _is_declared_rescue_attempt(row)
            or _is_declared_intervention_attempt(row)
        ):
            raise ValueError(f"invalid retained generation attempt: {row}")
        key = (cell_id, index)
        if key in attempted:
            raise ValueError(f"duplicate retained generation attempt: {key}")
        expected_id = _current_candidate_id(cell_id, index)
        if row["candidate_id"] != expected_id:
            raise ValueError(
                f"attempt ID does not match its fixed candidate position: {row}"
            )
        attempted.add(key)
    return [
        (cell, index)
        for cell in cells
        for index in range(1, PILOT_N + 1)
        if (cell["cell_id"], index) not in attempted
    ]


def _parallel_completed(
    rows: list[Any], function: Callable[[Any], Any], workers: int
):
    if workers < 1:
        raise ValueError("workers must be positive")
    if workers == 1:
        for row in rows:
            yield row, function(row)
        return
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(function, row): row for row in rows}
        for future in as_completed(futures):
            yield futures[future], future.result()


def generate_and_validate_missing(
    output_dir: Path,
    cells: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
    *,
    workers: int,
    generation_model: str,
    validation_model: str,
    reasoning_effort: str,
    model_call: ModelCall = call_model,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Generate and validate only positions lacking retained attempt records."""

    design = read_yaml(GENERATION_DESIGN_PATH)
    if int(design["generation"]["candidates_per_cell"]) != PILOT_N:
        raise ValueError("full-dataset runner is frozen to the active N=3 design")
    prompt = read_text(GENERATION_PROMPT_PATH)
    rulebook = read_text(GENERATION_RULEBOOK_PATH)
    item_format = read_yaml(ITEM_FORMAT_PATH)
    missing_positions = missing_generation_positions(cells, attempts)

    def generate_position(position: tuple[dict[str, Any], int]):
        cell, index = position
        started = time.monotonic()
        try:
            candidate = generate_item_candidate(
                cell,
                prompt,
                rulebook,
                design,
                item_format,
                candidate_index=index,
                model=generation_model,
                reasoning_effort=reasoning_effort,
                model_call=model_call,
                evidence_dir=output_dir / "items/generation_evidence",
            )
            return {
                "candidate": candidate,
                "runtime_seconds": time.monotonic() - started,
                "error": None,
            }
        except Exception as error:  # a failed call is still one of the fixed N attempts
            return {
                "candidate": None,
                "runtime_seconds": time.monotonic() - started,
                "error_type": type(error).__name__,
                "error": str(error),
            }

    for completed, (position, result) in enumerate(
        _parallel_completed(missing_positions, generate_position, workers), 1
    ):
        cell, index = position
        candidate_id = _current_candidate_id(cell["cell_id"], index)
        error = result.get("error")
        attempt = {
            "candidate_id": candidate_id,
            "cell_id": cell["cell_id"],
            "candidate_index": index,
            "candidate_count": PILOT_N,
            "structurally_valid": error is None,
            "structural_errors": [] if error is None else [error],
            "call_error": result.get("error_type"),
            "runtime_seconds": result["runtime_seconds"],
            "model": generation_model,
            "provenance": {"status": "phase6_live_model_evidence"},
        }
        attempts = _merge_unique(attempts, [attempt], "candidate_id")
        if result["candidate"] is not None:
            candidates = _merge_unique(
                candidates, [result["candidate"]], "item_id"
            )
        # Both files are rewritten after every completed position. An
        # interruption can therefore lose at most an in-flight call.
        write_jsonl(output_dir / "items/generation_attempts.jsonl", attempts)
        write_jsonl(output_dir / "items/candidates.jsonl", candidates)
        print(
            f"generation attempts completed: {completed}/{len(missing_positions)}",
            flush=True,
        )
    write_jsonl(
        output_dir / "items/generation_failures.jsonl",
        [row for row in attempts if not row["structurally_valid"]],
    )

    judged_ids = {row["item_id"] for row in judgments}
    unjudged = [
        row
        for row in candidates
        if row["item_id"] not in judged_ids
        and int(row["generation_metadata"]["candidate_index"]) <= PILOT_N
        and row["generation_metadata"].get("provenance", {}).get("status")
        != RESCUE_STATUS
    ]
    validation_prompt = read_text(VALIDATION_PROMPT_PATH)
    validation_criteria = read_yaml(VALIDATION_CRITERIA_PATH)

    def validate_candidate(candidate: dict[str, Any]):
        started = time.monotonic()
        try:
            _, rows = validate_items(
                [candidate],
                cells,
                validation_prompt,
                validation_criteria,
                model=validation_model,
                reasoning_effort=reasoning_effort,
                model_call=model_call,
                evidence_dir=output_dir / "items/validation_evidence",
            )
            return {
                "judgment": rows[0],
                "runtime_seconds": time.monotonic() - started,
                "error": None,
            }
        except Exception as error:  # retain a terminal invalid-judgment record
            return {
                "judgment": {
                    "item_id": candidate["item_id"],
                    "deterministic_checks": {},
                    "judgments": {},
                    "accepted": False,
                    "rejection_stage": "validator_call_or_output_failure",
                },
                "runtime_seconds": time.monotonic() - started,
                "error_type": type(error).__name__,
                "error": str(error),
            }

    for completed, (candidate, result) in enumerate(
        _parallel_completed(unjudged, validate_candidate, workers), 1
    ):
        judgment = result["judgment"]
        judgment["validation_metadata"] = {
            "status": "phase6_live_model_evidence",
            "model": validation_model,
            "runtime_seconds": result["runtime_seconds"],
            "error_type": result.get("error_type"),
            "error": result.get("error"),
        }
        judgments = _merge_unique(judgments, [judgment], "item_id")
        # A retained row, including an invalid judge output, is never silently
        # overwritten or re-called on resume.
        write_jsonl(output_dir / "items/validation.jsonl", judgments)
        if completed % 10 == 0 or completed == len(unjudged):
            print(
                f"validation items completed: {completed}/{len(unjudged)}",
                flush=True,
            )
    write_jsonl(
        output_dir / "items/validation_failures.jsonl",
        [
            row
            for row in judgments
            if row.get("rejection_stage") == "validator_call_or_output_failure"
        ],
    )
    return attempts, candidates, judgments


def _uncovered_cells(
    cells: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidate_by_id = {row["item_id"]: row for row in candidates}
    covered = {
        candidate_by_id[row["item_id"]]["cell_id"]
        for row in judgments
        if row.get("accepted") and row["item_id"] in candidate_by_id
    }
    return [row for row in cells if row["cell_id"] not in covered]


def prepare_rescue_plan(
    output_dir: Path,
    cells: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
) -> dict[str, Any]:
    """Freeze or reload the conditional zero-coverage rescue cohort."""

    missing_default = missing_generation_positions(cells, attempts)
    if missing_default:
        raise ValueError(
            "conditional rescue requires terminal attempts for all default N=3 "
            f"positions; {len(missing_default)} positions remain"
        )

    judgment_ids = {row["item_id"] for row in judgments}
    unjudged_default = [
        row["item_id"]
        for row in candidates
        if int(row["generation_metadata"]["candidate_index"]) <= PILOT_N
        and row["item_id"] not in judgment_ids
    ]
    if unjudged_default:
        raise ValueError(
            "conditional rescue requires terminal validation for every valid "
            f"default candidate; {len(unjudged_default)} judgments remain"
        )

    plan_path = output_dir / "items/rescue_plan.json"
    if plan_path.exists():
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        expected_fixed = {
            "protocol": RESCUE_PROTOCOL,
            "trigger": "zero_validator_accepted_after_default_n3",
            "default_candidates_per_cell": PILOT_N,
            "candidate_indices": list(RESCUE_INDICES),
        }
        for key, value in expected_fixed.items():
            if plan.get(key) != value:
                raise ValueError(f"retained rescue plan has unexpected {key}: {plan}")
        valid_cell_ids = {row["cell_id"] for row in cells}
        if (
            not plan.get("cell_ids")
            or len(plan["cell_ids"]) != len(set(plan["cell_ids"]))
            or not set(plan["cell_ids"]) <= valid_cell_ids
        ):
            raise ValueError(f"retained rescue plan has invalid cell IDs: {plan}")
        return plan

    if any(_is_declared_rescue_attempt(row) for row in attempts):
        raise ValueError("declared rescue attempts exist without a frozen rescue plan")
    uncovered = _uncovered_cells(cells, candidates, judgments)
    if not uncovered:
        raise ValueError(
            "conditional rescue is forbidden because the default N=3 bank "
            "already covers every GrammarCell"
        )
    plan = {
        "protocol": RESCUE_PROTOCOL,
        "trigger": "zero_validator_accepted_after_default_n3",
        "default_candidates_per_cell": PILOT_N,
        "candidate_indices": list(RESCUE_INDICES),
        "cell_ids": sorted(row["cell_id"] for row in uncovered),
        "planned_generation_attempts": len(uncovered) * len(RESCUE_INDICES),
    }
    # The plan is persisted before any model call so later acceptance cannot
    # shrink the preregistered cohort during an interrupted/resumed run.
    write_json(plan_path, plan)
    return plan


def missing_rescue_positions(
    cells: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    plan: dict[str, Any],
) -> list[tuple[dict[str, Any], int]]:
    """Return the unattempted positions 4/5 in the frozen rescue cohort."""

    cells_by_id = {row["cell_id"]: row for row in cells}
    plan_ids = set(plan["cell_ids"])
    attempted: set[tuple[str, int]] = set()
    for row in attempts:
        index = int(row["candidate_index"])
        if index <= PILOT_N:
            continue
        if index in INTERVENTION_INDICES and _is_declared_intervention_attempt(row):
            continue
        if index not in RESCUE_INDICES or not _is_declared_rescue_attempt(row):
            raise ValueError(f"invalid post-N=3 generation attempt: {row}")
        if row["cell_id"] not in plan_ids:
            raise ValueError(f"rescue attempt is outside the frozen cohort: {row}")
        key = (row["cell_id"], index)
        if key in attempted:
            raise ValueError(f"duplicate retained rescue attempt: {key}")
        if row["candidate_id"] != _current_candidate_id(*key):
            raise ValueError(f"rescue attempt ID does not match its position: {row}")
        attempted.add(key)
    return [
        (cells_by_id[cell_id], index)
        for cell_id in sorted(plan_ids)
        for index in RESCUE_INDICES
        if (cell_id, index) not in attempted
    ]


def generate_and_validate_rescue(
    output_dir: Path,
    cells: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
    *,
    workers: int,
    generation_model: str,
    validation_model: str,
    reasoning_effort: str,
    model_call: ModelCall = call_model,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Run the frozen two-position rescue without recalling retained rows."""

    plan = prepare_rescue_plan(output_dir, cells, attempts, candidates, judgments)
    design = read_yaml(GENERATION_DESIGN_PATH)
    if int(design["generation"]["candidates_per_cell"]) != PILOT_N:
        raise ValueError("conditional rescue assumes the frozen default N=3 design")
    # Only the declared candidate-position extent changes. Prompt, rulebook,
    # task format, lexical design, models, and validation criteria are reused.
    rescue_design = json.loads(json.dumps(design))
    rescue_design["generation"]["candidates_per_cell"] = max(RESCUE_INDICES)
    prompt = read_text(GENERATION_PROMPT_PATH)
    rulebook = read_text(GENERATION_RULEBOOK_PATH)
    item_format = read_yaml(ITEM_FORMAT_PATH)
    missing_positions = missing_rescue_positions(cells, attempts, plan)

    def generate_position(position: tuple[dict[str, Any], int]):
        cell, index = position
        started = time.monotonic()
        try:
            candidate = generate_item_candidate(
                cell,
                prompt,
                rulebook,
                rescue_design,
                item_format,
                candidate_index=index,
                model=generation_model,
                reasoning_effort=reasoning_effort,
                model_call=model_call,
                evidence_dir=output_dir / "items/generation_evidence/rescue",
            )
            candidate["generation_metadata"]["provenance"] = _rescue_provenance()
            return {
                "candidate": candidate,
                "runtime_seconds": time.monotonic() - started,
                "error": None,
            }
        except Exception as error:
            return {
                "candidate": None,
                "runtime_seconds": time.monotonic() - started,
                "error_type": type(error).__name__,
                "error": str(error),
            }

    for completed, (position, result) in enumerate(
        _parallel_completed(missing_positions, generate_position, workers), 1
    ):
        cell, index = position
        candidate_id = _current_candidate_id(cell["cell_id"], index)
        error = result.get("error")
        attempt = {
            "candidate_id": candidate_id,
            "cell_id": cell["cell_id"],
            "candidate_index": index,
            "candidate_count": max(RESCUE_INDICES),
            "structurally_valid": error is None,
            "structural_errors": [] if error is None else [error],
            "call_error": result.get("error_type"),
            "runtime_seconds": result["runtime_seconds"],
            "model": generation_model,
            "provenance": _rescue_provenance(),
        }
        attempts = _merge_unique(attempts, [attempt], "candidate_id")
        if result["candidate"] is not None:
            candidates = _merge_unique(
                candidates, [result["candidate"]], "item_id"
            )
        write_jsonl(output_dir / "items/generation_attempts.jsonl", attempts)
        write_jsonl(output_dir / "items/candidates.jsonl", candidates)
        print(
            f"rescue generation attempts completed: {completed}/"
            f"{len(missing_positions)}",
            flush=True,
        )

    judgment_ids = {row["item_id"] for row in judgments}
    plan_ids = set(plan["cell_ids"])
    unjudged = [
        row
        for row in candidates
        if row["cell_id"] in plan_ids
        and int(row["generation_metadata"]["candidate_index"])
        in RESCUE_INDICES
        and row["generation_metadata"].get("provenance", {}).get("status")
        == RESCUE_STATUS
        and row["item_id"] not in judgment_ids
    ]
    validation_prompt = read_text(VALIDATION_PROMPT_PATH)
    validation_criteria = read_yaml(VALIDATION_CRITERIA_PATH)

    def validate_candidate(candidate: dict[str, Any]):
        started = time.monotonic()
        try:
            _, rows = validate_items(
                [candidate],
                cells,
                validation_prompt,
                validation_criteria,
                model=validation_model,
                reasoning_effort=reasoning_effort,
                model_call=model_call,
                evidence_dir=output_dir / "items/validation_evidence/rescue",
            )
            return {
                "judgment": rows[0],
                "runtime_seconds": time.monotonic() - started,
                "error": None,
            }
        except Exception as error:
            return {
                "judgment": {
                    "item_id": candidate["item_id"],
                    "deterministic_checks": {},
                    "judgments": {},
                    "accepted": False,
                    "rejection_stage": "validator_call_or_output_failure",
                },
                "runtime_seconds": time.monotonic() - started,
                "error_type": type(error).__name__,
                "error": str(error),
            }

    for completed, (candidate, result) in enumerate(
        _parallel_completed(unjudged, validate_candidate, workers), 1
    ):
        judgment = result["judgment"]
        judgment["validation_metadata"] = {
            **_rescue_provenance(),
            "model": validation_model,
            "runtime_seconds": result["runtime_seconds"],
            "error_type": result.get("error_type"),
            "error": result.get("error"),
        }
        judgments = _merge_unique(judgments, [judgment], "item_id")
        write_jsonl(output_dir / "items/validation.jsonl", judgments)
        print(
            f"rescue validation items completed: {completed}/{len(unjudged)}",
            flush=True,
        )
    return attempts, candidates, judgments


def prepare_determinacy_intervention_plan(
    output_dir: Path,
    cells: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
) -> dict[str, Any]:
    """Freeze cells still uncovered after rescue due to determinacy failure."""

    missing_default = missing_generation_positions(cells, attempts)
    if missing_default:
        raise ValueError(
            "determinacy intervention requires terminal attempts for all default "
            f"N=3 positions; {len(missing_default)} positions remain"
        )
    rescue_plan_path = output_dir / "items/rescue_plan.json"
    if not rescue_plan_path.exists():
        raise ValueError(
            "determinacy intervention requires the frozen unchanged-prompt "
            "rescue to exist and be complete"
        )
    rescue_plan = json.loads(rescue_plan_path.read_text(encoding="utf-8"))
    if (
        rescue_plan.get("protocol") != RESCUE_PROTOCOL
        or rescue_plan.get("candidate_indices") != list(RESCUE_INDICES)
    ):
        raise ValueError(
            f"determinacy intervention found an invalid rescue plan: {rescue_plan}"
        )
    pending_rescue = missing_rescue_positions(cells, attempts, rescue_plan)
    if pending_rescue:
        raise ValueError(
            "determinacy intervention requires the unchanged-prompt rescue to "
            f"be complete; {len(pending_rescue)} positions remain"
        )

    judgment_ids = {row["item_id"] for row in judgments}
    pre_intervention_candidates = [
        row
        for row in candidates
        if row.get("generation_metadata", {}).get("provenance", {}).get("status")
        != INTERVENTION_STATUS
    ]
    unjudged_pre_intervention = [
        row["item_id"]
        for row in pre_intervention_candidates
        if row["item_id"] not in judgment_ids
    ]
    if unjudged_pre_intervention:
        raise ValueError(
            "determinacy intervention requires terminal validation for every valid "
            "default/rescue candidate; "
            f"{len(unjudged_pre_intervention)} judgments remain"
        )

    plan_path = output_dir / "items/determinacy_intervention_plan.json"
    prompt_sha256 = _sha256(INTERVENTION_PROMPT_PATH)
    if plan_path.exists():
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        expected_fixed = {
            "protocol": INTERVENTION_PROTOCOL,
            "trigger": (
                "zero_coverage_after_rescue_with_repeated_determinacy_failure"
            ),
            "candidate_indices": list(INTERVENTION_INDICES),
            "generation_prompt": str(INTERVENTION_PROMPT_PATH.relative_to(ROOT)),
            "generation_prompt_sha256": prompt_sha256,
            "only_generation_prompt_changes": True,
        }
        for key, value in expected_fixed.items():
            if plan.get(key) != value:
                raise ValueError(
                    f"retained determinacy intervention plan has unexpected "
                    f"{key}: {plan}"
                )
        valid_cell_ids = {row["cell_id"] for row in cells}
        if (
            not plan.get("cell_ids")
            or len(plan["cell_ids"]) != len(set(plan["cell_ids"]))
            or not set(plan["cell_ids"]) <= valid_cell_ids
        ):
            raise ValueError(
                "retained determinacy intervention plan has invalid cell IDs: "
                f"{plan}"
            )
        return plan

    if any(_is_declared_intervention_attempt(row) for row in attempts):
        raise ValueError(
            "declared determinacy-intervention attempts exist without a frozen plan"
        )
    uncovered = _uncovered_cells(cells, candidates, judgments)
    if not uncovered:
        raise ValueError(
            "determinacy intervention is forbidden because the unchanged-prompt "
            "rescue already covers every GrammarCell"
        )

    candidates_by_id = {row["item_id"]: row for row in candidates}
    failure_counts: dict[str, int] = {}
    prior_counts: dict[str, int] = {}
    for cell in uncovered:
        cell_id = cell["cell_id"]
        prior = [
            row
            for row in judgments
            if row["item_id"] in candidates_by_id
            and candidates_by_id[row["item_id"]]["cell_id"] == cell_id
            and row.get("validation_metadata", {}).get("status")
            != INTERVENTION_STATUS
        ]
        determinacy_failures = [
            row
            for row in prior
            if row.get("judgments", {})
            .get("determinacy", {})
            .get("passed")
            is False
        ]
        if not prior or len(determinacy_failures) != len(prior):
            raise ValueError(
                "determinacy intervention is restricted to uncovered cells whose "
                "every prior terminal item judgment failed determinacy; "
                f"{cell_id} has {len(determinacy_failures)}/{len(prior)}"
            )
        prior_counts[cell_id] = len(prior)
        failure_counts[cell_id] = len(determinacy_failures)

    plan = {
        "protocol": INTERVENTION_PROTOCOL,
        "trigger": "zero_coverage_after_rescue_with_repeated_determinacy_failure",
        "candidate_indices": list(INTERVENTION_INDICES),
        "cell_ids": sorted(row["cell_id"] for row in uncovered),
        "planned_generation_attempts": len(uncovered)
        * len(INTERVENTION_INDICES),
        "prior_terminal_judgments_by_cell": dict(sorted(prior_counts.items())),
        "prior_determinacy_failures_by_cell": dict(sorted(failure_counts.items())),
        "generation_prompt": str(INTERVENTION_PROMPT_PATH.relative_to(ROOT)),
        "generation_prompt_sha256": prompt_sha256,
        "only_generation_prompt_changes": True,
    }
    # Freeze the complete cohort before the first call. Acceptance at position
    # 6 therefore cannot suppress the preregistered position-7 call.
    write_json(plan_path, plan)
    return plan


def missing_determinacy_intervention_positions(
    cells: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    plan: dict[str, Any],
) -> list[tuple[dict[str, Any], int]]:
    """Return unattempted positions 6/7 in the frozen intervention cohort."""

    cells_by_id = {row["cell_id"]: row for row in cells}
    plan_ids = set(plan["cell_ids"])
    attempted: set[tuple[str, int]] = set()
    for row in attempts:
        index = int(row["candidate_index"])
        if index <= PILOT_N:
            continue
        if index in RESCUE_INDICES and _is_declared_rescue_attempt(row):
            continue
        if (
            index not in INTERVENTION_INDICES
            or not _is_declared_intervention_attempt(row)
        ):
            raise ValueError(f"invalid post-rescue generation attempt: {row}")
        if row["cell_id"] not in plan_ids:
            raise ValueError(
                f"determinacy-intervention attempt is outside the frozen cohort: {row}"
            )
        key = (row["cell_id"], index)
        if key in attempted:
            raise ValueError(
                f"duplicate retained determinacy-intervention attempt: {key}"
            )
        if row["candidate_id"] != _current_candidate_id(*key):
            raise ValueError(
                "determinacy-intervention attempt ID does not match its position: "
                f"{row}"
            )
        attempted.add(key)
    return [
        (cells_by_id[cell_id], index)
        for cell_id in sorted(plan_ids)
        for index in INTERVENTION_INDICES
        if (cell_id, index) not in attempted
    ]


def generate_and_validate_determinacy_intervention(
    output_dir: Path,
    cells: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
    *,
    workers: int,
    generation_model: str,
    validation_model: str,
    reasoning_effort: str,
    model_call: ModelCall = call_model,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Run the frozen prompt intervention without recalling retained rows."""

    plan = prepare_determinacy_intervention_plan(
        output_dir, cells, attempts, candidates, judgments
    )
    rescue_generation_models = {
        row["model"] for row in attempts if _is_declared_rescue_attempt(row)
    }
    rescue_validation_models = {
        row.get("validation_metadata", {}).get("model")
        for row in judgments
        if row.get("validation_metadata", {}).get("status") == RESCUE_STATUS
    }
    if rescue_generation_models != {generation_model}:
        raise ValueError(
            "determinacy intervention must reuse the rescue generation model; "
            f"retained={sorted(rescue_generation_models)}, requested={generation_model}"
        )
    if rescue_validation_models != {validation_model}:
        raise ValueError(
            "determinacy intervention must reuse the rescue validation model; "
            f"retained={sorted(rescue_validation_models)}, requested={validation_model}"
        )
    retained_manifest_path = output_dir / "manifest.json"
    if retained_manifest_path.exists():
        retained_models = json.loads(
            retained_manifest_path.read_text(encoding="utf-8")
        ).get("models", {})
        expected_models = {
            "generation": generation_model,
            "validation": validation_model,
            "reasoning_effort": reasoning_effort,
        }
        mismatches = {
            name: (retained_models.get(name), value)
            for name, value in expected_models.items()
            if retained_models.get(name) != value
        }
        if mismatches:
            raise ValueError(
                "determinacy intervention must reuse the retained rescue model "
                f"settings: {mismatches}"
            )

    design = read_yaml(GENERATION_DESIGN_PATH)
    if int(design["generation"]["candidates_per_cell"]) != PILOT_N:
        raise ValueError(
            "determinacy intervention assumes the frozen default N=3 design"
        )
    intervention_design = json.loads(json.dumps(design))
    intervention_design["generation"]["candidates_per_cell"] = max(
        INTERVENTION_INDICES
    )
    prompt = read_text(INTERVENTION_PROMPT_PATH)
    rulebook = read_text(GENERATION_RULEBOOK_PATH)
    item_format = read_yaml(ITEM_FORMAT_PATH)
    missing_positions = missing_determinacy_intervention_positions(
        cells, attempts, plan
    )

    def generate_position(position: tuple[dict[str, Any], int]):
        cell, index = position
        started = time.monotonic()
        try:
            candidate = generate_item_candidate(
                cell,
                prompt,
                rulebook,
                intervention_design,
                item_format,
                candidate_index=index,
                model=generation_model,
                reasoning_effort=reasoning_effort,
                model_call=model_call,
                evidence_dir=(
                    output_dir / "items/generation_evidence/determinacy_intervention"
                ),
            )
            candidate["generation_metadata"]["provenance"] = (
                _intervention_provenance()
            )
            return {
                "candidate": candidate,
                "runtime_seconds": time.monotonic() - started,
                "error": None,
            }
        except Exception as error:
            return {
                "candidate": None,
                "runtime_seconds": time.monotonic() - started,
                "error_type": type(error).__name__,
                "error": str(error),
            }

    for completed, (position, result) in enumerate(
        _parallel_completed(missing_positions, generate_position, workers), 1
    ):
        cell, index = position
        candidate_id = _current_candidate_id(cell["cell_id"], index)
        error = result.get("error")
        attempt = {
            "candidate_id": candidate_id,
            "cell_id": cell["cell_id"],
            "candidate_index": index,
            "candidate_count": max(INTERVENTION_INDICES),
            "structurally_valid": error is None,
            "structural_errors": [] if error is None else [error],
            "call_error": result.get("error_type"),
            "runtime_seconds": result["runtime_seconds"],
            "model": generation_model,
            "provenance": _intervention_provenance(),
        }
        attempts = _merge_unique(attempts, [attempt], "candidate_id")
        if result["candidate"] is not None:
            candidates = _merge_unique(
                candidates, [result["candidate"]], "item_id"
            )
        write_jsonl(output_dir / "items/generation_attempts.jsonl", attempts)
        write_jsonl(output_dir / "items/candidates.jsonl", candidates)
        print(
            f"determinacy-intervention generation attempts completed: "
            f"{completed}/{len(missing_positions)}",
            flush=True,
        )

    judgment_ids = {row["item_id"] for row in judgments}
    plan_ids = set(plan["cell_ids"])
    unjudged = [
        row
        for row in candidates
        if row["cell_id"] in plan_ids
        and int(row["generation_metadata"]["candidate_index"])
        in INTERVENTION_INDICES
        and row["generation_metadata"].get("provenance", {}).get("status")
        == INTERVENTION_STATUS
        and row["item_id"] not in judgment_ids
    ]
    validation_prompt = read_text(VALIDATION_PROMPT_PATH)
    validation_criteria = read_yaml(VALIDATION_CRITERIA_PATH)

    def validate_candidate(candidate: dict[str, Any]):
        started = time.monotonic()
        try:
            _, rows = validate_items(
                [candidate],
                cells,
                validation_prompt,
                validation_criteria,
                model=validation_model,
                reasoning_effort=reasoning_effort,
                model_call=model_call,
                evidence_dir=(
                    output_dir / "items/validation_evidence/determinacy_intervention"
                ),
            )
            return {
                "judgment": rows[0],
                "runtime_seconds": time.monotonic() - started,
                "error": None,
            }
        except Exception as error:
            return {
                "judgment": {
                    "item_id": candidate["item_id"],
                    "deterministic_checks": {},
                    "judgments": {},
                    "accepted": False,
                    "rejection_stage": "validator_call_or_output_failure",
                },
                "runtime_seconds": time.monotonic() - started,
                "error_type": type(error).__name__,
                "error": str(error),
            }

    for completed, (candidate, result) in enumerate(
        _parallel_completed(unjudged, validate_candidate, workers), 1
    ):
        judgment = result["judgment"]
        judgment["validation_metadata"] = {
            **_intervention_provenance(),
            "model": validation_model,
            "runtime_seconds": result["runtime_seconds"],
            "error_type": result.get("error_type"),
            "error": result.get("error"),
        }
        judgments = _merge_unique(judgments, [judgment], "item_id")
        write_jsonl(output_dir / "items/validation.jsonl", judgments)
        print(
            f"determinacy-intervention validation items completed: "
            f"{completed}/{len(unjudged)}",
            flush=True,
        )
    return attempts, candidates, judgments


def write_manifest(
    output_dir: Path,
    static_summary: dict[str, Any],
    item_summary: dict[str, Any],
    cells: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    *,
    exact_command: str,
    generation_model: str,
    validation_model: str,
    reasoning_effort: str,
) -> dict[str, Any]:
    missing_positions = missing_generation_positions(cells, attempts)
    missing = cells_missing_generation_attempts(cells, attempts)
    covered = item_summary["covered_cells"]
    rescue_plan_path = output_dir / "items/rescue_plan.json"
    rescue_plan = (
        json.loads(rescue_plan_path.read_text(encoding="utf-8"))
        if rescue_plan_path.exists()
        else None
    )
    rescue_attempts = [row for row in attempts if _is_declared_rescue_attempt(row)]
    rescue_candidate_ids = {
        row["item_id"]
        for row in read_jsonl(output_dir / "items/candidates.jsonl")
        if row.get("generation_metadata", {}).get("provenance", {}).get("status")
        == RESCUE_STATUS
    }
    rescue_judgments = [
        row for row in read_jsonl(output_dir / "items/validation.jsonl")
        if row.get("validation_metadata", {}).get("status") == RESCUE_STATUS
    ]
    intervention_plan_path = output_dir / "items/determinacy_intervention_plan.json"
    intervention_plan = (
        json.loads(intervention_plan_path.read_text(encoding="utf-8"))
        if intervention_plan_path.exists()
        else None
    )
    intervention_attempts = [
        row for row in attempts if _is_declared_intervention_attempt(row)
    ]
    intervention_candidate_ids = {
        row["item_id"]
        for row in read_jsonl(output_dir / "items/candidates.jsonl")
        if row.get("generation_metadata", {}).get("provenance", {}).get("status")
        == INTERVENTION_STATUS
    }
    intervention_judgments = [
        row
        for row in read_jsonl(output_dir / "items/validation.jsonl")
        if row.get("validation_metadata", {}).get("status")
        == INTERVENTION_STATUS
    ]
    uncovered = _uncovered_cells(
        cells,
        read_jsonl(output_dir / "items/candidates.jsonl"),
        read_jsonl(output_dir / "items/validation.jsonl"),
    )
    pending_rescue_positions = (
        missing_rescue_positions(cells, attempts, rescue_plan)
        if rescue_plan is not None
        else []
    )
    rescue_judgment_ids = {row["item_id"] for row in rescue_judgments}
    pending_rescue_judgments = rescue_candidate_ids - rescue_judgment_ids
    pending_intervention_positions = (
        missing_determinacy_intervention_positions(
            cells, attempts, intervention_plan
        )
        if intervention_plan is not None
        else []
    )
    intervention_judgment_ids = {
        row["item_id"] for row in intervention_judgments
    }
    pending_intervention_judgments = (
        intervention_candidate_ids - intervention_judgment_ids
    )
    if missing_positions:
        status = "prepared_for_missing_candidate_generation"
    elif rescue_plan is not None and (
        pending_rescue_positions or pending_rescue_judgments
    ):
        status = "conditional_rescue_in_progress"
    elif intervention_plan is not None and (
        pending_intervention_positions or pending_intervention_judgments
    ):
        status = "determinacy_intervention_in_progress"
    elif covered == len(cells):
        status = "fixed_item_bank_complete"
    elif intervention_plan is not None:
        status = "determinacy_intervention_complete_item_bank_incomplete"
    elif rescue_plan is not None:
        status = "rescue_complete_item_bank_incomplete"
    else:
        status = "generation_complete_item_bank_incomplete"
    default_candidate_count = (
        item_summary["generated_candidates"]
        - len(rescue_candidate_ids)
        - len(intervention_candidate_ids)
    )
    default_judgment_count = len(
        read_jsonl(output_dir / "items/validation.jsonl")
    ) - len(rescue_judgments) - len(intervention_judgments)
    manifest = {
        "dataset_id": DATASET_ID,
        "status": status,
        "artifact_scope": "source_through_fixed_item_bank",
        "static_summary": static_summary,
        "item_summary": item_summary,
        "missing_generation_cells": [row["cell_id"] for row in missing],
        "missing_generation_positions": [
            {
                "cell_id": cell["cell_id"],
                "candidate_index": index,
            }
            for cell, index in missing_positions
        ],
        "uncovered_cell_ids": [row["cell_id"] for row in uncovered],
        "item_construction_counts": {
            "default": {
                "candidate_positions_per_cell": PILOT_N,
                "attempts": (
                    len(attempts)
                    - len(rescue_attempts)
                    - len(intervention_attempts)
                ),
                "structurally_valid_candidates": default_candidate_count,
                "validation_judgments": default_judgment_count,
                "validator_accepted": (
                    item_summary["validator_accepted_candidates"]
                    - sum(bool(row.get("accepted")) for row in rescue_judgments)
                    - sum(
                        bool(row.get("accepted"))
                        for row in intervention_judgments
                    )
                ),
            },
            "conditional_rescue": {
                "activated": rescue_plan is not None,
                "protocol": RESCUE_PROTOCOL,
                "cell_ids": rescue_plan["cell_ids"] if rescue_plan else [],
                "candidate_indices": list(RESCUE_INDICES),
                "planned_attempts": (
                    rescue_plan["planned_generation_attempts"]
                    if rescue_plan
                    else 0
                ),
                "attempts": len(rescue_attempts),
                "structurally_valid_candidates": len(rescue_candidate_ids),
                "validation_judgments": len(rescue_judgments),
                "validator_accepted": sum(
                    bool(row.get("accepted")) for row in rescue_judgments
                ),
            },
            "determinacy_intervention": {
                "activated": intervention_plan is not None,
                "protocol": INTERVENTION_PROTOCOL,
                "cell_ids": (
                    intervention_plan["cell_ids"] if intervention_plan else []
                ),
                "candidate_indices": list(INTERVENTION_INDICES),
                "planned_attempts": (
                    intervention_plan["planned_generation_attempts"]
                    if intervention_plan
                    else 0
                ),
                "attempts": len(intervention_attempts),
                "structurally_valid_candidates": len(
                    intervention_candidate_ids
                ),
                "validation_judgments": len(intervention_judgments),
                "validator_accepted": sum(
                    bool(row.get("accepted"))
                    for row in intervention_judgments
                ),
            },
        },
        "models": {
            "normalisation": "retained gpt-5.6-sol, medium, 2026-08-20",
            "generation": generation_model,
            "validation": validation_model,
            "reasoning_effort": reasoning_effort,
        },
        "item_method": {
            "default_candidates_per_cell": PILOT_N,
            "independent_validation": True,
            "maximum_selected_items_per_cell": 2,
            "conditional_rescue": {
                "trigger": "zero accepted items after all default N=3 positions",
                "candidate_indices": list(RESCUE_INDICES),
                "calls_per_uncovered_cell": len(RESCUE_INDICES),
                "prompt_models_and_validation_criteria_unchanged": True,
            },
            "determinacy_intervention": {
                "trigger": (
                    "zero accepted items after the completed unchanged-prompt "
                    "rescue, with determinacy failure in every prior terminal "
                    "item judgment"
                ),
                "candidate_indices": list(INTERVENTION_INDICES),
                "calls_per_uncovered_cell": len(INTERVENTION_INDICES),
                "generation_prompt": str(
                    INTERVENTION_PROMPT_PATH.relative_to(ROOT)
                ),
                "only_generation_prompt_changes": True,
                "models_rulebook_format_and_validation_criteria_unchanged": True,
            },
            "pilot_reuse": (
                "first-three prefix of the Phase-4 live model-selected condition, "
                "translated only by exact GrammarCell feature tuple"
            ),
            "construction_boundary": (
                "No grammar fold, learner evidence, KC, simulation, outcome, or KT "
                "information enters generation or validation."
            ),
        },
        "inputs": {
            "grammar_schema": str(GRAMMAR_SCHEMA_PATH.relative_to(ROOT)),
            "resource_schema": str(RESOURCE_SCHEMA_PATH.relative_to(ROOT)),
            "generation_design": str(GENERATION_DESIGN_PATH.relative_to(ROOT)),
            "determinacy_intervention_prompt": str(
                INTERVENTION_PROMPT_PATH.relative_to(ROOT)
            ),
            "phase4_pilot": str(PILOT_DIR.relative_to(ROOT)),
        },
        "exact_command": exact_command,
    }
    write_json(output_dir / "manifest.json", manifest)
    write_jsonl(output_dir / "items/missing_cells.jsonl", missing)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare or extend the retained medium grammar item bank."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--prepare-only",
        action="store_true",
        help="prepare retained source/canonical/pilot artifacts without model calls",
    )
    mode.add_argument(
        "--generate-missing",
        action="store_true",
        help="make live calls for cells absent from the retained N=3 pilot",
    )
    mode.add_argument(
        "--rescue-uncovered",
        action="store_true",
        help=(
            "after completed default N=3 construction, make exactly positions "
            "4 and 5 for each zero-coverage cell"
        ),
    )
    mode.add_argument(
        "--determinacy-intervention",
        action="store_true",
        help=(
            "after completed unchanged-prompt rescue, make exactly positions "
            "6 and 7 for cells with repeated determinacy failures, using the "
            "separately declared explicit-construction prompt"
        ),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--legacy-run", type=Path, default=ROOT / "runs/base")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--generation-model", default=GENERATION_MODEL)
    parser.add_argument("--validation-model", default=VALIDATION_MODEL)
    parser.add_argument("--reasoning-effort", default=REASONING_EFFORT)
    arguments = parser.parse_args()
    if (
        arguments.generate_missing
        or arguments.rescue_uncovered
        or arguments.determinacy_intervention
    ) and shutil.which("codex") is None:
        parser.error("codex CLI is unavailable; run --prepare-only")
    return arguments


def main() -> int:
    arguments = parse_args()
    output_dir = arguments.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    static_summary = prepare_static_inputs(output_dir, arguments.legacy_run.resolve())
    schema = read_yaml(GRAMMAR_SCHEMA_PATH)
    cells = read_jsonl(output_dir / "canonical/cells.jsonl")
    design = read_yaml(GENERATION_DESIGN_PATH)
    attempts, candidates, judgments = prepare_pilot_items(output_dir, cells, schema)
    if arguments.generate_missing:
        attempts, candidates, judgments = generate_and_validate_missing(
            output_dir,
            cells,
            attempts,
            candidates,
            judgments,
            workers=arguments.workers,
            generation_model=arguments.generation_model,
            validation_model=arguments.validation_model,
            reasoning_effort=arguments.reasoning_effort,
        )
    elif arguments.rescue_uncovered:
        attempts, candidates, judgments = generate_and_validate_rescue(
            output_dir,
            cells,
            attempts,
            candidates,
            judgments,
            workers=arguments.workers,
            generation_model=arguments.generation_model,
            validation_model=arguments.validation_model,
            reasoning_effort=arguments.reasoning_effort,
        )
    elif arguments.determinacy_intervention:
        attempts, candidates, judgments = (
            generate_and_validate_determinacy_intervention(
                output_dir,
                cells,
                attempts,
                candidates,
                judgments,
                workers=arguments.workers,
                generation_model=arguments.generation_model,
                validation_model=arguments.validation_model,
                reasoning_effort=arguments.reasoning_effort,
            )
        )
    item_summary = _write_item_state(
        output_dir, attempts, candidates, judgments, cells, design
    )
    manifest = write_manifest(
        output_dir,
        static_summary,
        item_summary,
        cells,
        attempts,
        exact_command=" ".join([sys.executable, *sys.argv]),
        generation_model=arguments.generation_model,
        validation_model=arguments.validation_model,
        reasoning_effort=arguments.reasoning_effort,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
