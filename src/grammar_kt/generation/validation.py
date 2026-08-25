"""Generator-independent hard checks and blind grammatical reconstruction."""

from __future__ import annotations

import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from ..backend import invoke_model, save_model_result
from ..io import ROOT, read_json, read_yaml, repo_path, write_json
from ..measurement.operations import derive_agreement_site
from ..records import grammar_cell, measurement_opportunity
from .diagnostic_reliability import analyse_repeated_diagnostics
from .items import (
    FORBIDDEN_GENERATION_KEYS,
    ITEM_FIELDS,
    item_bank_fingerprint,
    item_identity,
    nested_keys,
    valid_content,
    valid_item_id,
)


VALIDATION_DIR = ROOT / "modules" / "generation" / "validation"
STRUCTURAL_PROMPT = VALIDATION_DIR / "structural_prompt.txt"
STRUCTURAL_SCHEMA = VALIDATION_DIR / "structural_schema.json"
QUALITY_PROMPT = VALIDATION_DIR / "quality_prompt.txt"
QUALITY_SCHEMA = VALIDATION_DIR / "quality_schema.json"
INSTRUCTIONS = VALIDATION_DIR / "evaluator_instructions.md"
STRUCTURE_FIELDS = {"cell", "operations", "predicate_class", "agreement_site"}
QUALITY_FIELDS = {
    "naturalness",
    "answer_ambiguity",
    "pedagogical_suitability",
    "world_knowledge_required",
    "lexical_cefr_appropriate",
    "dialogue_coherence",
    "pragmatic_licensing",
    "natural_speaker_turns",
    "context_appropriateness",
    "note",
}
DEFAULT_KNOWN_GENERATORS = {"llm_standalone_v0", "llm_dialogue_v0"}


def _load_config(value: str | Path | dict[str, Any]) -> dict[str, Any]:
    return read_yaml(repo_path(value)) if isinstance(value, (str, Path)) else dict(value)


def _load_backend(value: str | Path | dict[str, Any]) -> dict[str, Any]:
    return read_yaml(repo_path(value)) if isinstance(value, (str, Path)) else dict(value)


def _fixture_backend(
    backend_value: str | Path | dict[str, Any], item_id: str, unit_root: Path, label: str
) -> dict[str, Any]:
    backend = _load_backend(backend_value)
    if backend.get("kind") != "fixture_map":
        return backend
    fixture_data = (
        backend
        if "responses" in backend or "default" in backend
        else read_json(backend["response_file"])
    )
    response = fixture_data.get("responses", {}).get(item_id, fixture_data.get("default"))
    if response is None:
        raise KeyError(f"{label} fixture lacks response for {item_id}")
    response_path = unit_root / f"{label}_fixture_response.json"
    write_json(response_path, response)
    return {"kind": "fixture_file", "response_file": str(response_path)}


def _blind_input(item: dict[str, Any]) -> dict[str, Any]:
    """Expose only the generated exercise and learner response, never its target."""

    return {
        "item_family": item["item_family"],
        "content": item["content"],
        "learner_response": item["target_answer"],
        "accepted_surface_variants": item["accepted_answers"],
    }


def _parse_structure(raw: str) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        parsed = json.loads(raw)
    except Exception as error:
        return None, [f"JSON parse error: {error}"]
    errors: list[str] = []
    if not isinstance(parsed, dict) or set(parsed) != STRUCTURE_FIELDS:
        return parsed if isinstance(parsed, dict) else None, ["structural reconstruction fields differ from schema"]
    try:
        grammar_cell(parsed["cell"], label="blind reconstruction cell")
    except (KeyError, ValueError) as error:
        errors.append(str(error))
    if not isinstance(parsed.get("operations"), list) or any(not isinstance(value, str) for value in parsed.get("operations", [])):
        errors.append("operations must be a string list")
    if parsed.get("predicate_class") not in {"lexical_transitive", "lexical_intransitive", "copular"}:
        errors.append("invalid predicate_class")
    if parsed.get("agreement_site") not in {"none", "modal", "do", "have", "be", "main_verb"}:
        errors.append("invalid agreement_site")
    return parsed, errors


