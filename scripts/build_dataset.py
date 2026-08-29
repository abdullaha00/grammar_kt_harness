#!/usr/bin/env python3
"""Construct the full Grammar-KT baseline in explicit scientific stages.

The model-backed linguistic and item stages are resumable because every call
is immutable and every completed row is checkpointed. Raw EGP text and rendered
prompts stay under the ignored private directory; publishable dataset artifacts
contain only source identity, derived mappings, cells, K*, items, Q*, responses,
and declared provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.full_normalisation import (
    adapt_full_egp_source,
    normalise_phase1_record,
    normalise_phase2_record,
    sha256_file,
    source_cell_relations,
    stable_canonicalise,
)
from grammar_kt.full_items import (
    DETERMINACY_INTERVENTION_CANDIDATES_PER_CELL,
    DETERMINACY_INTERVENTION_ID,
    PACKAGING_CORRECTION_ID,
    UNCHANGED_RESCUE_CANDIDATES_PER_CELL,
    UNCHANGED_RESCUE_ID,
    build_campaign_generation_call,
    build_generation_call,
    build_validation_call,
    candidate_audit_summary,
    construct_packaging_corrected_candidate,
    generate_one_campaign_candidate,
    generate_one_candidate,
    item_construction_audit,
    merge_completed_candidate_rows,
    merge_completed_judgment_rows,
    reconstruct_validation_judgment,
    recover_campaign_candidate,
    recover_generated_candidate,
    recover_validator_judgment,
    validate_one_candidate,
    validation_audit_summary,
)
from grammar_kt.generator_kcs import construct_generator_kcs
from grammar_kt.io import (
    load_typed_resource,
    read_jsonl,
    read_text,
    read_yaml,
    render,
    write_json,
    write_jsonl,
)
from grammar_kt.model_evidence import audited_model_call
from grammar_kt.normalise import (
    PHASE1_FIELDS,
    _validate_mapping,
    _validate_phase2_transition,
)
from grammar_kt.validate_items import select_item_bank


DATASET_ID = "grammar_kt_full_v1"
EXPECTED_SOURCE_SHA256 = (
    "e38c4f959f188150dae7b88f21e35d77828048772e222191818dc0c2488486cd"
)
EXPECTED_SOURCE_ROWS = 1222

RESOURCE_SCHEMA_PATH = ROOT / "modules/grammar/resource/egp/schema.yaml"
GRAMMAR_SCHEMA_PATH = ROOT / "modules/grammar/canonical/schema.yaml"
PHASE1_PROMPT_PATH = (
    ROOT / "modules/grammar/resource/egp/normalisation/phase1.txt"
)
PHASE2_PROMPT_PATH = (
    ROOT / "modules/grammar/resource/egp/normalisation/phase2.txt"
)
NORMALISATION_RULEBOOK_PATH = (
    ROOT / "modules/grammar/resource/egp/normalisation/rulebook.md"
)
MODEL_BACKENDS_PATH = ROOT / "modules/model_backends.yaml"
GENERATOR_DESIGN_PATH = ROOT / "modules/kcs/generator/design.yaml"
GENERATOR_DECLARATION_PATH = ROOT / "modules/kcs/generator/english_kcs.yaml"
GENERATION_PROMPT_PATH = ROOT / "modules/items/generation/prompt.txt"
GENERATION_RULEBOOK_PATH = ROOT / "modules/items/generation/rulebook.md"
GENERATION_DESIGN_PATH = ROOT / "modules/items/generation/design.yaml"
ITEM_FORMAT_PATH = (
    ROOT / "modules/items/generation/formats/controlled_production.yaml"
)
VALIDATION_PROMPT_PATH = ROOT / "modules/items/validation/prompt.txt"
VALIDATION_CRITERIA_PATH = ROOT / "modules/items/validation/criteria.yaml"
RESCUE_PROTOCOL_PATH = (
    ROOT
    / "modules/items/generation/interventions/full_v1_rescue.yaml"
)
DETERMINACY_INTERVENTION_PROMPT_PATH = (
    ROOT
    / "modules/items/generation/ablations/"
    "determinacy_explicit_construction_prompt.txt"
)
PACKAGING_CORRECTIONS_PATH = (
    ROOT / "modules/items/corrections/full_v1_packaging_corrections.yaml"
)
EXPECTED_PACKAGING_CORRECTIONS_SHA256 = (
    "3bd85b52db7d0f5679bc24e142657c6a35bb42bc08250aa364e40123ef6037e6"
)
PUBLIC_NORMALISATION_NOTE = (
    "Unsanitised model note retained in restricted normalisation evidence."
)


def _git_revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def _json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_checkpoint(path: Path, rows: dict[str, dict[str, Any]], order: list[str]) -> None:
    write_jsonl(path, [rows[source_id] for source_id in order if source_id in rows])


def _public_normalisation_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    """Remove free text that could reproduce consult-only source prose."""

    return {**mapping, "note": PUBLIC_NORMALISATION_NOTE}


def _verify_public_normalisation_mapping(
    public: dict[str, Any], private: dict[str, Any], source_id: str
) -> None:
    """Verify a public checkpoint against its immutable private model result.

    Legacy full-v1 checkpoints may still contain the exact private note.  That
    one migration case is accepted and immediately rewritten in sanitised form;
    arbitrary note changes and all structured-field changes are rejected.
    """

    public_structured = {key: value for key, value in public.items() if key != "note"}
    private_structured = {
        key: value for key, value in private.items() if key != "note"
    }
    if public_structured != private_structured:
        raise ValueError(
            f"public normalisation mapping does not match private evidence: {source_id}"
        )
    public_note = public.get("note")
    if public_note != private.get("note") and public_note != PUBLIC_NORMALISATION_NOTE:
        raise ValueError(
            f"public normalisation note does not match private evidence: {source_id}"
        )


def _read_public_normalisation_mappings(
    path: Path,
    *,
    allowed_source_ids: set[str],
    schema: dict[str, Any],
    allow_resolved_eligibility: bool = False,
) -> dict[str, dict[str, Any]]:
    rows = read_jsonl(path) if path.exists() else []
    mappings: dict[str, dict[str, Any]] = {}
    for row in rows:
        source_id = row.get("source_id")
        if source_id in mappings:
            raise ValueError(f"duplicate public normalisation mapping: {source_id}")
        if source_id not in allowed_source_ids:
            raise ValueError(f"public normalisation mapping has unknown ID: {source_id}")
        _validate_mapping(
            row,
            source_id,
            schema,
            allow_resolved_eligibility=allow_resolved_eligibility,
        )
        mappings[source_id] = row
    return mappings


def _write_public_normalisation_mappings(
    path: Path,
    mappings: dict[str, dict[str, Any]],
    order: list[str],
) -> None:
    write_jsonl(
        path,
        [
            _public_normalisation_mapping(mappings[source_id])
            for source_id in order
            if source_id in mappings
        ],
    )


def _public_normalisation_attempt(row: dict[str, Any]) -> dict[str, Any]:
    """Publish technical error type names, never exception messages."""

    allowed = {
        "source_id",
        "status",
        "attempt_count",
        "runtime_seconds",
        "errors",
        "technical_error_types",
    }
    unknown = set(row) - allowed
    if unknown:
        raise ValueError(f"unknown public normalisation attempt fields: {sorted(unknown)}")
    errors = row.get("errors")
    if errors is not None:
        if not isinstance(errors, list) or any(
            not isinstance(error, dict)
            or not isinstance(error.get("error_type"), str)
            for error in errors
        ):
            raise ValueError("invalid legacy normalisation attempt errors")
        error_types = [error["error_type"] for error in errors]
    else:
        error_types = row.get("technical_error_types", [])
        if not isinstance(error_types, list) or any(
            not isinstance(error_type, str) for error_type in error_types
        ):
            raise ValueError("invalid normalisation technical error types")
    return {
        "source_id": row["source_id"],
        "status": row["status"],
        "attempt_count": row["attempt_count"],
        "runtime_seconds": row["runtime_seconds"],
        "errors": [{"error_type": error_type} for error_type in error_types],
    }


def _read_public_normalisation_attempts(
    path: Path, *, allowed_source_ids: set[str]
) -> dict[str, dict[str, Any]]:
    rows = read_jsonl(path) if path.exists() else []
    attempts: dict[str, dict[str, Any]] = {}
    for raw in rows:
        row = _public_normalisation_attempt(raw)
        source_id = row["source_id"]
        if source_id in attempts:
            raise ValueError(f"duplicate public normalisation attempt: {source_id}")
        if source_id not in allowed_source_ids:
            raise ValueError(f"public normalisation attempt has unknown ID: {source_id}")
        attempts[source_id] = row
    return attempts


def _write_public_normalisation_attempts(
    path: Path,
    attempts: dict[str, dict[str, Any]],
    order: list[str],
) -> None:
    write_jsonl(
        path,
        [
            _public_normalisation_attempt(attempts[source_id])
            for source_id in order
            if source_id in attempts
        ],
    )


def _assert_private_dir(private_dir: Path) -> None:
    resolved = private_dir.resolve()
    runs = (ROOT / "runs").resolve()
    if runs not in resolved.parents:
        raise ValueError(
            "consult-only source/call evidence must stay under the ignored runs/ directory"
        )


def _load_and_verify_source(source_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_hash = sha256_file(source_path)
    if source_hash != EXPECTED_SOURCE_SHA256:
        raise ValueError(
            f"EGP source SHA-256 differs: {source_hash} != {EXPECTED_SOURCE_SHA256}"
        )
    raw = read_jsonl(source_path)
    if len(raw) != EXPECTED_SOURCE_ROWS:
        raise ValueError(
            f"EGP source row count differs: {len(raw)} != {EXPECTED_SOURCE_ROWS}"
        )
    resources = adapt_full_egp_source(raw)
    resource_schema = read_yaml(RESOURCE_SCHEMA_PATH)
    # Validate through the active typed boundary without publishing the rows.
    for row in resources:
        required = {
            name
            for name, declaration in resource_schema["fields"].items()
            if declaration["required"]
        }
        if required - set(row) or set(row) - set(resource_schema["fields"]):
            raise ValueError(f"typed EGP source contract failed: {row['source_id']}")
    source_summary = {
        "raw_source_sha256": source_hash,
        "raw_source_rows": len(raw),
        "unique_source_ids": len({row["source_id"] for row in resources}),
        "extractor_usable": dict(
            sorted(Counter(str(row.get("usable")) for row in raw).items())
        ),
        "typed_stream_sha256": _json_sha256(resources),
    }
    return resources, source_summary


def prepare_source(
    source_path: Path, dataset_dir: Path, private_dir: Path, exact_command: str
) -> None:
    _assert_private_dir(private_dir)
    resources, summary = _load_and_verify_source(source_path)
    private_source = private_dir / "source/descriptors.jsonl"
    if private_source.exists() and read_jsonl(private_source) != resources:
        raise ValueError("private typed source differs from the verified snapshot")
    write_jsonl(private_source, resources)
    write_json(
        dataset_dir / "provenance/source_manifest.json",
        {
            "dataset_id": DATASET_ID,
            "resource": "English Grammar Profile consult-only snapshot",
            **summary,
            "scope_policy": (
                "All 1,222 descriptors enter Phase 1; each is classified against "
                "the declared single-main-clause English verbal-morphosyntax scope."
            ),
            "redistribution": (
                "Raw descriptor text and rendered model prompts are restricted and "
                "not included in the publishable dataset tree."
            ),
            "resource_schema": str(RESOURCE_SCHEMA_PATH.relative_to(ROOT)),
            "code_revision_at_stage_start": _git_revision(),
            "exact_command": exact_command,
        },
    )


def _existing_attempt_count(base: Path) -> int:
    return len([path for path in base.glob("attempt-*") if path.is_dir()])


def _call_with_technical_retries(
    function: Callable[[Path], dict[str, Any]],
    evidence_base: Path,
    *,
    max_attempts: int,
) -> dict[str, Any]:
    errors = []
    existing = _existing_attempt_count(evidence_base)
    for attempt_number in range(existing + 1, max_attempts + 1):
        evidence_dir = evidence_base / f"attempt-{attempt_number:02d}"
        started = time.monotonic()
        try:
            value = function(evidence_dir)
            return {
                "status": "success",
                "mapping": value,
                "attempt_count": attempt_number,
                "runtime_seconds": time.monotonic() - started,
                "errors": errors,
            }
        except Exception as error:  # terminal evidence is retained for audit
            errors.append(
                {
                    "attempt": attempt_number,
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            )
    return {
        "status": "technical_failure",
        "mapping": None,
        "attempt_count": max(existing, max_attempts),
        "runtime_seconds": None,
        "errors": errors,
    }


def _verify_normalisation_evidence_context(
    attempt_dir: Path,
    *,
    expected_input: dict[str, Any],
    expected_prompt: str,
    expected_model: str,
    expected_reasoning_effort: str,
    expected_stage: str,
    source_id: str,
) -> None:
    """Reject private evidence copied from a different scientific input."""

    required = ("input.json", "rendered_prompt.txt", "model_settings.json")
    present = [(attempt_dir / name).exists() for name in required]
    if not any(present):
        if (attempt_dir / "parsed_result.json").exists():
            raise ValueError(
                f"normalisation result lacks immutable call context: {source_id}"
            )
        return
    if not all(present):
        raise ValueError(f"incomplete normalisation call context: {source_id}")
    if _read_json(attempt_dir / "input.json") != expected_input:
        raise ValueError(f"normalisation private input drift: {source_id}")
    if (
        attempt_dir / "rendered_prompt.txt"
    ).read_text(encoding="utf-8") != expected_prompt:
        raise ValueError(f"normalisation rendered-prompt drift: {source_id}")
    settings = _read_json(attempt_dir / "model_settings.json")
    expected_settings = {
        "model": expected_model,
        "reasoning_effort": expected_reasoning_effort,
        "stage": expected_stage,
        "call_key": source_id,
    }
    if any(
        settings.get(key) != value for key, value in expected_settings.items()
    ):
        raise ValueError(f"normalisation model/settings drift: {source_id}")


def _recover_phase1(
    resource: dict[str, Any],
    evidence_base: Path,
    schema: dict[str, Any],
    *,
    phase1_prompt: str,
    rulebook: str,
    backend: dict[str, str],
) -> dict[str, Any] | None:
    descriptor = {name: resource[name] for name in PHASE1_FIELDS}
    expected_input = {"descriptor": descriptor}
    expected_prompt = render(
        phase1_prompt,
        {
            "descriptor": descriptor,
            "canonical_schema": schema,
            "rulebook": rulebook,
        },
    )
    recovered = None
    for attempt_dir in sorted(
        path for path in evidence_base.glob("attempt-*") if path.is_dir()
    ):
        _verify_normalisation_evidence_context(
            attempt_dir,
            expected_input=expected_input,
            expected_prompt=expected_prompt,
            expected_model=backend["model"],
            expected_reasoning_effort=backend["reasoning_effort"],
            expected_stage="normalisation.phase1",
            source_id=resource["source_id"],
        )
        path = attempt_dir / "parsed_result.json"
        if not path.exists():
            continue
        mapping = _read_json(path)
        try:
            _validate_mapping(mapping, resource["source_id"], schema)
        except Exception:
            continue
        if recovered is not None and recovered != mapping:
            raise ValueError(
                f"multiple valid Phase-1 results in private evidence: "
                f"{resource['source_id']}"
            )
        recovered = mapping
    return recovered


def _recover_phase2(
    resource: dict[str, Any],
    phase1_mapping: dict[str, Any],
    evidence_base: Path,
    schema: dict[str, Any],
    *,
    phase2_prompt: str,
    rulebook: str,
    backend: dict[str, str],
) -> dict[str, Any] | None:
    descriptor = {name: resource[name] for name in PHASE1_FIELDS}
    expected_input = {
        "descriptor": descriptor,
        "phase1_mapping": phase1_mapping,
        "examples": resource["examples"],
    }
    expected_prompt = render(
        phase2_prompt,
        {
            "descriptor": descriptor,
            "phase1_mapping": phase1_mapping,
            "examples": resource["examples"],
            "canonical_schema": schema,
            "rulebook": rulebook,
        },
    )
    recovered = None
    for attempt_dir in sorted(
        path for path in evidence_base.glob("attempt-*") if path.is_dir()
    ):
        _verify_normalisation_evidence_context(
            attempt_dir,
            expected_input=expected_input,
            expected_prompt=expected_prompt,
            expected_model=backend["model"],
            expected_reasoning_effort=backend["reasoning_effort"],
            expected_stage="normalisation.phase2",
            source_id=resource["source_id"],
        )
        path = attempt_dir / "parsed_result.json"
        if not path.exists():
            continue
        mapping = _read_json(path)
        try:
            _validate_mapping(
                mapping,
                resource["source_id"],
                schema,
                allow_resolved_eligibility=True,
            )
            _validate_phase2_transition(phase1_mapping, mapping, schema)
        except Exception:
            continue
        if recovered is not None and recovered != mapping:
            raise ValueError(
                f"multiple valid Phase-2 results in private evidence: "
                f"{resource['source_id']}"
            )
        recovered = mapping
    return recovered


def run_phase1(
    source_path: Path,
    dataset_dir: Path,
    private_dir: Path,
    *,
    workers: int,
    max_attempts: int,
    retry_failures: bool,
    exact_command: str,
) -> None:
    _assert_private_dir(private_dir)
    resources, source_summary = _load_and_verify_source(source_path)
    source_manifest = dataset_dir / "provenance/source_manifest.json"
    if not source_manifest.exists():
        prepare_source(source_path, dataset_dir, private_dir, exact_command)
    elif _read_json(source_manifest)["raw_source_sha256"] != source_summary[
        "raw_source_sha256"
    ]:
        raise ValueError("source manifest and supplied source differ")

    output_dir = dataset_dir / "provenance/normalisation"
    mappings_path = output_dir / "phase1_mappings.jsonl"
    attempts_path = output_dir / "phase1_attempts.jsonl"
    schema = read_yaml(GRAMMAR_SCHEMA_PATH)
    backend = read_yaml(MODEL_BACKENDS_PATH)["normalisation"]
    phase1_prompt = read_text(PHASE1_PROMPT_PATH)
    rulebook = read_text(NORMALISATION_RULEBOOK_PATH)
    order = [row["source_id"] for row in resources]
    allowed_source_ids = set(order)
    public_mappings = _read_public_normalisation_mappings(
        mappings_path,
        allowed_source_ids=allowed_source_ids,
        schema=schema,
    )
    attempts = _read_public_normalisation_attempts(
        attempts_path, allowed_source_ids=allowed_source_ids
    )
    mappings: dict[str, dict[str, Any]] = {}
    for resource in resources:
        source_id = resource["source_id"]
        recovered = _recover_phase1(
            resource,
            private_dir / "normalisation/phase1" / source_id,
            schema,
            phase1_prompt=phase1_prompt,
            rulebook=rulebook,
            backend=backend,
        )
        if source_id in public_mappings:
            if recovered is None:
                raise ValueError(
                    f"public Phase-1 mapping lacks private evidence: {source_id}"
                )
            _verify_public_normalisation_mapping(
                public_mappings[source_id], recovered, source_id
            )
        if recovered is not None:
            mappings[source_id] = recovered
            if source_id not in attempts:
                attempts[source_id] = {
                    "source_id": source_id,
                    "status": "success_recovered_private_evidence",
                    "attempt_count": _existing_attempt_count(
                        private_dir / "normalisation/phase1" / source_id
                    ),
                    "runtime_seconds": None,
                    "errors": [],
                }

    _write_public_normalisation_mappings(mappings_path, mappings, order)
    _write_public_normalisation_attempts(attempts_path, attempts, order)
    tasks = [
        resource
        for resource in resources
        if resource["source_id"] not in mappings
        and (
            retry_failures
            or attempts.get(resource["source_id"], {}).get("status")
            != "technical_failure"
        )
    ]

    def execute(resource: dict[str, Any]) -> dict[str, Any]:
        source_id = resource["source_id"]
        result = _call_with_technical_retries(
            lambda evidence_dir: normalise_phase1_record(
                resource,
                phase1_prompt,
                rulebook,
                schema,
                model=backend["model"],
                reasoning_effort=backend["reasoning_effort"],
                model_call=audited_model_call,
                evidence_dir=evidence_dir,
            ),
            private_dir / "normalisation/phase1" / source_id,
            max_attempts=max_attempts,
        )
        return {"source_id": source_id, **result}

    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(execute, row): row for row in tasks}
        for future in as_completed(futures):
            result = future.result()
            source_id = result["source_id"]
            returned = result.pop("mapping")
            if returned is not None:
                recovered = _recover_phase1(
                    next(row for row in resources if row["source_id"] == source_id),
                    private_dir / "normalisation/phase1" / source_id,
                    schema,
                    phase1_prompt=phase1_prompt,
                    rulebook=rulebook,
                    backend=backend,
                )
                if recovered is None or recovered != returned:
                    raise ValueError(
                        f"Phase-1 return differs from private evidence: {source_id}"
                    )
                mappings[source_id] = recovered
            attempts[source_id] = _public_normalisation_attempt(result)
            _write_public_normalisation_mappings(mappings_path, mappings, order)
            _write_public_normalisation_attempts(attempts_path, attempts, order)
            completed += 1
            if completed % 10 == 0 or completed == len(tasks):
                print(
                    f"Phase 1 terminal descriptors: {completed}/{len(tasks)}; "
                    f"valid total={len(mappings)}/{len(resources)}",
                    flush=True,
                )

    failures = sorted(set(order) - set(mappings))
    write_json(
        output_dir / "phase1_summary.json",
        {
            "dataset_id": DATASET_ID,
            "source_descriptors": len(resources),
            "valid_mappings": len(mappings),
            "technical_failure_source_ids": failures,
            "result_counts": dict(
                sorted(Counter(row["result"] for row in mappings.values()).items())
            ),
            "phase2_eligible": sum(
                row["result"] == "partial" and bool(row["phase2_eligible"])
                for row in mappings.values()
            ),
            "models": backend,
            "max_technical_attempts": max_attempts,
            "code_revision_at_stage_start": _git_revision(),
            "exact_command": exact_command,
        },
    )
    if failures:
        raise RuntimeError(
            f"Phase 1 has {len(failures)} technical failures; rerun with "
            "--retry-failures after inspection"
        )


def run_phase2(
    source_path: Path,
    dataset_dir: Path,
    private_dir: Path,
    *,
    workers: int,
    max_attempts: int,
    retry_failures: bool,
    exact_command: str,
) -> None:
    _assert_private_dir(private_dir)
    resources, _summary = _load_and_verify_source(source_path)
    by_source = {row["source_id"]: row for row in resources}
    output_dir = dataset_dir / "provenance/normalisation"
    phase1_path = output_dir / "phase1_mappings.jsonl"
    if not phase1_path.exists():
        raise FileNotFoundError("Phase 1 mappings do not exist")
    schema = read_yaml(GRAMMAR_SCHEMA_PATH)
    backend = read_yaml(MODEL_BACKENDS_PATH)["normalisation"]
    phase1_prompt = read_text(PHASE1_PROMPT_PATH)
    phase2_prompt = read_text(PHASE2_PROMPT_PATH)
    rulebook = read_text(NORMALISATION_RULEBOOK_PATH)
    source_order = [row["source_id"] for row in resources]
    phase1_public = _read_public_normalisation_mappings(
        phase1_path,
        allowed_source_ids=set(source_order),
        schema=schema,
    )
    if set(phase1_public) != set(source_order):
        raise ValueError("Phase 1 must classify all source descriptors first")
    phase1_by_id: dict[str, dict[str, Any]] = {}
    for resource in resources:
        source_id = resource["source_id"]
        recovered = _recover_phase1(
            resource,
            private_dir / "normalisation/phase1" / source_id,
            schema,
            phase1_prompt=phase1_prompt,
            rulebook=rulebook,
            backend=backend,
        )
        if recovered is None:
            raise ValueError(f"Phase-1 mapping lacks private evidence: {source_id}")
        _verify_public_normalisation_mapping(
            phase1_public[source_id], recovered, source_id
        )
        phase1_by_id[source_id] = recovered
    phase1 = [phase1_by_id[source_id] for source_id in source_order]

    eligible_ids = [
        row["source_id"]
        for row in phase1
        if row["result"] == "partial"
        and row["phase2_eligible"]
        and by_source[row["source_id"]]["examples"]
    ]
    cohort = {
        "cohort_id": "full_v1_phase2_eligible",
        "source_ids": eligible_ids,
        "source_ids_sha256": _json_sha256(eligible_ids),
        "eligibility_rule": (
            "Phase-1 result is partial, phase2_eligible is nonempty, and source "
            "examples are present."
        ),
        "frozen_before_phase2_calls": True,
    }
    cohort_path = output_dir / "phase2_cohort.json"
    if cohort_path.exists() and _read_json(cohort_path) != cohort:
        raise ValueError("frozen Phase-2 cohort changed")
    write_json(cohort_path, cohort)

    mappings_path = output_dir / "phase2_mappings.jsonl"
    attempts_path = output_dir / "phase2_attempts.jsonl"
    public_mappings = _read_public_normalisation_mappings(
        mappings_path,
        allowed_source_ids=set(eligible_ids),
        schema=schema,
        allow_resolved_eligibility=True,
    )
    attempts = _read_public_normalisation_attempts(
        attempts_path, allowed_source_ids=set(eligible_ids)
    )
    mappings: dict[str, dict[str, Any]] = {}
    for source_id in eligible_ids:
        recovered = _recover_phase2(
            by_source[source_id],
            phase1_by_id[source_id],
            private_dir / "normalisation/phase2" / source_id,
            schema,
            phase2_prompt=phase2_prompt,
            rulebook=rulebook,
            backend=backend,
        )
        if source_id in public_mappings:
            if recovered is None:
                raise ValueError(
                    f"public Phase-2 mapping lacks private evidence: {source_id}"
                )
            _verify_public_normalisation_mapping(
                public_mappings[source_id], recovered, source_id
            )
        if recovered is not None:
            mappings[source_id] = recovered
            if source_id not in attempts:
                attempts[source_id] = {
                    "source_id": source_id,
                    "status": "success_recovered_private_evidence",
                    "attempt_count": _existing_attempt_count(
                        private_dir / "normalisation/phase2" / source_id
                    ),
                    "runtime_seconds": None,
                    "errors": [],
                }
    _write_public_normalisation_mappings(mappings_path, mappings, eligible_ids)
    _write_public_normalisation_attempts(attempts_path, attempts, eligible_ids)

    tasks = [
        source_id
        for source_id in eligible_ids
        if source_id not in mappings
        and (
            retry_failures
            or attempts.get(source_id, {}).get("status") != "technical_failure"
        )
    ]

    def execute(source_id: str) -> dict[str, Any]:
        result = _call_with_technical_retries(
            lambda evidence_dir: normalise_phase2_record(
                by_source[source_id],
                phase1_by_id[source_id],
                phase2_prompt,
                rulebook,
                schema,
                model=backend["model"],
                reasoning_effort=backend["reasoning_effort"],
                model_call=audited_model_call,
                evidence_dir=evidence_dir,
            ),
            private_dir / "normalisation/phase2" / source_id,
            max_attempts=max_attempts,
        )
        return {"source_id": source_id, **result}

    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(execute, source_id): source_id for source_id in tasks}
        for future in as_completed(futures):
            result = future.result()
            source_id = result["source_id"]
            returned = result.pop("mapping")
            if returned is not None:
                recovered = _recover_phase2(
                    by_source[source_id],
                    phase1_by_id[source_id],
                    private_dir / "normalisation/phase2" / source_id,
                    schema,
                    phase2_prompt=phase2_prompt,
                    rulebook=rulebook,
                    backend=backend,
                )
                if recovered is None or recovered != returned:
                    raise ValueError(
                        f"Phase-2 return differs from private evidence: {source_id}"
                    )
                mappings[source_id] = recovered
            attempts[source_id] = _public_normalisation_attempt(result)
            _write_public_normalisation_mappings(
                mappings_path, mappings, eligible_ids
            )
            _write_public_normalisation_attempts(
                attempts_path, attempts, eligible_ids
            )
            completed += 1
            if completed % 10 == 0 or completed == len(tasks):
                print(
                    f"Phase 2 terminal descriptors: {completed}/{len(tasks)}; "
                    f"valid total={len(mappings)}/{len(eligible_ids)}",
                    flush=True,
                )

    failures = sorted(set(eligible_ids) - set(mappings))
    final = [mappings.get(row["source_id"], row) for row in phase1]
    write_jsonl(
        output_dir / "final_mappings.jsonl",
        [_public_normalisation_mapping(mapping) for mapping in final],
    )
    write_json(
        output_dir / "summary.json",
        {
            "dataset_id": DATASET_ID,
            "source_descriptors": len(resources),
            "phase2_eligible": len(eligible_ids),
            "phase2_valid": len(mappings),
            "phase2_technical_failure_source_ids": failures,
            "phase2_resolved_to_complete": sum(
                phase1_by_id[source_id]["result"] != "complete"
                and mappings[source_id]["result"] == "complete"
                for source_id in mappings
            ),
            "final_result_counts": dict(
                sorted(Counter(row["result"] for row in final).items())
            ),
            "models": backend,
            "max_technical_attempts": max_attempts,
            "code_revision_at_stage_start": _git_revision(),
            "exact_command": exact_command,
        },
    )
    if failures:
        raise RuntimeError(
            f"Phase 2 has {len(failures)} technical failures; rerun with "
            "--retry-failures after inspection"
        )


def canonicalise_full(dataset_dir: Path, exact_command: str) -> None:
    mappings_path = dataset_dir / "provenance/normalisation/final_mappings.jsonl"
    if not mappings_path.exists():
        raise FileNotFoundError("final normalisation mappings do not exist")
    mappings = read_jsonl(mappings_path)
    if len(mappings) != EXPECTED_SOURCE_ROWS:
        raise ValueError("canonicalisation requires all 1,222 source dispositions")
    schema = read_yaml(GRAMMAR_SCHEMA_PATH)
    for mapping in mappings:
        _validate_mapping(
            mapping,
            mapping["source_id"],
            schema,
            allow_resolved_eligibility=True,
        )
    cells = stable_canonicalise(mappings, schema)
    relations = source_cell_relations(mappings, cells, schema)
    write_jsonl(dataset_dir / "grammar/cells.jsonl", cells)
    write_jsonl(dataset_dir / "grammar/source_cell_relations.jsonl", relations)
    value_support = {
        dimension: dict(
            sorted(Counter(row["features"][dimension] for row in cells).items())
        )
        for dimension in schema["dimension_order"]
    }
    write_json(
        dataset_dir / "grammar/inventory_audit.json",
        {
            "dataset_id": DATASET_ID,
            "declared_scope": schema["description"],
            "source_dispositions": dict(
                sorted(Counter(row["result"] for row in mappings).items())
            ),
            "complete_source_descriptors": sum(
                row["result"] == "complete" for row in mappings
            ),
            "canonical_cells": len(cells),
            "source_cell_relations": len(relations),
            "canonical_value_support": value_support,
            "schema_id": schema["schema_id"],
            "schema_path": str(GRAMMAR_SCHEMA_PATH.relative_to(ROOT)),
            "stable_cell_id_method": "sha256(canonical feature JSON), first 16 hex",
            "code_revision_at_stage_start": _git_revision(),
            "exact_command": exact_command,
        },
    )


def construct_k_star(dataset_dir: Path, exact_command: str) -> None:
    cells = read_jsonl(dataset_dir / "grammar/cells.jsonl")
    schema = read_yaml(GRAMMAR_SCHEMA_PATH)
    design = read_yaml(GENERATOR_DESIGN_PATH)
    declaration = read_yaml(GENERATOR_DECLARATION_PATH)
    inventory = construct_generator_kcs(cells, schema, design, declaration)
    write_jsonl(dataset_dir / "kcs.jsonl", inventory["kcs"])
    write_json(
        dataset_dir / "provenance/kcs/construction.json",
        {
            **{key: value for key, value in inventory.items() if key != "kcs"},
            "design_path": str(GENERATOR_DESIGN_PATH.relative_to(ROOT)),
            "language_declaration_path": str(
                GENERATOR_DECLARATION_PATH.relative_to(ROOT)
            ),
            "code_revision_at_stage_start": _git_revision(),
            "exact_command": exact_command,
        },
    )


def _require_k_star_ordering_gate(dataset_dir: Path) -> None:
    """Require K* construction without opening or passing KC contents."""

    required = [
        dataset_dir / "kcs.jsonl",
        dataset_dir / "provenance/kcs/construction.json",
    ]
    missing = [path for path in required if not path.is_file() or path.stat().st_size == 0]
    if missing:
        raise FileNotFoundError(
            "item generation requires frozen K* and its construction provenance: "
            + ", ".join(str(path) for path in missing)
        )


def _freeze_public_jsonl(path: Path, rows: list[dict[str, Any]], label: str) -> None:
    if path.exists():
        if read_jsonl(path) != rows:
            raise ValueError(f"frozen {label} changed")
        return
    write_jsonl(path, rows)


def _freeze_public_json(path: Path, value: dict[str, Any], label: str) -> None:
    if path.exists():
        if _read_json(path) != value:
            raise ValueError(f"frozen {label} changed")
        return
    write_json(path, value)


def _unique_rows(
    path: Path, id_field: str
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    rows = read_jsonl(path) if path.exists() else []
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        identifier = row.get(id_field)
        if not isinstance(identifier, str) or not identifier:
            raise ValueError(f"checkpoint row lacks {id_field}: {path}")
        if identifier in by_id:
            raise ValueError(f"duplicate {id_field} in checkpoint: {identifier}")
        by_id[identifier] = row
    return rows, by_id


def _write_item_checkpoint(
    path: Path,
    rows: dict[str, dict[str, Any]],
    order: list[str],
) -> None:
    write_jsonl(path, [rows[identifier] for identifier in order if identifier in rows])


def _generation_calls(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prompt = read_text(GENERATION_PROMPT_PATH)
    rulebook = read_text(GENERATION_RULEBOOK_PATH)
    design = read_yaml(GENERATION_DESIGN_PATH)
    item_format = read_yaml(ITEM_FORMAT_PATH)
    backend = read_yaml(MODEL_BACKENDS_PATH)["generation"]
    return [
        build_generation_call(
            cell,
            prompt,
            rulebook,
            design,
            item_format,
            candidate_index=index,
            model=backend["model"],
            reasoning_effort=backend["reasoning_effort"],
        )
        for cell in sorted(cells, key=lambda row: row["cell_id"])
        for index in range(1, 4)
    ]


def _public_generation_plan(
    calls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": call["candidate_id"],
            "cell_id": call["cell_id"],
            "candidate_index": call["candidate_index"],
            "input_sha256": call["input_sha256"],
            "model": call["model"],
            "reasoning_effort": call["reasoning_effort"],
        }
        for call in calls
    ]


def _evidence_context_matches(
    call: dict[str, Any], attempt_dir: Path, stage: str
) -> bool:
    required = {
        "input": attempt_dir / "input.json",
        "prompt": attempt_dir / "rendered_prompt.txt",
        "settings": attempt_dir / "model_settings.json",
        "parsed": attempt_dir / "parsed_result.json",
    }
    if not all(path.is_file() for path in required.values()):
        return False
    try:
        model_input = _read_json(required["input"])
        rendered_prompt = required["prompt"].read_text(encoding="utf-8")
        settings = _read_json(required["settings"])
        _read_json(required["parsed"])
    except (OSError, UnicodeError, ValueError):
        return False
    return (
        model_input == call["model_input"]
        and rendered_prompt == call["rendered_prompt"]
        and settings.get("model") == call["model"]
        and settings.get("reasoning_effort") == call["reasoning_effort"]
        and settings.get("stage") == stage
        and settings.get("call_key") == call["candidate_id"]
    )


def _attempt_number(attempt_dir: Path) -> int:
    try:
        return int(attempt_dir.name.rsplit("-", 1)[1])
    except (IndexError, ValueError) as error:
        raise ValueError(f"invalid immutable attempt directory: {attempt_dir}") from error


def _recover_generation_evidence(
    call: dict[str, Any], evidence_base: Path
) -> tuple[dict[str, Any], int] | None:
    for parsed_path in sorted(evidence_base.glob("attempt-*/parsed_result.json")):
        attempt_dir = parsed_path.parent
        if not _evidence_context_matches(call, attempt_dir, "generation"):
            continue
        try:
            candidate = recover_generated_candidate(_read_json(parsed_path), call)
        except (KeyError, OSError, TypeError, UnicodeError, ValueError):
            continue
        return candidate, _attempt_number(attempt_dir)
    return None


def _recover_campaign_generation_evidence(
    call: dict[str, Any], evidence_base: Path
) -> tuple[dict[str, Any], int] | None:
    """Recover only evidence matching a frozen post-N=3 campaign call."""

    for parsed_path in sorted(evidence_base.glob("attempt-*/parsed_result.json")):
        attempt_dir = parsed_path.parent
        if not _evidence_context_matches(call, attempt_dir, "generation"):
            continue
        try:
            candidate = recover_campaign_candidate(_read_json(parsed_path), call)
        except (KeyError, OSError, TypeError, UnicodeError, ValueError):
            continue
        return candidate, _attempt_number(attempt_dir)
    return None


def _recover_validation_evidence(
    call: dict[str, Any], evidence_base: Path
) -> tuple[dict[str, Any], int] | None:
    for parsed_path in sorted(evidence_base.glob("attempt-*/parsed_result.json")):
        attempt_dir = parsed_path.parent
        if not _evidence_context_matches(call, attempt_dir, "validation"):
            continue
        try:
            judgment = recover_validator_judgment(_read_json(parsed_path), call)
        except (KeyError, OSError, TypeError, UnicodeError, ValueError):
            continue
        return judgment, _attempt_number(attempt_dir)
    return None


def _public_attempt(
    call: dict[str, Any], result: dict[str, Any], *, recovered: bool
) -> dict[str, Any]:
    return {
        "candidate_id": call["candidate_id"],
        "input_sha256": call["input_sha256"],
        "status": result["status"],
        "attempt_count": result["attempt_count"],
        "runtime_seconds": result.get("runtime_seconds"),
        "error_types": [row["error_type"] for row in result.get("errors", [])],
        "recovered_from_private_evidence": recovered,
    }


def _validate_attempt_rows(
    attempts: dict[str, dict[str, Any]], calls: list[dict[str, Any]]
) -> None:
    expected = {call["candidate_id"]: call["input_sha256"] for call in calls}
    for candidate_id, row in attempts.items():
        if candidate_id not in expected:
            raise ValueError(f"attempt is outside the frozen item plan: {candidate_id}")
        if row.get("input_sha256") != expected[candidate_id]:
            raise ValueError(f"attempt checkpoint input drift: {candidate_id}")


def generate_items_full(
    dataset_dir: Path,
    private_dir: Path,
    *,
    workers: int,
    max_attempts: int,
    retry_failures: bool,
    exact_command: str,
    model_call: Callable[..., dict[str, Any]] = audited_model_call,
) -> None:
    """Generate the fixed N=3 candidates after, but without reading, K*."""

    _assert_private_dir(private_dir)
    _require_k_star_ordering_gate(dataset_dir)
    cells_path = dataset_dir / "grammar/cells.jsonl"
    if not cells_path.exists():
        raise FileNotFoundError("canonical GrammarCells do not exist")
    cells = read_jsonl(cells_path)
    if not cells:
        raise ValueError("item generation requires at least one canonical GrammarCell")
    calls = _generation_calls(cells)
    order = [call["candidate_id"] for call in calls]
    provenance_dir = dataset_dir / "provenance/items"
    plan_path = provenance_dir / "generation_plan.jsonl"
    _freeze_public_jsonl(plan_path, _public_generation_plan(calls), "generation plan")

    candidates_path = provenance_dir / "candidates.jsonl"
    existing_candidates = read_jsonl(candidates_path) if candidates_path.exists() else []
    merged_candidates = merge_completed_candidate_rows(existing_candidates, [], calls)
    candidates = {row["item_id"]: row for row in merged_candidates}
    existing_audit_path = provenance_dir / "generation_audit.json"
    if existing_audit_path.exists():
        existing_audit = _read_json(existing_audit_path)
        if (
            existing_audit.get("status") == "PASS"
            and existing_audit.get("candidate_checkpoint_sha256")
            != _json_sha256(merged_candidates)
        ):
            raise ValueError("completed candidate checkpoint changed after generation")
    attempts_path = provenance_dir / "generation_attempts.jsonl"
    _attempt_rows, attempts = _unique_rows(attempts_path, "candidate_id")
    _validate_attempt_rows(attempts, calls)

    for call in calls:
        candidate_id = call["candidate_id"]
        if candidate_id in candidates:
            recovered = _recover_generation_evidence(
                call, private_dir / "items/generation" / candidate_id
            )
            if recovered is not None and recovered[0] != candidates[candidate_id]:
                raise ValueError(
                    f"public candidate differs from immutable private evidence: "
                    f"{candidate_id}"
                )
            if candidate_id not in attempts:
                attempts[candidate_id] = _public_attempt(
                    call,
                    {
                        "status": "success",
                        "attempt_count": recovered[1] if recovered is not None else 0,
                        "runtime_seconds": None,
                        "errors": [],
                    },
                    recovered=recovered is not None,
                )
            continue
        recovered = _recover_generation_evidence(
            call, private_dir / "items/generation" / candidate_id
        )
        if recovered is None:
            continue
        candidate, attempt_count = recovered
        merged_candidates = merge_completed_candidate_rows(
            list(candidates.values()), [candidate], calls
        )
        candidates = {row["item_id"]: row for row in merged_candidates}
        attempts[candidate_id] = _public_attempt(
            call,
            {
                "status": "success",
                "attempt_count": attempt_count,
                "runtime_seconds": None,
                "errors": [],
            },
            recovered=True,
        )
    _write_item_checkpoint(candidates_path, candidates, order)
    _write_item_checkpoint(attempts_path, attempts, order)

    tasks = [
        call
        for call in calls
        if call["candidate_id"] not in candidates
        and (
            retry_failures
            or attempts.get(call["candidate_id"], {}).get("status")
            != "technical_failure"
        )
    ]

    def execute(call: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        result = _call_with_technical_retries(
            lambda evidence_dir: generate_one_candidate(
                call, model_call=model_call, evidence_dir=evidence_dir
            ),
            private_dir / "items/generation" / call["candidate_id"],
            max_attempts=max_attempts,
        )
        return call, result

    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(execute, call): call for call in tasks}
        for future in as_completed(futures):
            call, result = future.result()
            candidate_id = call["candidate_id"]
            candidate = result.pop("mapping")
            if candidate is not None:
                merged_candidates = merge_completed_candidate_rows(
                    list(candidates.values()), [candidate], calls
                )
                candidates = {row["item_id"]: row for row in merged_candidates}
            attempts[candidate_id] = _public_attempt(call, result, recovered=False)
            _write_item_checkpoint(candidates_path, candidates, order)
            _write_item_checkpoint(attempts_path, attempts, order)
            completed += 1
            if completed % 10 == 0 or completed == len(tasks):
                print(
                    f"item generation terminal calls: {completed}/{len(tasks)}; "
                    f"valid total={len(candidates)}/{len(calls)}",
                    flush=True,
                )

    candidate_rows = [candidates[item_id] for item_id in order if item_id in candidates]
    failures = sorted(set(order) - set(candidates))
    audit = candidate_audit_summary(cells, candidate_rows)
    audit.update(
        {
            "dataset_id": DATASET_ID,
            "status": "PASS" if not failures else "FAIL",
            "technical_failure_candidate_ids": failures,
            "candidate_checkpoint_sha256": _json_sha256(candidate_rows),
            "models": read_yaml(MODEL_BACKENDS_PATH)["generation"],
            "ordering_gate": {
                "kcs_artifact_existed": True,
                "kc_construction_provenance_existed": True,
                "kc_contents_read": False,
            },
            "max_technical_attempts": max_attempts,
            "code_revision_at_stage_start": _git_revision(),
            "exact_command": exact_command,
        }
    )
    write_json(provenance_dir / "generation_audit.json", audit)
    if failures:
        raise RuntimeError(
            f"item generation has {len(failures)} terminal technical failures; "
            "inspect private evidence before an explicit retry"
        )


def _load_complete_generation(
    dataset_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    _require_k_star_ordering_gate(dataset_dir)
    cells = read_jsonl(dataset_dir / "grammar/cells.jsonl")
    calls = _generation_calls(cells)
    plan_path = dataset_dir / "provenance/items/generation_plan.jsonl"
    if not plan_path.exists():
        raise FileNotFoundError("frozen item-generation plan does not exist")
    if read_jsonl(plan_path) != _public_generation_plan(calls):
        raise ValueError("frozen generation plan changed")
    candidates_path = dataset_dir / "provenance/items/candidates.jsonl"
    if not candidates_path.exists():
        raise FileNotFoundError("raw candidate checkpoint does not exist")
    candidates = merge_completed_candidate_rows(read_jsonl(candidates_path), [], calls)
    if len(candidates) != len(calls):
        raise ValueError("generation must complete every frozen N=3 position first")
    audit_path = dataset_dir / "provenance/items/generation_audit.json"
    if not audit_path.exists():
        raise FileNotFoundError("successful item-generation audit does not exist")
    audit = _read_json(audit_path)
    if audit.get("status") != "PASS" or audit.get(
        "candidate_checkpoint_sha256"
    ) != _json_sha256(candidates):
        raise ValueError("item-generation audit does not match the complete checkpoint")
    return cells, calls, candidates


def _validation_calls(
    cells: list[dict[str, Any]], candidates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    cells_by_id = {cell["cell_id"]: cell for cell in cells}
    prompt = read_text(VALIDATION_PROMPT_PATH)
    criteria = read_yaml(VALIDATION_CRITERIA_PATH)
    backend = read_yaml(MODEL_BACKENDS_PATH)["validation"]
    calls = []
    for candidate in candidates:
        cell_id = candidate["cell_id"]
        if cell_id not in cells_by_id:
            raise ValueError(f"candidate refers to unknown GrammarCell: {cell_id}")
        calls.append(
            build_validation_call(
                candidate,
                cells_by_id[cell_id],
                prompt,
                criteria,
                model=backend["model"],
                reasoning_effort=backend["reasoning_effort"],
            )
        )
    return calls


def _public_validation_plan(
    calls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": call["candidate_id"],
            "cell_id": call["cell_id"],
            "validation_item_id": call["model_input"]["visible_item"]["item_id"],
            "input_sha256": call["input_sha256"],
            "model": call["model"],
            "reasoning_effort": call["reasoning_effort"],
            "call_required": call["call_required"],
            "deterministic_rejection_checks": sorted(
                name
                for name, result in call["deterministic_checks"].items()
                if not result["passed"]
            ),
        }
        for call in calls
    ]


def validate_items_full(
    dataset_dir: Path,
    private_dir: Path,
    *,
    workers: int,
    max_attempts: int,
    retry_failures: bool,
    exact_command: str,
    model_call: Callable[..., dict[str, Any]] = audited_model_call,
) -> None:
    """Run deterministic checks and independent validation over fixed candidates."""

    _assert_private_dir(private_dir)
    cells, _generation_call_rows, candidates = _load_complete_generation(dataset_dir)
    calls = _validation_calls(cells, candidates)
    order = [call["candidate_id"] for call in calls]
    provenance_dir = dataset_dir / "provenance/items"
    plan_path = provenance_dir / "validation_plan.jsonl"
    _freeze_public_jsonl(plan_path, _public_validation_plan(calls), "validation plan")

    judgments_path = provenance_dir / "validation_judgments.jsonl"
    existing = read_jsonl(judgments_path) if judgments_path.exists() else []
    merged = merge_completed_judgment_rows(existing, [], calls)
    judgments = {row["item_id"]: row for row in merged}
    attempts_path = provenance_dir / "validation_attempts.jsonl"
    _attempt_rows, attempts = _unique_rows(attempts_path, "candidate_id")
    _validate_attempt_rows(attempts, calls)

    for call in calls:
        candidate_id = call["candidate_id"]
        if candidate_id in judgments:
            recovered = (
                _recover_validation_evidence(
                    call, private_dir / "items/validation" / candidate_id
                )
                if call["call_required"]
                else None
            )
            if recovered is not None and recovered[0] != judgments[candidate_id]:
                raise ValueError(
                    f"public judgment differs from immutable private evidence: "
                    f"{candidate_id}"
                )
            if candidate_id not in attempts:
                attempts[candidate_id] = {
                    "candidate_id": candidate_id,
                    "input_sha256": call["input_sha256"],
                    "status": (
                        "deterministic_rejection"
                        if not call["call_required"]
                        else "success"
                    ),
                    "attempt_count": recovered[1] if recovered is not None else 0,
                    "runtime_seconds": None,
                    "error_types": [],
                    "recovered_from_private_evidence": recovered is not None,
                }
            continue
        if not call["call_required"]:
            judgment = reconstruct_validation_judgment(call)
            merged = merge_completed_judgment_rows(
                list(judgments.values()), [judgment], calls
            )
            judgments = {row["item_id"]: row for row in merged}
            attempts[candidate_id] = {
                "candidate_id": candidate_id,
                "input_sha256": call["input_sha256"],
                "status": "deterministic_rejection",
                "attempt_count": 0,
                "runtime_seconds": 0.0,
                "error_types": [],
                "recovered_from_private_evidence": False,
            }
            continue
        recovered = _recover_validation_evidence(
            call, private_dir / "items/validation" / candidate_id
        )
        if recovered is None:
            continue
        judgment, attempt_count = recovered
        merged = merge_completed_judgment_rows(
            list(judgments.values()), [judgment], calls
        )
        judgments = {row["item_id"]: row for row in merged}
        attempts[candidate_id] = _public_attempt(
            call,
            {
                "status": "success",
                "attempt_count": attempt_count,
                "runtime_seconds": None,
                "errors": [],
            },
            recovered=True,
        )
    _write_item_checkpoint(judgments_path, judgments, order)
    _write_item_checkpoint(attempts_path, attempts, order)

    tasks = [
        call
        for call in calls
        if call["candidate_id"] not in judgments
        and call["call_required"]
        and (
            retry_failures
            or attempts.get(call["candidate_id"], {}).get("status")
            != "technical_failure"
        )
    ]

    def execute(call: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        result = _call_with_technical_retries(
            lambda evidence_dir: validate_one_candidate(
                call, model_call=model_call, evidence_dir=evidence_dir
            ),
            private_dir / "items/validation" / call["candidate_id"],
            max_attempts=max_attempts,
        )
        return call, result

    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(execute, call): call for call in tasks}
        for future in as_completed(futures):
            call, result = future.result()
            candidate_id = call["candidate_id"]
            judgment = result.pop("mapping")
            if judgment is not None:
                merged = merge_completed_judgment_rows(
                    list(judgments.values()), [judgment], calls
                )
                judgments = {row["item_id"]: row for row in merged}
            attempts[candidate_id] = _public_attempt(call, result, recovered=False)
            _write_item_checkpoint(judgments_path, judgments, order)
            _write_item_checkpoint(attempts_path, attempts, order)
            completed += 1
            if completed % 10 == 0 or completed == len(tasks):
                print(
                    f"item validation terminal calls: {completed}/{len(tasks)}; "
                    f"complete total={len(judgments)}/{len(calls)}",
                    flush=True,
                )

    judgment_rows = [judgments[item_id] for item_id in order if item_id in judgments]
    failures = sorted(set(order) - set(judgments))
    candidate_by_id = {row["item_id"]: row for row in candidates}
    accepted = [
        candidate_by_id[row["item_id"]]
        for row in judgment_rows
        if row["accepted"]
    ]
    write_jsonl(provenance_dir / "validator_accepted_candidates.jsonl", accepted)
    audit = item_construction_audit(
        cells,
        candidates,
        judgment_rows,
        read_yaml(VALIDATION_CRITERIA_PATH),
    )
    audit.update(
        {
            "dataset_id": DATASET_ID,
            "status": "PASS" if not failures else "FAIL",
            "technical_failure_candidate_ids": failures,
            "judgment_checkpoint_sha256": _json_sha256(judgment_rows),
            "models": read_yaml(MODEL_BACKENDS_PATH)["validation"],
            "max_technical_attempts": max_attempts,
            "code_revision_at_stage_start": _git_revision(),
            "exact_command": exact_command,
        }
    )
    write_json(provenance_dir / "validation_audit.json", audit)
    if failures:
        raise RuntimeError(
            f"item validation has {len(failures)} terminal technical failures; "
            "inspect private evidence before an explicit retry"
        )


def _load_complete_baseline_item_evidence(
    dataset_dir: Path,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Load the immutable N=3 candidates and their complete judgments."""

    cells, _generation_call_rows, candidates = _load_complete_generation(dataset_dir)
    calls = _validation_calls(cells, candidates)
    plan_path = dataset_dir / "provenance/items/validation_plan.jsonl"
    if not plan_path.exists() or read_jsonl(plan_path) != _public_validation_plan(calls):
        raise ValueError("frozen baseline validation plan is missing or changed")
    judgments_path = dataset_dir / "provenance/items/validation_judgments.jsonl"
    if not judgments_path.exists():
        raise FileNotFoundError("baseline validation judgments do not exist")
    judgments = merge_completed_judgment_rows(
        read_jsonl(judgments_path), [], calls
    )
    if len(judgments) != len(candidates):
        raise ValueError("baseline validation must be complete before a campaign")
    audit_path = dataset_dir / "provenance/items/validation_audit.json"
    if not audit_path.exists():
        raise FileNotFoundError("successful baseline validation audit does not exist")
    audit = _read_json(audit_path)
    if audit.get("status") != "PASS" or audit.get(
        "judgment_checkpoint_sha256"
    ) != _json_sha256(judgments):
        raise ValueError("baseline validation audit does not match its checkpoint")
    accepted = [
        candidate
        for candidate in candidates
        if next(
            row for row in judgments if row["item_id"] == candidate["item_id"]
        )["accepted"]
    ]
    accepted_path = (
        dataset_dir / "provenance/items/validator_accepted_candidates.jsonl"
    )
    if not accepted_path.exists() or read_jsonl(accepted_path) != accepted:
        raise ValueError("baseline validator-accepted checkpoint is missing or changed")
    return cells, candidates, judgments


