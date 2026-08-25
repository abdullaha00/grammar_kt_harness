"""Two-phase, fresh-context normalisation with inspectable model evidence."""

from __future__ import annotations

import json
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from ..backend import invoke_model, save_model_result
from ..io import ROOT, read_jsonl, read_yaml, repo_path, write_json, write_jsonl
from .normalisation_validation import RESULTS, parse_raw_mapping, validate_mapping, validate_phase2_transition
from .normalisation_reliability import analyse_repeated_normalisations
from .schema import prompt_declaration


NORMALISATION_DIR = ROOT / "modules" / "grammar" / "normalisation"
WRAPPER = NORMALISATION_DIR / "prompts" / "wrapper.txt"
RULEBOOK = NORMALISATION_DIR / "rules" / "rulebook.md"
MODEL_INSTRUCTIONS = NORMALISATION_DIR / "rules" / "model_instructions.md"
OUTPUT_SCHEMA = NORMALISATION_DIR / "configs" / "mapping_schema.json"
PHASE1_FIELDS = ("egp_id", "supercategory", "subcategory", "guideword", "can_do")


# Model invocation and validation

def invoke_and_validate(
    *,
    phase: int,
    unit_id: str,
    egp_id: str,
    prompt: str,
    evidence_input: dict[str, Any],
    unit_root: Path,
    backend_config: dict[str, Any],
    max_attempts: int,
    phase1_mapping: dict[str, Any] | None = None,
) -> dict[str, Any]:
    phase_dir = unit_root / f"phase{phase}"
    phase_dir.mkdir(parents=True, exist_ok=False)
    attempts = []
    for number in range(1, max_attempts + 1):
        attempt = phase_dir / f"attempt-{number:02d}"
        write_json(attempt / "input.json", {"phase": phase, "unit_id": unit_id, **evidence_input})
        raw_path, returncode = invoke_model(
            prompt=prompt,
            output_schema=OUTPUT_SCHEMA,
            instructions=MODEL_INSTRUCTIONS,
            unit_dir=attempt,
            backend_config=backend_config,
        )
        mapping, errors = parse_raw_mapping(raw_path.read_text(encoding="utf-8"))
        if returncode:
            errors.append(f"backend exited {returncode}")
        if mapping is not None:
            errors.extend(validate_mapping(mapping, egp_id, phase=phase))
            if phase1_mapping is not None:
                errors.extend(validate_phase2_transition(phase1_mapping, mapping))
        save_model_result(attempt, mapping, errors)
        attempts.append({"attempt": number, "valid": not errors, "errors": errors})
        if mapping is not None and not errors:
            result = {"mapping": mapping, "selected_attempt": number, "attempts": attempts}
            write_json(phase_dir / "result.json", result)
            return result
    raise RuntimeError(f"normalisation {unit_id} phase {phase} exhausted attempts: {attempts}")