def _parse_quality(raw: str) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        parsed = json.loads(raw)
    except Exception as error:
        return None, [f"JSON parse error: {error}"]
    if not isinstance(parsed, dict) or set(parsed) != QUALITY_FIELDS:
        return parsed if isinstance(parsed, dict) else None, ["quality diagnostic fields differ from schema"]
    errors: list[str] = []
    for field in ("naturalness", "pedagogical_suitability"):
        if not isinstance(parsed[field], int) or not 1 <= parsed[field] <= 5:
            errors.append(f"{field} must be an integer from 1 to 5")
    for field in ("answer_ambiguity", "world_knowledge_required", "lexical_cefr_appropriate"):
        if not isinstance(parsed[field], bool):
            errors.append(f"{field} must be Boolean")
    for field in ("dialogue_coherence", "pragmatic_licensing", "natural_speaker_turns", "context_appropriateness"):
        if parsed[field] is not None and (not isinstance(parsed[field], int) or not 1 <= parsed[field] <= 5):
            errors.append(f"{field} must be null or an integer from 1 to 5")
    if not isinstance(parsed["note"], str):
        errors.append("note must be a string")
    return parsed, errors


def _evaluate(
    *,
    item: dict[str, Any],
    label: str,
    prompt_path: Path,
    schema_path: Path,
    backend_value: str | Path | dict[str, Any],
    parser: Callable[[str], tuple[dict[str, Any] | None, list[str]]],
    root: Path,
    repetition: int,
    max_attempts: int,
) -> dict[str, Any]:
    blind = _blind_input(item)
    rendered = prompt_path.read_text(encoding="utf-8").replace(
        "{{generated_item}}", json.dumps(blind, ensure_ascii=False, indent=2, sort_keys=True)
    )
    unit_root = root / item["item_id"] / label / f"repetition-{repetition:02d}"
    write_json(unit_root / "blind_input.json", blind)
    attempts = []
    for attempt_number in range(1, max_attempts + 1):
        attempt = unit_root / f"attempt-{attempt_number:02d}"
        backend = _fixture_backend(backend_value, item["item_id"], unit_root, label)
        raw_path, returncode = invoke_model(
            prompt=rendered,
            output_schema=schema_path,
            instructions=INSTRUCTIONS,
            unit_dir=attempt,
            backend_config=backend,
        )
        parsed, errors = parser(raw_path.read_text(encoding="utf-8"))
        if returncode:
            errors.append(f"backend exited {returncode}")
        save_model_result(attempt, parsed, errors)
        attempts.append({"attempt": attempt_number, "valid": not errors, "errors": errors})
        if not errors:
            result = {
                "item_id": item["item_id"],
                "label": label,
                "repetition": repetition,
                "result": parsed,
                "successful_attempt": attempt_number,
                "attempts": attempts,
                "intended_target_hidden": True,
            }
            write_json(unit_root / "result.json", result)
            return result
    result = {
        "item_id": item["item_id"],
        "label": label,
        "repetition": repetition,
        "result": None,
        "successful_attempt": None,
        "attempts": attempts,
        "intended_target_hidden": True,
    }
    write_json(unit_root / "result.json", result)
    return result


