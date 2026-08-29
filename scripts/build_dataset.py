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
from grammar_kt.generator_kcs import construct_generator_kcs
from grammar_kt.io import (
    load_typed_resource,
    read_jsonl,
    read_text,
    read_yaml,
    write_json,
    write_jsonl,
)
from grammar_kt.model_evidence import audited_model_call
from grammar_kt.normalise import _validate_mapping, _validate_phase2_transition


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


def _recover_phase1(
    resource: dict[str, Any],
    evidence_base: Path,
    schema: dict[str, Any],
) -> dict[str, Any] | None:
    for path in sorted(evidence_base.glob("attempt-*/parsed_result.json")):
        mapping = _read_json(path)
        try:
            _validate_mapping(mapping, resource["source_id"], schema)
        except Exception:
            continue
        return mapping
    return None


def _recover_phase2(
    resource: dict[str, Any],
    phase1_mapping: dict[str, Any],
    evidence_base: Path,
    schema: dict[str, Any],
) -> dict[str, Any] | None:
    for path in sorted(evidence_base.glob("attempt-*/parsed_result.json")):
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
        return mapping
    return None


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
    mappings = {
        row["source_id"]: row
        for row in (read_jsonl(mappings_path) if mappings_path.exists() else [])
    }
    attempts = {
        row["source_id"]: row
        for row in (read_jsonl(attempts_path) if attempts_path.exists() else [])
    }
    schema = read_yaml(GRAMMAR_SCHEMA_PATH)
    for resource in resources:
        source_id = resource["source_id"]
        if source_id in mappings:
            _validate_mapping(mappings[source_id], source_id, schema)
            continue
        recovered = _recover_phase1(
            resource,
            private_dir / "normalisation/phase1" / source_id,
            schema,
        )
        if recovered is not None:
            mappings[source_id] = recovered

    order = [row["source_id"] for row in resources]
    _write_checkpoint(mappings_path, mappings, order)
    backend = read_yaml(MODEL_BACKENDS_PATH)["normalisation"]
    phase1_prompt = read_text(PHASE1_PROMPT_PATH)
    rulebook = read_text(NORMALISATION_RULEBOOK_PATH)
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
            if result["mapping"] is not None:
                mappings[source_id] = result.pop("mapping")
            else:
                result.pop("mapping")
            attempts[source_id] = result
            _write_checkpoint(mappings_path, mappings, order)
            _write_checkpoint(attempts_path, attempts, order)
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
    phase1 = read_jsonl(phase1_path)
    if len(phase1) != len(resources):
        raise ValueError("Phase 1 must classify all source descriptors first")
    phase1_by_id = {row["source_id"]: row for row in phase1}
    schema = read_yaml(GRAMMAR_SCHEMA_PATH)
    for row in phase1:
        _validate_mapping(row, row["source_id"], schema)

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
    mappings = {
        row["source_id"]: row
        for row in (read_jsonl(mappings_path) if mappings_path.exists() else [])
    }
    attempts = {
        row["source_id"]: row
        for row in (read_jsonl(attempts_path) if attempts_path.exists() else [])
    }
    for source_id in eligible_ids:
        if source_id in mappings:
            _validate_phase2_transition(phase1_by_id[source_id], mappings[source_id], schema)
            continue
        recovered = _recover_phase2(
            by_source[source_id],
            phase1_by_id[source_id],
            private_dir / "normalisation/phase2" / source_id,
            schema,
        )
        if recovered is not None:
            mappings[source_id] = recovered
    _write_checkpoint(mappings_path, mappings, eligible_ids)

    backend = read_yaml(MODEL_BACKENDS_PATH)["normalisation"]
    phase2_prompt = read_text(PHASE2_PROMPT_PATH)
    rulebook = read_text(NORMALISATION_RULEBOOK_PATH)
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
            if result["mapping"] is not None:
                mappings[source_id] = result.pop("mapping")
            else:
                result.pop("mapping")
            attempts[source_id] = result
            _write_checkpoint(mappings_path, mappings, eligible_ids)
            _write_checkpoint(attempts_path, attempts, eligible_ids)
            completed += 1
            if completed % 10 == 0 or completed == len(tasks):
                print(
                    f"Phase 2 terminal descriptors: {completed}/{len(tasks)}; "
                    f"valid total={len(mappings)}/{len(eligible_ids)}",
                    flush=True,
                )

    failures = sorted(set(eligible_ids) - set(mappings))
    final = [mappings.get(row["source_id"], row) for row in phase1]
    write_jsonl(output_dir / "final_mappings.jsonl", final)
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
    else:  # pragma: no cover - argparse exhausts the stage values
        raise AssertionError(arguments.stage)
    print(f"completed {arguments.stage}: {dataset_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
