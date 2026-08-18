"""Fresh-context two-phase execution of the frozen EGP normalization v1.3 contract."""

from __future__ import annotations

import importlib.util
import argparse
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

from shared.utils.contracts import declared_hashes, render_template, validate_jsonl
from shared.utils.io import ROOT, read_json, read_jsonl, repo_path, sha256_file, utc_now, write_json, write_jsonl
from shared.utils.manifests import write_stage_manifest
from shared.utils.model_backend import get_backend
from shared.utils.model_units import begin_attempt, begin_model_unit, completed_model_unit, finish_attempt, invocation_reuse_key, select_attempt
from shared.utils.research import prepare_stage_directory


def _load_validator(path: Path):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("grammar_kt_frozen_v13_validator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load frozen validator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _verify_frozen_artifacts(hash_path: Path) -> None:
    expected = read_json(hash_path)
    errors = []
    for filename, digest in expected.items():
        path = hash_path.parent / filename
        if not path.is_file():
            errors.append(f"missing frozen normalization artifact: {path}")
        elif sha256_file(path) != digest:
            errors.append(f"frozen normalization artifact drift: {path}")
    if errors:
        raise RuntimeError("; ".join(errors))


def _prompt(phase: int, config: dict[str, Any], replacements: dict[str, str]) -> str:
    schema = repo_path(config["schema"]).read_text(encoding="utf-8")
    rulebook = repo_path(config["rulebook"]).read_text(encoding="utf-8")
    template = repo_path(config[f"phase{phase}_prompt"]).read_text(encoding="utf-8")
    rendered = render_template(template, replacements)
    wrapper = repo_path(config["prompt_wrapper"]).read_text(encoding="utf-8")
    prefix = render_template(
        wrapper,
        {"schema": schema, "rulebook": rulebook, "phase": str(phase)},
    )
    return prefix + rendered


def _annotate(
    *,
    phase: int,
    task: dict[str, Any],
    config: dict[str, Any],
    output: Path,
    parse_raw: Callable,
    validate_mapping: Callable,
    validate_transition: Callable,
) -> dict[str, Any]:
    backend = get_backend(config["backend"])
    unit_id = task["unit_id"]
    egp_id = task["egp_id"]
    replacements = {
        "record": json.dumps(task["record"], ensure_ascii=False, separators=(",", ":")),
    }
    if phase == 2:
        replacements.update(
            {
                "phase1_mapping": json.dumps(task["phase1_mapping"], ensure_ascii=False, separators=(",", ":")),
                "examples": json.dumps(task["examples"], ensure_ascii=False, separators=(",", ":")),
            }
        )
    prompt = _prompt(phase, config, replacements)
    unit_input = {
        "phase": phase,
        "unit_id": unit_id,
        "egp_id": egp_id,
        "duplicate_of": task["duplicate_of"],
        "record": task["record"],
        **(
            {"phase1_mapping": task["phase1_mapping"], "examples": task["examples"]}
            if phase == 2 else {}
        ),
    }
    scientific_inputs = declared_hashes(
        [
            repo_path(config["model_config"]),
            repo_path(config["schema"]),
            repo_path(config["rulebook"]),
            repo_path(config["prompt_wrapper"]),
            repo_path(config[f"phase{phase}_prompt"]),
            repo_path(config["output_schema"]),
            repo_path(config["annotation_instructions"]),
            repo_path(config["artifact_hashes"]),
        ]
    )
    implementation = declared_hashes(
        [
            Path(__file__),
            ROOT / "shared/utils/model_backend.py",
            ROOT / "shared/utils/model_units.py",
            repo_path(config["validator"]),
        ]
    )
    expected_invocation = invocation_reuse_key(
        prompt=prompt,
        config=config,
        scientific_inputs=scientific_inputs,
        implementation=implementation,
    )
    unit_dir = output / "units" / unit_id / f"phase{phase}"
    if unit_dir.exists():
        if completed_model_unit(unit_dir, unit_input, expected_invocation):
            recorded_mapping = read_json(unit_dir / "parsed_output.json")
            # Reparse the verbatim response so insertion order is the same as
            # on the original invocation. Parsed JSON is written with sorted
            # keys; using it directly would reorder Phase 1 inside the Phase 2
            # prompt and make an otherwise identical Phase 2 look different.
            mapping, reuse_errors = parse_raw(
                (unit_dir / "raw_output.txt").read_text(encoding="utf-8")
            )
            if mapping is not None:
                reuse_errors.extend(validate_mapping(mapping, egp_id, phase=phase))
                if phase == 2:
                    reuse_errors.extend(validate_transition(task["phase1_mapping"], mapping))
            if mapping is None or reuse_errors or mapping != recorded_mapping:
                raise RuntimeError(
                    f"completed normalization evidence no longer reparses identically: {unit_dir}; "
                    f"errors={reuse_errors}"
                )
            invocation = read_json(unit_dir / "invocation.json")
            return {
                "unit_id": unit_id,
                "egp_id": egp_id,
                "duplicate_of": task["duplicate_of"],
                "mapping": mapping,
                "parsed_path": unit_dir / "parsed_output.json",
                "successful_attempt": invocation.get("attempt", 1),
                "unit_reused": True,
            }
        raise RuntimeError(
            f"normalization unit is incomplete or has different input/methodology: {unit_dir}; "
            "use a new experiment ID or run-one --force"
        )
    begin_model_unit(unit_dir, unit_input)
    parsed_path = unit_dir / "parsed_output.json"
    attempt_errors: list[list[str]] = []
    last_attempt_dir: Path | None = None
    for attempt in range(1, int(config["max_attempts"]) + 1):
        stem = f"{unit_id}.phase{phase}.attempt-{attempt:02d}"
        attempt_dir = begin_attempt(unit_dir, attempt)
        last_attempt_dir = attempt_dir
        raw_path = attempt_dir / "raw_output.txt"
        result = backend.invoke(
            prompt=prompt,
            output_schema=repo_path(config["output_schema"]),
            instructions=repo_path(config["annotation_instructions"]),
            raw_path=raw_path,
            log_dir=attempt_dir,
            stem=stem,
            config=config,
            context={
                "phase": phase,
                "unit_id": unit_id,
                "egp_id": egp_id,
                "attempt": attempt,
                "selection_or_duplicate_metadata_exposed": False,
                "other_descriptors_or_mappings_exposed": False,
                "examples_exposed": phase == 2,
                "parent_rewrite_or_adjudication": False,
                "scientific_inputs": scientific_inputs,
                "implementation": implementation,
            },
            invocation_dir=attempt_dir,
        )
        errors: list[str] = []
        mapping = None
        transition_errors: list[str] = []
        if result.returncode != 0:
            errors.append(f"codex exited {result.returncode}")
        elif not raw_path.is_file():
            errors.append("backend produced no final raw output")
        else:
            mapping, errors = parse_raw(raw_path.read_text(encoding="utf-8"))
            if mapping is not None:
                errors.extend(validate_mapping(mapping, egp_id, phase=phase))
                if phase == 2:
                    transition_errors = validate_transition(task["phase1_mapping"], mapping)
                    errors.extend(transition_errors)
        validation = {
            "valid": not errors,
            "errors": errors,
            "transition_errors": transition_errors,
            "validator": str(repo_path(config["validator"])),
        }
        finish_attempt(attempt_dir, parsed=mapping, validation=validation)
        metadata = read_json(result.metadata_path)
        metadata["attempt"] = attempt
        metadata["validation"] = validation
        write_json(result.metadata_path, metadata)
        attempt_errors.append(errors)
        if mapping is not None and not errors:
            select_attempt(unit_dir, attempt_dir)
            return {
                "unit_id": unit_id,
                "egp_id": egp_id,
                "duplicate_of": task["duplicate_of"],
                "mapping": mapping,
                "parsed_path": parsed_path,
                "successful_attempt": attempt,
                "unit_reused": False,
            }
    if last_attempt_dir is not None:
        select_attempt(unit_dir, last_attempt_dir)
    raise RuntimeError(f"{phase=} {unit_id} exhausted attempts: {attempt_errors}")


def _run_phase(
    tasks: list[dict[str, Any]],
    *,
    phase: int,
    config: dict[str, Any],
    output: Path,
    validator: Any,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, int(config["workers"]))) as pool:
        futures = {
            pool.submit(
                _annotate,
                phase=phase,
                task=task,
                config=config,
                output=output,
                parse_raw=validator.parse_raw_mapping,
                validate_mapping=validator.validate_mapping,
                validate_transition=validator.validate_phase2_transition,
            ): task
            for task in tasks
        }
        for future in as_completed(futures):
            row = future.result()
            results.append(row)
            print(f"normalization phase{phase} {row['unit_id']} valid", flush=True)
    by_unit = {row["unit_id"]: row for row in results}
    return [by_unit[task["unit_id"]] for task in tasks]


