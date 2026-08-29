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
    build_generation_call,
    build_validation_call,
    candidate_audit_summary,
    generate_one_candidate,
    item_construction_audit,
    merge_completed_candidate_rows,
    merge_completed_judgment_rows,
    reconstruct_validation_judgment,
    recover_generated_candidate,
    recover_validator_judgment,
    validate_one_candidate,
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


def _selection_for_maximum(
    accepted: list[dict[str, Any]], design: dict[str, Any], maximum: int
) -> list[dict[str, Any]]:
    if maximum in {1, 2}:
        selected_design = json.loads(json.dumps(design))
        selected_design["bank_selection"]["maximum_items_per_cell"] = maximum
        return select_item_bank(accepted, selected_design)
    if maximum != 3:
        raise ValueError("curation comparison supports maxima 1, 2, and 3")
    return sorted(
        accepted,
        key=lambda row: (
            row["cell_id"],
            int(row["generation_metadata"]["candidate_index"]),
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

    cells, _generation_call_rows, candidates = _load_complete_generation(dataset_dir)
    validation_calls = _validation_calls(cells, candidates)
    validation_plan_path = dataset_dir / "provenance/items/validation_plan.jsonl"
    if not validation_plan_path.exists():
        raise FileNotFoundError("frozen item-validation plan does not exist")
    if read_jsonl(validation_plan_path) != _public_validation_plan(validation_calls):
        raise ValueError("frozen validation plan changed")
    judgments_path = dataset_dir / "provenance/items/validation_judgments.jsonl"
    if not judgments_path.exists():
        raise FileNotFoundError("validation judgments do not exist")
    judgments = merge_completed_judgment_rows(
        read_jsonl(judgments_path), [], validation_calls
    )
    if len(judgments) != len(candidates):
        raise ValueError("validation must complete every recovered candidate first")
    validation_audit_path = dataset_dir / "provenance/items/validation_audit.json"
    if not validation_audit_path.exists():
        raise FileNotFoundError("successful item-validation audit does not exist")
    validation_audit = _read_json(validation_audit_path)
    if validation_audit.get("status") != "PASS" or validation_audit.get(
        "judgment_checkpoint_sha256"
    ) != _json_sha256(judgments):
        raise ValueError("item-validation audit does not match the complete checkpoint")

    candidate_by_id = {row["item_id"]: row for row in candidates}
    accepted = [
        candidate_by_id[row["item_id"]] for row in judgments if row["accepted"]
    ]
    accepted_path = dataset_dir / "provenance/items/validator_accepted_candidates.jsonl"
    if not accepted_path.exists() or read_jsonl(accepted_path) != accepted:
        raise ValueError("validator-accepted checkpoint is missing or changed")
    accepted_cells = {row["cell_id"] for row in accepted}
    zero_accepted = sorted(
        cell["cell_id"] for cell in cells if cell["cell_id"] not in accepted_cells
    )
    if zero_accepted:
        write_json(
            dataset_dir / "provenance/items/curation_blockers.json",
            {
                "status": "DECLARED_RESCUE_DECISION_REQUIRED",
                "zero_accepted_candidate_cell_ids": zero_accepted,
                "automatic_rescue_or_repair_performed": False,
                "next_step": (
                    "Inspect failures and freeze a separate rescue decision before "
                    "making any additional generation calls."
                ),
            },
        )
        raise RuntimeError(
            f"curation blocked: {len(zero_accepted)} cells have zero accepted candidates"
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
    elif arguments.stage == "curate-items":
        curate_items_full(dataset_dir, exact_command)
    else:  # pragma: no cover - argparse exhausts the stage values
        raise AssertionError(arguments.stage)
    print(f"completed {arguments.stage}: {dataset_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
