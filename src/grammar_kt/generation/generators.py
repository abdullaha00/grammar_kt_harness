"""Constrained LLM generators sharing one MeasurementOpportunity interface."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from ..backend import invoke_model, save_model_result
from ..io import read_json, read_jsonl, read_yaml, repo_path, write_json, write_jsonl
from ..measurement.opportunities import opportunity_bank_fingerprint
from ..records import measurement_opportunity
from .items import candidate_item, nested_keys


GENERATOR_MODES = {"llm_standalone", "llm_dialogue"}
MODE_TO_FAMILY = {
    "llm_standalone": "standalone_completion",
    "llm_dialogue": "dialogue_completion",
}
FORBIDDEN_CONFIG_KEYS = {
    "kc",
    "kc_id",
    "kc_ids",
    "kc_policy",
    "fold",
    "fold_id",
    "canonical_split",
    "dataset_split",
}


def load_generator_config(value: str | Path | dict[str, Any]) -> dict[str, Any]:
    config = read_yaml(repo_path(value)) if isinstance(value, (str, Path)) else dict(value)
    required = {
        "generator_id",
        "mode",
        "prompt",
        "instructions",
        "output_schema",
        "backend_config",
    }
    missing = required - set(config)
    if missing:
        raise ValueError(f"generator config missing {sorted(missing)}")
    if config["mode"] not in GENERATOR_MODES:
        raise ValueError(f"unknown generator mode {config['mode']!r}")
    leaked = nested_keys(config) & FORBIDDEN_CONFIG_KEYS
    if leaked:
        raise ValueError(f"generator config contains forbidden experimental labels: {sorted(leaked)}")
    return config


def render_generation_prompt(
    opportunity: dict[str, Any], config: dict[str, Any]
) -> str:
    """Render the fixed grammar target; the model never selects the target."""

    template = repo_path(config["prompt"]).read_text(encoding="utf-8")
    target = {
        "canonical_cell_id": opportunity["canonical_cell_id"],
        "cell": opportunity["cell"],
        "structural_conditions": opportunity["structural_conditions"],
        "expected_operations": opportunity["expected_operations"],
    }
    constraints = config.get("constraints", {})
    rendered = template.replace(
        "{{measurement_opportunity}}",
        json.dumps(target, ensure_ascii=False, indent=2, sort_keys=True),
    ).replace(
        "{{generation_constraints}}",
        json.dumps(constraints, ensure_ascii=False, indent=2, sort_keys=True),
    )
    if "{{" in rendered:
        raise ValueError("unresolved generation prompt placeholder")
    return rendered


def _parse_output(raw: str, mode: str) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    try:
        parsed = json.loads(raw)
    except Exception as error:
        return None, [f"JSON parse error: {error}"]
    if not isinstance(parsed, dict) or set(parsed) != {"content", "target_answer", "accepted_answers"}:
        return parsed if isinstance(parsed, dict) else None, ["generated output fields differ from schema"]
    family = MODE_TO_FAMILY[mode]
    try:
        candidate_item(
            opportunity={
                "measurement_opportunity_id": "OPP_0000000000000000",
                "canonical_cell_id": "CELL_FIX",
                "source_descriptor_ids": [],
            },
            generator_id="shape_check",
            item_family=family,
            content=parsed["content"],
            target_answer=parsed["target_answer"],
            accepted_answers=parsed["accepted_answers"],
            generation_metadata={},
        )
    except (KeyError, TypeError, ValueError) as error:
        errors.append(str(error))
    return parsed, errors


def _fixture_backend(config: dict[str, Any], opportunity_id: str, unit_root: Path) -> dict[str, Any]:
    fixture = config["backend_config"]
    if isinstance(fixture, (str, Path)):
        backend = read_yaml(repo_path(fixture))
    else:
        backend = dict(fixture)
    if backend.get("kind") != "fixture_map":
        return backend
    if "responses" in backend or "default" in backend:
        fixture_data = backend
    else:
        fixture_data = read_json(repo_path(backend["response_file"]))
    response = fixture_data.get("responses", {}).get(
        opportunity_id, fixture_data.get("default")
    )
    if response is None:
        raise KeyError(f"fixture backend lacks response for {opportunity_id}")
    response_path = unit_root / "fixture_response.json"
    write_json(response_path, response)
    return {"kind": "fixture_file", "response_file": str(response_path)}


def generate_items(
    opportunities: list[dict[str, Any]],
    generator_config: str | Path | dict[str, Any],
    *,
    evidence_root: Path | None = None,
) -> dict[str, Any]:
    """Generate one candidate per opportunity through a swappable LLM slot."""

    config = load_generator_config(generator_config)
    root = evidence_root or Path(tempfile.mkdtemp(prefix="grammar-kt-generation-"))
    root.mkdir(parents=True, exist_ok=True)
    generator_id = config["generator_id"]
    mode = config["mode"]
    family = MODE_TO_FAMILY[mode]
    max_attempts = int(config.get("max_attempts", 2))
    candidates: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    for opportunity in sorted(opportunities, key=lambda row: row["measurement_opportunity_id"]):
        measurement_opportunity(opportunity)
        opportunity_id = opportunity["measurement_opportunity_id"]
        unit_root = root / opportunity_id
        write_json(unit_root / "input_opportunity.json", opportunity)
        prompt = render_generation_prompt(opportunity, config)
        backend = _fixture_backend(config, opportunity_id, unit_root)
        history: list[dict[str, Any]] = []
        accepted_output: dict[str, Any] | None = None
        accepted_raw = ""
        for number in range(1, max_attempts + 1):
            attempt = unit_root / f"attempt-{number:02d}"
            raw_path, returncode = invoke_model(
                prompt=prompt,
                output_schema=repo_path(config["output_schema"]),
                instructions=repo_path(config["instructions"]),
                unit_dir=attempt,
                backend_config=backend,
            )
            raw = raw_path.read_text(encoding="utf-8")
            parsed, errors = _parse_output(raw, mode)
            if returncode:
                errors.append(f"backend exited {returncode}")
            save_model_result(attempt, parsed, errors)
            history.append({"attempt": number, "accepted": not errors, "rejection_reasons": errors})
            if not errors and parsed is not None:
                accepted_output, accepted_raw = parsed, raw
                break
        if accepted_output is None:
            rejected = {
                "measurement_opportunity_id": opportunity_id,
                "generator_id": generator_id,
                "attempts": history,
                "rejection_reason": "generation exhausted all attempts",
            }
            rejections.append(rejected)
            write_json(unit_root / "result.json", rejected)
            continue
        metadata = {
            "input_opportunity": opportunity,
            "rendered_prompt": prompt,
            "backend": {
                "kind": backend.get("kind"),
                "model": backend.get("model"),
            },
            "raw_output": accepted_raw,
            "parsed_output": accepted_output,
            "attempt": next(row["attempt"] for row in history if row["accepted"]),
            "attempt_history": history,
            "generator_config": {
                "generator_id": generator_id,
                "mode": mode,
                "constraints": config.get("constraints", {}),
            },
            "evidence_directory": str(unit_root),
        }
        item = candidate_item(
            opportunity=opportunity,
            generator_id=generator_id,
            item_family=family,
            content=accepted_output["content"],
            target_answer=accepted_output["target_answer"],
            accepted_answers=accepted_output["accepted_answers"],
            generation_metadata=metadata,
        )
        candidates.append(item)
        write_json(unit_root / "result.json", {"status": "candidate", "item": item})
    return {
        "candidates": sorted(candidates, key=lambda row: row["item_id"]),
        "rejections": rejections,
        "audit": {
            "generator_id": generator_id,
            "mode": mode,
            "opportunities": len(opportunities),
            "candidates": len(candidates),
            "generation_rejections": len(rejections),
            "opportunity_bank_sha256": opportunity_bank_fingerprint(opportunities),
            "kc_policy_consulted": False,
            "fold_assignment_consulted": False,
            "target_grammar_fixed_before_generation": True,
        },
    }


def run(run_dir: Path, settings: dict[str, Any]) -> dict[str, Any]:
    """Run generation and independent validation inside one scientific module."""

    from .validation import validate_items

    output = run_dir / "generation"
    output.mkdir(parents=True, exist_ok=False)
    opportunities = read_jsonl(run_dir / "measurement" / "measurement_opportunities.jsonl")
    generated = generate_items(
        opportunities,
        settings["generator"],
        evidence_root=output / "generation_evidence",
    )
    write_jsonl(output / "candidate_items.jsonl", generated["candidates"], sort_keys=False)
    write_jsonl(output / "generation_rejections.jsonl", generated["rejections"], sort_keys=False)
    write_json(output / "generation_audit.json", generated["audit"])
    validated = validate_items(
        generated["candidates"],
        opportunities,
        settings["validation"],
        evidence_root=output / "validation_evidence",
    )
    write_jsonl(output / "accepted_items.jsonl", validated["accepted"], sort_keys=False)
    write_jsonl(output / "rejected_items.jsonl", validated["rejected"], sort_keys=False)
    write_json(output / "validation_report.json", validated["report"])
    return {
        **generated["audit"],
        "accepted": len(validated["accepted"]),
        "validation_rejected": len(validated["rejected"]),
        "accepted_item_bank_sha256": validated["report"]["accepted_item_bank_sha256"],
    }
