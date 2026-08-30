#!/usr/bin/env python3
"""Execute the append-only automated dialogue-continuum pilot.

The frozen zero-call source plan remains unchanged.  This script creates a
separate plan, requires an explicit live-call guard, retains byte-exact call
evidence, validates provider envelopes against stricter local contracts, keeps
critic roles isolated, and delegates descriptive analysis to the frozen source
analyzer.  Automated judgments are stress tests rather than human evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Mapping, Sequence

import jsonschema
import yaml


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from grammar_kt.model_evidence import audited_model_call


DEFAULT_OUTPUT = ROOT / "experiments/measurement_realism/dialogue_pilot_live_v1"
DEFAULT_EVIDENCE = ROOT / "runs/measurement_realism/dialogue_pilot_live_v1"
SOURCE = ROOT / "experiments/measurement_realism/dialogue_pilot"
DEFAULT_CONFIG = DEFAULT_OUTPUT / "config.yaml"
SCRIPT = Path(__file__).resolve()
BACKEND = ROOT / "src/grammar_kt/model_evidence.py"
AUTHORIZATION_FLAG = "--authorize-live-calls-after-root-approval"

FORMAT_ORDER = (
    "constrained_cloze",
    "sentence_transformation",
    "contextual_production",
    "dialogue_completion",
    "open_dialogue",
)
RESPONSE_TYPES = {
    "constrained_cloze": "typed_span",
    "sentence_transformation": "typed_sentence",
    "contextual_production": "typed_short_clause",
    "dialogue_completion": "typed_turn",
    "open_dialogue": "typed_free_turn",
}
CALL_EVIDENCE_FILES = (
    "input.json",
    "rendered_prompt.txt",
    "model_settings.json",
    "output_schema.json",
    "raw_output.txt",
    "cli_stderr.txt",
    "call_metadata.json",
    "parsed_result.json",
)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"expected JSON objects: {path}")
    return rows


def write_frozen_text(path: Path, payload: str, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise FileExistsError(f"refusing to overwrite changed {label}: {path}")
        return
    path.write_text(payload, encoding="utf-8")


def write_frozen_json(path: Path, value: Any, label: str) -> None:
    write_frozen_text(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        label,
    )


def write_frozen_jsonl(path: Path, rows: Sequence[Mapping[str, Any]], label: str) -> str:
    payload = "".join(canonical_json(dict(row)) + "\n" for row in rows)
    write_frozen_text(path, payload, label)
    return payload


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected YAML mapping: {path}")
    return value


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=check,
    )


def repository_head() -> str:
    return git("rev-parse", "HEAD").stdout.strip()


def protected_reference_state(config: Mapping[str, Any]) -> dict[str, Any]:
    reference = ROOT / str(config["protected_reference"]["root"])
    manifest_path = reference / "manifest.json"
    manifest = read_json(manifest_path)
    expected_status = config["protected_reference"]["required_manifest_status"]
    if manifest.get("status") != expected_status:
        raise ValueError("protected full-v1 manifest status changed")
    tracked_diff = git("diff", "--quiet", "HEAD", "--", relative(reference), check=False)
    if tracked_diff.returncode != 0:
        raise ValueError("protected full-v1 has tracked changes")
    untracked = git(
        "ls-files", "--others", "--exclude-standard", "--", relative(reference)
    ).stdout.strip()
    if untracked:
        raise ValueError("protected full-v1 has untracked additions")
    tree = git("rev-parse", f"HEAD:{relative(reference)}").stdout.strip()
    return {
        "path": relative(reference),
        "git_tree": tree,
        "manifest_sha256": file_sha256(manifest_path),
        "manifest_status": manifest["status"],
    }


def path_record(path: Path) -> dict[str, Any]:
    return {
        "path": relative(path),
        "sha256": file_sha256(path),
        "bytes": path.stat().st_size,
    }


def static_input_paths(output: Path, config: Mapping[str, Any]) -> dict[str, Path]:
    source = config["source_protocol"]
    return {
        "config": output / "config.yaml",
        "execution_protocol": output / "PROTOCOL.md",
        "generation_prompt": output / config["generation"]["prompt"],
        "generation_provider_schema": output / config["generation"]["provider_schema"],
        "critic_prompt": output / config["critique"]["prompt"],
        "critic_provider_schema": output / config["critique"]["provider_schema"],
        "source_selected_cells": ROOT / source["selected_cells"],
        "source_generation_requests": ROOT / source["generation_requests"],
        "generation_local_schema": ROOT / source["generation_local_schema"],
        "critic_local_schema": ROOT / source["critic_local_schema"],
        "source_analyzer": ROOT / source["analyzer"],
        "implementation": SCRIPT,
        "audited_model_backend": BACKEND,
    }


def assert_provider_compatible(schema: Mapping[str, Any]) -> None:
    """Check the deliberately small strict-JSON-schema transport subset."""

    forbidden = {
        "$ref",
        "$defs",
        "const",
        "pattern",
        "minProperties",
        "maxProperties",
        "uniqueItems",
        "oneOf",
        "allOf",
        "anyOf",
    }

    def walk(value: Any, location: str) -> None:
        if isinstance(value, dict):
            bad = set(value) & forbidden
            if bad:
                raise ValueError(f"provider schema uses unsupported keys at {location}: {sorted(bad)}")
            if value.get("type") == "object":
                properties = value.get("properties")
                required = value.get("required")
                if not isinstance(properties, dict) or set(required or []) != set(properties):
                    raise ValueError(f"provider object must require every property at {location}")
                if value.get("additionalProperties") is not False:
                    raise ValueError(f"provider object must forbid extra properties at {location}")
            for key, child in value.items():
                walk(child, f"{location}/{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{location}/{index}")

    walk(schema, "$")
    jsonschema.Draft202012Validator.check_schema(dict(schema))


def _model_request(source_request: Mapping[str, Any]) -> dict[str, Any]:
    if source_request.get("live_call_authorized") is not False:
        raise ValueError("source zero-call request authorization boundary changed")
    return {
        key: value
        for key, value in source_request.items()
        if key != "live_call_authorized"
    } | {
        "execution_protocol": "dialogue_pilot_live_v1_separate_from_frozen_zero_call_plan",
        "generator_must_not_use": [
            "learner outcomes",
            "private oracle trajectories",
            "KT results",
            "critic outputs",
        ],
    }


def render_generation_prompt(template: str, request: Mapping[str, Any]) -> str:
    marker = "{{REQUEST_JSON}}"
    if template.count(marker) != 1:
        raise ValueError("generation prompt must contain one request marker")
    return template.replace(marker, canonical_json(dict(request)))


def plan(config_path: Path, output: Path) -> dict[str, Any]:
    config = load_yaml(config_path)
    if config_path.resolve() != (output / "config.yaml").resolve():
        raise ValueError("live protocol config must remain inside its output directory")
    if config.get("status") != "PREREGISTERED_EXECUTION_PROTOCOL_BEFORE_LIVE_CALLS":
        raise ValueError("execution protocol status changed")
    if config["authorization"]["live_calls_authorized_by_protocol_file"] is not False:
        raise ValueError("protocol file may not authorize live calls")
    paths = static_input_paths(output, config)
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing static inputs: {missing}")
    generation_provider_schema = read_json(paths["generation_provider_schema"])
    critic_provider_schema = read_json(paths["critic_provider_schema"])
    assert_provider_compatible(generation_provider_schema)
    assert_provider_compatible(critic_provider_schema)

    source_plan = read_json(paths["source_selected_cells"])
    if source_plan.get("status") != config["source_protocol"]["expected_source_status"]:
        raise ValueError("frozen source-plan status changed")
    if tuple(source_plan["format_order"]) != FORMAT_ORDER:
        raise ValueError("frozen format order changed")
    requests = read_jsonl(paths["source_generation_requests"])
    if len(requests) != 4:
        raise ValueError("frozen source must contain four generation requests")
    if config["generation"]["calls"] != 4 or config["critique"]["calls"] != 20:
        raise ValueError("declared call counts changed")
    if list(config["critique"]["roles"]) != list(source_plan["critic_roles"]):
        raise ValueError("critic role order differs from source plan")

    template = paths["generation_prompt"].read_text(encoding="utf-8")
    call_rows: list[dict[str, Any]] = []
    expected_family_ids = [cell["family_id"] for cell in source_plan["selected_cells"]]
    if [row["family_id"] for row in requests] != expected_family_ids:
        raise ValueError("source request order differs from selected families")
    for source_request in requests:
        exact_input = _model_request(source_request)
        rendered = render_generation_prompt(template, exact_input)
        call_rows.append(
            {
                "stage": "dialogue_continuum_generation",
                "call_key": source_request["family_id"],
                "family_id": source_request["family_id"],
                "model": config["generation"]["model"],
                "reasoning_effort": config["generation"]["reasoning_effort"],
                "input": exact_input,
                "input_sha256": sha256_bytes(canonical_json(exact_input).encode("utf-8")),
                "rendered_prompt": rendered,
                "rendered_prompt_sha256": sha256_bytes(rendered.encode("utf-8")),
                "provider_schema_sha256": file_sha256(paths["generation_provider_schema"]),
            }
        )
    call_payload = write_frozen_jsonl(
        output / "generation_call_plan.jsonl", call_rows, "generation call plan"
    )
    study_plan = {
        "study_id": config["study_id"],
        "status": "FROZEN_BEFORE_LIVE_CALLS",
        "evidence_type": "independent_automated_rubric_stress_test",
        "human_or_expert_gold": False,
        "dataset_release_justified_by_this_pilot_alone": False,
        "source_pilot_status_preserved": source_plan["status"],
        "scale": {
            "families": 4,
            "formats": 5,
            "opportunities": 20,
            "generation_calls": 4,
            "critic_calls": 20,
            "critic_judgments": 100,
        },
        "models": {
            "generation": {
                "name": config["generation"]["model"],
                "reasoning_effort": config["generation"]["reasoning_effort"],
            },
            "critique": {
                "name": config["critique"]["model"],
                "reasoning_effort": config["critique"]["reasoning_effort"],
            },
        },
        "critic_roles": list(config["critique"]["roles"]),
        "role_visibility": {
            role: {
                "sees_oracle_annotations": declaration["sees_oracle_annotations"],
                "sees_scoring_key": declaration["sees_scoring_key"],
            }
            for role, declaration in config["critique"]["roles"].items()
        },
        "scientific_boundary": {
            "generation_reads_learner_outcomes": False,
            "generation_reads_private_oracle_trajectories": False,
            "generation_reads_kt_results": False,
            "critic_roles_share_outputs": False,
            "scalar_realism_score": False,
            "full_v1_mutated": False,
        },
        "authorization": {
            "live_calls_authorized_by_plan": False,
            "conversational_root_approval_required": True,
            "command_guard": AUTHORIZATION_FLAG,
        },
        "protected_reference": protected_reference_state(config),
        "static_inputs": {name: path_record(path) for name, path in sorted(paths.items())},
        "generation_call_plan": {
            "path": "generation_call_plan.jsonl",
            "rows": len(call_rows),
            "sha256": sha256_bytes(call_payload.encode("utf-8")),
        },
        "implementation": {
            "repository_head_at_plan": repository_head(),
            "python": sys.version.split()[0],
        },
        "commands": {
            "plan": ".venv/bin/python scripts/experiments/measurement_realism_dialogue_live.py plan",
            "generate": ".venv/bin/python scripts/experiments/measurement_realism_dialogue_live.py generate --authorize-live-calls-after-root-approval --workers 4",
            "critic": ".venv/bin/python scripts/experiments/measurement_realism_dialogue_live.py critic --authorize-live-calls-after-root-approval --workers 4",
            "analyse": ".venv/bin/python scripts/experiments/measurement_realism_dialogue_live.py analyse",
            "package": ".venv/bin/python scripts/experiments/measurement_realism_dialogue_live.py package",
            "verify": ".venv/bin/python scripts/experiments/measurement_realism_dialogue_live.py verify",
        },
    }
    write_frozen_json(output / "study_plan.json", study_plan, "study plan")
    return study_plan


def validate_plan(config_path: Path, output: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    plan_path = output / "study_plan.json"
    if not plan_path.is_file():
        raise FileNotFoundError("run plan before any later stage")
    config = load_yaml(config_path)
    study_plan = read_json(plan_path)
    if study_plan.get("status") != "FROZEN_BEFORE_LIVE_CALLS":
        raise ValueError("invalid study-plan status")
    if study_plan.get("study_id") != config.get("study_id"):
        raise ValueError("study ID changed")
    paths = static_input_paths(output, config)
    current = {name: path_record(path) for name, path in sorted(paths.items())}
    if current != study_plan["static_inputs"]:
        raise ValueError("static study inputs changed after plan")
    reference = protected_reference_state(config)
    if reference != study_plan["protected_reference"]:
        raise ValueError("protected full-v1 reference changed after plan")
    call_path = output / study_plan["generation_call_plan"]["path"]
    if file_sha256(call_path) != study_plan["generation_call_plan"]["sha256"]:
        raise ValueError("generation call plan changed")
    if len(read_jsonl(call_path)) != study_plan["generation_call_plan"]["rows"]:
        raise ValueError("generation call-plan row count changed")
    return study_plan, config


def validate_generated_family(
    result: Mapping[str, Any],
    call: Mapping[str, Any],
    local_schema: Mapping[str, Any],
) -> dict[str, Any]:
    jsonschema.Draft202012Validator(local_schema).validate(dict(result))
    request = call["input"]
    exact = {
        "family_id": request["family_id"],
        "cell_id": request["cell_id"],
        "pilot_stratum": request["pilot_stratum"],
        "grammar_cell": request["grammar_cell"],
        "active_generator_kc_ids": request["active_generator_kc_ids"],
        "q_row": request["q_row"],
    }
    for field, expected in exact.items():
        if result[field] != expected:
            raise ValueError(f"generated family changed frozen {field}: {call['family_id']}")
    if len(result["q_row"]) != 18 or sum(result["q_row"]) != len(result["active_generator_kc_ids"]):
        raise ValueError(f"invalid generated Q row: {call['family_id']}")
    opportunities = result["opportunities"]
    expected_slots = request["formats"]
    if len(opportunities) != 5:
        raise ValueError(f"family must contain exactly five opportunities: {call['family_id']}")
    expected_identity = [
        (slot["opportunity_id"], slot["format"]) for slot in expected_slots
    ]
    observed_identity = [
        (row["opportunity_id"], row["format"]) for row in opportunities
    ]
    if observed_identity != expected_identity:
        raise ValueError(f"opportunity order or identity changed: {call['family_id']}")
    shared_target = result["shared_semantic_specification"]["canonical_target_example"]
    for row in opportunities:
        expected_type = RESPONSE_TYPES[row["format"]]
        if row["response_mechanism"]["type"] != expected_type:
            raise ValueError(f"response mechanism changed: {row['opportunity_id']}")
        if row["canonical_target_example"] != shared_target:
            raise ValueError(f"canonical target differs within family: {row['opportunity_id']}")
    open_row = opportunities[-1]
    if open_row["scoring_interpretation"]["kind"] != "interpretive_rubric":
        raise ValueError("open dialogue must use an interpretive rubric")
    if open_row["scoring_interpretation"]["accepted_responses"]:
        raise ValueError("open dialogue may not imply an exhaustive accepted-answer set")
    return dict(result)


def _evidence_result(evidence_dir: Path) -> dict[str, Any] | None:
    parsed = evidence_dir / "parsed_result.json"
    if parsed.is_file():
        missing = [name for name in CALL_EVIDENCE_FILES if not (evidence_dir / name).is_file()]
        if missing:
            raise FileNotFoundError(f"completed evidence is missing files in {evidence_dir}: {missing}")
        return read_json(parsed)
    if evidence_dir.exists():
        raise FileExistsError(f"incomplete call evidence requires audit: {evidence_dir}")
    return None


def _call_record(evidence_dir: Path, call_key: str, stage: str) -> dict[str, Any]:
    metadata = read_json(evidence_dir / "call_metadata.json")
    settings = read_json(evidence_dir / "model_settings.json")
    if settings["call_key"] != call_key or settings["stage"] != stage:
        raise ValueError(f"evidence settings identity changed: {evidence_dir}")
    return {
        "stage": stage,
        "call_key": call_key,
        "evidence_dir": relative(evidence_dir),
        "model": settings["model"],
        "reasoning_effort": settings["reasoning_effort"],
        "tokens_used": metadata.get("tokens_used"),
        "runtime_seconds": metadata.get("runtime_seconds"),
        "files": {name: path_record(evidence_dir / name) for name in CALL_EVIDENCE_FILES},
    }


def generate(
    config_path: Path,
    output: Path,
    evidence_root: Path,
    workers: int,
    authorized: bool,
) -> dict[str, Any]:
    if not authorized:
        raise PermissionError(f"generation requires {AUTHORIZATION_FLAG} after root approval")
    study_plan, config = validate_plan(config_path, output)
    calls = read_jsonl(output / study_plan["generation_call_plan"]["path"])
    provider_schema = read_json(output / config["generation"]["provider_schema"])
    local_schema = read_json(ROOT / config["source_protocol"]["generation_local_schema"])

    def one(call: Mapping[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any]]:
        family_id = str(call["family_id"])
        evidence_dir = evidence_root / "generation" / family_id
        parsed = _evidence_result(evidence_dir)
        if parsed is None:
            parsed = audited_model_call(
                str(call["rendered_prompt"]),
                model=str(config["generation"]["model"]),
                reasoning_effort=str(config["generation"]["reasoning_effort"]),
                input_data={
                    "study_id": study_plan["study_id"],
                    "stage": "generation",
                    "call_key": family_id,
                    "exact_model_input": call["input"],
                    "input_sha256": call["input_sha256"],
                    "rendered_prompt_sha256": call["rendered_prompt_sha256"],
                },
                stage="dialogue_continuum_generation",
                call_key=family_id,
                evidence_dir=evidence_dir,
                output_schema=provider_schema,
            )
        clean = validate_generated_family(parsed, call, local_schema)
        record = _call_record(evidence_dir, family_id, "dialogue_continuum_generation")
        print(canonical_json({"completed_generation": family_id}), flush=True)
        return family_id, clean, record

    results: dict[str, dict[str, Any]] = {}
    records: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(one, call): call for call in calls}
        for future in as_completed(futures):
            family_id, result, record = future.result()
            results[family_id] = result
            records[family_id] = record
    ordered_ids = [call["family_id"] for call in calls]
    ordered_results = [results[family_id] for family_id in ordered_ids]
    payload = write_frozen_jsonl(
        output / "generated_families.jsonl", ordered_results, "generated families"
    )
    ordered_records = [records[family_id] for family_id in ordered_ids]
    manifest = {
        "study_id": study_plan["study_id"],
        "status": "GENERATION_COMPLETE_AND_LOCALLY_VALIDATED",
        "calls": len(ordered_records),
        "families": len(ordered_results),
        "opportunities": sum(len(row["opportunities"]) for row in ordered_results),
        "model": study_plan["models"]["generation"],
        "generated_families_sha256": sha256_bytes(payload.encode("utf-8")),
        "generation_call_plan_sha256": study_plan["generation_call_plan"]["sha256"],
        "token_total": sum(int(row["tokens_used"] or 0) for row in ordered_records),
        "call_records": ordered_records,
        "scientific_boundary": {
            "local_rich_schema_validated": True,
            "exact_frozen_identities_validated": True,
            "learner_outcomes_read": False,
            "critic_outputs_read": False,
            "human_validation": False,
        },
    }
    if manifest["calls"] != 4 or manifest["opportunities"] != 20:
        raise ValueError("generation scale changed")
    write_frozen_json(output / "generation_manifest.json", manifest, "generation manifest")
    return manifest


def validate_generation(
    config: Mapping[str, Any], output: Path, study_plan: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest = read_json(output / "generation_manifest.json")
    path = output / "generated_families.jsonl"
    if file_sha256(path) != manifest["generated_families_sha256"]:
        raise ValueError("generated families changed")
    calls = read_jsonl(output / study_plan["generation_call_plan"]["path"])
    families = read_jsonl(path)
    if len(calls) != 4 or len(families) != 4:
        raise ValueError("generated family scale changed")
    local_schema = read_json(ROOT / config["source_protocol"]["generation_local_schema"])
    clean = [
        validate_generated_family(family, call, local_schema)
        for family, call in zip(families, calls)
    ]
    if manifest["status"] != "GENERATION_COMPLETE_AND_LOCALLY_VALIDATED":
        raise ValueError("generation manifest status changed")
    return clean, manifest


def family_view(
    family: Mapping[str, Any], role_config: Mapping[str, Any]
) -> dict[str, Any]:
    if role_config["sees_oracle_annotations"]:
        return dict(family)
    base: dict[str, Any] = {
        "family_id": family["family_id"],
        "opportunities": [],
    }
    sees_key = bool(role_config["sees_scoring_key"])
    for opportunity in family["opportunities"]:
        visible = {
            key: opportunity[key]
            for key in (
                "opportunity_id",
                "format",
                "instruction",
                "context",
                "stimulus",
                "dialogue_history",
                "response_mechanism",
            )
        }
        if sees_key:
            visible.update(
                {
                    "canonical_target_example": opportunity["canonical_target_example"],
                    "scoring_interpretation": opportunity["scoring_interpretation"],
                    "feedback_target": opportunity["feedback_target"],
                    "opportunity_boundary": opportunity["opportunity_boundary"],
                    "viability": opportunity["viability"],
                    "viability_note": opportunity["viability_note"],
                }
            )
        base["opportunities"].append(visible)
    return base


def render_critic_prompt(
    template: str,
    role: str,
    declaration: Mapping[str, Any],
    family: Mapping[str, Any],
) -> str:
    replacements = {
        "{{CRITIC_ROLE}}": role,
        "{{CRITIC_ID}}": str(declaration["critic_id"]),
        "{{ROLE_LENS}}": str(declaration["lens"]),
        "{{FAMILY_JSON}}": canonical_json(family_view(family, declaration)),
    }
    rendered = template
    for marker, value in replacements.items():
        if rendered.count(marker) != 1:
            raise ValueError(f"critic prompt must contain one {marker} marker")
        rendered = rendered.replace(marker, value)
    if any(marker in rendered for marker in replacements):
        raise ValueError("unresolved critic prompt marker")
    return rendered


def validate_critic_envelope(
    result: Mapping[str, Any],
    *,
    role: str,
    declaration: Mapping[str, Any],
    family: Mapping[str, Any],
    provider_schema: Mapping[str, Any],
    local_schema: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    jsonschema.Draft202012Validator(provider_schema).validate(dict(result))
    if set(result) != {"critic_role", "family_id", "judgments"}:
        raise ValueError("critic envelope fields changed")
    if result["critic_role"] != role or result["family_id"] != family["family_id"]:
        raise ValueError(f"critic envelope identity changed: {family['family_id']}/{role}")
    judgments = result["judgments"]
    if not isinstance(judgments, list) or len(judgments) != 5:
        raise ValueError(f"critic call must return exactly five judgments: {family['family_id']}/{role}")
    expected = [
        (row["opportunity_id"], row["format"]) for row in family["opportunities"]
    ]
    observed: list[tuple[str, str]] = []
    clean: list[dict[str, Any]] = []
    for judgment in judgments:
        jsonschema.Draft202012Validator(local_schema).validate(judgment)
        if judgment["critic_role"] != role:
            raise ValueError("critic role changed inside judgment")
        if judgment["critic_id"] != declaration["critic_id"]:
            raise ValueError("critic ID changed inside judgment")
        if judgment["family_id"] != family["family_id"]:
            raise ValueError("family ID changed inside judgment")
        observed.append((judgment["opportunity_id"], judgment["format"]))
        clean.append(dict(judgment))
    if observed != expected or len(set(observed)) != 5:
        raise ValueError(f"critic opportunity order or coverage changed: {family['family_id']}/{role}")
    return dict(result), clean


def create_critic_call_plan(
    config: Mapping[str, Any], output: Path, families: Sequence[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], str]:
    template = (output / config["critique"]["prompt"]).read_text(encoding="utf-8")
    provider_schema_path = output / config["critique"]["provider_schema"]
    rows: list[dict[str, Any]] = []
    for family in families:
        for role, declaration in config["critique"]["roles"].items():
            visible = family_view(family, declaration)
            rendered = render_critic_prompt(template, role, declaration, family)
            call_key = f"{family['family_id']}__{role}"
            exact_input = {
                "study_id": config["study_id"],
                "family_id": family["family_id"],
                "critic_role": role,
                "critic_id": declaration["critic_id"],
                "role_lens": declaration["lens"],
                "role_visibility": {
                    "sees_oracle_annotations": declaration["sees_oracle_annotations"],
                    "sees_scoring_key": declaration["sees_scoring_key"],
                },
                "family_view": visible,
            }
            rows.append(
                {
                    "stage": "dialogue_continuum_critique",
                    "call_key": call_key,
                    "family_id": family["family_id"],
                    "critic_role": role,
                    "critic_id": declaration["critic_id"],
                    "model": config["critique"]["model"],
                    "reasoning_effort": config["critique"]["reasoning_effort"],
                    "input": exact_input,
                    "input_sha256": sha256_bytes(canonical_json(exact_input).encode("utf-8")),
                    "rendered_prompt": rendered,
                    "rendered_prompt_sha256": sha256_bytes(rendered.encode("utf-8")),
                    "provider_schema_sha256": file_sha256(provider_schema_path),
                }
            )
    if len(rows) != 20:
        raise ValueError("critic call-plan scale changed")
    payload = write_frozen_jsonl(
        output / "critic_call_plan.jsonl", rows, "critic call plan"
    )
    return rows, payload


def critic(
    config_path: Path,
    output: Path,
    evidence_root: Path,
    workers: int,
    authorized: bool,
) -> dict[str, Any]:
    if not authorized:
        raise PermissionError(f"critique requires {AUTHORIZATION_FLAG} after root approval")
    study_plan, config = validate_plan(config_path, output)
    families, generation_manifest = validate_generation(config, output, study_plan)
    calls, call_plan_payload = create_critic_call_plan(config, output, families)
    family_index = {family["family_id"]: family for family in families}
    provider_schema = read_json(output / config["critique"]["provider_schema"])
    local_schema = read_json(ROOT / config["source_protocol"]["critic_local_schema"])

    def one(call: Mapping[str, Any]) -> tuple[str, dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
        call_key = str(call["call_key"])
        role = str(call["critic_role"])
        family = family_index[str(call["family_id"])]
        declaration = config["critique"]["roles"][role]
        evidence_dir = evidence_root / "critique" / call_key
        parsed = _evidence_result(evidence_dir)
        if parsed is None:
            parsed = audited_model_call(
                str(call["rendered_prompt"]),
                model=str(config["critique"]["model"]),
                reasoning_effort=str(config["critique"]["reasoning_effort"]),
                input_data=call["input"],
                stage="dialogue_continuum_critique",
                call_key=call_key,
                evidence_dir=evidence_dir,
                output_schema=provider_schema,
            )
        envelope, judgments = validate_critic_envelope(
            parsed,
            role=role,
            declaration=declaration,
            family=family,
            provider_schema=provider_schema,
            local_schema=local_schema,
        )
        record = _call_record(evidence_dir, call_key, "dialogue_continuum_critique")
        print(canonical_json({"completed_critique": call_key}), flush=True)
        return call_key, envelope, judgments, record

    envelopes: dict[str, dict[str, Any]] = {}
    judgments_by_call: dict[str, list[dict[str, Any]]] = {}
    records: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(one, call): call for call in calls}
        for future in as_completed(futures):
            call_key, envelope, judgments, record = future.result()
            envelopes[call_key] = envelope
            judgments_by_call[call_key] = judgments
            records[call_key] = record
    ordered_keys = [call["call_key"] for call in calls]
    envelope_payload = write_frozen_jsonl(
        output / "critic_envelopes.jsonl",
        [envelopes[key] for key in ordered_keys],
        "critic envelopes",
    )
    flattened = [row for key in ordered_keys for row in judgments_by_call[key]]
    judgment_payload = write_frozen_jsonl(
        output / "critic_judgments.jsonl", flattened, "critic judgments"
    )
    manifest = {
        "study_id": study_plan["study_id"],
        "status": "INDEPENDENT_AUTOMATED_CRITIQUE_COMPLETE",
        "calls": len(ordered_keys),
        "families": len(families),
        "roles": list(config["critique"]["roles"]),
        "judgments": len(flattened),
        "judgments_per_call": config["critique"]["judgments_per_call"],
        "model": study_plan["models"]["critique"],
        "critic_call_plan_sha256": sha256_bytes(call_plan_payload.encode("utf-8")),
        "generation_manifest_sha256": file_sha256(output / "generation_manifest.json"),
        "critic_envelopes_sha256": sha256_bytes(envelope_payload.encode("utf-8")),
        "critic_judgments_sha256": sha256_bytes(judgment_payload.encode("utf-8")),
        "token_total": sum(int(records[key]["tokens_used"] or 0) for key in ordered_keys),
        "call_records": [records[key] for key in ordered_keys],
        "role_independence": {
            "one_family_and_one_role_per_call": True,
            "roles_receive_other_role_outputs": False,
            "fresh_model_context_per_call": True,
        },
        "evidence_boundary": {
            "automated_stress_test": True,
            "human_or_expert_gold": False,
            "role_labels_do_not_confer_human_identity": True,
        },
        "source_generation_manifest_status": generation_manifest["status"],
    }
    if manifest["calls"] != 20 or manifest["judgments"] != 100:
        raise ValueError("critic scale changed")
    write_frozen_json(output / "critique_manifest.json", manifest, "critique manifest")
    return manifest


def validate_critique(
    config: Mapping[str, Any],
    output: Path,
    families: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest = read_json(output / "critique_manifest.json")
    call_plan_path = output / "critic_call_plan.jsonl"
    envelope_path = output / "critic_envelopes.jsonl"
    judgment_path = output / "critic_judgments.jsonl"
    if file_sha256(call_plan_path) != manifest["critic_call_plan_sha256"]:
        raise ValueError("critic call plan changed")
    if file_sha256(envelope_path) != manifest["critic_envelopes_sha256"]:
        raise ValueError("critic envelopes changed")
    if file_sha256(judgment_path) != manifest["critic_judgments_sha256"]:
        raise ValueError("critic judgments changed")
    calls = read_jsonl(call_plan_path)
    envelopes = read_jsonl(envelope_path)
    judgments = read_jsonl(judgment_path)
    if len(calls) != 20 or len(envelopes) != 20 or len(judgments) != 100:
        raise ValueError("critic artifact scale changed")
    provider_schema = read_json(output / config["critique"]["provider_schema"])
    local_schema = read_json(ROOT / config["source_protocol"]["critic_local_schema"])
    family_index = {family["family_id"]: family for family in families}
    reconstructed: list[dict[str, Any]] = []
    for call, envelope in zip(calls, envelopes):
        role = call["critic_role"]
        _envelope, clean = validate_critic_envelope(
            envelope,
            role=role,
            declaration=config["critique"]["roles"][role],
            family=family_index[call["family_id"]],
            provider_schema=provider_schema,
            local_schema=local_schema,
        )
        reconstructed.extend(clean)
    if reconstructed != judgments:
        raise ValueError("flat critic judgments do not replay from envelopes")
    if manifest["status"] != "INDEPENDENT_AUTOMATED_CRITIQUE_COMPLETE":
        raise ValueError("critique manifest status changed")
    return judgments, manifest


def load_source_analyzer(config: Mapping[str, Any]):
    path = ROOT / config["source_protocol"]["analyzer"]
    spec = importlib.util.spec_from_file_location("dialogue_pilot_frozen_analyzer", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import source analyzer: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render_report(
    analysis: Mapping[str, Any],
    families: Sequence[Mapping[str, Any]],
    critique_manifest: Mapping[str, Any],
    judgments: Sequence[Mapping[str, Any]],
) -> str:
    viability: dict[str, Counter[str]] = {format_id: Counter() for format_id in FORMAT_ORDER}
    for family in families:
        for opportunity in family["opportunities"]:
            viability[opportunity["format"]][opportunity["viability"]] += 1
    lines = [
        "# Automated ecological-precision dialogue pilot",
        "",
        "## Evidence boundary",
        "",
        "This four-family pilot contains automated generation and five independent",
        "automated critic lenses. It is a structured stress test, not human learner,",
        "teacher, expert, product, or response-process evidence. It does not establish",
        "ecological validity, platform deployability, learner answerability, or justify",
        "an extended dataset release on its own.",
        "",
        "No scalar realism score or weighted ecology/precision composite was computed.",
        "",
        "## Executed scale",
        "",
        f"- Generated families: {len(families)}",
        f"- Learner-facing opportunities: {sum(len(row['opportunities']) for row in families)}",
        f"- Independent family-by-role critic calls: {critique_manifest['calls']}",
        f"- Opportunity judgments: {analysis['scale']['judgments']}",
        "",
        "## Generated viability by format",
        "",
        "| Format | Candidate | Not viable |",
        "|---|---:|---:|",
    ]
    for format_id in FORMAT_ORDER:
        lines.append(
            f"| `{format_id}` | {viability[format_id]['candidate']} | {viability[format_id]['not_viable']} |"
        )
    lines.extend(
        [
            "",
            "## Separate automated diagnostics by format",
            "",
            "Counts below retain categories rather than converting them to a score.",
            "",
            "| Format | Task comprehension | Interaction naturalness | Platform plausibility | Answer determinacy | KC attribution | Shortcut true/applicable |",
            "|---|---|---|---|---|---|---:|",
        ]
    )
    for format_id in FORMAT_ORDER:
        summary = analysis["by_format"][format_id]
        ratings = summary["rating_distributions"]
        shortcut = summary["target_avoiding_shortcut"]
        format_counts = lambda key: ", ".join(
            f"{name}:{count}" for name, count in ratings[key].items()
        )
        lines.append(
            f"| `{format_id}` | {format_counts('task_comprehensibility')} | "
            f"{format_counts('interaction_naturalness')} | "
            f"{format_counts('platform_plausibility')} | "
            f"{format_counts('answer_determinacy')} | "
            f"{format_counts('kc_attribution')} | {shortcut['true']}/"
            f"{shortcut['applicable_judgments']} |"
        )
    lines.extend(
        [
            "",
            "## Role disagreement",
            "",
            "Disagreement is retained at the exact opportunity level.",
            "",
            "| Dimension | Opportunities with disagreement |",
            "|---|---:|",
        ]
    )
    for dimension, record in analysis["role_disagreement"].items():
        lines.append(f"| `{dimension}` | {record['count']} |")
    open_not_viable = viability["open_dialogue"]["not_viable"]
    measurement_open = [
        row
        for row in judgments
        if row["critic_role"] == "measurement" and row["format"] == "open_dialogue"
    ]
    not_attributable = sum(
        row["ratings"]["kc_attribution"] == "not_attributable" for row in measurement_open
    )
    lines.extend(
        [
            "",
            "## Scale decision boundary",
            "",
            f"The generator marked {open_not_viable} of four open-dialogue opportunities `not_viable`.",
            f"The measurement critic marked {not_attributable} open-dialogue opportunities `not_attributable`.",
            "Regardless of these automated counts, the preregistered human/expert and",
            "learner response-space gates remain outstanding. This pilot therefore remains",
            "a bounded qualitative mechanism study and cannot authorize bank-scale dialogue",
            "generation or a dataset release.",
            "",
            "## Interpretation limits",
            "",
            "- Four selected GrammarCells do not estimate bank- or platform-level rates.",
            "- Model roles are prompts, not members of the named human populations.",
            "- Category agreement does not validate the response process.",
            "- A more natural interaction can still be a weaker measurement opportunity.",
            "- Human review and actual learner responses are required before deployability",
            "  or answerability claims.",
            "",
        ]
    )
    return "\n".join(lines)


def analyse(config_path: Path, output: Path) -> dict[str, Any]:
    study_plan, config = validate_plan(config_path, output)
    families, generation_manifest = validate_generation(config, output, study_plan)
    judgments, critique_manifest = validate_critique(config, output, families)
    source_plan_path = ROOT / config["source_protocol"]["selected_cells"]
    source_plan = read_json(source_plan_path)
    analyzer = load_source_analyzer(config)
    clean_rows, opportunities = analyzer.validate(
        source_plan, judgments, allow_incomplete=False
    )
    input_records = {
        "source_plan": path_record(source_plan_path),
        "generated_families": path_record(output / "generated_families.jsonl")
        | {"rows": len(families)},
        "critic_judgments": path_record(output / "critic_judgments.jsonl")
        | {"rows": len(judgments)},
        "source_analyzer": path_record(ROOT / config["source_protocol"]["analyzer"]),
    }
    result = analyzer.analyze(
        source_plan, clean_rows, opportunities, input_records=input_records
    )
    if result["evidence_boundary"]["scalar_realism_score_computed"] is not False:
        raise ValueError("source analyzer computed a scalar realism score")
    if result["evidence_boundary"]["weighted_composite_computed"] is not False:
        raise ValueError("source analyzer computed a weighted composite")
    analysis_payload = json.dumps(
        result, ensure_ascii=False, indent=2, sort_keys=True
    ) + "\n"
    write_frozen_text(output / "analysis.json", analysis_payload, "analysis")
    report_payload = render_report(result, families, critique_manifest, judgments)
    write_frozen_text(output / "report.md", report_payload, "pilot report")
    manifest = {
        "study_id": study_plan["study_id"],
        "status": "AUTOMATED_DIALOGUE_PILOT_ANALYSED",
        "analysis_sha256": sha256_bytes(analysis_payload.encode("utf-8")),
        "report_sha256": sha256_bytes(report_payload.encode("utf-8")),
        "generation_manifest_sha256": file_sha256(output / "generation_manifest.json"),
        "critique_manifest_sha256": file_sha256(output / "critique_manifest.json"),
        "scale": result["scale"],
        "scalar_realism_score_computed": False,
        "weighted_composite_computed": False,
        "human_or_expert_gold": False,
        "dataset_release_justified_by_this_pilot_alone": False,
        "source_generation_manifest_status": generation_manifest["status"],
    }
    write_frozen_json(output / "analysis_manifest.json", manifest, "analysis manifest")
    return manifest


def _bundle_call(evidence_dir: Path, stage: str, call_key: str) -> dict[str, Any]:
    missing = [name for name in CALL_EVIDENCE_FILES if not (evidence_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"call evidence missing for {call_key}: {missing}")
    files: dict[str, Any] = {}
    for name in CALL_EVIDENCE_FILES:
        path = evidence_dir / name
        content = path.read_text(encoding="utf-8")
        files[name] = {
            "sha256": sha256_bytes(content.encode("utf-8")),
            "bytes": len(content.encode("utf-8")),
            "content": content,
        }
    return {
        "stage": stage,
        "call_key": call_key,
        "source_evidence_dir": relative(evidence_dir),
        "files": files,
    }


def package(config_path: Path, output: Path, evidence_root: Path) -> dict[str, Any]:
    study_plan, config = validate_plan(config_path, output)
    families, _generation_manifest = validate_generation(config, output, study_plan)
    _judgments, _critique_manifest = validate_critique(config, output, families)
    analysis_manifest = read_json(output / "analysis_manifest.json")
    if file_sha256(output / "analysis.json") != analysis_manifest["analysis_sha256"]:
        raise ValueError("analysis changed before packaging")
    if file_sha256(output / "report.md") != analysis_manifest["report_sha256"]:
        raise ValueError("report changed before packaging")
    generation_calls = read_jsonl(output / "generation_call_plan.jsonl")
    critic_calls = read_jsonl(output / "critic_call_plan.jsonl")
    bundle_rows = [
        _bundle_call(
            evidence_root / "generation" / call["family_id"],
            "dialogue_continuum_generation",
            call["call_key"],
        )
        for call in generation_calls
    ]
    bundle_rows.extend(
        _bundle_call(
            evidence_root / "critique" / call["call_key"],
            "dialogue_continuum_critique",
            call["call_key"],
        )
        for call in critic_calls
    )
    if len(bundle_rows) != 24:
        raise ValueError("evidence bundle call count changed")
    bundle_payload = write_frozen_jsonl(
        output / "call_evidence_bundle.jsonl", bundle_rows, "call evidence bundle"
    )
    artifact_names = (
        "study_plan.json",
        "generation_call_plan.jsonl",
        "generated_families.jsonl",
        "generation_manifest.json",
        "critic_call_plan.jsonl",
        "critic_envelopes.jsonl",
        "critic_judgments.jsonl",
        "critique_manifest.json",
        "analysis.json",
        "analysis_manifest.json",
        "report.md",
    )
    manifest = {
        "study_id": study_plan["study_id"],
        "status": "BYTE_EXACT_CALL_EVIDENCE_PACKAGED",
        "calls": len(bundle_rows),
        "generation_calls": len(generation_calls),
        "critic_calls": len(critic_calls),
        "call_evidence_bundle": {
            "path": "call_evidence_bundle.jsonl",
            "rows": len(bundle_rows),
            "sha256": sha256_bytes(bundle_payload.encode("utf-8")),
            "bytes": len(bundle_payload.encode("utf-8")),
        },
        "artifacts": {
            name: path_record(output / name) for name in artifact_names
        },
        "restricted_evidence_root": relative(evidence_root),
        "evidence_boundary": {
            "automated_calls": 24,
            "human_or_expert_gold": False,
            "full_v1_mutated": False,
        },
    }
    write_frozen_json(output / "package_manifest.json", manifest, "package manifest")
    return manifest


def verify(config_path: Path, output: Path) -> dict[str, Any]:
    study_plan, config = validate_plan(config_path, output)
    families, generation_manifest = validate_generation(config, output, study_plan)
    judgments, critique_manifest = validate_critique(config, output, families)
    analysis_manifest = read_json(output / "analysis_manifest.json")
    analysis = read_json(output / "analysis.json")
    if file_sha256(output / "analysis.json") != analysis_manifest["analysis_sha256"]:
        raise ValueError("analysis hash mismatch")
    if file_sha256(output / "report.md") != analysis_manifest["report_sha256"]:
        raise ValueError("report hash mismatch")
    if analysis["scale"]["planned_opportunities"] != 20:
        raise ValueError("analysis opportunity scale changed")
    if analysis["scale"]["judgments"] != 100:
        raise ValueError("analysis judgment scale changed")
    if analysis["evidence_boundary"]["scalar_realism_score_computed"] is not False:
        raise ValueError("scalar realism score appeared")
    if analysis["evidence_boundary"]["weighted_composite_computed"] is not False:
        raise ValueError("weighted composite appeared")

    source_plan = read_json(ROOT / config["source_protocol"]["selected_cells"])
    analyzer = load_source_analyzer(config)
    clean_rows, opportunities = analyzer.validate(
        source_plan, judgments, allow_incomplete=False
    )
    replayed = analyzer.analyze(
        source_plan,
        clean_rows,
        opportunities,
        input_records=analysis["inputs"],
    )
    if replayed != analysis:
        raise ValueError("analysis does not replay exactly")

    package_manifest = read_json(output / "package_manifest.json")
    bundle_path = output / package_manifest["call_evidence_bundle"]["path"]
    if file_sha256(bundle_path) != package_manifest["call_evidence_bundle"]["sha256"]:
        raise ValueError("call evidence bundle hash mismatch")
    bundle_rows = read_jsonl(bundle_path)
    if len(bundle_rows) != 24:
        raise ValueError("call evidence bundle row count changed")
    for row in bundle_rows:
        for name, record in row["files"].items():
            payload = record["content"].encode("utf-8")
            if sha256_bytes(payload) != record["sha256"] or len(payload) != record["bytes"]:
                raise ValueError(f"bundled call evidence changed: {row['call_key']}/{name}")
    for name, record in package_manifest["artifacts"].items():
        path = output / name
        if path_record(path) != record:
            raise ValueError(f"packaged artifact changed: {name}")
    reference = protected_reference_state(config)
    if reference != study_plan["protected_reference"]:
        raise ValueError("full-v1 changed during study")
    verification = {
        "study_id": study_plan["study_id"],
        "status": "VERIFIED_COMPLETE_AUTOMATED_DIALOGUE_PILOT",
        "protected_full_v1_unchanged": True,
        "generation_calls": generation_manifest["calls"],
        "generated_families": len(families),
        "opportunities": sum(len(row["opportunities"]) for row in families),
        "critic_calls": critique_manifest["calls"],
        "critic_judgments": len(judgments),
        "critic_roles_independent": True,
        "strict_local_validation_replayed": True,
        "analysis_replayed_exactly": True,
        "byte_exact_call_evidence_rows": len(bundle_rows),
        "scalar_realism_score_computed": False,
        "weighted_composite_computed": False,
        "human_or_expert_gold": False,
        "dataset_release_justified_by_this_pilot_alone": False,
        "hashes": {
            "study_plan": file_sha256(output / "study_plan.json"),
            "generated_families": file_sha256(output / "generated_families.jsonl"),
            "critic_judgments": file_sha256(output / "critic_judgments.jsonl"),
            "analysis": file_sha256(output / "analysis.json"),
            "call_evidence_bundle": file_sha256(bundle_path),
            "package_manifest": file_sha256(output / "package_manifest.json"),
        },
    }
    write_frozen_json(output / "verification.json", verification, "verification result")
    return verification


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "stage", choices=("plan", "generate", "critic", "analyse", "package", "verify")
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(AUTHORIZATION_FLAG, action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = args.config.resolve()
    output = args.output.resolve()
    evidence = args.evidence_root.resolve()
    authorized = bool(args.authorize_live_calls_after_root_approval)
    if args.stage == "plan":
        result = plan(config, output)
    elif args.stage == "generate":
        result = generate(config, output, evidence, args.workers, authorized)
    elif args.stage == "critic":
        result = critic(config, output, evidence, args.workers, authorized)
    elif args.stage == "analyse":
        result = analyse(config, output)
    elif args.stage == "package":
        result = package(config, output, evidence)
    else:
        result = verify(config, output)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