def hard_validation_results(
    candidates: list[dict[str, Any]], opportunities: list[dict[str, Any]],
    *, known_generators: set[str],
) -> list[dict[str, Any]]:
    opportunity_by_id = {
        row["measurement_opportunity_id"]: measurement_opportunity(row)
        for row in opportunities
    }
    id_counts = Counter(row.get("item_id") for row in candidates)
    results = []
    for item in candidates:
        errors: list[str] = []
        if set(item) != ITEM_FIELDS:
            errors.append("item fields differ from the generator-independent schema")
        if not valid_item_id(item.get("item_id")):
            errors.append("invalid item_id")
        opportunity = opportunity_by_id.get(item.get("measurement_opportunity_id"))
        if opportunity is None:
            errors.append("unknown measurement_opportunity_id")
        elif item.get("canonical_cell_id") != opportunity["canonical_cell_id"]:
            errors.append("canonical cell reference differs from MeasurementOpportunity")
        elif item.get("source_descriptor_ids") != opportunity["source_descriptor_ids"]:
            errors.append("source provenance differs from MeasurementOpportunity")
        if item.get("generator_id") not in known_generators:
            errors.append("unknown generator")
        errors.extend(valid_content(item.get("item_family"), item.get("content")))
        if id_counts[item.get("item_id")] != 1:
            errors.append("duplicate item_id")
        try:
            if item.get("item_id") != item_identity(item):
                errors.append("item_id differs from concrete surface identity")
        except (KeyError, TypeError, ValueError):
            errors.append("item identity could not be reconstructed")
        leaked = nested_keys(item.get("generation_metadata", {})) & FORBIDDEN_GENERATION_KEYS
        if leaked:
            errors.append(f"generation evidence contains KC/fold labels: {sorted(leaked)}")
        input_opportunity = item.get("generation_metadata", {}).get("input_opportunity")
        if opportunity is not None and input_opportunity != opportunity:
            errors.append("generation evidence does not preserve exact opportunity input")
        results.append(
            {
                "item_id": item.get("item_id"),
                "measurement_opportunity_id": item.get("measurement_opportunity_id"),
                "status": "accepted" if not errors else "rejected",
                "errors": errors,
            }
        )
    return results