def _campaign_slug(campaign_id: str) -> str:
    if campaign_id == UNCHANGED_RESCUE_ID:
        return "unchanged_rescue"
    if campaign_id == DETERMINACY_INTERVENTION_ID:
        return "determinacy_intervention"
    raise ValueError(f"unknown item campaign: {campaign_id}")


def _campaign_protocol() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    protocol = read_yaml(RESCUE_PROTOCOL_PATH)
    if not isinstance(protocol, dict) or set(protocol) != {
        "protocol_id",
        "campaigns",
        "curation",
    }:
        raise ValueError("full-v1 item-rescue protocol fields changed")
    if protocol.get("protocol_id") != "full_v1_two_campaign_item_rescue_v1":
        raise ValueError("unexpected full-v1 item-rescue protocol ID")
    campaigns = protocol.get("campaigns")
    if not isinstance(campaigns, dict) or set(campaigns) != {
        "unchanged_rescue",
        "determinacy_intervention",
    }:
        raise ValueError("full-v1 item-rescue campaigns changed")
    declarations = {
        UNCHANGED_RESCUE_ID: campaigns["unchanged_rescue"],
        DETERMINACY_INTERVENTION_ID: campaigns["determinacy_intervention"],
    }
    for campaign_id, declaration in declarations.items():
        if not isinstance(declaration, dict) or declaration.get(
            "campaign_id"
        ) != campaign_id:
            raise ValueError(f"invalid item-campaign declaration: {campaign_id}")
    return protocol, declarations


