#!/usr/bin/env python3
"""Freeze and execute the full-v1 repeated Phase-1 annotation study.

The study deliberately repeats descriptor-only Phase 1.  It never consults
examples, Phase-2 mappings, or the primary call evidence.  Consult-only source
rows, rendered prompts, raw model output, and unsanitised notes remain below an
ignored ``runs/`` directory; the public directory contains only the frozen
opaque cohort, derived mappings, technical status, and aggregate provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.full_normalisation import normalise_phase1_record, sha256_file
from grammar_kt.io import (
    ModelCall,
    read_jsonl,
    read_text,
    read_yaml,
    render,
    write_json,
    write_jsonl,
)
from grammar_kt.model_evidence import audited_model_call
from grammar_kt.normalise import PHASE1_FIELDS, _validate_mapping


DEFAULT_SCHEMA = ROOT / "modules/grammar/canonical/schema.yaml"
DEFAULT_PROMPT = ROOT / "modules/grammar/resource/egp/normalisation/phase1.txt"
DEFAULT_RULEBOOK = ROOT / "modules/grammar/resource/egp/normalisation/rulebook.md"
DEFAULT_BACKENDS = ROOT / "modules/model_backends.yaml"
DEFAULT_PRIVATE_EVIDENCE = ROOT / "runs/grammar_kt_full_v1_private"
DEFAULT_PUBLIC_OUTPUT = (
    ROOT / "data/grammar_kt_full_v1/provenance/normalisation/stability"
)
DEFAULT_COHORT_SEED = "grammar-kt-full-v1-phase1-stability-v1"
GROUP_ORDER = ("complete", "partial_or_unresolved", "out_of_scope")
RESULT_ORDER = ("complete", "partial", "unresolved", "out_of_scope")
PUBLIC_NOTE = "Unsanitised model note retained in restricted repeat evidence."
REPEAT_STAGE = "normalisation.phase1.stability_repeat"


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
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_private_evidence_dir(path: Path) -> None:
    resolved = path.resolve()
    runs = (ROOT / "runs").resolve()
    if runs not in resolved.parents:
        raise ValueError(
            "repeat call evidence must stay below the ignored runs/ directory"
        )


def _unique_by_source(
    rows: list[dict[str, Any]], *, label: str
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        source_id = row.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError(f"{label} contains a missing or invalid source_id")
        if source_id in result:
            raise ValueError(f"{label} contains duplicate source_id {source_id}")
        result[source_id] = row
    return result


def _primary_group(result: str) -> str:
    if result == "complete":
        return "complete"
    if result in {"partial", "unresolved"}:
        return "partial_or_unresolved"
    if result == "out_of_scope":
        return "out_of_scope"
    raise ValueError(f"unknown primary result {result!r}")


def _balance_strategy(source: list[dict[str, Any]]) -> str:
    if all(
        isinstance(row.get("cefr"), str) and row["cefr"].strip()
        for row in source
    ):
        return "cefr"
    return "category_hash"


def _balance_stratum(row: dict[str, Any], strategy: str) -> str:
    if strategy == "cefr":
        return f"cefr:{row['cefr'].strip()}"
    category = json.dumps(
        [row.get("supercategory"), row.get("subcategory")],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    # Category-aware fallback without publishing the resource category text.
    return (
        "category_sha256:"
        + hashlib.sha256(category.encode("utf-8")).hexdigest()[:16]
    )


def _balanced_group_quotas(
    target: int, capacities: dict[str, int]
) -> tuple[dict[str, int], dict[str, int]]:
    if target < 1:
        raise ValueError("target must be positive")
    effective_target = min(target, sum(capacities.values()))
    initial = {
        group: effective_target // len(GROUP_ORDER)
        + (index < effective_target % len(GROUP_ORDER))
        for index, group in enumerate(GROUP_ORDER)
    }
    final = {
        group: min(initial[group], capacities[group]) for group in GROUP_ORDER
    }
    remaining = effective_target - sum(final.values())
    # Reallocate one unit at a time to the currently least represented group.
    # The fixed GROUP_ORDER resolves all ties and makes the policy reproducible.
    while remaining:
        candidates = [
            group for group in GROUP_ORDER if final[group] < capacities[group]
        ]
        if not candidates:  # pragma: no cover - guarded by effective_target
            raise AssertionError("quota reallocation exhausted available rows")
        chosen = min(
            candidates,
            key=lambda group: (final[group], GROUP_ORDER.index(group)),
        )
        final[chosen] += 1
        remaining -= 1
    return initial, final


def _hash_rank(seed: str, group: str, stratum: str, source_id: str) -> str:
    return hashlib.sha256(
        f"{seed}\0{group}\0{stratum}\0{source_id}".encode("utf-8")
    ).hexdigest()


def _stratified_select(
    candidates: list[dict[str, Any]],
    quota: int,
    *,
    group: str,
    strategy: str,
    seed: str,
) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        buckets[_balance_stratum(row, strategy)].append(row)
    for stratum, rows in buckets.items():
        rows.sort(
            key=lambda row: (
                _hash_rank(seed, group, stratum, row["source_id"]),
                row["source_id"],
            )
        )

    selected: list[dict[str, Any]] = []
    strata = sorted(buckets)
    cursor = {stratum: 0 for stratum in strata}
    while len(selected) < quota:
        progressed = False
        for stratum in strata:
            index = cursor[stratum]
            if index >= len(buckets[stratum]):
                continue
            selected.append(buckets[stratum][index])
            cursor[stratum] += 1
            progressed = True
            if len(selected) == quota:
                break
        if not progressed:  # pragma: no cover - quota is capacity bounded
            raise AssertionError("stratified selection exhausted candidates")
    return selected


def _load_and_validate_inputs(
    typed_source_path: Path,
    primary_phase1_path: Path,
    schema_path: Path,
    prompt_path: Path,
    rulebook_path: Path,
    backends_path: Path,
) -> dict[str, Any]:
    source = read_jsonl(typed_source_path)
    primary = read_jsonl(primary_phase1_path)
    by_source = _unique_by_source(source, label="typed source")
    by_primary = _unique_by_source(primary, label="primary Phase-1 mappings")
    if set(by_primary) != set(by_source):
        raise ValueError(
            "completed primary Phase-1 mappings must exactly cover typed source IDs"
        )
    required_source_fields = {*PHASE1_FIELDS, "examples"}
    for source_id, row in by_source.items():
        missing = required_source_fields - set(row)
        if missing:
            raise ValueError(f"typed source {source_id} lacks fields {sorted(missing)}")

    schema = read_yaml(schema_path)
    for source_id in by_source:
        _validate_mapping(by_primary[source_id], source_id, schema)
    prompt = read_text(prompt_path)
    rulebook = read_text(rulebook_path)
    backends = read_yaml(backends_path)
    backend = backends.get("normalisation") if isinstance(backends, dict) else None
    if not isinstance(backend, dict) or not {
        "model",
        "reasoning_effort",
    } <= set(backend):
        raise ValueError("backend declaration lacks normalisation model/settings")

    source_order = [row["source_id"] for row in source]
    primary_ordered = [by_primary[source_id] for source_id in source_order]
    hashes = {
        "typed_source_file_sha256": sha256_file(typed_source_path),
        "typed_source_stream_sha256": _json_sha256(source),
        "primary_phase1_file_sha256": sha256_file(primary_phase1_path),
        "primary_phase1_stream_sha256": _json_sha256(primary_ordered),
        "grammar_schema_sha256": sha256_file(schema_path),
        "phase1_prompt_sha256": sha256_file(prompt_path),
        "rulebook_sha256": sha256_file(rulebook_path),
        "backend_declaration_sha256": sha256_file(backends_path),
    }
    return {
        "source": source,
        "by_source": by_source,
        "primary": primary_ordered,
        "by_primary": by_primary,
        "schema": schema,
        "prompt": prompt,
        "rulebook": rulebook,
        "backend": {key: backend[key] for key in ("model", "reasoning_effort")},
        "hashes": hashes,
    }


def build_cohort(
    inputs: dict[str, Any], *, target: int = 120, seed: str = DEFAULT_COHORT_SEED
) -> dict[str, Any]:
    """Return the deterministic, source-text-free repeated-annotation cohort."""

    if not seed:
        raise ValueError("cohort seed must be nonempty")
    source = inputs["source"]
    by_primary = inputs["by_primary"]
    strategy = _balance_strategy(source)
    grouped: dict[str, list[dict[str, Any]]] = {group: [] for group in GROUP_ORDER}
    for row in source:
        grouped[_primary_group(by_primary[row["source_id"]]["result"])].append(row)
    capacities = {group: len(grouped[group]) for group in GROUP_ORDER}
    initial, final = _balanced_group_quotas(target, capacities)

    selected_rows: list[dict[str, Any]] = []
    for group in GROUP_ORDER:
        selected_rows.extend(
            {
                "source_id": row["source_id"],
                "primary_result_group": group,
                "balance_stratum": _balance_stratum(row, strategy),
            }
            for row in _stratified_select(
                grouped[group],
                final[group],
                group=group,
                strategy=strategy,
                seed=seed,
            )
        )
    selected_rows.sort(key=lambda row: row["source_id"])
    selected_ids = [row["source_id"] for row in selected_rows]
    selected_strata = Counter(row["balance_stratum"] for row in selected_rows)
    core = {
        "study": "full_v1_descriptor_only_phase1_repeated_annotation",
        "selection_seed": seed,
        "selection_algorithm": (
            "balanced primary-result quotas with capacity-aware reallocation; "
            "round-robin balance strata; SHA-256 ranking within each stratum"
        ),
        "balance_strategy": strategy,
        "requested_target": target,
        "effective_target": len(selected_rows),
        "primary_result_counts": {
            result: Counter(row["result"] for row in inputs["primary"])[result]
            for result in RESULT_ORDER
        },
        "primary_group_capacities": capacities,
        "initial_group_quotas": initial,
        "final_group_quotas": final,
        "quota_reallocation": {
            group: final[group] - initial[group] for group in GROUP_ORDER
        },
        "selected_group_counts": dict(
            sorted(
                Counter(
                    row["primary_result_group"] for row in selected_rows
                ).items()
            )
        ),
        "selected_balance_stratum_counts": dict(sorted(selected_strata.items())),
        "selected": selected_rows,
        "source_ids_sha256": _json_sha256(selected_ids),
        "input_hashes": inputs["hashes"],
        "frozen_before_repeat_calls": True,
    }
    content_hash = _json_sha256(core)
    return {
        "cohort_id": f"full_v1_phase1_repeat_{content_hash[:16]}",
        "cohort_content_sha256": content_hash,
        **core,
    }


def prepare_cohort(
    *,
    typed_source_path: Path,
    primary_phase1_path: Path,
    schema_path: Path,
    prompt_path: Path,
    rulebook_path: Path,
    backends_path: Path,
    private_evidence_dir: Path,
    public_output_dir: Path,
    target: int,
    seed: str,
    exact_command: str,
    code_revision: str | None = None,
) -> dict[str, Any]:
    _assert_private_evidence_dir(private_evidence_dir)
    inputs = _load_and_validate_inputs(
        typed_source_path,
        primary_phase1_path,
        schema_path,
        prompt_path,
        rulebook_path,
        backends_path,
    )
    cohort = build_cohort(inputs, target=target, seed=seed)
    cohort_path = public_output_dir / "cohort.json"
    repeat_root = private_evidence_dir / "normalisation_stability/phase1_repeat"
    if not cohort_path.exists() and repeat_root.exists() and any(repeat_root.iterdir()):
        raise ValueError("repeat evidence exists but the public cohort was not frozen first")
    if cohort_path.exists():
        frozen = _read_json(cohort_path)
        if frozen != cohort:
            raise ValueError("frozen repeated-annotation cohort or its inputs drifted")
    else:
        write_json(cohort_path, cohort)

    summary = {
        "stage": "prepare",
        "status": "cohort_frozen",
        "cohort_id": cohort["cohort_id"],
        "cohort_content_sha256": cohort["cohort_content_sha256"],
        "selected_descriptors": cohort["effective_target"],
        "model_settings_for_future_run": inputs["backend"],
        "provider_sampling_seed": {
            "available": False,
            "value": None,
            "consequence": (
                "The Codex CLI backend exposes no provider sampling seed; "
                "stability is measured empirically over fresh calls."
            ),
        },
        "input_hashes": inputs["hashes"],
        "code_revision_at_stage_start": code_revision or _git_revision(),
        "exact_command": exact_command,
    }
    write_json(public_output_dir / "prepare_summary.json", summary)
    return cohort


def _public_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    # A free-text model note can accidentally reproduce licensed source prose.
    # The exact result remains in the restricted parsed_result.json evidence.
    return {**mapping, "note": PUBLIC_NOTE}


def _write_mapping_checkpoint(
    path: Path,
    mappings: dict[str, dict[str, Any]],
    order: list[str],
) -> None:
    # Intentionally contains only derived mappings: no source rows, prompts,
    # model settings, raw output, errors, or oracle metadata.
    write_jsonl(
        path,
        [mappings[source_id] for source_id in order if source_id in mappings],
    )


def _write_attempt_status(
    path: Path,
    attempts: dict[str, dict[str, Any]],
    order: list[str],
) -> None:
    write_jsonl(
        path,
        [attempts[source_id] for source_id in order if source_id in attempts],
    )


def _validate_public_attempt_status(row: dict[str, Any], source_id: str) -> None:
    expected_fields = {
        "source_id",
        "status",
        "attempt_count",
        "runtime_seconds",
        "technical_error_types",
    }
    if set(row) != expected_fields or row["source_id"] != source_id:
        raise ValueError(f"invalid public repeat attempt status for {source_id}")
    if row["status"] not in {
        "success",
        "success_recovered_repeat_evidence",
        "technical_failure",
    }:
        raise ValueError(f"invalid public repeat attempt status for {source_id}")
    if not isinstance(row["attempt_count"], int) or row["attempt_count"] < 1:
        raise ValueError(f"invalid public repeat attempt count for {source_id}")
    runtime = row["runtime_seconds"]
    if runtime is not None and not isinstance(runtime, (int, float)):
        raise ValueError(f"invalid public repeat runtime for {source_id}")
    errors = row["technical_error_types"]
    if not isinstance(errors, list) or any(
        not isinstance(value, str) for value in errors
    ):
        raise ValueError(f"invalid public repeat error types for {source_id}")


def _expected_prompt(
    resource: dict[str, Any], prompt: str, rulebook: str, schema: dict[str, Any]
) -> str:
    descriptor = {name: resource[name] for name in PHASE1_FIELDS}
    return render(
        prompt,
        {
            "descriptor": descriptor,
            "canonical_schema": schema,
            "rulebook": rulebook,
        },
    )


def _validate_repeat_evidence_context(
    evidence_dir: Path,
    resource: dict[str, Any],
    *,
    prompt: str,
    rulebook: str,
    schema: dict[str, Any],
    backend: dict[str, str],
) -> None:
    context_files = (
        "input.json",
        "rendered_prompt.txt",
        "model_settings.json",
    )
    if not any((evidence_dir / name).exists() for name in context_files):
        if (evidence_dir / "parsed_result.json").exists():
            raise ValueError(f"repeat parsed result lacks context: {evidence_dir}")
        return
    if not all((evidence_dir / name).exists() for name in context_files):
        raise ValueError(f"incomplete repeat evidence context: {evidence_dir}")
    descriptor = {name: resource[name] for name in PHASE1_FIELDS}
    if _read_json(evidence_dir / "input.json") != {"descriptor": descriptor}:
        raise ValueError(f"repeat evidence input drift: {evidence_dir}")
    rendered_prompt = (evidence_dir / "rendered_prompt.txt").read_text(
        encoding="utf-8"
    )
    if rendered_prompt != _expected_prompt(resource, prompt, rulebook, schema):
        raise ValueError(f"repeat evidence prompt drift: {evidence_dir}")
    settings = _read_json(evidence_dir / "model_settings.json")
    expected = {
        "model": backend["model"],
        "reasoning_effort": backend["reasoning_effort"],
        "stage": REPEAT_STAGE,
        "call_key": resource["source_id"],
    }
    if any(settings.get(key) != value for key, value in expected.items()):
        raise ValueError(f"repeat evidence model/settings drift: {evidence_dir}")


def _recover_repeat_mapping(
    evidence_base: Path,
    resource: dict[str, Any],
    *,
    prompt: str,
    rulebook: str,
    schema: dict[str, Any],
    backend: dict[str, str],
) -> tuple[dict[str, Any] | None, int]:
    attempts = sorted(
        path for path in evidence_base.glob("attempt-*") if path.is_dir()
    )
    recovered = None
    for path in attempts:
        _validate_repeat_evidence_context(
            path,
            resource,
            prompt=prompt,
            rulebook=rulebook,
            schema=schema,
            backend=backend,
        )
        parsed_path = path / "parsed_result.json"
        if not parsed_path.exists():
            continue
        candidate = _read_json(parsed_path)
        try:
            _validate_mapping(candidate, resource["source_id"], schema)
        except Exception:
            continue
        if recovered is not None and candidate != recovered:
            raise ValueError(
                f"multiple valid but different repeat results exist for {resource['source_id']}"
            )
        recovered = candidate
    return recovered, len(attempts)


def _technical_error_types(evidence_base: Path) -> list[str]:
    values = []
    for path in sorted(evidence_base.glob("attempt-*/technical_error.json")):
        value = _read_json(path)
        if isinstance(value.get("error_type"), str):
            values.append(value["error_type"])
    return values


def _call_repeat_with_retries(
    resource: dict[str, Any],
    evidence_base: Path,
    *,
    prompt: str,
    rulebook: str,
    schema: dict[str, Any],
    backend: dict[str, str],
    max_attempts: int,
    model_call: ModelCall,
) -> dict[str, Any]:
    existing = len([path for path in evidence_base.glob("attempt-*") if path.is_dir()])
    error_types = _technical_error_types(evidence_base)
    started = time.monotonic()
    for attempt_number in range(existing + 1, max_attempts + 1):
        evidence_dir = evidence_base / f"attempt-{attempt_number:02d}"

        def repeat_model_call(call_prompt: str, **kwargs: Any) -> dict[str, Any]:
            kwargs["stage"] = REPEAT_STAGE
            return model_call(call_prompt, **kwargs)

        try:
            mapping = normalise_phase1_record(
                resource,
                prompt,
                rulebook,
                schema,
                model=backend["model"],
                reasoning_effort=backend["reasoning_effort"],
                model_call=repeat_model_call,
                evidence_dir=evidence_dir,
            )
            return {
                "source_id": resource["source_id"],
                "status": "success",
                "mapping": mapping,
                "attempt_count": attempt_number,
                "runtime_seconds": time.monotonic() - started,
                "technical_error_types": error_types,
            }
        except Exception as error:
            error_types.append(type(error).__name__)
            evidence_dir.mkdir(parents=True, exist_ok=True)
            write_json(
                evidence_dir / "technical_error.json",
                {"error_type": type(error).__name__, "error": str(error)},
            )
    return {
        "source_id": resource["source_id"],
        "status": "technical_failure",
        "mapping": None,
        "attempt_count": max(existing, max_attempts),
        "runtime_seconds": time.monotonic() - started,
        "technical_error_types": error_types,
    }


def _run_summary(
    *,
    status: str,
    cohort: dict[str, Any],
    mappings: dict[str, dict[str, Any]],
    attempts: dict[str, dict[str, Any]],
    backend: dict[str, str],
    max_attempts: int,
    exact_command: str,
    code_revision: str,
) -> dict[str, Any]:
    order = [row["source_id"] for row in cohort["selected"]]
    missing = sorted(set(order) - set(mappings))
    return {
        "stage": "run",
        "status": status,
        "cohort_id": cohort["cohort_id"],
        "cohort_content_sha256": cohort["cohort_content_sha256"],
        "selected_descriptors": len(order),
        "valid_repeat_mappings": len(mappings),
        "missing_source_ids": missing,
        "repeat_result_counts": dict(
            sorted(Counter(row["result"] for row in mappings.values()).items())
        ),
        "attempt_status_counts": dict(
            sorted(Counter(row["status"] for row in attempts.values()).items())
        ),
        "technical_error_type_counts": dict(
            sorted(
                Counter(
                    error_type
                    for row in attempts.values()
                    for error_type in row.get("technical_error_types", [])
                ).items()
            )
        ),
        "model_settings": backend,
        "max_total_technical_attempts_per_descriptor": max_attempts,
        "retry_policy": (
            "Retry only model/transport/JSON/schema-contract failures; never retry "
            "because a valid annotation disagrees with the primary annotation."
        ),
        "provider_sampling_seed": {
            "available": False,
            "value": None,
            "consequence": (
                "The Codex CLI backend exposes no provider sampling seed; this is "
                "a fresh-call empirical repeat, not a seeded replay."
            ),
        },
        "input_hashes": cohort["input_hashes"],
        "code_revision_at_stage_start": code_revision,
        "exact_command": exact_command,
    }


def run_repeat(
    *,
    typed_source_path: Path,
    primary_phase1_path: Path,
    schema_path: Path,
    prompt_path: Path,
    rulebook_path: Path,
    backends_path: Path,
    private_evidence_dir: Path,
    public_output_dir: Path,
    workers: int,
    max_attempts: int,
    exact_command: str,
    model_call: ModelCall = audited_model_call,
    code_revision: str | None = None,
) -> dict[str, Any]:
    if workers < 1 or max_attempts < 1:
        raise ValueError("workers and max_attempts must be positive")
    _assert_private_evidence_dir(private_evidence_dir)
    cohort_path = public_output_dir / "cohort.json"
    if not cohort_path.exists():
        raise FileNotFoundError("prepare must freeze cohort.json before repeat calls")
    cohort = _read_json(cohort_path)
    inputs = _load_and_validate_inputs(
        typed_source_path,
        primary_phase1_path,
        schema_path,
        prompt_path,
        rulebook_path,
        backends_path,
    )
    expected_cohort = build_cohort(
        inputs,
        target=cohort["requested_target"],
        seed=cohort["selection_seed"],
    )
    if expected_cohort != cohort:
        raise ValueError("frozen repeated-annotation cohort or its inputs drifted")

    order = [row["source_id"] for row in cohort["selected"]]
    selected = set(order)
    mappings_path = public_output_dir / "repeat_mappings.jsonl"
    attempts_path = public_output_dir / "repeat_attempts.jsonl"
    mappings = _unique_by_source(
        read_jsonl(mappings_path) if mappings_path.exists() else [],
        label="repeat mapping checkpoint",
    )
    attempts = _unique_by_source(
        read_jsonl(attempts_path) if attempts_path.exists() else [],
        label="repeat attempt status",
    )
    if not set(mappings) <= selected or not set(attempts) <= selected:
        raise ValueError("repeat checkpoint contains a source outside the frozen cohort")
    repeat_root = (
        private_evidence_dir
        / "normalisation_stability/phase1_repeat"
        / cohort["cohort_id"]
    )
    for source_id, mapping in mappings.items():
        _validate_mapping(mapping, source_id, inputs["schema"])
        if mapping["note"] != PUBLIC_NOTE:
            raise ValueError(
                f"repeat mapping checkpoint contains an unsanitised note: {source_id}"
            )
        recovered, attempt_count = _recover_repeat_mapping(
            repeat_root / source_id,
            inputs["by_source"][source_id],
            prompt=inputs["prompt"],
            rulebook=inputs["rulebook"],
            schema=inputs["schema"],
            backend=inputs["backend"],
        )
        if recovered is None or _public_mapping(recovered) != mapping:
            raise ValueError(
                f"repeat checkpoint lacks matching restricted repeat evidence: {source_id}"
            )
        if source_id not in attempts:
            attempts[source_id] = {
                "source_id": source_id,
                "status": "success_recovered_repeat_evidence",
                "attempt_count": attempt_count,
                "runtime_seconds": None,
                "technical_error_types": _technical_error_types(
                    repeat_root / source_id
                ),
            }
    for source_id, attempt in attempts.items():
        _validate_public_attempt_status(attempt, source_id)
    for source_id in order:
        if source_id in mappings:
            continue
        recovered, attempt_count = _recover_repeat_mapping(
            repeat_root / source_id,
            inputs["by_source"][source_id],
            prompt=inputs["prompt"],
            rulebook=inputs["rulebook"],
            schema=inputs["schema"],
            backend=inputs["backend"],
        )
        if recovered is not None:
            mappings[source_id] = _public_mapping(recovered)
            attempts[source_id] = {
                "source_id": source_id,
                "status": "success_recovered_repeat_evidence",
                "attempt_count": attempt_count,
                "runtime_seconds": None,
                "technical_error_types": _technical_error_types(
                    repeat_root / source_id
                ),
            }
    _write_mapping_checkpoint(mappings_path, mappings, order)
    _write_attempt_status(attempts_path, attempts, order)

    tasks = [source_id for source_id in order if source_id not in mappings]
    revision = code_revision or _git_revision()
    write_json(
        public_output_dir / "run_summary.json",
        _run_summary(
            status="running",
            cohort=cohort,
            mappings=mappings,
            attempts=attempts,
            backend=inputs["backend"],
            max_attempts=max_attempts,
            exact_command=exact_command,
            code_revision=revision,
        ),
    )

    def execute(source_id: str) -> dict[str, Any]:
        return _call_repeat_with_retries(
            inputs["by_source"][source_id],
            repeat_root / source_id,
            prompt=inputs["prompt"],
            rulebook=inputs["rulebook"],
            schema=inputs["schema"],
            backend=inputs["backend"],
            max_attempts=max_attempts,
            model_call=model_call,
        )

    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(execute, source_id): source_id
            for source_id in tasks
        }
        for future in as_completed(futures):
            result = future.result()
            source_id = result["source_id"]
            mapping = result.pop("mapping")
            if mapping is not None:
                mappings[source_id] = _public_mapping(mapping)
            attempts[source_id] = result
            _write_mapping_checkpoint(mappings_path, mappings, order)
            _write_attempt_status(attempts_path, attempts, order)
            completed += 1
            if completed % 10 == 0 or completed == len(tasks):
                print(
                    f"repeat Phase 1 terminal descriptors: {completed}/{len(tasks)}; "
                    f"valid total={len(mappings)}/{len(order)}",
                    flush=True,
                )

    failures = sorted(selected - set(mappings))
    status = "complete" if not failures else "technical_failure"
    summary = _run_summary(
        status=status,
        cohort=cohort,
        mappings=mappings,
        attempts=attempts,
        backend=inputs["backend"],
        max_attempts=max_attempts,
        exact_command=exact_command,
        code_revision=revision,
    )
    write_json(public_output_dir / "run_summary.json", summary)
    if failures:
        raise RuntimeError(
            f"repeat Phase 1 has {len(failures)} technical failures; inspect private "
            "evidence and rerun with a larger --max-attempts if justified"
        )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("prepare", "run"))
    parser.add_argument("--typed-source", type=Path, required=True)
    parser.add_argument("--primary-phase1", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--phase1-prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--rulebook", type=Path, default=DEFAULT_RULEBOOK)
    parser.add_argument("--backends", type=Path, default=DEFAULT_BACKENDS)
    parser.add_argument(
        "--private-evidence-dir", type=Path, default=DEFAULT_PRIVATE_EVIDENCE
    )
    parser.add_argument(
        "--public-output-dir", type=Path, default=DEFAULT_PUBLIC_OUTPUT
    )
    parser.add_argument("--target", type=int, default=120)
    parser.add_argument("--cohort-seed", default=DEFAULT_COHORT_SEED)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-attempts", type=int, default=2)
    arguments = parser.parse_args()
    if arguments.target < 1 or arguments.workers < 1 or arguments.max_attempts < 1:
        parser.error("target, workers, and max-attempts must be positive")
    return arguments


def main() -> int:
    arguments = parse_args()
    exact_command = shlex.join([sys.executable, *sys.argv])
    shared = {
        "typed_source_path": arguments.typed_source.resolve(),
        "primary_phase1_path": arguments.primary_phase1.resolve(),
        "schema_path": arguments.schema.resolve(),
        "prompt_path": arguments.phase1_prompt.resolve(),
        "rulebook_path": arguments.rulebook.resolve(),
        "backends_path": arguments.backends.resolve(),
        "private_evidence_dir": arguments.private_evidence_dir.resolve(),
        "public_output_dir": arguments.public_output_dir.resolve(),
        "exact_command": exact_command,
    }
    if arguments.stage == "prepare":
        prepare_cohort(
            **shared,
            target=arguments.target,
            seed=arguments.cohort_seed,
        )
    else:
        run_repeat(
            **shared,
            workers=arguments.workers,
            max_attempts=arguments.max_attempts,
        )
    print(
        f"completed stability {arguments.stage}: "
        f"{arguments.public_output_dir.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