def validate_items(
    candidates: list[dict[str, Any]],
    opportunities: list[dict[str, Any]],
    evaluator_config: str | Path | dict[str, Any],
    *,
    evidence_root: Path | None = None,
) -> dict[str, Any]:
    """Apply hard checks, blind structure recovery, and separate quality diagnostics."""

    config = _load_config(evaluator_config)
    root = evidence_root or Path(tempfile.mkdtemp(prefix="grammar-kt-validation-"))
    root.mkdir(parents=True, exist_ok=True)
    known = set(config.get("known_generators", DEFAULT_KNOWN_GENERATORS))
    hard = hard_validation_results(candidates, opportunities, known_generators=known)
    hard_by_id = {row["item_id"]: row for row in hard}
    opportunity_by_id = {row["measurement_opportunity_id"]: row for row in opportunities}
    max_attempts = int(config.get("max_attempts", 2))
    repeated_first_n = int(config.get("repeat_first_n", 0))
    repeated_ids = {
        row["item_id"] for row in sorted(candidates, key=lambda row: row["item_id"])[:repeated_first_n]
    }
    structure_runs = []
    quality_runs = []
    accepted = []
    rejected = []
    failure_types: Counter[str] = Counter()
    for item in sorted(candidates, key=lambda row: row["item_id"]):
        reasons = list(hard_by_id[item["item_id"]]["errors"])
        repetitions = 2 if item["item_id"] in repeated_ids else 1
        structures = []
        qualities = []
        if not reasons:
            for repetition in range(1, repetitions + 1):
                structure = _evaluate(
                    item=item,
                    label="structural",
                    prompt_path=STRUCTURAL_PROMPT,
                    schema_path=STRUCTURAL_SCHEMA,
                    backend_value=config["structural_backend_config"],
                    parser=_parse_structure,
                    root=root,
                    repetition=repetition,
                    max_attempts=max_attempts,
                )
                quality = _evaluate(
                    item=item,
                    label="quality",
                    prompt_path=QUALITY_PROMPT,
                    schema_path=QUALITY_SCHEMA,
                    backend_value=config["quality_backend_config"],
                    parser=_parse_quality,
                    root=root,
                    repetition=repetition,
                    max_attempts=max_attempts,
                )
                structure_runs.append(structure)
                quality_runs.append(quality)
                structures.append(structure)
                qualities.append(quality)
            primary = structures[0]["result"]
            opportunity = opportunity_by_id[item["measurement_opportunity_id"]]
            if primary is None:
                reasons.append("blind grammatical reconstruction exhausted")
            else:
                expected = {
                    "cell": opportunity["cell"],
                    "operations": opportunity["expected_operations"],
                    "predicate_class": opportunity["structural_conditions"]["predicate_class"],
                    "agreement_site": derive_agreement_site(
                        opportunity["cell"], opportunity["structural_conditions"]
                    ),
                }
                for field in ("cell", "operations", "predicate_class", "agreement_site"):
                    actual = primary[field]
                    matches = set(actual) == set(expected[field]) if field == "operations" else actual == expected[field]
                    if not matches:
                        label = f"{field}_mismatch"
                        reasons.append(
                            f"blind reconstruction {label}: intended={expected[field]!r}, recovered={actual!r}"
                        )
            if qualities and qualities[0]["result"] is None:
                failure_types["quality_diagnostic_exhausted"] += 1
        for reason in reasons:
            if reason.startswith("blind reconstruction "):
                failure_types[
                    reason.removeprefix("blind reconstruction ").split(":", 1)[0]
                ] += 1
            elif reason == "blind grammatical reconstruction exhausted":
                failure_types["structural_reconstruction_exhausted"] += 1
            elif reason:
                failure_types["hard_schema_or_reference"] += 1
        primary_structure = structures[0]["result"] if structures else None
        primary_quality = qualities[0]["result"] if qualities else None
        final = {
            **item,
            "validated_structure": primary_structure or {},
            "quality_diagnostics": primary_quality or {},
            "validation_metadata": {
                "evaluator_id": config.get("evaluator_id", "blind_reconstruction_v1"),
                "hard_checks": hard_by_id[item["item_id"]],
                "structural_repetitions": structures,
                "quality_repetitions": qualities,
                "intended_target_hidden_from_evaluator": True,
                "quality_not_conflated_with_grammar_acceptance": True,
            },
        }
        if reasons:
            rejected.append({"item": final, "reasons": reasons})
        else:
            accepted.append(final)

    intended_ids = {row["measurement_opportunity_id"] for row in opportunities}
    candidate_ids = {row["measurement_opportunity_id"] for row in candidates}
    accepted_ids = {row["measurement_opportunity_id"] for row in accepted}
    cell_matches = sum(
        row["validated_structure"]["cell"] == opportunity_by_id[row["measurement_opportunity_id"]]["cell"]
        for row in accepted
    )
    operation_matches = sum(
        set(row["validated_structure"]["operations"])
        == set(opportunity_by_id[row["measurement_opportunity_id"]]["expected_operations"])
        for row in accepted
    )
    report = {
        "status": "PASS" if not rejected and candidate_ids == intended_ids else "PARTIAL",
        "candidate_items": len(candidates),
        "accepted_items": len(accepted),
        "rejected_items": len(rejected),
        "candidate_opportunity_coverage": len(candidate_ids & intended_ids) / len(intended_ids) if intended_ids else 1.0,
        "accepted_opportunity_coverage": len(accepted_ids & intended_ids) / len(intended_ids) if intended_ids else 1.0,
        "missing_candidate_opportunity_ids": sorted(intended_ids - candidate_ids),
        "missing_accepted_opportunity_ids": sorted(intended_ids - accepted_ids),
        "grammar_cell_exact_match_rate": cell_matches / len(candidates) if candidates else None,
        "operation_exact_match_rate": operation_matches / len(candidates) if candidates else None,
        "failure_types": dict(sorted(failure_types.items())),
        "structural_evaluator_reliability": analyse_repeated_diagnostics(structure_runs, result_field="cell"),
        "quality_evaluator_reliability": analyse_repeated_diagnostics(quality_runs, result_field="naturalness"),
        "accepted_item_bank_sha256": item_bank_fingerprint(accepted),
        "independent_blind_reconstruction": True,
        "quality_is_separate_diagnostic": True,
    }
    return {"accepted": accepted, "rejected": rejected, "hard_results": hard, "report": report}
