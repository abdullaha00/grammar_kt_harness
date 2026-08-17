"""Deterministic hard validation followed by independent fresh-context diagnostics."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from jsonschema.validators import validator_for

from modules.items.helpers import item_id, nuisance_signature, render_prompt
from modules.realization.engine import realize, validate_spec
from shared.utils.io import ROOT, read_json, read_jsonl, repo_path, require_new_directory, sha256_file, utc_now, write_json, write_jsonl
from shared.utils.manifests import write_stage_manifest
from shared.utils.model_backend import get_backend


ITEM_FIELDS = {
    "item_id", "source_descriptor_ids", "canonical_cell_id", "realization_spec",
    "item_family", "primary_kc_id", "all_kc_ids", "prompt", "target_answer",
    "accepted_answers", "contrast_set_id", "generation_metadata", "validator_results", "provenance",
}
DIAGNOSTIC_FIELDS = {
    "structurally_plausible", "natural", "world_knowledge_required",
    "unsupported_construction", "answer_ambiguity_suspected", "note",
}


def _diagnostic_valid(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == DIAGNOSTIC_FIELDS
        and all(
            isinstance(value[key], bool)
            for key in DIAGNOSTIC_FIELDS - {"note"}
        )
        and isinstance(value["note"], str)
    )


def deterministic_results(
    candidates: list[dict[str, Any]],
    *,
    cells: dict[str, dict[str, str]],
    edge_sources: dict[str, set[str]],
    mappings: dict[str, dict[str, Any]],
    frames: dict[str, dict[str, Any]],
    projections: dict[str, list[str]],
    kc_ids: set[str],
    template: str,
    template_hash: str,
    item_schema: dict[str, Any],
) -> list[dict[str, Any]]:
    schema_class = validator_for(item_schema)
    schema_class.check_schema(item_schema)
    schema_validator = schema_class(item_schema)
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
        elif sum(
            cells[rows[0]["canonical_cell_id"]][key] != cells[rows[1]["canonical_cell_id"]][key]
            for key in cells[rows[0]["canonical_cell_id"]]
        ) != 1:
            contrast_errors[contrast_id].append("contrast is not Hamming-one")
    results = []
    for row in candidates:
        errors = [error.message for error in schema_validator.iter_errors(row)]
        if set(row) != ITEM_FIELDS or row.get("item_family") != "CONTROLLED_TRANSFORMATION_v0_1":
            errors.append("ItemSpec shape/family mismatch")
        if not re.fullmatch(r"ITEM_[A-F0-9]{16}", str(row.get("item_id", ""))):
            errors.append("invalid item ID")
        cell_id = row["canonical_cell_id"]
        spec = row["realization_spec"]
        cell = cells.get(cell_id)
        frame = frames.get(spec.get("predicate_frame_id"))
        if cell is None or frame is None or spec.get("canonical_cell_id") != cell_id:
            errors.append("unknown or mismatched cell/frame")
        else:
            if not set(row["source_descriptor_ids"]) <= edge_sources[cell_id] or spec["source_descriptor_id"] not in edge_sources[cell_id]:
                errors.append("source-cell provenance mismatch")
            errors.extend(validate_spec(spec, cell, frame, mappings[spec["source_descriptor_id"]].get("note")))
            derivation = realize(spec, cell, frame)
            if derivation["surface"] != row["target_answer"] or row["accepted_answers"] != [derivation["surface"]]:
                errors.append("target/answer set differs from deterministic singleton")
            if row["prompt"] != render_prompt(template, cell, spec, frame):
                errors.append("prompt differs from frozen current template")
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
            errors.append("stable current item ID mismatch")
        if row["generation_metadata"].get("template_sha256") != template_hash:
            errors.append("generation template hash mismatch")
        if prompt_counts[row["prompt"]] != 1 or answer_counts[row["target_answer"]] != 1:
            errors.append("duplicate prompt or target answer")
        if row["provenance"].get("parent_rewrite_or_adjudication") is not False:
            errors.append("parent rewrite/adjudication provenance is not false")
        errors.extend(contrast_errors.get(row["contrast_set_id"], []))
        results.append(
            {
                "item_id": row["item_id"],
                "split": row["generation_metadata"]["split"],
                "status": "accepted" if not errors else "rejected",
                "errors": errors,
            }
        )
    return results


def _run_diagnostic(
    unit: dict[str, Any],
    item: dict[str, Any],
    *,
    output: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    backend = get_backend(config["backend"])
    uid = unit["validation_unit_id"]
    prompt_template = repo_path(config["prompt"]).read_text(encoding="utf-8")
    prompt = prompt_template.replace("{item}", json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    attempts = []
    for attempt in range(1, int(config["max_attempts"]) + 1):
        stem = f"{uid}.attempt-{attempt:02d}"
        raw_root = output / "raw_validator"
        raw_path = raw_root / "responses" / f"{stem}.txt"
        backend_result = backend.invoke(
            prompt=prompt,
            output_schema=repo_path(config["output_schema"]),
            instructions=repo_path(config["instructions"]),
            raw_path=raw_path,
            log_dir=raw_root / "logs",
            stem=stem,
            config=config,
            context={
                "validation_unit_id": uid,
                "item_id": item["item_id"],
                "duplicate_of": unit["duplicate_of"],
                "attempt": attempt,
                "generator_context_exposed": False,
                "other_items_exposed": False,
                "parent_rewrite_or_adjudication": False,
            },
        )
        parsed = None
        parse_error = None
        if raw_path.is_file():
            try:
                candidate = json.loads(raw_path.read_text(encoding="utf-8"))
                if _diagnostic_valid(candidate):
                    parsed = candidate
                else:
                    parse_error = "output object failed fixed shape/type check"
            except Exception as error:
                parse_error = f"JSON parse error: {error}"
        else:
            parse_error = "raw last-message output missing"
        metadata = read_json(backend_result.metadata_path)
        metadata["parse_error"] = parse_error
        write_json(backend_result.metadata_path, metadata)
        attempts.append(metadata)
        if parsed is not None and backend_result.returncode == 0:
            parsed_path = output / "raw_validator" / "parsed" / f"{uid}.json"
            write_json(parsed_path, parsed)
            return {
                "validation_unit_id": uid,
                "item_id": item["item_id"],
                "duplicate_of": unit["duplicate_of"],
                "status": "accepted_output",
                "successful_attempt": attempt,
                "parsed_sha256": sha256_file(parsed_path),
                "result": parsed,
                "attempts": attempts,
            }
    return {
        "validation_unit_id": uid,
        "item_id": item["item_id"],
        "duplicate_of": unit["duplicate_of"],
        "status": "exhausted",
        "successful_attempt": None,
        "parsed_sha256": None,
        "result": None,
        "attempts": attempts,
    }


def _model_reasons(result: dict[str, Any], expected: dict[str, bool]) -> list[str]:
    labels = {
        "structurally_plausible": "structurally implausible",
        "natural": "unnatural",
        "world_knowledge_required": "world knowledge required",
        "unsupported_construction": "unsupported construction",
        "answer_ambiguity_suspected": "answer ambiguity suspected",
    }
    return [f"automated diagnostic: {labels[key]}" for key, value in expected.items() if result.get(key) != value]


def run_validation(items_dir: Path, run_dir: Path, config: dict[str, Any], experiment_manifest: Path, command: list[str]) -> None:
    started = utc_now()
    output = items_dir / "validation"
    require_new_directory(output)
    (output / "raw_validator" / "responses").mkdir(parents=True)
    (output / "raw_validator" / "parsed").mkdir(parents=True)
    (output / "raw_validator" / "logs").mkdir(parents=True)
    candidates_path = items_dir / "generation" / "candidate_items.jsonl"
    units_path = items_dir / "generation" / "validation_units.jsonl"
    cells_path = run_dir / "canonical" / "canonical_cells.jsonl"
    edges_path = run_dir / "canonical" / "source_cell_edges.jsonl"
    mappings_path = run_dir / "normalization" / "final_mappings.jsonl"
    projection_path = run_dir / "kc" / "cell_kc_projection.jsonl"
    inventory_path = run_dir / "kc" / "kc_inventory.jsonl"
    template_path = repo_path(config["generation"]["template"])
    lexicon_path = repo_path(config["_realization"]["lexicon"])
    rules_path = repo_path(config["_realization"]["rules"])
    item_schema_path = ROOT / "shared" / "schemas" / "item.schema.json"
    validation_config_path = repo_path(config["validation"]["deterministic_rules"])
    validation_config = read_json(validation_config_path)
    candidates = read_jsonl(candidates_path)
    items_by_id = {row["item_id"]: row for row in candidates}
    cells = {row["canonical_cell_id"]: row["cell"] for row in read_jsonl(cells_path)}
    edge_sources: dict[str, set[str]] = defaultdict(set)
    for edge in read_jsonl(edges_path):
        edge_sources[edge["canonical_cell_id"]].add(edge["egp_id"])
    hard = deterministic_results(
        candidates,
        cells=cells,
        edge_sources=edge_sources,
        mappings={row["egp_id"]: row for row in read_jsonl(mappings_path)},
        frames={row["predicate_frame_id"]: row for row in read_jsonl(lexicon_path)},
        projections={row["canonical_cell_id"]: row["kc_ids"] for row in read_jsonl(projection_path)},
        kc_ids={row["kc_id"] for row in read_jsonl(inventory_path)},
        template=template_path.read_text(encoding="utf-8"),
        template_hash=sha256_file(template_path),
        item_schema=read_json(item_schema_path),
    )
    hard_path = output / "deterministic_results.jsonl"
    write_jsonl(hard_path, hard)
    hard_by_item = {row["item_id"]: row for row in hard}
    eligible = {row["item_id"] for row in hard if row["status"] == "accepted"}
    units = [row for row in read_jsonl(units_path) if row["item_id"] in eligible]
    diagnostics = []
    with ThreadPoolExecutor(max_workers=max(1, int(config["validation"]["workers"]))) as pool:
        futures = {
            pool.submit(
                _run_diagnostic,
                unit,
                items_by_id[unit["item_id"]],
                output=output,
                config=config["validation"],
            ): unit
            for unit in units
        }
        for future in as_completed(futures):
            row = future.result()
            diagnostics.append(row)
            print(f"item diagnostic {row['validation_unit_id']} {row['status']}", flush=True)
    diagnostics.sort(key=lambda row: row["validation_unit_id"])
    diagnostic_index_path = output / "diagnostic_index.jsonl"
    write_jsonl(diagnostic_index_path, [{key: value for key, value in row.items() if key != "result"} for row in diagnostics])
    if any(row["status"] == "exhausted" for row in diagnostics):
        raise RuntimeError("one or more independent item diagnostics exhausted all attempts")
    diagnostics_by_uid = {row["validation_unit_id"]: row for row in diagnostics}
    primary_uid = {
        row["item_id"]: row["validation_unit_id"]
        for row in read_jsonl(units_path)
        if row["duplicate_of"] is None
    }
    accepted = []
    rejected = []
    result_rows = []
    expected_model = validation_config["model_acceptance"]
    for item in candidates:
        reasons = list(hard_by_item[item["item_id"]]["errors"])
        diagnostic = diagnostics_by_uid.get(primary_uid[item["item_id"]])
        if diagnostic is not None:
            reasons.extend(_model_reasons(diagnostic["result"], expected_model))
        elif not reasons:
            reasons.append("independent automated diagnostic missing")
        final = {
            **item,
            "validator_results": {
                "deterministic": hard_by_item[item["item_id"]],
                "independent_automated_diagnostic": (
                    {"validation_unit_id": diagnostic["validation_unit_id"], "result": diagnostic["result"]}
                    if diagnostic is not None
                    else None
                ),
                "automated_not_human_validation": True,
            },
        }
        if reasons:
            rejected.append({"item": final, "reasons": reasons, "failure_layer": "VALIDATION"})
        else:
            accepted.append(final)
        result_rows.append(
            {
                "item_id": item["item_id"],
                "status": "rejected" if reasons else "accepted",
                "reasons": reasons,
                "deterministic": hard_by_item[item["item_id"]],
                "diagnostic_unit_id": diagnostic["validation_unit_id"] if diagnostic else None,
            }
        )
    duplicate_rows = []
    for unit in read_jsonl(units_path):
        if unit["duplicate_of"] is None or unit["validation_unit_id"] not in diagnostics_by_uid:
            continue
        original = diagnostics_by_uid[unit["duplicate_of"]]["result"]
        duplicate = diagnostics_by_uid[unit["validation_unit_id"]]["result"]
        duplicate_rows.append(
            {
                "item_id": unit["item_id"],
                "original_unit_id": unit["duplicate_of"],
                "duplicate_unit_id": unit["validation_unit_id"],
                "exact_match": original == duplicate,
                "acceptance_match": (not _model_reasons(original, expected_model)) == (not _model_reasons(duplicate, expected_model)),
            }
        )
    accepted_path = output / "accepted_items.jsonl"
    rejected_path = output / "rejected_items.jsonl"
    results_path = output / "validation_results.jsonl"
    duplicate_path = output / "duplicate_diagnostics.jsonl"
    write_jsonl(accepted_path, sorted(accepted, key=lambda row: row["item_id"]))
    write_jsonl(rejected_path, rejected)
    write_jsonl(results_path, result_rows)
    write_jsonl(duplicate_path, duplicate_rows)
    validation = config["validation"]
    write_stage_manifest(
        output,
        module="items.validation",
        version=config["version"],
        started_utc=started,
        command=command,
        inputs=[candidates_path, units_path, cells_path, edges_path, mappings_path, projection_path, inventory_path],
        configs=[
            experiment_manifest,
            validation_config_path,
            template_path,
            lexicon_path,
            rules_path,
            item_schema_path,
            repo_path(validation["prompt"]),
            repo_path(validation["output_schema"]),
            repo_path(validation["instructions"]),
        ],
        code=[Path(__file__), ROOT / "modules" / "items" / "helpers.py", ROOT / "modules" / "realization" / "engine.py", ROOT / "shared" / "utils" / "model_backend.py"],
        outputs=[hard_path, diagnostic_index_path, accepted_path, rejected_path, results_path, duplicate_path, output / "raw_validator"],
        details={
            "backend": validation["backend"],
            "codex_cli_version_expected": validation.get("codex_cli_version"),
            "model": validation["model"],
            "reasoning_effort": validation["reasoning_effort"],
            "generator_validator_contexts_independent": True,
            "model_snapshot_pinned": False,
            "attempted_items": len(candidates),
            "accepted_items": len(accepted),
            "rejected_items": len(rejected),
            "diagnostic_units": len(diagnostics),
            "automated_not_human_validation": True,
        },
    )
