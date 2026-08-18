"""Two-phase, fresh-context normalisation with inspectable model evidence."""

from __future__ import annotations

import json
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .backend import get_backend, save_model_result
from .io import read_jsonl, read_yaml, resource, write_json, write_jsonl
from .normalisation_validation import RESULTS, parse_raw_mapping, validate_mapping, validate_phase2_transition


def configured(value: dict[str, Any]) -> dict[str, Any]:
    backend = read_yaml(resource("normalisation", "configs", value.get("backend_config", "backend"), ".yaml"))
    return {**backend, **value}


def render_prompt(phase: int, config: dict[str, Any], task: dict[str, Any]) -> str:
    schema = resource("normalisation", "rules", config["dimensions"], ".txt").read_text(encoding="utf-8")
    rulebook = resource("normalisation", "rules", config["rulebook"], ".md").read_text(encoding="utf-8")
    wrapper = resource("normalisation", "prompts", config["wrapper"], ".txt").read_text(encoding="utf-8")
    template = resource("normalisation", "prompts", config[f"phase{phase}_prompt"], ".txt").read_text(encoding="utf-8")
    values = {"schema": schema, "rulebook": rulebook, "phase": str(phase), "record": json.dumps(task["record"], ensure_ascii=False, separators=(",", ":"))}
    if phase == 2:
        values.update({
            "phase1_mapping": json.dumps(task["phase1_mapping"], ensure_ascii=False, separators=(",", ":")),
            "examples": json.dumps(task["examples"], ensure_ascii=False, separators=(",", ":")),
        })
    for key, replacement in values.items():
        wrapper = wrapper.replace("{{" + key + "}}", replacement)
        template = template.replace("{{" + key + "}}", replacement)
        wrapper = wrapper.replace("{" + key + "}", replacement)
        template = template.replace("{" + key + "}", replacement)
    unresolved = [part.split("}}", 1)[0] for part in (wrapper + template).split("{{")[1:]]
    if unresolved:
        raise ValueError(f"unresolved prompt placeholders: {unresolved}")
    return wrapper + template


def invoke_phase(phase: int, task: dict[str, Any], config: dict[str, Any], unit_root: Path) -> dict[str, Any]:
    prompt = render_prompt(phase, config, task)
    phase_dir = unit_root / f"phase{phase}"
    phase_dir.mkdir(parents=True, exist_ok=False)
    attempts = []
    for number in range(1, int(config.get("max_attempts", 2)) + 1):
        attempt = phase_dir / f"attempt-{number:02d}"
        write_json(attempt / "input.json", {
            "phase": phase,
            "unit_id": task["unit_id"],
            "egp_id": task["egp_id"],
            "record": task["record"],
            **({"phase1_mapping": task["phase1_mapping"], "examples": task["examples"]} if phase == 2 else {}),
        })
        result = get_backend(config["backend"]).invoke(
            prompt=prompt,
            output_schema=resource("normalisation", "configs", config["output_schema"], ".json"),
            instructions=resource("normalisation", "rules", config["instructions"], ".md"),
            unit_dir=attempt,
            config=config,
        )
        mapping, errors = parse_raw_mapping(result.raw_path.read_text(encoding="utf-8"))
        if result.returncode:
            errors.append(f"backend exited {result.returncode}")
        if mapping is not None:
            errors.extend(validate_mapping(mapping, task["egp_id"], phase=phase))
            if phase == 2:
                errors.extend(validate_phase2_transition(task["phase1_mapping"], mapping))
        save_model_result(attempt, mapping, errors)
        attempts.append({"attempt": number, "valid": not errors, "errors": errors})
        if mapping is not None and not errors:
            result_row = {"mapping": mapping, "selected_attempt": number, "attempts": attempts}
            write_json(phase_dir / "result.json", result_row)
            return result_row
    raise RuntimeError(f"normalisation {task['unit_id']} phase {phase} exhausted attempts: {attempts}")


def normalise_one(record: dict[str, Any], config: dict[str, Any], *, output: Path | None = None,
                  phase1_only: bool = False, unit_id: str | None = None) -> dict[str, Any]:
    config = configured(config)
    output = output or Path(tempfile.mkdtemp(prefix="grammar-kt-normalisation-"))
    unit = unit_id or str(record["egp_id"])
    unit_root = output / "units" / unit
    projected = {key: record.get(key) for key in ("egp_id", "supercategory", "subcategory", "guideword", "can_do")}
    task = {"unit_id": unit, "egp_id": record["egp_id"], "record": projected}
    first = invoke_phase(1, task, config, unit_root)
    second = None
    if not phase1_only and first["mapping"]["result"] in {"partial", "unresolved"}:
        second = invoke_phase(2, {**task, "phase1_mapping": first["mapping"], "examples": record.get("examples", [])}, config, unit_root)
    result = {
        "input": record,
        "phase1": first["mapping"],
        "phase2_routing_reason": (
            f"phase1 result was {first['mapping']['result']}" if second else
            "phase1-only requested" if phase1_only else
            f"phase1 result {first['mapping']['result']} does not route to phase2"
        ),
        "phase2": second["mapping"] if second else None,
        "output": (second or first)["mapping"],
        "evidence_directory": str(unit_root),
    }
    write_json(unit_root / "result.json", result)
    return result


def run(run_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    output = run_dir / "normalisation"
    output.mkdir(parents=True, exist_ok=False)
    source = {row["egp_id"]: row for row in read_jsonl(run_dir / "source" / "source_subset.jsonl")}
    phase1 = {row["egp_id"]: row for row in read_jsonl(run_dir / "source" / "phase1_records.jsonl")}
    units = read_jsonl(run_dir / "source" / "annotation_units.jsonl")
    jobs = [(unit, {**source[unit["egp_id"]], **phase1[unit["egp_id"]]}) for unit in units]
    results: list[tuple[dict[str, Any], dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=max(1, int(config.get("workers", 3)))) as pool:
        futures = {
            pool.submit(normalise_one, record, config, output=output, unit_id=unit["unit_id"]): unit
            for unit, record in jobs
        }
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
