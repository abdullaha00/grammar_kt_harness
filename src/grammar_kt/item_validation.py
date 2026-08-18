"""Deterministic item checks followed by an independent model diagnostic."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .backend import get_backend, save_model_result
from .io import read_json, read_jsonl, read_yaml, resource, write_json, write_jsonl
from .items import item_id, nuisance_signature, render_prompt
from .realisation import realise, validate_spec


ITEM_FIELDS = {
    "item_id", "source_descriptor_ids", "canonical_cell_id", "realization_spec",
    "item_family", "primary_kc_id", "all_kc_ids", "prompt", "target_answer",
    "accepted_answers", "contrast_set_id", "generation_metadata", "validator_results", "provenance",
}
DIAGNOSTIC_FIELDS = {
    "structurally_plausible", "natural", "world_knowledge_required",
    "unsupported_construction", "answer_ambiguity_suspected", "note",
}


def diagnostic_valid(value: Any) -> bool:
    return (
        isinstance(value, dict) and set(value) == DIAGNOSTIC_FIELDS
        and all(isinstance(value[key], bool) for key in DIAGNOSTIC_FIELDS - {"note"})
        and isinstance(value["note"], str)
    )


def deterministic_results(candidates: list[dict[str, Any]], *, cells: dict[str, dict[str, str]],
                          edge_sources: dict[str, set[str]], mappings: dict[str, dict[str, Any]],
                          frames: dict[str, dict[str, Any]], projections: dict[str, list[str]],
                          kc_ids: set[str], template: str) -> list[dict[str, Any]]:
    prompt_counts = Counter(row["prompt"] for row in candidates)
    answer_counts = Counter(row["target_answer"] for row in candidates)
    contrasts: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        if row["contrast_set_id"]:
            contrasts[row["contrast_set_id"]].append(row)
    contrast_errors: dict[str, list[str]] = defaultdict(list)
    for contrast_id, rows in contrasts.items():
        if len(rows) != 2:
            contrast_errors[contrast_id].append("contrast set size is not two")
        elif nuisance_signature(rows[0]["realization_spec"]) != nuisance_signature(rows[1]["realization_spec"]):
            contrast_errors[contrast_id].append("contrast nuisance mismatch")
        elif sum(cells[rows[0]["canonical_cell_id"]][key] != cells[rows[1]["canonical_cell_id"]][key] for key in cells[rows[0]["canonical_cell_id"]]) != 1:
            contrast_errors[contrast_id].append("contrast is not Hamming-one")
    results = []
    for row in candidates:
        errors: list[str] = []
        if set(row) != ITEM_FIELDS or row.get("item_family") != "CONTROLLED_TRANSFORMATION_v0_1":
            errors.append("Item shape/family mismatch")
        if not re.fullmatch(r"ITEM_[A-F0-9]{16}", str(row.get("item_id", ""))):
            errors.append("invalid item ID")
        cell_id, spec = row["canonical_cell_id"], row["realization_spec"]
        cell, frame = cells.get(cell_id), frames.get(spec.get("predicate_frame_id"))
        if cell is None or frame is None or spec.get("canonical_cell_id") != cell_id:
            errors.append("unknown or mismatched cell/frame")
        else:
            if not set(row["source_descriptor_ids"]) <= edge_sources[cell_id] or spec["source_descriptor_id"] not in edge_sources[cell_id]:
                errors.append("source-cell relationship mismatch")
            errors.extend(validate_spec(spec, cell, frame, mappings[spec["source_descriptor_id"]].get("note")))
            derivation = realise(spec, cell, frame)
            if derivation["surface"] != row["target_answer"] or row["accepted_answers"] != [derivation["surface"]]:
                errors.append("target/answer set differs from deterministic singleton")
            if row["prompt"] != render_prompt(template, cell, spec, frame):
                errors.append("prompt differs from selected item-family template")
            expected_end = "?" if cell["clause"].endswith("question") else "."
            punctuation = "a question mark (?)" if expected_end == "?" else "a period (.)"
            if not row["target_answer"].endswith(expected_end) or f"End with exactly {punctuation}" not in row["prompt"]:
                errors.append("exact punctuation constraint missing")
            if frame["complement"] is not None:
                errors.append("free complement/adjunct frame prohibited")
            if cell["voice"] == "passive" and spec["subject"]["text"] != frame["object"]:
                errors.append("passive subject is not the frame patient")
            if cell["clause"] == "imperative" and 'subject="IMPLICIT YOU"' not in row["prompt"]:
                errors.append("imperative implicit-subject cue missing")
        expected_kcs = projections.get(cell_id, [])
        if row["all_kc_ids"] != expected_kcs or not set(expected_kcs) <= kc_ids or row["primary_kc_id"] not in expected_kcs:
            errors.append("KC activation mismatch")
        if row["item_id"] != item_id(row["primary_kc_id"], spec, row["generation_metadata"]["replicate"]):
            errors.append("stable item ID mismatch")
        if prompt_counts[row["prompt"]] != 1 or answer_counts[row["target_answer"]] != 1:
            errors.append("duplicate prompt or target answer")
        errors.extend(contrast_errors.get(row["contrast_set_id"], []))
        results.append({"item_id": row["item_id"], "split": row["generation_metadata"]["split"], "status": "accepted" if not errors else "rejected", "errors": errors})
    return results


def _diagnostic_config(config: dict[str, Any]) -> dict[str, Any]:
    backend = read_yaml(resource("items", "validation", config.get("backend_config", "backend"), ".yaml"))
    return {**backend, **config}


def run_diagnostic(unit: dict[str, Any], item: dict[str, Any], *, root: Path,
                   config: dict[str, Any]) -> dict[str, Any]:
    uid = unit["validation_unit_id"]
    prompt = resource("items", "validation", config["prompt"], ".txt").read_text(encoding="utf-8")
    rendered_item = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    prompt = prompt.replace("{{item}}", rendered_item).replace("{item}", rendered_item)
    attempts = []
    for number in range(1, int(config.get("max_attempts", 2)) + 1):
        attempt = root / uid / f"attempt-{number:02d}"
        write_json(attempt / "input.json", item)
        backend_result = get_backend(config["backend"]).invoke(
            prompt=prompt,
            output_schema=resource("items", "validation", config["output_schema"], ".json"),
            instructions=resource("items", "validation", config["instructions"], ".md"),
            unit_dir=attempt,
            config=config,
        )
        parsed, errors = None, []
        try:
            parsed = json.loads(backend_result.raw_path.read_text(encoding="utf-8"))
            if not diagnostic_valid(parsed):
                errors.append("output failed diagnostic shape/type check")
        except Exception as error:
            errors.append(f"JSON parse error: {error}")
        if backend_result.returncode:
            errors.append(f"backend exited {backend_result.returncode}")
        save_model_result(attempt, parsed, errors)
        attempts.append({"attempt": number, "valid": not errors, "errors": errors})
        if not errors:
            return {"validation_unit_id": uid, "item_id": item["item_id"], "duplicate_of": unit["duplicate_of"], "status": "accepted_output", "successful_attempt": number, "result": parsed, "attempts": attempts}
    return {"validation_unit_id": uid, "item_id": item["item_id"], "duplicate_of": unit["duplicate_of"], "status": "exhausted", "successful_attempt": None, "result": None, "attempts": attempts}


def model_reasons(result: dict[str, Any], expected: dict[str, bool]) -> list[str]:
    labels = {
        "structurally_plausible": "structurally implausible", "natural": "unnatural",
        "world_knowledge_required": "world knowledge required", "unsupported_construction": "unsupported construction",
        "answer_ambiguity_suspected": "answer ambiguity suspected",
    }
    return [f"automated diagnostic: {labels[key]}" for key, value in expected.items() if result.get(key) != value]


def run_validation(items_dir: Path, run_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    output = items_dir / "validation"
    output.mkdir(parents=True, exist_ok=False)
    candidates = read_jsonl(items_dir / "generation" / "candidate_items.jsonl")
    units = read_jsonl(items_dir / "generation" / "validation_units.jsonl")
    projections = read_jsonl(run_dir / "kc" / "cell_kc_projection.jsonl")
    inventory = read_jsonl(run_dir / "kc" / "kc_inventory.jsonl")
    template = resource("items", "families", config["family"], ".txt").read_text(encoding="utf-8")
    lexicon = resource("realisation", "lexicons", config["realisation_lexicon"], ".jsonl")
    frames = {row["predicate_frame_id"]: row for row in read_jsonl(lexicon)}
    cells = {row["canonical_cell_id"]: row["cell"] for row in projections}
    edge_sources = {row["canonical_cell_id"]: set(row["source_descriptor_ids"]) for row in projections}
    mappings = {source_id: {"egp_id": source_id, "note": row.get("source_mapping_notes", {}).get(source_id)} for row in projections for source_id in row["source_descriptor_ids"]}
    hard = deterministic_results(
        candidates, cells=cells, edge_sources=edge_sources, mappings=mappings, frames=frames,
        projections={row["canonical_cell_id"]: row["kc_ids"] for row in projections},
        kc_ids={row["kc_id"] for row in inventory}, template=template,
    )
    write_jsonl(output / "deterministic_results.jsonl", hard)
    hard_by_id = {row["item_id"]: row for row in hard}
    items_by_id = {row["item_id"]: row for row in candidates}
    eligible = {row["item_id"] for row in hard if row["status"] == "accepted"}
    diagnostic_config = _diagnostic_config(config["validation"])
    diagnostics = []
    with ThreadPoolExecutor(max_workers=max(1, int(config["validation"].get("workers", 6)))) as pool:
        futures = [pool.submit(run_diagnostic, unit, items_by_id[unit["item_id"]], root=output / "model_units", config=diagnostic_config) for unit in units if unit["item_id"] in eligible]
        for future in as_completed(futures):
            diagnostics.append(future.result())
    diagnostics.sort(key=lambda row: row["validation_unit_id"])
    if any(row["status"] == "exhausted" for row in diagnostics):
        raise RuntimeError("one or more item diagnostics exhausted all attempts")
    write_jsonl(output / "diagnostics.jsonl", diagnostics)
    diagnostics_by_uid = {row["validation_unit_id"]: row for row in diagnostics}
    primary_uid = {row["item_id"]: row["validation_unit_id"] for row in units if row["duplicate_of"] is None}
    expected = read_json(resource("items", "validation", config["validation"]["rules"], ".json"))["model_acceptance"]
    accepted, rejected, result_rows = [], [], []
    for item in candidates:
        reasons = list(hard_by_id[item["item_id"]]["errors"])
        diagnostic = diagnostics_by_uid.get(primary_uid[item["item_id"]])
        if diagnostic:
            reasons.extend(model_reasons(diagnostic["result"], expected))
        elif not reasons:
            reasons.append("independent automated diagnostic missing")
        final = {**item, "validator_results": {"deterministic": hard_by_id[item["item_id"]], "independent_automated_diagnostic": diagnostic, "automated_not_human_validation": True}}
        (rejected if reasons else accepted).append({"item": final, "reasons": reasons} if reasons else final)
        result_rows.append({"item_id": item["item_id"], "status": "rejected" if reasons else "accepted", "reasons": reasons, "diagnostic_unit_id": diagnostic["validation_unit_id"] if diagnostic else None})
    write_jsonl(output / "accepted_items.jsonl", sorted(accepted, key=lambda row: row["item_id"]))
    write_jsonl(output / "rejected_items.jsonl", rejected)
    write_jsonl(output / "validation_results.jsonl", result_rows)
    return {"candidates": len(candidates), "accepted": len(accepted), "rejected": len(rejected), "diagnostic_units": len(diagnostics)}
