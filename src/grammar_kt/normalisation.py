"""Two-phase, fresh-context normalisation with inspectable model evidence."""

from __future__ import annotations

import json
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .backend import invoke_model, save_model_result
from .io import ROOT, read_jsonl, read_yaml, repo_path, write_json, write_jsonl
from .normalisation_validation import RESULTS, parse_raw_mapping, validate_mapping, validate_phase2_transition


NORMALISATION_DIR = ROOT / "modules" / "normalisation"
WRAPPER = NORMALISATION_DIR / "prompts" / "wrapper.txt"
GRAMMAR_DIMENSIONS = NORMALISATION_DIR / "rules" / "grammar_dimensions.txt"
RULEBOOK = NORMALISATION_DIR / "rules" / "rulebook.md"
MODEL_INSTRUCTIONS = NORMALISATION_DIR / "rules" / "model_instructions.md"
OUTPUT_SCHEMA = NORMALISATION_DIR / "configs" / "mapping_schema.json"
PHASE1_FIELDS = ("egp_id", "supercategory", "subcategory", "guideword", "can_do")


def _fill_prompt(template: str, values: dict[str, str]) -> str:
    for key, replacement in values.items():
        template = template.replace("{{" + key + "}}", replacement)
        template = template.replace("{" + key + "}", replacement)
    unresolved = [part.split("}}", 1)[0] for part in template.split("{{")[1:]]
    if unresolved:
        raise ValueError(f"unresolved prompt placeholders: {unresolved}")
    return template


def _prompt_wrapper(phase: int) -> str:
    values = {
        "schema": GRAMMAR_DIMENSIONS.read_text(encoding="utf-8"),
        "rulebook": RULEBOOK.read_text(encoding="utf-8"),
        "phase": str(phase),
    }
    return _fill_prompt(WRAPPER.read_text(encoding="utf-8"), values)


def render_phase1_prompt(record: dict[str, Any], template: str) -> str:
    values = {"record": json.dumps(record, ensure_ascii=False, separators=(",", ":"))}
    return _prompt_wrapper(1) + _fill_prompt(template, values)


def render_phase2_prompt(
    record: dict[str, Any],
    phase1_mapping: dict[str, Any],
    examples: list[Any],
    template: str,
) -> str:
    values = {
        "record": json.dumps(record, ensure_ascii=False, separators=(",", ":")),
        "phase1_mapping": json.dumps(phase1_mapping, ensure_ascii=False, separators=(",", ":")),
        "examples": json.dumps(examples, ensure_ascii=False, separators=(",", ":")),
    }
    return _prompt_wrapper(2) + _fill_prompt(template, values)


def _invoke_mapping(
    *,
    phase: int,
    unit_id: str,
    egp_id: str,
    prompt: str,
    evidence_input: dict[str, Any],
    unit_root: Path,
    backend_settings: dict[str, Any],
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
            settings=backend_settings,
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


def run_phase1(
    record: dict[str, Any],
    *,
    unit_id: str,
    unit_root: Path,
    prompt_template: str,
    backend_settings: dict[str, Any],
    max_attempts: int,
) -> dict[str, Any]:
    prompt = render_phase1_prompt(record, prompt_template)
    return _invoke_mapping(
        phase=1,
        unit_id=unit_id,
        egp_id=record["egp_id"],
        prompt=prompt,
        evidence_input={"egp_id": record["egp_id"], "record": record},
        unit_root=unit_root,
        backend_settings=backend_settings,
        max_attempts=max_attempts,
    )


def run_phase2(
    record: dict[str, Any],
    phase1_mapping: dict[str, Any],
    examples: list[Any],
    *,
    unit_id: str,
    unit_root: Path,
    prompt_template: str,
    backend_settings: dict[str, Any],
    max_attempts: int,
) -> dict[str, Any]:
    prompt = render_phase2_prompt(record, phase1_mapping, examples, prompt_template)
    return _invoke_mapping(
        phase=2,
        unit_id=unit_id,
        egp_id=record["egp_id"],
        prompt=prompt,
        evidence_input={
            "egp_id": record["egp_id"],
            "record": record,
            "phase1_mapping": phase1_mapping,
            "examples": examples,
        },
        unit_root=unit_root,
        backend_settings=backend_settings,
        max_attempts=max_attempts,
        phase1_mapping=phase1_mapping,
    )


def normalise_record(
    record: dict[str, Any],
    *,
    unit_id: str,
    output: Path,
    phase1_template: str,
    phase2_template: str,
    backend_settings: dict[str, Any],
    max_attempts: int,
    phase1_only: bool = False,
) -> dict[str, Any]:
    unit_root = output / "units" / unit_id
    phase1_record = {key: record.get(key) for key in PHASE1_FIELDS}
    first = run_phase1(
        phase1_record,
        unit_id=unit_id,
        unit_root=unit_root,
        prompt_template=phase1_template,
        backend_settings=backend_settings,
        max_attempts=max_attempts,
    )
    second = None
    if not phase1_only and first["mapping"]["result"] == "partial":
        second = run_phase2(
            phase1_record,
            first["mapping"],
            record.get("examples", []),
            unit_id=unit_id,
            unit_root=unit_root,
            prompt_template=phase2_template,
            backend_settings=backend_settings,
            max_attempts=max_attempts,
        )
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


def normalise_one(
    record: dict[str, Any],
    settings: dict[str, Any],
    *,
    output: Path | None = None,
    phase1_only: bool = False,
    unit_id: str | None = None,
) -> dict[str, Any]:
    """Convenience adapter for scripts: load settings, then normalise one record."""

    return normalise_record(
        record,
        unit_id=unit_id or str(record["egp_id"]),
        output=output or Path(tempfile.mkdtemp(prefix="grammar-kt-normalisation-")),
        phase1_template=repo_path(settings["phase1_prompt"]).read_text(encoding="utf-8"),
        phase2_template=repo_path(settings["phase2_prompt"]).read_text(encoding="utf-8"),
        backend_settings=read_yaml(settings["backend"]),
        max_attempts=int(settings.get("max_attempts", 2)),
        phase1_only=phase1_only,
    )


def run(run_dir: Path, settings: dict[str, Any]) -> dict[str, Any]:
    output = run_dir / "normalisation"
    output.mkdir(parents=True, exist_ok=False)
    source = {row["egp_id"]: row for row in read_jsonl(run_dir / "source" / "source_subset.jsonl")}
    phase1 = {row["egp_id"]: row for row in read_jsonl(run_dir / "source" / "phase1_records.jsonl")}
    units = read_jsonl(run_dir / "source" / "annotation_units.jsonl")

    phase1_template = repo_path(settings["phase1_prompt"]).read_text(encoding="utf-8")
    phase2_template = repo_path(settings["phase2_prompt"]).read_text(encoding="utf-8")
    backend_settings = read_yaml(settings["backend"])
    max_attempts = int(settings.get("max_attempts", 2))

    results: list[tuple[dict[str, Any], dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=max(1, int(settings.get("workers", 3)))) as pool:
        futures = {}
        for unit in units:
            record = {**source[unit["egp_id"]], **phase1[unit["egp_id"]]}
            future = pool.submit(
                normalise_record,
                record,
                unit_id=unit["unit_id"],
                output=output,
                phase1_template=phase1_template,
                phase2_template=phase2_template,
                backend_settings=backend_settings,
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
    return {"records": len(final), "result_counts": counts}