def normalise_one(
    record: dict[str, Any],
    *,
    phase1_template: str,
    phase2_template: str,
    backend_config: dict[str, Any],
    max_attempts: int,
    output: Path | None = None,
    phase1_only: bool = False,
    unit_id: str | None = None,
) -> dict[str, Any]:
    """Execute the two-phase method for one descriptor in fresh model contexts."""

    selected_unit_id = unit_id or str(record["egp_id"])
    selected_output = output or Path(tempfile.mkdtemp(prefix="grammar-kt-normalisation-"))
    unit_root = selected_output / "units" / selected_unit_id

    # Phase 1: descriptor evidence only
    phase1_record = {key: record.get(key) for key in PHASE1_FIELDS}
    method_context = WRAPPER.read_text(encoding="utf-8")
    for key, replacement in {
        "schema": prompt_declaration(),
        "rulebook": RULEBOOK.read_text(encoding="utf-8"),
        "phase": "1",
    }.items():
        method_context = method_context.replace("{{" + key + "}}", replacement)
        method_context = method_context.replace("{" + key + "}", replacement)
    phase1_prompt = phase1_template
    phase1_json = json.dumps(phase1_record, ensure_ascii=False, separators=(",", ":"))
    phase1_prompt = phase1_prompt.replace("{{record}}", phase1_json).replace("{record}", phase1_json)
    unresolved = [part.split("}}", 1)[0] for part in (method_context + phase1_prompt).split("{{")[1:]]
    if unresolved:
        raise ValueError(f"unresolved prompt placeholders: {unresolved}")
    first = invoke_and_validate(
        phase=1,
        unit_id=selected_unit_id,
        egp_id=phase1_record["egp_id"],
        prompt=method_context + phase1_prompt,
        evidence_input={"egp_id": phase1_record["egp_id"], "record": phase1_record},
        unit_root=unit_root,
        backend_config=backend_config,
        max_attempts=max_attempts,
    )

    # Phase 2: examples may refine only an eligible part of a partial mapping
    second = None
    if not phase1_only and first["mapping"]["result"] == "partial":
        examples = record.get("examples", [])
        method_context = WRAPPER.read_text(encoding="utf-8")
        for key, replacement in {
            "schema": prompt_declaration(),
            "rulebook": RULEBOOK.read_text(encoding="utf-8"),
            "phase": "2",
        }.items():
            method_context = method_context.replace("{{" + key + "}}", replacement)
            method_context = method_context.replace("{" + key + "}", replacement)
        phase2_prompt = phase2_template
        for key, value in {
            "record": phase1_record,
            "phase1_mapping": first["mapping"],
            "examples": examples,
        }.items():
            replacement = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            phase2_prompt = phase2_prompt.replace("{{" + key + "}}", replacement)
            phase2_prompt = phase2_prompt.replace("{" + key + "}", replacement)
        unresolved = [part.split("}}", 1)[0] for part in (method_context + phase2_prompt).split("{{")[1:]]
        if unresolved:
            raise ValueError(f"unresolved prompt placeholders: {unresolved}")
        second = invoke_and_validate(
            phase=2,
            unit_id=selected_unit_id,
            egp_id=phase1_record["egp_id"],
            prompt=method_context + phase2_prompt,
            evidence_input={
                "egp_id": phase1_record["egp_id"],
                "record": phase1_record,
                "phase1_mapping": first["mapping"],
                "examples": examples,
            },
            unit_root=unit_root,
            backend_config=backend_config,
            max_attempts=max_attempts,
            phase1_mapping=first["mapping"],
        )

    # Final mapping and retained evidence
    result = {
        "input": record,
        "phase1": first["mapping"],
        "phase2_routing_reason": (
            "phase1 result was partial"
            if second
            else "phase1-only requested"
            if phase1_only
            else f"phase1 result {first['mapping']['result']} does not route to phase2"
        ),
        "phase2": second["mapping"] if second else None,
        "output": (second or first)["mapping"],
        "evidence_directory": str(unit_root),
    }
    write_json(unit_root / "result.json", result)
    return result


# Full stage

def run(run_dir: Path, settings: dict[str, Any]) -> dict[str, Any]:
    output = run_dir / "normalisation"
    output.mkdir(parents=True, exist_ok=False)
    source = {row["egp_id"]: row for row in read_jsonl(run_dir / "source" / "source_subset.jsonl")}
    phase1 = {row["egp_id"]: row for row in read_jsonl(run_dir / "source" / "phase1_records.jsonl")}
    units = read_jsonl(run_dir / "source" / "annotation_units.jsonl")

    phase1_template = repo_path(settings["phase1_prompt"]).read_text(encoding="utf-8")
    phase2_template = repo_path(settings["phase2_prompt"]).read_text(encoding="utf-8")
    backend_config = read_yaml(settings["backend_config"])
    max_attempts = int(settings.get("max_attempts", 2))

    results: list[tuple[dict[str, Any], dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=max(1, int(settings.get("workers", 3)))) as pool:
        futures = {}
        for unit in units:
            record = {**source[unit["egp_id"]], **phase1[unit["egp_id"]]}
            future = pool.submit(
                normalise_one,
                record,
                unit_id=unit["unit_id"],
                output=output,
                phase1_template=phase1_template,
                phase2_template=phase2_template,
                backend_config=backend_config,
                max_attempts=max_attempts,
            )
            futures[future] = unit
        for future in as_completed(futures):
            results.append((futures[future], future.result()))

    by_unit = {unit["unit_id"]: result for unit, result in results}
    primary = [unit for unit in units if unit["duplicate_of"] is None]
    final = [by_unit[unit["unit_id"]]["output"] for unit in primary]
    write_jsonl(output / "final_mappings.jsonl", final, sort_keys=False)
    for name in RESULTS:
        write_jsonl(output / f"{name}.jsonl", [row for row in final if row["result"] == name], sort_keys=False)
    counts = {name: sum(row["result"] == name for row in final) for name in sorted(RESULTS)}
    write_json(output / "summary.json", {"records": len(final), "result_counts": counts})
    reliability, comparisons = analyse_repeated_normalisations(units, by_unit)
    write_json(output / "reliability.json", reliability)
    write_jsonl(output / "repeated_comparisons.jsonl", comparisons, sort_keys=False)
    return {
        "records": len(final),
        "result_counts": counts,
        "repeated_pairs": reliability["repeated_pairs"],
    }
