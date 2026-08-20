"""Deterministic item checks followed by an independent model diagnostic."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .backend import invoke_model, save_model_result
from .io import ROOT, read_jsonl, write_json, write_jsonl
from .items import (
    ITEM_FAMILY,
    item_bank_fingerprint,
    item_identity,
    nuisance_signature,
    render_prompt,
)
from .realisation import LEXICON, realise, validate_spec


VALIDATION_DIR = ROOT / "modules" / "items" / "validation"
DIAGNOSTIC_PROMPT = VALIDATION_DIR / "diagnostic_prompt.txt"
DIAGNOSTIC_SCHEMA = VALIDATION_DIR / "diagnostic_schema.json"
DIAGNOSTIC_INSTRUCTIONS = VALIDATION_DIR / "diagnostic_instructions.md"


ITEM_FIELDS = {
    "item_id", "item_opportunity_id", "source_descriptor_ids", "canonical_cell_id",
    "realization_spec", "realization_evidence", "item_family", "prompt",
    "target_answer", "accepted_answers", "contrast_set_id", "generation_metadata",
}
DIAGNOSTIC_FIELDS = {
    "structurally_plausible", "natural", "world_knowledge_required",
    "unsupported_construction", "answer_ambiguity_suspected", "note",
}
GENERATION_FIELDS = {
    "canonical_split",
    "coverage_reasons",
    "deterministic",
}
DIAGNOSTIC_FAILURE_LABELS = {
    "structurally_plausible": "structurally implausible",
    "natural": "unnatural",
    "world_knowledge_required": "world knowledge required",
    "unsupported_construction": "unsupported construction",
    "answer_ambiguity_suspected": "answer ambiguity suspected",
}


# Deterministic acceptance checks

def deterministic_results(
    candidates: list[dict[str, Any]],
    *,
    cells: dict[str, dict[str, str]],
    edge_sources: dict[str, set[str]],
    mappings: dict[str, dict[str, Any]],
    frames: dict[str, dict[str, Any]],
    template: str,
) -> list[dict[str, Any]]:
    prompt_counts = Counter(row["prompt"] for row in candidates)
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
        if set(row) != ITEM_FIELDS or row.get("item_family") != "controlled_transformation":
            errors.append("Item shape/family mismatch")
        if not re.fullmatch(r"ITEM_[A-F0-9]{16}", str(row.get("item_id", ""))):
            errors.append("invalid item ID")
        if not re.fullmatch(r"ITEMOPP_[A-F0-9]{16}", str(row.get("item_opportunity_id", ""))):
            errors.append("invalid item opportunity ID")
        cell_id, spec = row["canonical_cell_id"], row["realization_spec"]
        cell, frame = cells.get(cell_id), frames.get(spec.get("predicate_frame_id"))
        if cell is None or frame is None or spec.get("canonical_cell_id") != cell_id:
            errors.append("unknown or mismatched cell/frame")
        else:
            if not set(row["source_descriptor_ids"]) <= edge_sources[cell_id] or spec["source_descriptor_id"] not in edge_sources[cell_id]:
                errors.append("source-cell relationship mismatch")
            source_note = mappings.get(spec["source_descriptor_id"], {}).get("note")
            errors.extend(validate_spec(spec, cell, frame, source_note))
            derivation = realise(spec, cell, frame)
            if derivation["surface"] != row["target_answer"] or row["accepted_answers"] != [derivation["surface"]]:
                errors.append("target/answer set differs from deterministic singleton")
            evidence = row.get("realization_evidence", {})
            if (
                not isinstance(evidence, dict)
                or set(evidence) != {"operations", "agreement_site", "auxiliary_chain", "coverage_tags"}
                or evidence.get("operations") != derivation["operations"]
                or evidence.get("agreement_site") != derivation["agreement_site"]
                or evidence.get("auxiliary_chain") != derivation["auxiliary_chain"]
                or not isinstance(evidence.get("coverage_tags"), list)
                or evidence.get("coverage_tags") != sorted(set(evidence.get("coverage_tags", [])))
            ):
                errors.append("realization evidence differs from deterministic derivation")
            if row["prompt"] != render_prompt(template, cell, spec, frame):
                errors.append("prompt differs from selected item-family template")
            expected_end = "?" if cell["clause"].endswith("question") else "."
            punctuation = "a question mark (?)" if expected_end == "?" else "a period (.)"
            if not row["target_answer"].endswith(expected_end) or f"End with exactly {punctuation}" not in row["prompt"]:
                errors.append("exact punctuation constraint missing")
            if frame["complement"] is not None and frame["frame_type"] != "copular":
                errors.append("free non-copular complement/adjunct frame prohibited")
            if cell["voice"] == "passive" and spec["subject"]["text"] != frame["object"]:
                errors.append("passive subject is not the frame patient")
            if cell["clause"] == "imperative" and 'subject="IMPLICIT YOU"' not in row["prompt"]:
                errors.append("imperative implicit-subject cue missing")
        metadata = row.get("generation_metadata")
        if (
            not isinstance(metadata, dict)
            or set(metadata) != GENERATION_FIELDS
            or metadata.get("canonical_split") not in {
                "development", "compositional_holdout", "novel_feature_holdout"
            }
            or metadata.get("deterministic") is not True
            or not isinstance(metadata.get("coverage_reasons"), list)
            or not metadata.get("coverage_reasons")
            or metadata.get("coverage_reasons") != sorted(set(metadata.get("coverage_reasons", [])))
        ):
            errors.append("generation metadata mismatch")
        elif row["item_id"] != item_identity(row):
            errors.append("stable item ID mismatch")
        if prompt_counts[row["prompt"]] != 1:
            errors.append("duplicate prompt")
        errors.extend(contrast_errors.get(row["contrast_set_id"], []))
        results.append({"item_id": row["item_id"], "split": row["generation_metadata"]["canonical_split"], "status": "accepted" if not errors else "rejected", "errors": errors})
    return results


# Independent model diagnostic

def run_diagnostic(unit: dict[str, Any], item: dict[str, Any], *, root: Path,
                   prompt_template: str, backend_config: dict[str, Any],
                   max_attempts: int) -> dict[str, Any]:
    uid = unit["validation_unit_id"]
    rendered_item = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    prompt = prompt_template.replace("{{item}}", rendered_item).replace("{item}", rendered_item)
    attempts = []
    for number in range(1, max_attempts + 1):
        attempt = root / uid / f"attempt-{number:02d}"
        write_json(attempt / "input.json", item)
        raw_path, returncode = invoke_model(
            prompt=prompt,
            output_schema=DIAGNOSTIC_SCHEMA,
            instructions=DIAGNOSTIC_INSTRUCTIONS,
            unit_dir=attempt,
            backend_config=backend_config,
        )
        parsed, errors = None, []
        try:
            parsed = json.loads(raw_path.read_text(encoding="utf-8"))
            if not (
                isinstance(parsed, dict)
                and set(parsed) == DIAGNOSTIC_FIELDS
                and all(isinstance(parsed[key], bool) for key in DIAGNOSTIC_FIELDS - {"note"})
                and isinstance(parsed["note"], str)
            ):
                errors.append("output failed diagnostic shape/type check")
        except Exception as error:
            errors.append(f"JSON parse error: {error}")
        if returncode:
            errors.append(f"backend exited {returncode}")
        save_model_result(attempt, parsed, errors)
        attempts.append({"attempt": number, "valid": not errors, "errors": errors})
        if not errors:
            return {"validation_unit_id": uid, "item_id": item["item_id"], "duplicate_of": unit["duplicate_of"], "status": "accepted_output", "successful_attempt": number, "result": parsed, "attempts": attempts}
    return {"validation_unit_id": uid, "item_id": item["item_id"], "duplicate_of": unit["duplicate_of"], "status": "exhausted", "successful_attempt": None, "result": None, "attempts": attempts}


# Full validation stage

def run_validation(
    items_dir: Path,
    run_dir: Path,
    *,
    family_template: str,
    acceptance: dict[str, bool],
    backend_config: dict[str, Any],
    workers: int,
    max_attempts: int,
) -> dict[str, Any]:
    output = items_dir / "validation"
    output.mkdir(parents=True, exist_ok=False)
    candidates = read_jsonl(items_dir / "generation" / "candidate_items.jsonl")
    units = read_jsonl(items_dir / "generation" / "validation_units.jsonl")
    canonical_rows = read_jsonl(run_dir / "canonical" / "canonical_cells.jsonl")
    frames = {row["predicate_frame_id"]: row for row in read_jsonl(LEXICON)}
    cells = {row["canonical_cell_id"]: row["cell"] for row in canonical_rows}
    edge_sources = {
        row["canonical_cell_id"]: set(row["source_descriptor_ids"])
        for row in canonical_rows
    }
    mappings = {
        source_id: {"egp_id": source_id, "note": row["source_mapping_notes"][source_id]}
        for row in canonical_rows
        for source_id in row["source_descriptor_ids"]
    }
    hard = deterministic_results(
        candidates,
        cells=cells,
        edge_sources=edge_sources,
        mappings=mappings,
        frames=frames,
        template=family_template,
    )
    write_jsonl(output / "deterministic_results.jsonl", hard)
    hard_by_id = {row["item_id"]: row for row in hard}
    items_by_id = {row["item_id"]: row for row in candidates}
    eligible = {row["item_id"] for row in hard if row["status"] == "accepted"}
    prompt_template = DIAGNOSTIC_PROMPT.read_text(encoding="utf-8")
    diagnostics = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [
            pool.submit(
                run_diagnostic,
                unit,
                items_by_id[unit["item_id"]],
                root=output / "model_units",
                prompt_template=prompt_template,
                backend_config=backend_config,
                max_attempts=max_attempts,
            )
            for unit in units
            if unit["item_id"] in eligible
        ]
        for future in as_completed(futures):
            diagnostics.append(future.result())
    diagnostics.sort(key=lambda row: row["validation_unit_id"])
    if any(row["status"] == "exhausted" for row in diagnostics):
        raise RuntimeError("one or more item diagnostics exhausted all attempts")
    write_jsonl(output / "diagnostics.jsonl", diagnostics)
    diagnostics_by_uid = {row["validation_unit_id"]: row for row in diagnostics}
    primary_uid = {row["item_id"]: row["validation_unit_id"] for row in units if row["duplicate_of"] is None}
    accepted, rejected, result_rows = [], [], []
    for item in candidates:
        reasons = list(hard_by_id[item["item_id"]]["errors"])
        diagnostic = diagnostics_by_uid.get(primary_uid[item["item_id"]])
        if diagnostic:
            reasons.extend(
                f"automated diagnostic: {DIAGNOSTIC_FAILURE_LABELS[key]}"
                for key, expected_value in acceptance.items()
                if diagnostic["result"].get(key) != expected_value
            )
        elif not reasons:
            reasons.append("independent automated diagnostic missing")
        validator_results = {
            "deterministic": hard_by_id[item["item_id"]],
            "independent_automated_diagnostic": diagnostic,
            "automated_not_human_validation": True,
        }
        final = {**item, "validator_results": validator_results}
        (rejected if reasons else accepted).append({"item": final, "reasons": reasons} if reasons else final)
        result_rows.append({"item_id": item["item_id"], "status": "rejected" if reasons else "accepted", "reasons": reasons, "diagnostic_unit_id": diagnostic["validation_unit_id"] if diagnostic else None})
    write_jsonl(output / "accepted_items.jsonl", sorted(accepted, key=lambda row: row["item_id"]))
    write_jsonl(output / "rejected_items.jsonl", rejected)
    write_jsonl(output / "validation_results.jsonl", result_rows)
    accepted_hash = item_bank_fingerprint(accepted)
    write_json(
        output / "bank_report.json",
        {
            "accepted_item_bank_sha256": accepted_hash,
            "candidate_items": len(candidates),
            "accepted_items": len(accepted),
            "rejected_items": len(rejected),
            "kc_policy_consulted": False,
        },
    )
    return {
        "candidates": len(candidates),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "diagnostic_units": len(diagnostics),
        "accepted_item_bank_sha256": accepted_hash,
    }