def run_stage(run_dir: Path, config: dict[str, Any], experiment_manifest: Path, command: list[str]) -> None:
    started = utc_now()
    output = run_dir / "normalization"
    prepare_stage_directory(output)
    _verify_frozen_artifacts(repo_path(config["artifact_hashes"]))
    validator_path = repo_path(config["validator"])
    validator = _load_validator(validator_path)
    source_dir = run_dir / "source"
    source_subset = source_dir / "source_subset.jsonl"
    phase1_records_path = source_dir / "phase1_records.jsonl"
    units_path = source_dir / "annotation_units.jsonl"
    validate_jsonl(
        source_subset,
        ROOT / "modules/stage_1_source/schemas/source_descriptor.schema.json",
        label="normalization input SourceDescriptor",
    )
    records = {row["egp_id"]: row for row in read_jsonl(phase1_records_path)}
    source_records = {row["egp_id"]: row for row in read_jsonl(source_subset)}
    units = read_jsonl(units_path)
    phase1_tasks = [{**unit, "record": records[unit["egp_id"]]} for unit in units]
    phase1 = _run_phase(phase1_tasks, phase=1, config=config, output=output, validator=validator)
    phase1_by_unit = {row["unit_id"]: row for row in phase1}
    phase2_tasks = []
    for task in phase1_tasks:
        first = phase1_by_unit[task["unit_id"]]
        if first["mapping"]["result"] not in {"partial", "unresolved"}:
            continue
        phase2_tasks.append(
            {
                **task,
                "phase1_mapping": first["mapping"],
                "examples": source_records[task["egp_id"]].get("examples", []),
            }
        )
    phase2 = _run_phase(phase2_tasks, phase=2, config=config, output=output, validator=validator)
    phase2_by_unit = {row["unit_id"]: row for row in phase2}

    phase1_path = output / "phase1.jsonl"
    phase2_path = output / "phase2.jsonl"
    phase1_index = output / "phase1_index.jsonl"
    phase2_index = output / "phase2_index.jsonl"
    routed_path = output / "routed_units.jsonl"
    write_jsonl(phase1_path, [row["mapping"] for row in phase1], sort_keys=False)
    write_jsonl(phase2_path, [row["mapping"] for row in phase2], sort_keys=False)
    write_jsonl(
        phase1_index,
        [
            {
                "unit_id": row["unit_id"],
                "egp_id": row["egp_id"],
                "duplicate_of": row["duplicate_of"],
                "successful_attempt": row["successful_attempt"],
                "parsed_sha256": sha256_file(row["parsed_path"]),
            }
            for row in phase1
        ],
    )
    write_jsonl(
        phase2_index,
        [
            {
                "unit_id": row["unit_id"],
                "egp_id": row["egp_id"],
                "duplicate_of": row["duplicate_of"],
                "successful_attempt": row["successful_attempt"],
                "phase1_sha256": sha256_file(phase1_by_unit[row["unit_id"]]["parsed_path"]),
                "parsed_sha256": sha256_file(row["parsed_path"]),
            }
            for row in phase2
        ],
    )
    write_jsonl(
        routed_path,
        [{key: task[key] for key in ("unit_id", "egp_id", "duplicate_of")} for task in phase2_tasks],
    )
    duplicate_diagnostics = []
    for unit in units:
        original = unit["duplicate_of"]
        if original is None:
            continue
        duplicate = unit["unit_id"]
        original_routed = original in phase2_by_unit
        duplicate_routed = duplicate in phase2_by_unit
        duplicate_diagnostics.append(
            {
                "original_unit_id": original,
                "duplicate_unit_id": duplicate,
                "egp_id": unit["egp_id"],
                "phase1_exact_match": phase1_by_unit[original]["mapping"] == phase1_by_unit[duplicate]["mapping"],
                "phase1_results": [
                    phase1_by_unit[original]["mapping"]["result"],
                    phase1_by_unit[duplicate]["mapping"]["result"],
                ],
                "routing_match": original_routed == duplicate_routed,
                "phase2_exact_match": (
                    phase2_by_unit[original]["mapping"] == phase2_by_unit[duplicate]["mapping"]
                    if original_routed and duplicate_routed
                    else None
                ),
            }
        )
    duplicate_path = output / "duplicate_diagnostics.jsonl"
    write_jsonl(duplicate_path, duplicate_diagnostics)

    primary_units = [unit for unit in units if unit["duplicate_of"] is None]
    final_rows = []
    provenance = []
    for unit in primary_units:
        unit_id = unit["unit_id"]
        first = phase1_by_unit[unit_id]
        second = phase2_by_unit.get(unit_id)
        final = second or first
        final_rows.append(final["mapping"])
        provenance.append(
            {
                "egp_id": unit["egp_id"],
                "primary_unit_id": unit_id,
                "final_phase": 2 if second else 1,
                "phase1_sha256": sha256_file(first["parsed_path"]),
                "phase2_sha256": sha256_file(second["parsed_path"]) if second else None,
            }
        )
    if len(final_rows) != 139:
        raise RuntimeError(f"expected 139 primary final mappings, got {len(final_rows)}")
    for mapping in final_rows:
        phase = next(row["final_phase"] for row in provenance if row["egp_id"] == mapping["egp_id"])
        errors = validator.validate_mapping(mapping, mapping["egp_id"], phase=phase)
        if errors:
            raise RuntimeError(f"invalid final mapping {mapping['egp_id']}: {errors}")

    final_path = output / "final_mappings.jsonl"
    complete_path = output / "complete.jsonl"
    partial_path = output / "partial.jsonl"
    oos_path = output / "out_of_scope.jsonl"
    unresolved_path = output / "unresolved.jsonl"
    failures_path = output / "schema_failures.jsonl"
    provenance_path = output / "mapping_provenance.jsonl"
    write_jsonl(final_path, final_rows, sort_keys=False)
    write_jsonl(complete_path, [row for row in final_rows if row["result"] == "complete"], sort_keys=False)
    write_jsonl(partial_path, [row for row in final_rows if row["result"] == "partial"], sort_keys=False)
    write_jsonl(oos_path, [row for row in final_rows if row["result"] == "out_of_scope"], sort_keys=False)
    write_jsonl(unresolved_path, [row for row in final_rows if row["result"] == "unresolved"], sort_keys=False)
    write_jsonl(failures_path, [row for row in final_rows if row["result"] == "schema_failure"], sort_keys=False)
    write_jsonl(provenance_path, provenance)
    try:
        codex_version = subprocess.check_output(["codex", "--version"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        codex_version = "unknown"
    result_counts = {name: sum(row["result"] == name for row in final_rows) for name in sorted(validator.RESULTS)}
    config_paths = [
        experiment_manifest,
        repo_path(config["schema"]),
        repo_path(config["output_schema"]),
        repo_path(config["rulebook"]),
        repo_path(config["prompt_wrapper"]),
        repo_path(config["phase1_prompt"]),
        repo_path(config["phase2_prompt"]),
        repo_path(config["annotation_instructions"]),
        repo_path(config["artifact_hashes"]),
    ]
    outputs = [
        phase1_path,
        phase2_path,
        phase1_index,
        phase2_index,
        routed_path,
        duplicate_path,
        final_path,
        complete_path,
        partial_path,
        oos_path,
        unresolved_path,
        failures_path,
        provenance_path,
        output / "units",
    ]
    write_stage_manifest(
        output,
        module="normalization",
        version=config["version"],
        started_utc=started,
        command=command,
        inputs=[source_subset, phase1_records_path, units_path],
        configs=config_paths,
        code=[Path(__file__), ROOT / "shared" / "utils" / "model_backend.py", validator_path],
        outputs=outputs,
        details={
            "backend": config["backend"],
            "transport": "codex-cli exec",
            "codex_cli_version": codex_version,
            "model": config["model"],
            "reasoning_effort": config["reasoning_effort"],
            "model_snapshot_pinned": False,
            "decoding_parameters_pinned": False,
            "workers": config["workers"],
            "max_attempts": config["max_attempts"],
            "fresh_process_per_annotation": True,
            "phase1_units": len(phase1),
            "phase2_units": len(phase2),
            "unit_level_reuse": sum(bool(row.get("unit_reused")) for row in (*phase1, *phase2)),
            "duplicate_pairs": len(duplicate_diagnostics),
            "duplicate_results_are_diagnostic_only": True,
            "final_result_counts": result_counts,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run normalization on a small explicit JSONL fixture set.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--experiment", "--config", dest="experiment", default="current")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--phase1-only", action="store_true")
    args = parser.parse_args()
    from shared.utils.config import resolve_experiment

    config = resolve_experiment(args.experiment).resolved["normalization"]
    _verify_frozen_artifacts(repo_path(config["artifact_hashes"]))
    validator = _load_validator(repo_path(config["validator"]))
    output = args.output or Path(tempfile.mkdtemp(prefix="grammar-kt-normalization-fixtures-"))
    if args.output:
        prepare_stage_directory(output)
    records = read_jsonl(args.input.resolve())
    results = []
    for index, record in enumerate(records, 1):
        unit_id = f"fixture_{index:03d}"
        projected = {
            key: record.get(key)
            for key in ("egp_id", "supercategory", "subcategory", "guideword", "can_do")
        }
        task = {"unit_id": unit_id, "egp_id": record["egp_id"], "duplicate_of": None, "record": projected}
        first = _annotate(
            phase=1, task=task, config=config, output=output,
            parse_raw=validator.parse_raw_mapping,
            validate_mapping=validator.validate_mapping,
            validate_transition=validator.validate_phase2_transition,
        )
        second = None
        if not args.phase1_only and first["mapping"]["result"] in {"partial", "unresolved"}:
            second = _annotate(
                phase=2,
                task={**task, "phase1_mapping": first["mapping"], "examples": record.get("examples", [])},
                config=config,
                output=output,
                parse_raw=validator.parse_raw_mapping,
                validate_mapping=validator.validate_mapping,
                validate_transition=validator.validate_phase2_transition,
            )
        results.append((second or first)["mapping"])
    write_jsonl(output / "final_mappings.jsonl", results, sort_keys=False)
    write_json(
        output / "fixture_summary.json",
        {"input": str(args.input.resolve()), "records": len(records), "output": str(output), "phase1_only": args.phase1_only},
    )
    print(json.dumps({"output": str(output), "records": len(records)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