def _accepted_cell_ids(
    candidates: list[dict[str, Any]], judgments: list[dict[str, Any]]
) -> set[str]:
    candidate_by_id = {row["item_id"]: row for row in candidates}
    if len(candidate_by_id) != len(candidates):
        raise ValueError("candidate IDs must be unique when computing coverage")
    accepted: set[str] = set()
    for judgment in judgments:
        if judgment.get("item_id") not in candidate_by_id:
            raise ValueError("judgment refers to an unknown candidate")
        if judgment.get("accepted") is True:
            accepted.add(candidate_by_id[judgment["item_id"]]["cell_id"])
    return accepted


def _determinacy_eligibility(
    cell_ids: list[str],
    candidates: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Audit the preregistered recurring/dominant determinacy trigger."""

    candidate_cell = {row["item_id"]: row["cell_id"] for row in candidates}
    results: dict[str, dict[str, Any]] = {}
    for cell_id in cell_ids:
        rows = [
            row
            for row in judgments
            if candidate_cell.get(row.get("item_id")) == cell_id
        ]
        failure_counts: Counter[str] = Counter()
        model_judgments = 0
        for row in rows:
            if row.get("rejection_stage") == "independent_model_judgment":
                model_judgments += 1
            for name, value in row.get("judgments", {}).items():
                if value.get("passed") is False:
                    failure_counts[name] += 1
        determinacy = failure_counts.get("determinacy", 0)
        other_maximum = max(
            (count for name, count in failure_counts.items() if name != "determinacy"),
            default=0,
        )
        eligible = determinacy >= 2 and determinacy > other_maximum
        results[cell_id] = {
            "prior_terminal_judgments": len(rows),
            "prior_model_judgments": model_judgments,
            "criterion_failure_counts": dict(sorted(failure_counts.items())),
            "determinacy_failures": determinacy,
            "maximum_other_criterion_failures": other_maximum,
            "eligible": eligible,
            "rule": (
                "determinacy failures >= 2 and strictly exceed every other "
                "criterion's failure count"
            ),
        }
    return results


def _prepare_campaign_plan(
    dataset_dir: Path,
    cells: list[dict[str, Any]],
    prior_candidates: list[dict[str, Any]],
    prior_judgments: list[dict[str, Any]],
    campaign_id: str,
) -> dict[str, Any]:
    """Freeze the complete conditional cohort before its first model call."""

    protocol, declarations = _campaign_protocol()
    declaration = declarations[campaign_id]
    all_cell_ids = sorted(cell["cell_id"] for cell in cells)
    accepted = _accepted_cell_ids(prior_candidates, prior_judgments)
    residual = sorted(set(all_cell_ids) - accepted)
    if campaign_id == UNCHANGED_RESCUE_ID:
        eligibility: dict[str, dict[str, Any]] = {}
    else:
        eligibility = _determinacy_eligibility(
            residual, prior_candidates, prior_judgments
        )
        ineligible = sorted(
            cell_id for cell_id, row in eligibility.items() if not row["eligible"]
        )
        if ineligible:
            blocker_path = (
                dataset_dir
                / "provenance/items/campaigns/determinacy_intervention/"
                "eligibility_blocker.json"
            )
            write_json(
                blocker_path,
                {
                    "status": "INELIGIBLE_RESIDUAL_CELLS",
                    "cell_ids": ineligible,
                    "eligibility": eligibility,
                    "model_calls_made": False,
                },
            )
            raise RuntimeError(
                "determinacy intervention blocked: residual cells do not all "
                f"meet the frozen trigger ({len(ineligible)} ineligible)"
            )

    prompt_path = (
        GENERATION_PROMPT_PATH
        if campaign_id == UNCHANGED_RESCUE_ID
        else DETERMINACY_INTERVENTION_PROMPT_PATH
    )
    count = (
        UNCHANGED_RESCUE_CANDIDATES_PER_CELL
        if campaign_id == UNCHANGED_RESCUE_ID
        else DETERMINACY_INTERVENTION_CANDIDATES_PER_CELL
    )
    plan = {
        "dataset_id": DATASET_ID,
        "protocol_id": protocol["protocol_id"],
        "protocol_path": str(RESCUE_PROTOCOL_PATH.relative_to(ROOT)),
        "protocol_sha256": sha256_file(RESCUE_PROTOCOL_PATH),
        "campaign_id": campaign_id,
        "trigger": declaration["trigger"],
        "cell_ids": residual,
        "candidates_per_cell": count,
        "planned_generation_calls": len(residual) * count,
        "prior_candidates": len(prior_candidates),
        "prior_candidates_sha256": _json_sha256(prior_candidates),
        "prior_judgments": len(prior_judgments),
        "prior_judgments_sha256": _json_sha256(prior_judgments),
        "generation_prompt_path": str(prompt_path.relative_to(ROOT)),
        "generation_prompt_sha256": sha256_file(prompt_path),
        "eligibility": eligibility,
        "uses_learner_data": False,
        "uses_q_matrix": False,
        "uses_discovered_kcs": False,
        "stops_after_early_acceptance": False,
    }
    plan_path = (
        dataset_dir
        / "provenance/items/campaigns"
        / _campaign_slug(campaign_id)
        / "plan.json"
    )
    _freeze_public_json(plan_path, plan, f"{campaign_id} cohort plan")
    return plan


def _campaign_generation_calls(
    cells: list[dict[str, Any]], plan: dict[str, Any]
) -> list[dict[str, Any]]:
    _, declarations = _campaign_protocol()
    campaign_id = plan["campaign_id"]
    declaration = declarations[campaign_id]
    cells_by_id = {row["cell_id"]: row for row in cells}
    unknown = set(plan["cell_ids"]) - set(cells_by_id)
    if unknown:
        raise ValueError(f"item-campaign plan contains unknown cells: {sorted(unknown)}")
    prompt_path = (
        GENERATION_PROMPT_PATH
        if campaign_id == UNCHANGED_RESCUE_ID
        else DETERMINACY_INTERVENTION_PROMPT_PATH
    )
    if plan.get("generation_prompt_sha256") != sha256_file(prompt_path):
        raise ValueError("item-campaign generation prompt changed")
    backend = read_yaml(MODEL_BACKENDS_PATH)["generation"]
    design = read_yaml(GENERATION_DESIGN_PATH)
    item_format = read_yaml(ITEM_FORMAT_PATH)
    prompt = read_text(prompt_path)
    rulebook = read_text(GENERATION_RULEBOOK_PATH)
    return [
        build_campaign_generation_call(
            cells_by_id[cell_id],
            prompt,
            rulebook,
            design,
            declaration,
            item_format,
            campaign_index=index,
            model=backend["model"],
            reasoning_effort=backend["reasoning_effort"],
        )
        for cell_id in plan["cell_ids"]
        for index in range(1, int(plan["candidates_per_cell"]) + 1)
    ]


def _public_campaign_generation_plan(
    calls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "campaign_id": call["campaign_id"],
            "candidate_id": call["candidate_id"],
            "cell_id": call["cell_id"],
            "campaign_index": call["campaign_index"],
            "input_sha256": call["input_sha256"],
            "model": call["model"],
            "reasoning_effort": call["reasoning_effort"],
        }
        for call in calls
    ]


def _campaign_generation_audit(
    plan: dict[str, Any], candidates: list[dict[str, Any]]
) -> dict[str, Any]:
    by_cell = Counter(row["cell_id"] for row in candidates)
    expected = int(plan["candidates_per_cell"])
    return {
        "campaign_id": plan["campaign_id"],
        "planned_candidates": plan["planned_generation_calls"],
        "completed_candidates": len(candidates),
        "completion_rate": (
            len(candidates) / plan["planned_generation_calls"]
            if plan["planned_generation_calls"]
            else 1.0
        ),
        "cells": len(plan["cell_ids"]),
        "cells_with_all_candidates": sum(
            by_cell[cell_id] == expected for cell_id in plan["cell_ids"]
        ),
        "zero_candidate_cells": [
            cell_id for cell_id in plan["cell_ids"] if by_cell[cell_id] == 0
        ],
        "by_cell": {
            cell_id: {"completed_candidates": by_cell[cell_id]}
            for cell_id in plan["cell_ids"]
        },
    }


def _run_campaign_generation(
    dataset_dir: Path,
    private_dir: Path,
    cells: list[dict[str, Any]],
    plan: dict[str, Any],
    *,
    workers: int,
    max_attempts: int,
    retry_failures: bool,
    exact_command: str,
    model_call: Callable[..., dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    campaign_id = plan["campaign_id"]
    slug = _campaign_slug(campaign_id)
    public_dir = dataset_dir / "provenance/items/campaigns" / slug
    private_base = private_dir / "items/campaigns" / slug / "generation"
    calls = _campaign_generation_calls(cells, plan)
    order = [call["candidate_id"] for call in calls]
    _freeze_public_jsonl(
        public_dir / "generation_plan.jsonl",
        _public_campaign_generation_plan(calls),
        f"{campaign_id} generation plan",
    )

    candidates_path = public_dir / "candidates.jsonl"
    existing = read_jsonl(candidates_path) if candidates_path.exists() else []
    merged = merge_completed_candidate_rows(existing, [], calls)
    candidates = {row["item_id"]: row for row in merged}
    attempts_path = public_dir / "generation_attempts.jsonl"
    _attempt_rows, attempts = _unique_rows(attempts_path, "candidate_id")
    _validate_attempt_rows(attempts, calls)

    for call in calls:
        candidate_id = call["candidate_id"]
        recovered = _recover_campaign_generation_evidence(
            call, private_base / candidate_id
        )
        if candidate_id in candidates:
            if recovered is not None and recovered[0] != candidates[candidate_id]:
                raise ValueError(
                    "public item-campaign candidate differs from immutable private "
                    f"evidence: {candidate_id}"
                )
            if candidate_id not in attempts:
                attempts[candidate_id] = _public_attempt(
                    call,
                    {
                        "status": "success",
                        "attempt_count": recovered[1] if recovered is not None else 0,
                        "runtime_seconds": None,
                        "errors": [],
                    },
                    recovered=recovered is not None,
                )
            continue
        if recovered is None:
            continue
        candidate, attempt_count = recovered
        merged = merge_completed_candidate_rows(
            list(candidates.values()), [candidate], calls
        )
        candidates = {row["item_id"]: row for row in merged}
        attempts[candidate_id] = _public_attempt(
            call,
            {
                "status": "success",
                "attempt_count": attempt_count,
                "runtime_seconds": None,
                "errors": [],
            },
            recovered=True,
        )
    _write_item_checkpoint(candidates_path, candidates, order)
    _write_item_checkpoint(attempts_path, attempts, order)

    tasks = [
        call
        for call in calls
        if call["candidate_id"] not in candidates
        and (
            retry_failures
            or attempts.get(call["candidate_id"], {}).get("status")
            != "technical_failure"
        )
    ]

    def execute(call: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        result = _call_with_technical_retries(
            lambda evidence_dir: generate_one_campaign_candidate(
                call, model_call=model_call, evidence_dir=evidence_dir
            ),
            private_base / call["candidate_id"],
            max_attempts=max_attempts,
        )
        return call, result

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(execute, call): call for call in tasks}
        for completed, future in enumerate(as_completed(futures), 1):
            call, result = future.result()
            candidate_id = call["candidate_id"]
            candidate = result.pop("mapping")
            if candidate is not None:
                merged = merge_completed_candidate_rows(
                    list(candidates.values()), [candidate], calls
                )
                candidates = {row["item_id"]: row for row in merged}
            attempts[candidate_id] = _public_attempt(call, result, recovered=False)
            _write_item_checkpoint(candidates_path, candidates, order)
            _write_item_checkpoint(attempts_path, attempts, order)
            if completed % 10 == 0 or completed == len(tasks):
                print(
                    f"{slug} generation terminal calls: {completed}/{len(tasks)}; "
                    f"valid total={len(candidates)}/{len(calls)}",
                    flush=True,
                )

    candidate_rows = [candidates[item_id] for item_id in order if item_id in candidates]
    failures = sorted(set(order) - set(candidates))
    audit = _campaign_generation_audit(plan, candidate_rows)
    audit.update(
        {
            "dataset_id": DATASET_ID,
            "status": "PASS" if not failures else "FAIL",
            "technical_failure_candidate_ids": failures,
            "candidate_checkpoint_sha256": _json_sha256(candidate_rows),
            "models": read_yaml(MODEL_BACKENDS_PATH)["generation"],
            "max_technical_attempts": max_attempts,
            "code_revision_at_stage_start": _git_revision(),
            "exact_command": exact_command,
        }
    )
    write_json(public_dir / "generation_audit.json", audit)
    if failures:
        raise RuntimeError(
            f"{slug} generation has {len(failures)} terminal technical failures"
        )
    return calls, candidate_rows


def _run_campaign_validation(
    dataset_dir: Path,
    private_dir: Path,
    cells: list[dict[str, Any]],
    plan: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    workers: int,
    max_attempts: int,
    retry_failures: bool,
    exact_command: str,
    model_call: Callable[..., dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    campaign_id = plan["campaign_id"]
    slug = _campaign_slug(campaign_id)
    public_dir = dataset_dir / "provenance/items/campaigns" / slug
    private_base = private_dir / "items/campaigns" / slug / "validation"
    calls = _validation_calls(cells, candidates)
    order = [call["candidate_id"] for call in calls]
    _freeze_public_jsonl(
        public_dir / "validation_plan.jsonl",
        _public_validation_plan(calls),
        f"{campaign_id} validation plan",
    )
    judgments_path = public_dir / "validation_judgments.jsonl"
    existing = read_jsonl(judgments_path) if judgments_path.exists() else []
    merged = merge_completed_judgment_rows(existing, [], calls)
    judgments = {row["item_id"]: row for row in merged}
    attempts_path = public_dir / "validation_attempts.jsonl"
    _attempt_rows, attempts = _unique_rows(attempts_path, "candidate_id")
    _validate_attempt_rows(attempts, calls)

    for call in calls:
        candidate_id = call["candidate_id"]
        if not call["call_required"]:
            if candidate_id not in judgments:
                judgment = reconstruct_validation_judgment(call)
                merged = merge_completed_judgment_rows(
                    list(judgments.values()), [judgment], calls
                )
                judgments = {row["item_id"]: row for row in merged}
            attempts.setdefault(
                candidate_id,
                {
                    "candidate_id": candidate_id,
                    "input_sha256": call["input_sha256"],
                    "status": "deterministic_rejection",
                    "attempt_count": 0,
                    "runtime_seconds": 0.0,
                    "error_types": [],
                    "recovered_from_private_evidence": False,
                },
            )
            continue
        recovered = _recover_validation_evidence(call, private_base / candidate_id)
        if candidate_id in judgments:
            if recovered is not None and recovered[0] != judgments[candidate_id]:
                raise ValueError(
                    "public item-campaign judgment differs from immutable private "
                    f"evidence: {candidate_id}"
                )
            if candidate_id not in attempts:
                attempts[candidate_id] = _public_attempt(
                    call,
                    {
                        "status": "success",
                        "attempt_count": recovered[1] if recovered is not None else 0,
                        "runtime_seconds": None,
                        "errors": [],
                    },
                    recovered=recovered is not None,
                )
            continue
        if recovered is None:
            continue
        judgment, attempt_count = recovered
        merged = merge_completed_judgment_rows(
            list(judgments.values()), [judgment], calls
        )
        judgments = {row["item_id"]: row for row in merged}
        attempts[candidate_id] = _public_attempt(
            call,
            {
                "status": "success",
                "attempt_count": attempt_count,
                "runtime_seconds": None,
                "errors": [],
            },
            recovered=True,
        )
    _write_item_checkpoint(judgments_path, judgments, order)
    _write_item_checkpoint(attempts_path, attempts, order)

    tasks = [
        call
        for call in calls
        if call["candidate_id"] not in judgments
        and call["call_required"]
        and (
            retry_failures
            or attempts.get(call["candidate_id"], {}).get("status")
            != "technical_failure"
        )
    ]

    def execute(call: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        result = _call_with_technical_retries(
            lambda evidence_dir: validate_one_candidate(
                call, model_call=model_call, evidence_dir=evidence_dir
            ),
            private_base / call["candidate_id"],
            max_attempts=max_attempts,
        )
        return call, result

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(execute, call): call for call in tasks}
        for completed, future in enumerate(as_completed(futures), 1):
            call, result = future.result()
            candidate_id = call["candidate_id"]
            judgment = result.pop("mapping")
            if judgment is not None:
                merged = merge_completed_judgment_rows(
                    list(judgments.values()), [judgment], calls
                )
                judgments = {row["item_id"]: row for row in merged}
            attempts[candidate_id] = _public_attempt(call, result, recovered=False)
            _write_item_checkpoint(judgments_path, judgments, order)
            _write_item_checkpoint(attempts_path, attempts, order)
            if completed % 10 == 0 or completed == len(tasks):
                print(
                    f"{slug} validation terminal calls: {completed}/{len(tasks)}; "
                    f"complete total={len(judgments)}/{len(calls)}",
                    flush=True,
                )

    judgment_rows = [judgments[item_id] for item_id in order if item_id in judgments]
    failures = sorted(set(order) - set(judgments))
    cohort_ids = set(plan["cell_ids"])
    cohort_cells = [cell for cell in cells if cell["cell_id"] in cohort_ids]
    audit = validation_audit_summary(
        cohort_cells,
        candidates,
        judgment_rows,
        read_yaml(VALIDATION_CRITERIA_PATH),
    )
    accepted = [
        candidate
        for candidate in candidates
        if judgments.get(candidate["item_id"], {}).get("accepted") is True
    ]
    audit.update(
        {
            "dataset_id": DATASET_ID,
            "campaign_id": campaign_id,
            "status": "PASS" if not failures else "FAIL",
            "technical_failure_candidate_ids": failures,
            "judgment_checkpoint_sha256": _json_sha256(judgment_rows),
            "models": read_yaml(MODEL_BACKENDS_PATH)["validation"],
            "max_technical_attempts": max_attempts,
            "code_revision_at_stage_start": _git_revision(),
            "exact_command": exact_command,
        }
    )
    write_jsonl(public_dir / "validator_accepted_candidates.jsonl", accepted)
    write_json(public_dir / "validation_audit.json", audit)
    if failures:
        raise RuntimeError(
            f"{slug} validation has {len(failures)} terminal technical failures"
        )
    return judgment_rows, accepted


def _load_complete_campaign(
    dataset_dir: Path,
    cells: list[dict[str, Any]],
    campaign_id: str,
    prior_candidates: list[dict[str, Any]],
    prior_judgments: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Reload a campaign while revalidating its frozen upstream boundary."""

    slug = _campaign_slug(campaign_id)
    public_dir = dataset_dir / "provenance/items/campaigns" / slug
    plan_path = public_dir / "plan.json"
    if not plan_path.exists():
        raise FileNotFoundError(f"{slug} plan does not exist")
    plan = _read_json(plan_path)
    if plan.get("prior_candidates_sha256") != _json_sha256(
        prior_candidates
    ) or plan.get("prior_judgments_sha256") != _json_sha256(prior_judgments):
        raise ValueError(f"{slug} upstream item evidence changed")
    calls = _campaign_generation_calls(cells, plan)
    if read_jsonl(public_dir / "generation_plan.jsonl") != (
        _public_campaign_generation_plan(calls)
    ):
        raise ValueError(f"{slug} generation plan changed")
    candidates = merge_completed_candidate_rows(
        read_jsonl(public_dir / "candidates.jsonl"), [], calls
    )
    generation_audit = _read_json(public_dir / "generation_audit.json")
    if len(candidates) != len(calls) or generation_audit.get("status") != "PASS":
        raise ValueError(f"{slug} generation is incomplete")
    if generation_audit.get("candidate_checkpoint_sha256") != _json_sha256(
        candidates
    ):
        raise ValueError(f"{slug} candidate checkpoint changed")

    validation_calls = _validation_calls(cells, candidates)
    if read_jsonl(public_dir / "validation_plan.jsonl") != _public_validation_plan(
        validation_calls
    ):
        raise ValueError(f"{slug} validation plan changed")
    judgments = merge_completed_judgment_rows(
        read_jsonl(public_dir / "validation_judgments.jsonl"), [], validation_calls
    )
    validation_audit = _read_json(public_dir / "validation_audit.json")
    if len(judgments) != len(candidates) or validation_audit.get("status") != "PASS":
        raise ValueError(f"{slug} validation is incomplete")
    if validation_audit.get("judgment_checkpoint_sha256") != _json_sha256(
        judgments
    ):
        raise ValueError(f"{slug} judgment checkpoint changed")
    return candidates, judgments


def run_item_campaign(
    dataset_dir: Path,
    private_dir: Path,
    campaign_id: str,
    *,
    workers: int,
    max_attempts: int,
    retry_failures: bool,
    exact_command: str,
    model_call: Callable[..., dict[str, Any]] = audited_model_call,
) -> None:
    """Run one frozen post-N=3 generation-and-validation campaign."""

    _assert_private_dir(private_dir)
    cells, baseline_candidates, baseline_judgments = (
        _load_complete_baseline_item_evidence(dataset_dir)
    )
    prior_candidates = list(baseline_candidates)
    prior_judgments = list(baseline_judgments)
    if campaign_id == DETERMINACY_INTERVENTION_ID:
        rescue_candidates, rescue_judgments = _load_complete_campaign(
            dataset_dir,
            cells,
            UNCHANGED_RESCUE_ID,
            baseline_candidates,
            baseline_judgments,
        )
        prior_candidates = sorted(
            [*prior_candidates, *rescue_candidates], key=lambda row: row["item_id"]
        )
        prior_judgments = sorted(
            [*prior_judgments, *rescue_judgments], key=lambda row: row["item_id"]
        )
    plan = _prepare_campaign_plan(
        dataset_dir,
        cells,
        prior_candidates,
        prior_judgments,
        campaign_id,
    )
    _generation_calls_rows, candidates = _run_campaign_generation(
        dataset_dir,
        private_dir,
        cells,
        plan,
        workers=workers,
        max_attempts=max_attempts,
        retry_failures=retry_failures,
        exact_command=exact_command,
        model_call=model_call,
    )
    judgments, accepted = _run_campaign_validation(
        dataset_dir,
        private_dir,
        cells,
        plan,
        candidates,
        workers=workers,
        max_attempts=max_attempts,
        retry_failures=retry_failures,
        exact_command=exact_command,
        model_call=model_call,
    )
    accepted_before = _accepted_cell_ids(prior_candidates, prior_judgments)
    accepted_after = accepted_before | {row["cell_id"] for row in accepted}
    write_json(
        dataset_dir
        / "provenance/items/campaigns"
        / _campaign_slug(campaign_id)
        / "coverage_effect.json",
        {
            "dataset_id": DATASET_ID,
            "campaign_id": campaign_id,
            "cohort_cells": len(plan["cell_ids"]),
            "candidates": len(candidates),
            "judgments": len(judgments),
            "accepted_candidates": len(accepted),
            "covered_cells_before": len(accepted_before),
            "newly_covered_cell_ids": sorted(accepted_after - accepted_before),
            "newly_covered_cells": len(accepted_after - accepted_before),
            "covered_cells_after": len(accepted_after),
            "remaining_zero_coverage_cell_ids": sorted(
                set(cell["cell_id"] for cell in cells) - accepted_after
            ),
        },
    )


def _packaging_correction_config() -> dict[str, Any]:
    if sha256_file(PACKAGING_CORRECTIONS_PATH) != (
        EXPECTED_PACKAGING_CORRECTIONS_SHA256
    ):
        raise ValueError("full-v1 packaging-correction declaration hash changed")
    config = read_yaml(PACKAGING_CORRECTIONS_PATH)
    if not isinstance(config, dict) or set(config) != {
        "protocol_id",
        "scope",
        "source_campaign",
        "validation",
        "corrections",
    }:
        raise ValueError("full-v1 packaging-correction config fields changed")
    if config.get("protocol_id") != PACKAGING_CORRECTION_ID:
        raise ValueError("unexpected packaging-correction protocol ID")
    if config.get("scope") != "append_only_validator_named_accepted_answers":
        raise ValueError("packaging-correction scope changed")
    if config.get("source_campaign") != DETERMINACY_INTERVENTION_ID:
        raise ValueError("packaging corrections must copy intervention candidates")
    if config.get("validation") != {
        "reuse_baseline_prompt": True,
        "reuse_baseline_criteria": True,
        "independent_and_blinded": True,
    }:
        raise ValueError("packaging corrections must reuse unchanged validation")
    corrections = config.get("corrections")
    if not isinstance(corrections, list) or len(corrections) != 3:
        raise ValueError("full-v1 packaging correction must contain exactly three rows")
    source_ids = [row.get("source_item_id") for row in corrections]
    expected_sources = {
        "determinacy_intervention_gc_019f7fb10012b606_01",
        "determinacy_intervention_gc_04a854582c08aa84_02",
        "determinacy_intervention_gc_bb4f472f992ab76b_01",
    }
    if set(source_ids) != expected_sources or len(source_ids) != len(set(source_ids)):
        raise ValueError("full-v1 packaging-correction source cohort changed")
    expected_additions = {
        "determinacy_intervention_gc_019f7fb10012b606_01": [
            "The children mustn't enter the kitchen."
        ],
        "determinacy_intervention_gc_04a854582c08aa84_02": [
            "Don't touch it.",
            "Do not touch it.",
            "Don't touch that wall.",
            "Do not touch that wall.",
        ],
        "determinacy_intervention_gc_bb4f472f992ab76b_01": [
            "Turn the light off."
        ],
    }
    if {
        row["source_item_id"]: row.get("append_accepted_answers")
        for row in corrections
    } != expected_additions:
        raise ValueError("full-v1 packaging-correction answer additions changed")
    if len({row.get("correction_id") for row in corrections}) != 3:
        raise ValueError("packaging correction IDs must be unique")
    return config


def _load_complete_pre_correction_evidence(
    dataset_dir: Path,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Load all immutable raw item campaigns without accepting corrected rows."""

    cells, baseline_candidates, baseline_judgments = (
        _load_complete_baseline_item_evidence(dataset_dir)
    )
    rescue_candidates, rescue_judgments = _load_complete_campaign(
        dataset_dir,
        cells,
        UNCHANGED_RESCUE_ID,
        baseline_candidates,
        baseline_judgments,
    )
    prior_candidates = sorted(
        [*baseline_candidates, *rescue_candidates], key=lambda row: row["item_id"]
    )
    prior_judgments = sorted(
        [*baseline_judgments, *rescue_judgments], key=lambda row: row["item_id"]
    )
    intervention_candidates, intervention_judgments = _load_complete_campaign(
        dataset_dir,
        cells,
        DETERMINACY_INTERVENTION_ID,
        prior_candidates,
        prior_judgments,
    )
    candidates = sorted(
        [*prior_candidates, *intervention_candidates],
        key=lambda row: row["item_id"],
    )
    judgments = sorted(
        [*prior_judgments, *intervention_judgments],
        key=lambda row: row["item_id"],
    )
    if len({row["item_id"] for row in candidates}) != len(candidates):
        raise ValueError("pre-correction candidate IDs are not unique")
    return cells, candidates, judgments


def _expected_packaging_correction(
    cells: list[dict[str, Any]],
    prior_candidates: list[dict[str, Any]],
    prior_judgments: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    config = _packaging_correction_config()
    config_sha256 = sha256_file(PACKAGING_CORRECTIONS_PATH)
    candidate_by_id = {row["item_id"]: row for row in prior_candidates}
    judgment_by_id = {row["item_id"]: row for row in prior_judgments}
    residual_cells = sorted(
        set(cell["cell_id"] for cell in cells)
        - _accepted_cell_ids(prior_candidates, prior_judgments)
    )
    declared_source_cells: set[str] = set()
    corrected: list[dict[str, Any]] = []
    plan_rows: list[dict[str, Any]] = []
    required_criteria = {
        name
        for name, declaration in read_yaml(VALIDATION_CRITERIA_PATH)[
            "criteria"
        ].items()
        if declaration["required"]
    }
    for declaration in config["corrections"]:
        source_id = declaration["source_item_id"]
        if source_id not in candidate_by_id or source_id not in judgment_by_id:
            raise ValueError(f"packaging correction source evidence missing: {source_id}")
        source = candidate_by_id[source_id]
        judgment = judgment_by_id[source_id]
        if _json_sha256(judgment) != declaration["source_judgment_sha256"]:
            raise ValueError(f"packaging correction source judgment drift: {source_id}")
        failed_required = {
            name
            for name in required_criteria
            if judgment.get("judgments", {}).get(name, {}).get("passed") is False
        }
        if (
            judgment.get("accepted") is not False
            or judgment.get("rejection_stage") != "independent_model_judgment"
            or failed_required != {"determinacy"}
        ):
            raise ValueError(
                "packaging correction source must have determinacy as its sole "
                f"failed required criterion: {source_id}"
            )
        declared_source_cells.add(source["cell_id"])
        row = construct_packaging_corrected_candidate(
            source, declaration, config_sha256=config_sha256
        )
        corrected.append(row)
        plan_rows.append(
            {
                "correction_id": declaration["correction_id"],
                "source_item_id": source_id,
                "corrected_item_id": row["item_id"],
                "cell_id": row["cell_id"],
                "source_candidate_sha256": declaration[
                    "source_candidate_sha256"
                ],
                "source_judgment_sha256": declaration[
                    "source_judgment_sha256"
                ],
                "append_accepted_answers": declaration[
                    "append_accepted_answers"
                ],
                "corrected_candidate_sha256": _json_sha256(row),
                "correction_input_sha256": row["correction_metadata"][
                    "input_sha256"
                ],
            }
        )
    if sorted(declared_source_cells) != residual_cells:
        raise ValueError(
            "packaging-correction cells differ from the frozen residual cohort"
        )
    corrected.sort(key=lambda row: row["item_id"])
    plan_rows.sort(key=lambda row: row["corrected_item_id"])
    plan = {
        "dataset_id": DATASET_ID,
        "protocol_id": PACKAGING_CORRECTION_ID,
        "config_path": (
            str(PACKAGING_CORRECTIONS_PATH.relative_to(ROOT))
            if ROOT in PACKAGING_CORRECTIONS_PATH.parents
            else str(PACKAGING_CORRECTIONS_PATH)
        ),
        "config_sha256": config_sha256,
        "operation": "append_accepted_answers_only",
        "corrections": plan_rows,
        "source_candidate_checkpoint_sha256": _json_sha256(prior_candidates),
        "source_judgment_checkpoint_sha256": _json_sha256(prior_judgments),
        "corrected_candidate_checkpoint_sha256": _json_sha256(corrected),
        "validation_prompt_path": str(VALIDATION_PROMPT_PATH.relative_to(ROOT)),
        "validation_prompt_sha256": sha256_file(VALIDATION_PROMPT_PATH),
        "validation_criteria_path": str(
            VALIDATION_CRITERIA_PATH.relative_to(ROOT)
        ),
        "validation_criteria_sha256": sha256_file(VALIDATION_CRITERIA_PATH),
        "validation_backend": read_yaml(MODEL_BACKENDS_PATH)["validation"],
        "uses_learner_data": False,
        "uses_q_matrix": False,
        "uses_discovered_kcs": False,
        "raw_candidates_modified": False,
        "raw_judgments_modified": False,
    }
    return plan, corrected


def _run_packaging_correction_validation(
    dataset_dir: Path,
    private_dir: Path,
    cells: list[dict[str, Any]],
    corrected: list[dict[str, Any]],
    *,
    workers: int,
    max_attempts: int,
    retry_failures: bool,
    exact_command: str,
    model_call: Callable[..., dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    public_dir = dataset_dir / "provenance/items/packaging_corrections"
    private_base = private_dir / "items/packaging_corrections/validation"
    calls = _validation_calls(cells, corrected)
    order = [call["candidate_id"] for call in calls]
    _freeze_public_jsonl(
        public_dir / "validation_plan.jsonl",
        _public_validation_plan(calls),
        "packaging-correction validation plan",
    )
    judgments_path = public_dir / "validation_judgments.jsonl"
    existing = read_jsonl(judgments_path) if judgments_path.exists() else []
    merged = merge_completed_judgment_rows(existing, [], calls)
    judgments = {row["item_id"]: row for row in merged}
    attempts_path = public_dir / "validation_attempts.jsonl"
    _attempt_rows, attempts = _unique_rows(attempts_path, "candidate_id")
    _validate_attempt_rows(attempts, calls)

    for call in calls:
        candidate_id = call["candidate_id"]
        if candidate_id in judgments:
            recovered = (
                _recover_validation_evidence(
                    call, private_base / candidate_id
                )
                if call["call_required"]
                else None
            )
            if recovered is not None and recovered[0] != judgments[candidate_id]:
                raise ValueError(
                    "public packaging-correction judgment differs from immutable "
                    f"private evidence: {candidate_id}"
                )
            if candidate_id not in attempts:
                attempts[candidate_id] = {
                    "candidate_id": candidate_id,
                    "input_sha256": call["input_sha256"],
                    "status": (
                        "success"
                        if call["call_required"]
                        else "deterministic_rejection"
                    ),
                    "attempt_count": recovered[1] if recovered is not None else 0,
                    "runtime_seconds": None,
                    "error_types": [],
                    "recovered_from_private_evidence": recovered is not None,
                }
            continue
        if not call["call_required"]:
            judgment = reconstruct_validation_judgment(call)
            merged = merge_completed_judgment_rows(
                list(judgments.values()), [judgment], calls
            )
            judgments = {row["item_id"]: row for row in merged}
            attempts[candidate_id] = {
                "candidate_id": candidate_id,
                "input_sha256": call["input_sha256"],
                "status": "deterministic_rejection",
                "attempt_count": 0,
                "runtime_seconds": 0.0,
                "error_types": [],
                "recovered_from_private_evidence": False,
            }
            continue
        recovered = _recover_validation_evidence(
            call, private_base / candidate_id
        )
        if recovered is None:
            continue
        judgment, attempt_count = recovered
        merged = merge_completed_judgment_rows(
            list(judgments.values()), [judgment], calls
        )
        judgments = {row["item_id"]: row for row in merged}
        attempts[candidate_id] = _public_attempt(
            call,
            {
                "status": "success",
                "attempt_count": attempt_count,
                "runtime_seconds": None,
                "errors": [],
            },
            recovered=True,
        )
    _write_item_checkpoint(judgments_path, judgments, order)
    _write_item_checkpoint(attempts_path, attempts, order)

    tasks = [
        call
        for call in calls
        if call["candidate_id"] not in judgments
        and call["call_required"]
        and (
            retry_failures
            or attempts.get(call["candidate_id"], {}).get("status")
            != "technical_failure"
        )
    ]

    def execute(call: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        result = _call_with_technical_retries(
            lambda evidence_dir: validate_one_candidate(
                call, model_call=model_call, evidence_dir=evidence_dir
            ),
            private_base / call["candidate_id"],
            max_attempts=max_attempts,
        )
        return call, result

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(execute, call): call for call in tasks}
        for completed, future in enumerate(as_completed(futures), 1):
            call, result = future.result()
            candidate_id = call["candidate_id"]
            judgment = result.pop("mapping")
            if judgment is not None:
                merged = merge_completed_judgment_rows(
                    list(judgments.values()), [judgment], calls
                )
                judgments = {row["item_id"]: row for row in merged}
            attempts[candidate_id] = _public_attempt(call, result, recovered=False)
            _write_item_checkpoint(judgments_path, judgments, order)
            _write_item_checkpoint(attempts_path, attempts, order)
            print(
                "packaging-correction validation terminal calls: "
                f"{completed}/{len(tasks)}; complete total={len(judgments)}/{len(calls)}",
                flush=True,
            )

    judgment_rows = [judgments[item_id] for item_id in order if item_id in judgments]
    failures = sorted(set(order) - set(judgments))
    cell_ids = {row["cell_id"] for row in corrected}
    correction_cells = [row for row in cells if row["cell_id"] in cell_ids]
    audit = validation_audit_summary(
        correction_cells,
        corrected,
        judgment_rows,
        read_yaml(VALIDATION_CRITERIA_PATH),
    )
    accepted = [
        row
        for row in corrected
        if judgments.get(row["item_id"], {}).get("accepted") is True
    ]
    audit.update(
        {
            "dataset_id": DATASET_ID,
            "protocol_id": PACKAGING_CORRECTION_ID,
            "status": "PASS" if not failures else "FAIL",
            "technical_failure_candidate_ids": failures,
            "corrected_candidate_checkpoint_sha256": _json_sha256(corrected),
            "judgment_checkpoint_sha256": _json_sha256(judgment_rows),
            "models": read_yaml(MODEL_BACKENDS_PATH)["validation"],
            "max_technical_attempts": max_attempts,
            "raw_candidates_modified": False,
            "raw_judgments_modified": False,
            "code_revision_at_stage_start": _git_revision(),
            "exact_command": exact_command,
        }
    )
    write_jsonl(public_dir / "validator_accepted_candidates.jsonl", accepted)
    write_json(public_dir / "validation_audit.json", audit)
    if failures:
        raise RuntimeError(
            "packaging-correction validation has "
            f"{len(failures)} terminal technical failures"
        )
    return judgment_rows, accepted


def correct_items_full(
    dataset_dir: Path,
    private_dir: Path,
    *,
    workers: int,
    max_attempts: int,
    retry_failures: bool,
    exact_command: str,
    model_call: Callable[..., dict[str, Any]] = audited_model_call,
) -> None:
    """Freeze, copy, append, and independently revalidate three packages."""

    _assert_private_dir(private_dir)
    cells, prior_candidates, prior_judgments = (
        _load_complete_pre_correction_evidence(dataset_dir)
    )
    plan, corrected = _expected_packaging_correction(
        cells, prior_candidates, prior_judgments
    )
    public_dir = dataset_dir / "provenance/items/packaging_corrections"
    # Both files are frozen before the first validator call.  Reaching this
    # point never mutates any raw candidate or raw judgment checkpoint.
    _freeze_public_json(public_dir / "plan.json", plan, "packaging-correction plan")
    _freeze_public_jsonl(
        public_dir / "corrected_candidates.jsonl",
        corrected,
        "packaging-correction candidate checkpoint",
    )
    judgments, accepted = _run_packaging_correction_validation(
        dataset_dir,
        private_dir,
        cells,
        corrected,
        workers=workers,
        max_attempts=max_attempts,
        retry_failures=retry_failures,
        exact_command=exact_command,
        model_call=model_call,
    )
    write_json(
        public_dir / "coverage_effect.json",
        {
            "dataset_id": DATASET_ID,
            "protocol_id": PACKAGING_CORRECTION_ID,
            "corrected_candidates": len(corrected),
            "validation_judgments": len(judgments),
            "accepted_corrected_candidates": len(accepted),
            "newly_covered_cell_ids": sorted(
                {row["cell_id"] for row in accepted}
            ),
            "remaining_zero_coverage_cell_ids": sorted(
                set(row["cell_id"] for row in cells)
                - (
                    _accepted_cell_ids(prior_candidates, prior_judgments)
                    | {row["cell_id"] for row in accepted}
                )
            ),
            "raw_candidates_modified": False,
            "raw_judgments_modified": False,
        },
    )


def _load_complete_packaging_corrections(
    dataset_dir: Path,
    cells: list[dict[str, Any]],
    prior_candidates: list[dict[str, Any]],
    prior_judgments: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    public_dir = dataset_dir / "provenance/items/packaging_corrections"
    expected_plan, expected_corrected = _expected_packaging_correction(
        cells, prior_candidates, prior_judgments
    )
    if not (public_dir / "plan.json").exists() or _read_json(
        public_dir / "plan.json"
    ) != expected_plan:
        raise ValueError("packaging-correction plan is missing or changed")
    if not (public_dir / "corrected_candidates.jsonl").exists():
        raise FileNotFoundError("corrected candidate checkpoint does not exist")
    corrected = read_jsonl(public_dir / "corrected_candidates.jsonl")
    if corrected != expected_corrected:
        raise ValueError("packaging-correction candidate checkpoint changed")
    calls = _validation_calls(cells, corrected)
    if read_jsonl(public_dir / "validation_plan.jsonl") != _public_validation_plan(
        calls
    ):
        raise ValueError("packaging-correction validation plan changed")
    judgments = merge_completed_judgment_rows(
        read_jsonl(public_dir / "validation_judgments.jsonl"), [], calls
    )
    audit = _read_json(public_dir / "validation_audit.json")
    if len(judgments) != len(corrected) or audit.get("status") != "PASS":
        raise ValueError("packaging-correction validation is incomplete")
    if audit.get("judgment_checkpoint_sha256") != _json_sha256(judgments):
        raise ValueError("packaging-correction judgment checkpoint changed")
    accepted = [
        row
        for row in corrected
        if next(
            judgment
            for judgment in judgments
            if judgment["item_id"] == row["item_id"]
        )["accepted"]
    ]
    accepted_path = public_dir / "validator_accepted_candidates.jsonl"
    if not accepted_path.exists() or read_jsonl(accepted_path) != accepted:
        raise ValueError("packaging-correction accepted checkpoint changed")
    return corrected, judgments


def _selection_for_maximum(
    accepted: list[dict[str, Any]], design: dict[str, Any], maximum: int
) -> list[dict[str, Any]]:
    if maximum in {1, 2}:
        selected_design = json.loads(json.dumps(design))
        selected_design["bank_selection"]["maximum_items_per_cell"] = maximum
        return select_item_bank(accepted, selected_design)
    if maximum != 3:
        raise ValueError("curation comparison supports maxima 1, 2, and 3")
    selected = _selection_for_maximum(accepted, design, 2)
    selected_by_cell: dict[str, list[dict[str, Any]]] = {}
    for row in selected:
        selected_by_cell.setdefault(row["cell_id"], []).append(row)
    accepted_by_cell: dict[str, list[dict[str, Any]]] = {}
    for row in accepted:
        accepted_by_cell.setdefault(row["cell_id"], []).append(row)

    def tokens(row: dict[str, Any]) -> set[str]:
        return set(
            re.findall(
                r"[^\W_]+",
                f"{row['prompt']} {row['target_answer']}".casefold(),
            )
        )

    def distance(left: dict[str, Any], right: dict[str, Any]) -> float:
        left_tokens, right_tokens = tokens(left), tokens(right)
        union = left_tokens | right_tokens
        return 1.0 - len(left_tokens & right_tokens) / len(union) if union else 0.0

    for cell_id, rows in sorted(accepted_by_cell.items()):
        existing = selected_by_cell.get(cell_id, [])
        existing_ids = {row["item_id"] for row in existing}
        remaining = [row for row in rows if row["item_id"] not in existing_ids]
        if len(existing) < 2 or not remaining:
            continue
        third = min(
            remaining,
            key=lambda row: (
                -min(distance(row, chosen) for chosen in existing),
                int(row["generation_metadata"]["candidate_index"]),
                row["item_id"],
            ),
        )
        third_selected = dict(third)
        third_selected["selection_metadata"] = {
            "rank": 3,
            "rule": "maximum_minimum_token_set_distance_from_first_two",
            "minimum_token_set_distance_from_prior": min(
                distance(third, chosen) for chosen in existing
            ),
        }
        selected.append(third_selected)
    return sorted(
        selected,
        key=lambda row: (
            row["cell_id"],
            int(row["selection_metadata"]["rank"]),
            row["item_id"],
        ),
    )


def _selection_scale_row(
    cells: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    *,
    policy: str,
    maximum: int,
    previous_items: int,
    previous_cells: int,
) -> dict[str, Any]:
    support = Counter(row["cell_id"] for row in selected)
    prompts = [row["prompt"].casefold().strip() for row in selected]
    tokens = [
        token
        for row in selected
        for token in re.findall(
            r"[^\W_]+", f"{row['prompt']} {row['target_answer']}".casefold()
        )
    ]
    covered = len(support)
    item_count = len(selected)
    return {
        "policy": policy,
        "maximum_accepted_variants_per_cell": maximum,
        "items": item_count,
        "covered_cells": covered,
        "coverage_rate": covered / len(cells) if cells else 0.0,
        "support_distribution": dict(
            sorted(
                Counter(support.get(cell["cell_id"], 0) for cell in cells).items()
            )
        ),
        "duplicate_prompts": len(prompts) - len(set(prompts)),
        "lexical_types": len(set(tokens)),
        "lexical_tokens": len(tokens),
        "token_diversity": len(set(tokens)) / len(tokens) if tokens else 0.0,
        "marginal_items": item_count - previous_items,
        "marginal_covered_cells": covered - previous_cells,
    }


def curate_items_full(dataset_dir: Path, exact_command: str) -> None:
    """Freeze the current max-two diverse bank without response evidence."""

    cells, baseline_candidates, baseline_judgments = (
        _load_complete_baseline_item_evidence(dataset_dir)
    )
    candidates = list(baseline_candidates)
    judgments = list(baseline_judgments)
    campaigns_used: list[dict[str, Any]] = []
    corrections_used: list[dict[str, Any]] = []
    baseline_zero = sorted(
        set(cell["cell_id"] for cell in cells)
        - _accepted_cell_ids(candidates, judgments)
    )
    unchanged_plan = (
        dataset_dir
        / "provenance/items/campaigns/unchanged_rescue/plan.json"
    )
    if baseline_zero and not unchanged_plan.exists():
        write_json(
            dataset_dir / "provenance/items/curation_blockers.json",
            {
                "status": "UNCHANGED_RESCUE_REQUIRED",
                "zero_accepted_candidate_cell_ids": baseline_zero,
                "automatic_rescue_or_repair_performed": False,
                "next_stage": "rescue-items",
            },
        )
        raise RuntimeError(
            "curation blocked: "
            f"{len(baseline_zero)} cells have zero accepted candidates and "
            "require the frozen rescue"
        )
    if unchanged_plan.exists():
        rescue_candidates, rescue_judgments = _load_complete_campaign(
            dataset_dir,
            cells,
            UNCHANGED_RESCUE_ID,
            baseline_candidates,
            baseline_judgments,
        )
        candidates = sorted(
            [*candidates, *rescue_candidates], key=lambda row: row["item_id"]
        )
        judgments = sorted(
            [*judgments, *rescue_judgments], key=lambda row: row["item_id"]
        )
        campaigns_used.append(
            {
                "campaign_id": UNCHANGED_RESCUE_ID,
                "candidates": len(rescue_candidates),
                "accepted": sum(row["accepted"] for row in rescue_judgments),
            }
        )

    residual_after_rescue = sorted(
        set(cell["cell_id"] for cell in cells)
        - _accepted_cell_ids(candidates, judgments)
    )
    intervention_plan = (
        dataset_dir
        / "provenance/items/campaigns/determinacy_intervention/plan.json"
    )
    if residual_after_rescue and not intervention_plan.exists():
        write_json(
            dataset_dir / "provenance/items/curation_blockers.json",
            {
                "status": "DETERMINACY_INTERVENTION_REQUIRED",
                "zero_accepted_candidate_cell_ids": residual_after_rescue,
                "automatic_rescue_or_repair_performed": False,
                "next_stage": "intervene-items",
            },
        )
        raise RuntimeError(
            "curation blocked: "
            f"{len(residual_after_rescue)} cells remain after unchanged rescue"
        )
    if intervention_plan.exists():
        prior_candidates = list(candidates)
        prior_judgments = list(judgments)
        intervention_candidates, intervention_judgments = _load_complete_campaign(
            dataset_dir,
            cells,
            DETERMINACY_INTERVENTION_ID,
            prior_candidates,
            prior_judgments,
        )
        candidates = sorted(
            [*candidates, *intervention_candidates], key=lambda row: row["item_id"]
        )
        judgments = sorted(
            [*judgments, *intervention_judgments], key=lambda row: row["item_id"]
        )
        campaigns_used.append(
            {
                "campaign_id": DETERMINACY_INTERVENTION_ID,
                "candidates": len(intervention_candidates),
                "accepted": sum(row["accepted"] for row in intervention_judgments),
            }
        )

    residual_after_campaigns = sorted(
        set(cell["cell_id"] for cell in cells)
        - _accepted_cell_ids(candidates, judgments)
    )
    correction_plan = (
        dataset_dir / "provenance/items/packaging_corrections/plan.json"
    )
    if residual_after_campaigns and not correction_plan.exists():
        write_json(
            dataset_dir / "provenance/items/curation_blockers.json",
            {
                "status": "PACKAGING_CORRECTION_REQUIRED",
                "zero_accepted_candidate_cell_ids": residual_after_campaigns,
                "automatic_rescue_or_repair_performed": False,
                "next_stage": "correct-items",
            },
        )
        raise RuntimeError(
            "curation blocked: "
            f"{len(residual_after_campaigns)} cells require the frozen "
            "packaging correction"
        )
    if correction_plan.exists():
        prior_candidates = list(candidates)
        prior_judgments = list(judgments)
        corrected_candidates, corrected_judgments = (
            _load_complete_packaging_corrections(
                dataset_dir,
                cells,
                prior_candidates,
                prior_judgments,
            )
        )
        candidates = sorted(
            [*candidates, *corrected_candidates], key=lambda row: row["item_id"]
        )
        judgments = sorted(
            [*judgments, *corrected_judgments], key=lambda row: row["item_id"]
        )
        corrections_used.append(
            {
                "protocol_id": PACKAGING_CORRECTION_ID,
                "corrected_candidates": len(corrected_candidates),
                "accepted": sum(row["accepted"] for row in corrected_judgments),
            }
        )

    candidate_by_id = {row["item_id"]: row for row in candidates}
    accepted = [
        candidate_by_id[row["item_id"]] for row in judgments if row["accepted"]
    ]
    if len(candidate_by_id) != len(candidates):
        raise ValueError("combined item-campaign candidates contain duplicate IDs")
    accepted_cells = {row["cell_id"] for row in accepted}
    zero_accepted = sorted(
        cell["cell_id"] for cell in cells if cell["cell_id"] not in accepted_cells
    )
    if zero_accepted:
        write_json(
            dataset_dir / "provenance/items/curation_blockers.json",
            {
                "status": "UNRESOLVED_AFTER_DECLARED_CAMPAIGNS",
                "zero_accepted_candidate_cell_ids": zero_accepted,
                "automatic_rescue_or_repair_performed": False,
                "next_step": (
                    "Retain this negative result and freeze a new methodological "
                    "decision before making any additional generation calls."
                ),
            },
        )
        raise RuntimeError(
            f"curation blocked: {len(zero_accepted)} cells have zero accepted candidates"
        )

    write_jsonl(
        dataset_dir / "provenance/items/all_validator_accepted_candidates.jsonl",
        accepted,
    )

    design = read_yaml(GENERATION_DESIGN_PATH)
    selections = {
        "max_1": _selection_for_maximum(accepted, design, 1),
        "max_2": _selection_for_maximum(accepted, design, 2),
        "up_to_3": _selection_for_maximum(accepted, design, 3),
    }
    comparison = []
    previous_items = 0
    previous_cells = 0
    for policy, maximum in (("max_1", 1), ("max_2", 2), ("up_to_3", 3)):
        row = _selection_scale_row(
            cells,
            selections[policy],
            policy=policy,
            maximum=maximum,
            previous_items=previous_items,
            previous_cells=previous_cells,
        )
        comparison.append(row)
        previous_items = row["items"]
        previous_cells = row["covered_cells"]

    final_items = selections["max_2"]
    _freeze_public_jsonl(
        dataset_dir / "items/items.jsonl", final_items, "curated item bank"
    )
    write_json(
        dataset_dir / "provenance/items/curation_scale_comparison.json",
        {
            "dataset_id": DATASET_ID,
            "comparison": comparison,
            "selection_rules": design["bank_selection"],
            "declared_campaigns_used": campaigns_used,
            "declared_packaging_corrections_used": corrections_used,
            "uses_learner_data": False,
            "uses_kt_or_predictive_metrics": False,
            "uses_discovered_kcs": False,
            "uses_q_matrix": False,
            "code_revision_at_stage_start": _git_revision(),
            "exact_command": exact_command,
        },
    )
    write_json(
        dataset_dir / "provenance/items/curation.json",
        {
            "dataset_id": DATASET_ID,
            "status": "PASS",
            "raw_candidates_retained": len(candidates),
            "raw_judgments_retained": len(judgments),
            "validator_accepted_candidates": len(accepted),
            "selected_items": len(final_items),
            "covered_cells": len({row["cell_id"] for row in final_items}),
            "final_bank_sha256": _json_sha256(final_items),
            "selection_design_path": str(GENERATION_DESIGN_PATH.relative_to(ROOT)),
            "automatic_rescue_or_repair_performed": False,
            "declared_post_n3_campaigns": campaigns_used,
            "declared_packaging_corrections": corrections_used,
            "original_n3_candidates_retained": len(baseline_candidates),
            "original_n3_judgments_retained": len(baseline_judgments),
            "code_revision_at_stage_start": _git_revision(),
            "exact_command": exact_command,
        },
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        required=True,
        choices=[
            "prepare-source",
            "normalise-phase1",
            "normalise-phase2",
            "canonicalise",
            "construct-k-star",
            "generate-items",
            "validate-items",
            "rescue-items",
            "intervene-items",
            "correct-items",
            "curate-items",
        ],
    )
    parser.add_argument("--source", type=Path)
    parser.add_argument(
        "--dataset-dir", type=Path, default=ROOT / "data/grammar_kt_full_v1"
    )
    parser.add_argument(
        "--private-dir",
        type=Path,
        default=ROOT / "runs/grammar_kt_full_v1_private",
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--retry-failures", action="store_true")
    arguments = parser.parse_args()
    if arguments.workers < 1 or arguments.max_attempts < 1:
        parser.error("workers and max-attempts must be positive")
    if arguments.stage in {
        "prepare-source",
        "normalise-phase1",
        "normalise-phase2",
    } and arguments.source is None:
        parser.error(f"--source is required for {arguments.stage}")
    return arguments


def main() -> int:
    arguments = parse_args()
    dataset_dir = arguments.dataset_dir.resolve()
    private_dir = arguments.private_dir.resolve()
    exact_command = " ".join([sys.executable, *sys.argv])
    if arguments.stage == "prepare-source":
        prepare_source(arguments.source.resolve(), dataset_dir, private_dir, exact_command)
    elif arguments.stage == "normalise-phase1":
        run_phase1(
            arguments.source.resolve(),
            dataset_dir,
            private_dir,
            workers=arguments.workers,
            max_attempts=arguments.max_attempts,
            retry_failures=arguments.retry_failures,
            exact_command=exact_command,
        )
    elif arguments.stage == "normalise-phase2":
        run_phase2(
            arguments.source.resolve(),
            dataset_dir,
            private_dir,
            workers=arguments.workers,
            max_attempts=arguments.max_attempts,
            retry_failures=arguments.retry_failures,
            exact_command=exact_command,
        )
    elif arguments.stage == "canonicalise":
        canonicalise_full(dataset_dir, exact_command)
    elif arguments.stage == "construct-k-star":
        construct_k_star(dataset_dir, exact_command)
    elif arguments.stage == "generate-items":
        generate_items_full(
            dataset_dir,
            private_dir,
            workers=arguments.workers,
            max_attempts=arguments.max_attempts,
            retry_failures=arguments.retry_failures,
            exact_command=exact_command,
        )
    elif arguments.stage == "validate-items":
        validate_items_full(
            dataset_dir,
            private_dir,
            workers=arguments.workers,
            max_attempts=arguments.max_attempts,
            retry_failures=arguments.retry_failures,
            exact_command=exact_command,
        )
    elif arguments.stage == "rescue-items":
        run_item_campaign(
            dataset_dir,
            private_dir,
            UNCHANGED_RESCUE_ID,
            workers=arguments.workers,
            max_attempts=arguments.max_attempts,
            retry_failures=arguments.retry_failures,
            exact_command=exact_command,
        )
    elif arguments.stage == "intervene-items":
        run_item_campaign(
            dataset_dir,
            private_dir,
            DETERMINACY_INTERVENTION_ID,
            workers=arguments.workers,
            max_attempts=arguments.max_attempts,
            retry_failures=arguments.retry_failures,
            exact_command=exact_command,
        )
    elif arguments.stage == "correct-items":
        correct_items_full(
            dataset_dir,
            private_dir,
            workers=arguments.workers,
            max_attempts=arguments.max_attempts,
            retry_failures=arguments.retry_failures,
            exact_command=exact_command,
        )
    elif arguments.stage == "curate-items":
        curate_items_full(dataset_dir, exact_command)
    else:  # pragma: no cover - argparse exhausts the stage values
        raise AssertionError(arguments.stage)
    print(f"completed {arguments.stage}: {dataset_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
