#!/usr/bin/env python3
"""Build an audited, fully crossed matched-format grammar measurement bank.

No stage reads learner outcomes or private simulator truth.  Model-backed stages
are explicit, resumable ``codex exec`` calls whose complete evidence remains in
the run directory.  The final bank freezes only when all 38 whole families pass
the preregistered deterministic, solver, and role-separated critic gates.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import jsonschema
import yaml


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.io import render
from grammar_kt.model_evidence import audited_model_call


MODULE = ROOT / "modules/measurement_realism/matched_bank"
DEFAULT_CONFIG = MODULE / "config.yaml"
DEFAULT_SELECTED = (
    ROOT / "experiments/measurement_realism/design/format_selection/selected_cells.json"
)
DEFAULT_RUNS = ROOT / "experiments/measurement_realism/design/bank_protocol/runs"
FORMATS = (
    "constrained_cloze",
    "dialogue_completion",
    "multiple_choice",
    "sentence_transformation",
)
ROLES = ("linguistic", "measurement", "platform_product")
SLOT = "[[RESPONSE]]"


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def semantic_hash(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected one JSON object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


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
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        label,
    )


def write_frozen_jsonl(path: Path, rows: Iterable[Mapping[str, Any]], label: str) -> None:
    payload = "".join(canonical_json(dict(row)) + "\n" for row in rows)
    write_frozen_text(path, payload, label)


def _schema(path: Path) -> dict[str, Any]:
    value = read_json(path)
    jsonschema.Draft202012Validator.check_schema(value)
    return value


def validate_schema(instance: Any, schema: Mapping[str, Any], label: str) -> None:
    errors = sorted(
        jsonschema.Draft202012Validator(dict(schema)).iter_errors(instance),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.absolute_path) or "<root>"
        raise ValueError(f"{label} schema error at {location}: {first.message}")


def _exact_rank(rows: Sequence[Sequence[int]]) -> int:
    matrix = [[Fraction(value) for value in row] for row in rows]
    rank = 0
    columns = len(matrix[0]) if matrix else 0
    for column in range(columns):
        pivot = next((i for i in range(rank, len(matrix)) if matrix[i][column]), None)
        if pivot is None:
            continue
        matrix[rank], matrix[pivot] = matrix[pivot], matrix[rank]
        divisor = matrix[rank][column]
        matrix[rank] = [value / divisor for value in matrix[rank]]
        for i in range(len(matrix)):
            if i == rank or not matrix[i][column]:
                continue
            factor = matrix[i][column]
            matrix[i] = [
                left - factor * right
                for left, right in zip(matrix[i], matrix[rank])
            ]
        rank += 1
        if rank == len(matrix):
            break
    return rank


def load_inputs(
    config_path: Path = DEFAULT_CONFIG,
    selected_path: Path = DEFAULT_SELECTED,
) -> tuple[dict[str, Any], dict[str, Any]]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    selected = read_json(selected_path)
    validate_schema(selected, _schema(MODULE / config["selected_cells"]["schema"]), "selected cells")
    if sha256_file(selected_path) != config["selected_cells"]["sha256"]:
        raise ValueError("selected_cells.json does not match preregistered SHA-256")
    selection_input_manifest = read_json(selected_path.parent / "input_manifest.json")
    manifest_hashes = {
        name: metadata["sha256"]
        for name, metadata in selection_input_manifest["inputs"].items()
    }
    if selected["input_hashes"] != manifest_hashes:
        raise ValueError("selected cells do not retain their exact input hashes")
    for name, metadata in selection_input_manifest["inputs"].items():
        path = ROOT / metadata["path"]
        if not path.is_file() or sha256_file(path) != metadata["sha256"]:
            raise ValueError(f"selected-cell source input changed: {name}")
    expected = config["selected_cells"]["expected"]
    if len(selected["seen_cells"]) != expected["seen_cells"]:
        raise ValueError("wrong seen-cell count")
    if len(selected["held_out_cells"]) != 2:
        raise ValueError("wrong held-out cell count")
    if len(selected["kc_order"]) != expected["generator_kcs"]:
        raise ValueError("wrong KC count")
    if _exact_rank([row["q_row"] for row in selected["seen_cells"]]) != expected["seen_cell_q_rank"]:
        raise ValueError("selected seen-cell Q basis is not exact rank 18")
    cells = [*selected["seen_cells"], *selected["held_out_cells"]]
    if len({row["cell_id"] for row in cells}) != 20:
        raise ValueError("selected cells are not unique")
    if sorted(int(row["selection_order"]) for row in cells) != list(range(1, 21)):
        raise ValueError("selection order is not a permutation of 1..20")
    if any(
        row["grammar_regime"] != "seen" or not row["acquisition_updates"]
        for row in selected["seen_cells"]
    ):
        raise ValueError("seen cells must be updating acquisition cells")
    if {row["grammar_regime"] for row in selected["held_out_cells"]} != {
        "unseen_combination",
        "unseen_value",
    } or any(row["acquisition_updates"] for row in selected["held_out_cells"]):
        raise ValueError("held-out cells must be one non-updating probe per regime")
    for row in cells:
        projected = [
            kc_id for kc_id, active in zip(selected["kc_order"], row["q_row"])
            if active == 1
        ]
        if projected != row["generator_kc_ids"]:
            raise ValueError(f"selected-cell KC/Q mismatch: {row['cell_id']}")
    if tuple(config["design"]["canonical_format_order"]) != FORMATS:
        raise ValueError("canonical format order drifted")
    if config["generation"]["candidate_rounds_per_family"] != 3:
        raise ValueError("confirmatory protocol requires exactly three rounds")
    return config, selected


def load_kcs() -> dict[str, dict[str, Any]]:
    return {
        row["id"]: row
        for row in read_jsonl(ROOT / "data/grammar_kt_full_v1/kcs.jsonl")
    }


def family_specs(config: Mapping[str, Any], selected: Mapping[str, Any]) -> list[dict[str, Any]]:
    selection_prefix = config["selected_cells"]["sha256"][: config["deterministic_checks"]["id_specification"]["selection_hash_prefix_characters"]]
    regime_codes = config["deterministic_checks"]["id_specification"]["regime_codes"]
    rows: list[dict[str, Any]] = []
    cells = sorted(
        [*selected["seen_cells"], *selected["held_out_cells"]],
        key=lambda row: int(row["selection_order"]),
    )
    for cell in cells:
        variants = (1, 2) if cell["grammar_regime"] == "seen" else (1,)
        for variant in variants:
            family_id = (
                f"mb0_{selection_prefix}_{regime_codes[cell['grammar_regime']]}_"
                f"{cell['cell_id']}_sv{variant:02d}"
            )
            rows.append(
                {
                    "family_id": family_id,
                    "cell_id": cell["cell_id"],
                    "grammar_regime": cell["grammar_regime"],
                    "acquisition_updates": bool(cell["acquisition_updates"]),
                    "semantic_variant_index": variant,
                    "cell": cell,
                }
            )
    if len(rows) != config["design"]["expected_families"]:
        raise ValueError("family expansion did not produce 38 families")
    return rows


def candidate_id(family_id: str, round_index: int) -> str:
    return f"{family_id}_g{round_index:02d}"


def candidate_item_id(candidate: str, item_format: str, config: Mapping[str, Any]) -> str:
    return f"{candidate}_{config['deterministic_checks']['id_specification']['format_codes'][item_format]}"


def slot_item_id(family_id: str, item_format: str, config: Mapping[str, Any]) -> str:
    return f"{family_id}_{config['deterministic_checks']['id_specification']['format_codes'][item_format]}"


def generation_request(
    spec: Mapping[str, Any],
    round_index: int,
    config: Mapping[str, Any],
    kcs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    candidate = candidate_id(spec["family_id"], round_index)
    cell = spec["cell"]
    identifiers = {
        "protocol_id": config["protocol_id"],
        "family_id": spec["family_id"],
        "candidate_id": candidate,
        "candidate_round": round_index,
        "cell_id": spec["cell_id"],
        "semantic_variant_index": spec["semantic_variant_index"],
        "candidate_item_ids": {
            item_format: candidate_item_id(candidate, item_format, config)
            for item_format in FORMATS
        },
    }
    input_data = {
        "identifiers": identifiers,
        "intended_cefr": config["design"]["intended_proficiency"]["cefr"],
        "grammar_regime": spec["grammar_regime"],
        "grammar_cell": cell["features"],
        "generator_kcs": [
            {
                "id": kc_id,
                "name": kcs[kc_id]["name"],
                "description": kcs[kc_id]["description"],
                "activation_rule": kcs[kc_id]["activation_rule"],
            }
            for kc_id in cell["generator_kc_ids"]
        ],
        "q_row": cell["q_row"],
        "source_support": {
            "source_ids": cell["source_ids"],
            "reference_prompt": cell.get("reference_prompt"),
            "reference_target_answer": cell.get("reference_target_answer"),
            "reference_accepted_answers": cell.get("reference_accepted_answers", []),
            "copy_policy": cell.get("reference_stem_reuse"),
        },
        "format_contracts": {
            item_format: config["formats"][item_format] for item_format in FORMATS
        },
    }
    return {
        "request_id": f"gen_{candidate}",
        "stage": "generation",
        "family_id": spec["family_id"],
        "candidate_id": candidate,
        "candidate_round": round_index,
        "input": input_data,
    }


def _copy_frozen(source: Path, target: Path, label: str) -> None:
    write_frozen_text(target, source.read_text(encoding="utf-8"), label)


def repository_head() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def codex_cli_version() -> str | None:
    result = subprocess.run(
        ["codex", "--version"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def create_plan(run_root: Path, config_path: Path, selected_path: Path) -> dict[str, Any]:
    config, selected = load_inputs(config_path, selected_path)
    if run_root.exists() and not (run_root / "plan.json").is_file():
        raise FileExistsError(f"nonempty/unplanned run root: {run_root}")
    frozen = run_root / "frozen"
    _copy_frozen(config_path, frozen / "config.yaml", "frozen config")
    _copy_frozen(selected_path, frozen / "selected_cells.json", "frozen selected cells")
    _copy_frozen(
        selected_path.parent / "input_manifest.json",
        frozen / "selection_input_manifest.json",
        "frozen selection input manifest",
    )
    for path in sorted((MODULE / "prompts").glob("*.txt")):
        _copy_frozen(path, frozen / "prompts" / path.name, f"frozen prompt {path.name}")
    for path in sorted((MODULE / "schemas").glob("*.json")):
        _copy_frozen(path, frozen / "schemas" / path.name, f"frozen schema {path.name}")
    kcs = load_kcs()
    requests = [
        generation_request(spec, round_index, config, kcs)
        for round_index in range(1, 4)
        for spec in family_specs(config, selected)
    ]
    write_frozen_jsonl(
        run_root / "plans/generation_requests.jsonl",
        requests,
        "generation request plan",
    )
    source_paths = {
        "config": config_path,
        "selected_cells": selected_path,
        "selection_input_manifest": selected_path.parent / "input_manifest.json",
        "kcs": ROOT / "data/grammar_kt_full_v1/kcs.jsonl",
        "v1_manifest": ROOT / "data/grammar_kt_full_v1/manifest.json",
        "implementation": Path(__file__).resolve(),
        "audited_backend": ROOT / "src/grammar_kt/model_evidence.py",
    }
    for path in sorted((MODULE / "prompts").glob("*.txt")):
        source_paths[f"prompt:{path.name}"] = path
    for path in sorted((MODULE / "schemas").glob("*.json")):
        source_paths[f"schema:{path.name}"] = path
    inputs = {
        name: {
            "path": str(path.relative_to(ROOT)),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
        for name, path in source_paths.items()
    }
    write_frozen_json(frozen / "input_hashes.json", inputs, "input hashes")
    plan = {
        "protocol_id": config["protocol_id"],
        "status": "PREREGISTERED_BEFORE_MATCHED_BANK_MODEL_CALLS",
        "run_id": run_root.name,
        "repository_head_at_plan": repository_head(),
        "execution_environment": {
            "python": sys.version.split()[0],
            "codex_cli": codex_cli_version(),
            "provider_output_schema": True,
            "fresh_ephemeral_context_per_request": True,
        },
        "scientific_boundary": {
            "learner_outcomes_read": False,
            "simulator_or_kt_results_read": False,
            "full_v1_mutated": False,
            "q_projection_model_editable": False,
        },
        "counts": {"families": 38, "items_if_frozen": 152, "generation_requests": 114},
        "inputs": inputs,
        "generation_plan": {
            "path": "plans/generation_requests.jsonl",
            "sha256": sha256_file(run_root / "plans/generation_requests.jsonl"),
        },
        "commands": {
            "generate_round": f".venv/bin/python scripts/experiments/measurement_realism_bank.py generate --run-id {run_root.name} --round ROUND --workers 4",
            "solve_round": f".venv/bin/python scripts/experiments/measurement_realism_bank.py solve --run-id {run_root.name} --round ROUND --workers 4",
            "critic_round": f".venv/bin/python scripts/experiments/measurement_realism_bank.py critic --run-id {run_root.name} --round ROUND --workers 3",
            "curate_round": f".venv/bin/python scripts/experiments/measurement_realism_bank.py curate --run-id {run_root.name} --round ROUND",
            "freeze": f".venv/bin/python scripts/experiments/measurement_realism_bank.py freeze --run-id {run_root.name}",
            "verify": f".venv/bin/python scripts/experiments/verify_measurement_realism_bank.py --run-id {run_root.name}",
        },
    }
    write_frozen_json(run_root / "plan.json", plan, "run plan")
    return plan


def validate_run(run_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    plan = read_json(run_root / "plan.json")
    if plan.get("status") != "PREREGISTERED_BEFORE_MATCHED_BANK_MODEL_CALLS":
        raise ValueError("invalid or missing preregistered plan")
    for metadata in plan["inputs"].values():
        path = ROOT / metadata["path"]
        if not path.is_file() or sha256_file(path) != metadata["sha256"]:
            raise ValueError(f"planned input changed: {metadata['path']}")
    if sha256_file(run_root / plan["generation_plan"]["path"]) != plan["generation_plan"]["sha256"]:
        raise ValueError("generation request plan changed")
    config = yaml.safe_load((run_root / "frozen/config.yaml").read_text(encoding="utf-8"))
    selected = read_json(run_root / "frozen/selected_cells.json")
    frozen_targets = {
        "config": run_root / "frozen/config.yaml",
        "selected_cells": run_root / "frozen/selected_cells.json",
        "selection_input_manifest": run_root / "frozen/selection_input_manifest.json",
        **{
            name: run_root / "frozen/prompts" / name.split(":", 1)[1]
            for name in plan["inputs"] if name.startswith("prompt:")
        },
        **{
            name: run_root / "frozen/schemas" / name.split(":", 1)[1]
            for name in plan["inputs"] if name.startswith("schema:")
        },
    }
    for name, path in frozen_targets.items():
        if not path.is_file() or sha256_file(path) != plan["inputs"][name]["sha256"]:
            raise ValueError(f"frozen run input changed: {name}")
    if read_json(run_root / "frozen/input_hashes.json") != plan["inputs"]:
        raise ValueError("frozen input-hash ledger changed")
    return plan, config, selected


def _dynamic_schema(base: Mapping[str, Any], constants: Mapping[str, Any]) -> dict[str, Any]:
    schema = copy.deepcopy(dict(base))
    for key, value in constants.items():
        if value is None:
            value_type: str | list[str] = "null"
        elif isinstance(value, bool):
            value_type = "boolean"
        elif isinstance(value, int):
            value_type = "integer"
        elif isinstance(value, float):
            value_type = "number"
        elif isinstance(value, str):
            value_type = "string"
        else:
            raise TypeError(f"unsupported dynamic schema constant: {key}")
        # The Responses API structured-output subset requires an explicit type
        # alongside every constant.  Keep the exact identity constraint while
        # making the frozen provider schema executable.
        schema["properties"][key] = {"type": value_type, "const": value}
    return schema


def render_generation_prompt(run_root: Path, request: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    schema = _dynamic_schema(
        _schema(run_root / "frozen/schemas/generated_family.schema.json"),
        {
            "family_id": request["family_id"],
            "candidate_id": request["candidate_id"],
            "candidate_round": request["candidate_round"],
            "cell_id": request["input"]["identifiers"]["cell_id"],
            "grammar_regime": request["input"]["grammar_regime"],
            "semantic_variant_index": request["input"]["identifiers"]["semantic_variant_index"],
        },
    )
    values = dict(request["input"])
    values["semantic_variant_index"] = request["input"]["identifiers"]["semantic_variant_index"]
    values["output_schema"] = schema
    template = (run_root / "frozen/prompts/generate_family.txt").read_text(encoding="utf-8")
    return render(template, values), schema


def _attempt_record(
    run_root: Path,
    request: Mapping[str, Any],
    attempt: int,
    evidence: Path,
    prompt: str,
    schema: Mapping[str, Any],
    model: str,
    effort: str,
    status: str,
) -> dict[str, Any]:
    def maybe_hash(name: str) -> str | None:
        path = evidence / name
        return sha256_file(path) if path.is_file() else None

    return {
        "request_id": request["request_id"],
        "stage": request["stage"],
        "model": model,
        "reasoning_effort": effort,
        "attempt_id": attempt,
        "status": status,
        "input_sha256": semantic_hash(request["input"]),
        "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
        "output_schema_sha256": semantic_hash(schema),
        "evidence_path": str(evidence.relative_to(run_root)),
        "raw_output_sha256": maybe_hash("raw_output.txt"),
        "parsed_output_sha256": maybe_hash("parsed_result.json"),
    }


def _save_call_record(run_root: Path, record: Mapping[str, Any]) -> None:
    validate_schema(record, _schema(run_root / "frozen/schemas/call_record.schema.json"), "call record")
    name = f"{record['request_id']}__a{record['attempt_id']:02d}.json"
    write_frozen_json(run_root / "provenance/calls" / name, record, "call record")


def refresh_call_ledger(run_root: Path) -> list[dict[str, Any]]:
    records = [read_json(path) for path in sorted((run_root / "provenance/calls").glob("*.json"))]
    path = run_root / "provenance/call_records.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = read_jsonl(path) if path.is_file() else []
    existing_keys = {(row["request_id"], row["attempt_id"]) for row in existing}
    record_by_key = {(row["request_id"], row["attempt_id"]): row for row in records}
    for row in existing:
        key = (row["request_id"], row["attempt_id"])
        if key not in record_by_key or record_by_key[key] != row:
            raise ValueError(f"append-only call ledger disagrees at {key}")
    new_rows = [
        row for row in records
        if (row["request_id"], row["attempt_id"]) not in existing_keys
    ]
    if new_rows:
        with path.open("a", encoding="utf-8") as stream:
            for row in new_rows:
                stream.write(canonical_json(row) + "\n")
    return [*existing, *new_rows]


def _check_existing_attempt(
    evidence: Path,
    request: Mapping[str, Any],
    prompt: str,
    schema: Mapping[str, Any],
) -> dict[str, Any] | None:
    parsed = evidence / "parsed_result.json"
    if not parsed.is_file():
        return None
    if semantic_hash(read_json(evidence / "input.json")) != semantic_hash(request["input"]):
        raise ValueError(f"resumed request input changed: {request['request_id']}")
    if (evidence / "rendered_prompt.txt").read_text(encoding="utf-8") != prompt:
        raise ValueError(f"resumed prompt changed: {request['request_id']}")
    if semantic_hash(read_json(evidence / "output_schema.json")) != semantic_hash(schema):
        raise ValueError(f"resumed output schema changed: {request['request_id']}")
    value = read_json(parsed)
    validate_schema(value, schema, request["request_id"])
    return value


def run_audited_request(
    run_root: Path,
    request: Mapping[str, Any],
    prompt: str,
    schema: Mapping[str, Any],
    model: str,
    effort: str,
    evidence_parent: Path,
    expected: Callable[[Mapping[str, Any]], None],
) -> dict[str, Any]:
    failures: list[str] = []
    for attempt in range(1, 4):
        evidence = evidence_parent / f"attempt_{attempt:02d}"
        try:
            value = _check_existing_attempt(evidence, request, prompt, schema) if evidence.exists() else None
            if value is None:
                value = audited_model_call(
                    prompt,
                    model=model,
                    reasoning_effort=effort,
                    input_data=request["input"],
                    stage=request["stage"],
                    call_key=request["request_id"],
                    evidence_dir=evidence,
                    output_schema=dict(schema),
                )
                validate_schema(value, schema, request["request_id"])
            expected(value)
            record = _attempt_record(run_root, request, attempt, evidence, prompt, schema, model, effort, "complete")
            _save_call_record(run_root, record)
            return value
        except Exception as exc:  # technical evidence is retained before retry
            failures.append(f"attempt {attempt}: {type(exc).__name__}: {exc}")
            if evidence.exists():
                record = _attempt_record(run_root, request, attempt, evidence, prompt, schema, model, effort, "technical_failure")
                _save_call_record(run_root, record)
    raise RuntimeError(f"{request['request_id']} exhausted technical retries: {' | '.join(failures)}")


def normalize_response(value: str) -> str:
    value = re.sub(r"\s+", " ", value.strip()).casefold()
    return re.sub(r"[.!?]+$", "", value).strip()


def learner_view(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "item_id": item["candidate_item_id"],
        "format": item["format"],
        "response_mode": item["response_mode"],
        "instruction": item["instruction"],
        "context": item["context"],
        "format_payload": item["format_payload"],
    }


def _word_count(value: str) -> int:
    return len(re.findall(r"\b\w+(?:['’-]\w+)*\b", value, flags=re.UNICODE))


def deterministic_family_checks(
    family: Mapping[str, Any],
    spec: Mapping[str, Any],
    round_index: int,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    failed: list[str] = []
    expected_candidate = candidate_id(spec["family_id"], round_index)
    exact = {
        "protocol_id": config["protocol_id"],
        "family_id": spec["family_id"],
        "candidate_id": expected_candidate,
        "candidate_round": round_index,
        "cell_id": spec["cell_id"],
        "grammar_regime": spec["grammar_regime"],
        "semantic_variant_index": spec["semantic_variant_index"],
    }
    for field, expected in exact.items():
        if family.get(field) != expected:
            failed.append(f"envelope:{field}")
    items = family.get("items", [])
    if [row.get("format") for row in items] != list(FORMATS):
        failed.append("exact_format_order_and_crossing")
    seen_ids: set[str] = set()
    canonical = family.get("canonical_target_sentence", "")
    ui = config["deterministic_checks"]["ui_limits"]
    for item_format, item in zip(FORMATS, items):
        expected_id = candidate_item_id(expected_candidate, item_format, config)
        if item.get("candidate_item_id") != expected_id or expected_id in seen_ids:
            failed.append(f"{item_format}:candidate_item_id")
        seen_ids.add(expected_id)
        expected_mode = config["formats"][item_format]["response_mode"]
        if item.get("response_mode") != expected_mode:
            failed.append(f"{item_format}:response_mode")
        if _word_count(str(item.get("instruction", ""))) > ui["instruction_max_words"]:
            failed.append(f"{item_format}:instruction_word_limit")
        if _word_count(str(item.get("context", ""))) > ui["context_max_words"]:
            failed.append(f"{item_format}:context_word_limit")
        scoring = item.get("scoring", {})
        target = str(scoring.get("target_response", ""))
        accepted = scoring.get("accepted_responses", [])
        if not accepted or accepted[0] != target:
            failed.append(f"{item_format}:target_not_first_accepted")
        normalized = [normalize_response(str(value)) for value in accepted]
        if not normalized or "" in normalized or len(normalized) != len(set(normalized)):
            failed.append(f"{item_format}:accepted_responses_not_unique")
        if scoring.get("completed_target") != canonical:
            failed.append(f"{item_format}:completed_target")
        payload = item.get("format_payload", {})
        completed = ""
        visible_parts = [str(item.get("instruction", "")), str(item.get("context", ""))]
        if item_format == "constrained_cloze":
            template = payload.get("sentence_template")
            if not isinstance(template, str) or template.count(SLOT) != 1:
                failed.append("constrained_cloze:response_slot")
            else:
                completed = template.replace(SLOT, target)
                visible_parts.append(template)
            if scoring.get("correct_choice_id") is not None:
                failed.append("constrained_cloze:choice_key")
            if item.get("distractor_annotations"):
                failed.append("constrained_cloze:distractor_annotations")
        elif item_format == "dialogue_completion":
            template = payload.get("incomplete_turn_template")
            turns = payload.get("dialogue_turns", [])
            if not isinstance(template, str) or template.count(SLOT) != 1:
                failed.append("dialogue_completion:response_slot")
            else:
                completed_turn = template.replace(SLOT, target)
                # The visible turn may name its speaker (for example,
                # ``Mia: [[RESPONSE]]``).  The canonical target is the
                # utterance, not UI speaker metadata, so compare only the
                # portion after the first speaker-label colon when present.
                completed = (
                    completed_turn.split(":", 1)[1].strip()
                    if ":" in completed_turn
                    else completed_turn
                )
                visible_parts.extend([*map(str, turns), template])
            if len(turns) > ui["dialogue_max_complete_turns"]:
                failed.append("dialogue_completion:too_many_turns")
            if not turns:
                failed.append("dialogue_completion:missing_dialogue_context")
            if item.get("distractor_annotations"):
                failed.append("dialogue_completion:distractor_annotations")
        elif item_format == "multiple_choice":
            options = payload.get("options", [])
            option_ids = [row.get("id") for row in options]
            option_texts = [row.get("text") for row in options]
            if len(options) != 4 or set(option_ids) != {"A", "B", "C", "D"}:
                failed.append("multiple_choice:four_unique_option_ids")
            if len(option_texts) != len(set(option_texts)):
                failed.append("multiple_choice:unique_option_texts")
            key = scoring.get("correct_choice_id")
            keyed = [row for row in options if row.get("id") == key]
            if target != key or len(keyed) != 1 or keyed[0].get("text") != canonical:
                failed.append("multiple_choice:key_reconstruction")
            else:
                completed = keyed[0]["text"]
            if accepted != [key]:
                failed.append("multiple_choice:accepted_choice")
            annotations = item.get("distractor_annotations", [])
            if len(annotations) != 3 or {row.get("option_id") for row in annotations} != ({"A", "B", "C", "D"} - {key}):
                failed.append("multiple_choice:distractor_annotations")
            if not isinstance(payload.get("stem"), str) or not payload["stem"].strip():
                failed.append("multiple_choice:missing_stem")
            visible_parts.extend([str(payload.get("stem", "")), *map(str, option_texts)])
        else:
            completed = target
            if target != canonical:
                failed.append("sentence_transformation:target_reconstruction")
            if not isinstance(payload.get("source_sentence"), str) or not payload["source_sentence"].strip():
                failed.append("sentence_transformation:missing_source_sentence")
            if not isinstance(payload.get("transformation_cue"), str) or not payload["transformation_cue"].strip():
                failed.append("sentence_transformation:missing_transformation_cue")
            if item.get("distractor_annotations"):
                failed.append("sentence_transformation:distractor_annotations")
            visible_parts.extend([str(payload.get("source_sentence", "")), str(payload.get("transformation_cue", ""))])
        if re.sub(r"\s+", " ", completed.strip()) != re.sub(r"\s+", " ", str(canonical).strip()):
            failed.append(f"{item_format}:canonical_reconstruction")
        visible = " ".join(visible_parts)
        if _word_count(visible) > ui["visible_prompt_max_words"]:
            failed.append(f"{item_format}:visible_prompt_word_limit")
        if item_format != "multiple_choice" and canonical and normalize_response(canonical) in normalize_response(visible):
            failed.append(f"{item_format}:full_target_leakage")
    return {
        "family_id": spec["family_id"],
        "candidate_id": expected_candidate,
        "candidate_round": round_index,
        "passed": not failed,
        "failed_checks": sorted(set(failed)),
    }


def _generation_expected(
    value: Mapping[str, Any], request: Mapping[str, Any], config: Mapping[str, Any]
) -> None:
    if value.get("candidate_id") != request["candidate_id"]:
        raise ValueError("candidate ID mismatch")
    expected_items = request["input"]["identifiers"]["candidate_item_ids"]
    if [row.get("format") for row in value.get("items", [])] != list(FORMATS):
        raise ValueError("format envelope mismatch")
    for row in value["items"]:
        if row.get("candidate_item_id") != expected_items[row["format"]]:
            raise ValueError("candidate item ID mismatch")


def _parallel(requests: Sequence[Mapping[str, Any]], workers: int, task: Callable[[Mapping[str, Any]], Any]) -> list[Any]:
    if workers < 1:
        raise ValueError("workers must be positive")
    results: list[Any] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(task, request): request["request_id"] for request in requests}
        for future in as_completed(futures):
            results.append(future.result())
    return results


def accepted_families(run_root: Path) -> set[str]:
    path = run_root / "curation/family_decisions.jsonl"
    if not path.is_file():
        return set()
    return {row["family_id"] for row in read_jsonl(path) if row["decision"] == "accept"}


def require_generation_round_ready(
    run_root: Path,
    round_index: int,
    config: Mapping[str, Any],
    selected: Mapping[str, Any],
) -> None:
    if round_index == 1:
        return
    path = run_root / "curation/family_decisions.jsonl"
    if not path.is_file():
        raise RuntimeError(f"round {round_index} requires prior curation")
    rows = read_jsonl(path)
    accepted = {row["family_id"] for row in rows if row["decision"] == "accept"}
    indexed = {(row["family_id"], row["candidate_round"]): row for row in rows}
    for spec in family_specs(config, selected):
        if spec["family_id"] in accepted:
            continue
        prior = indexed.get((spec["family_id"], round_index - 1))
        if prior is None or prior["decision"] != "reject":
            raise RuntimeError(
                f"round {round_index} generation is premature for {spec['family_id']}"
            )


def _filter_request_id(
    requests: list[dict[str, Any]], request_id: str | None
) -> list[dict[str, Any]]:
    if request_id is None:
        return requests
    selected = [row for row in requests if row["request_id"] == request_id]
    if len(selected) != 1:
        raise ValueError(f"planned request ID not found exactly once: {request_id}")
    return selected


def run_generation(
    run_root: Path,
    round_index: int,
    workers: int,
    request_id: str | None = None,
) -> dict[str, Any]:
    _, config, selected = validate_run(run_root)
    require_generation_round_ready(run_root, round_index, config, selected)
    specs = {row["family_id"]: row for row in family_specs(config, selected)}
    accepted = accepted_families(run_root)
    requests = _filter_request_id([
        row
        for row in read_jsonl(run_root / "plans/generation_requests.jsonl")
        if row["candidate_round"] == round_index and row["family_id"] not in accepted
    ], request_id)

    def task(request: Mapping[str, Any]) -> dict[str, Any]:
        prompt, schema = render_generation_prompt(run_root, request)
        value = run_audited_request(
            run_root,
            request,
            prompt,
            schema,
            config["generation"]["model"],
            config["generation"]["reasoning_effort"],
            run_root / "raw/generation" / request["request_id"],
            lambda output: _generation_expected(output, request, config),
        )
        write_frozen_json(
            run_root / "parsed/generation" / f"{request['candidate_id']}.json",
            value,
            "parsed generation",
        )
        checks = deterministic_family_checks(
            value, specs[request["family_id"]], round_index, config
        )
        write_frozen_json(
            run_root / "provenance/deterministic_checks" / f"{request['candidate_id']}.json",
            checks,
            "deterministic checks",
        )
        return checks

    checks = _parallel(requests, workers, task)
    refresh_call_ledger(run_root)
    return {
        "round": round_index,
        "requested": len(requests),
        "deterministic_pass": sum(row["passed"] for row in checks),
        "deterministic_fail": sum(not row["passed"] for row in checks),
    }


def eligible_candidates(run_root: Path, round_index: int) -> list[dict[str, Any]]:
    _, config, selected = validate_run(run_root)
    rows: list[dict[str, Any]] = []
    for spec in family_specs(config, selected):
        if spec["family_id"] in accepted_families(run_root):
            continue
        candidate = candidate_id(spec["family_id"], round_index)
        generated = run_root / "parsed/generation" / f"{candidate}.json"
        checks = run_root / "provenance/deterministic_checks" / f"{candidate}.json"
        if generated.is_file() and checks.is_file() and read_json(checks)["passed"]:
            rows.append(read_json(generated))
    return rows


def build_solver_requests(run_root: Path, round_index: int) -> list[dict[str, Any]]:
    _, config, _ = validate_run(run_root)
    families = eligible_candidates(run_root, round_index)
    maximum = int(config["learner_solver_stress_test"]["maximum_items_per_call"])
    requests: list[dict[str, Any]] = []
    for replicate in (1, 2):
        for item_format in FORMATS:
            items = sorted(
                [
                    (family["family_id"], next(item for item in family["items"] if item["format"] == item_format))
                    for family in families
                ],
                key=lambda pair: pair[0],
            )
            for batch_index, start in enumerate(range(0, len(items), maximum), 1):
                batch = items[start : start + maximum]
                batch_id = f"solver_r{round_index:02d}_rep{replicate}_{item_format}_b{batch_index:02d}"
                views = []
                family_ids = []
                for family_id, item in batch:
                    attempt_id = f"{item['candidate_item_id']}_solver_r{replicate}"
                    view = learner_view(item)
                    view.update({"solver_attempt_id": attempt_id})
                    views.append(view)
                    family_ids.append(family_id)
                requests.append(
                    {
                        "request_id": batch_id,
                        "stage": "solver",
                        "candidate_round": round_index,
                        "replicate": replicate,
                        "family_ids": family_ids,
                        "input": {
                            "identifiers": {"batch_id": batch_id, "replicate": replicate},
                            "intended_cefr": config["design"]["intended_proficiency"]["cefr"],
                            "learner_views": views,
                        },
                    }
                )
    write_frozen_jsonl(
        run_root / f"plans/solver_requests_round_{round_index:02d}.jsonl",
        requests,
        f"round {round_index} solver requests",
    )
    return requests


def _solver_expected(value: Mapping[str, Any], request: Mapping[str, Any]) -> None:
    expected = request["input"]["learner_views"]
    if value.get("batch_id") != request["request_id"] or value.get("replicate") != request["replicate"]:
        raise ValueError("solver batch envelope mismatch")
    rows = value.get("responses", [])
    if [row.get("item_id") for row in rows] != [row["item_id"] for row in expected]:
        raise ValueError("solver item coverage/order mismatch")
    if [row.get("solver_attempt_id") for row in rows] != [row["solver_attempt_id"] for row in expected]:
        raise ValueError("solver attempt IDs mismatch")


def _item_lookup(families: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        item["candidate_item_id"]: dict(item)
        for family in families
        for item in family["items"]
    }


def run_solver(
    run_root: Path,
    round_index: int,
    workers: int,
    request_id: str | None = None,
) -> dict[str, Any]:
    _, config, selected = validate_run(run_root)
    for spec in family_specs(config, selected):
        if spec["family_id"] in accepted_families(run_root):
            continue
        candidate = candidate_id(spec["family_id"], round_index)
        if not (run_root / "parsed/generation" / f"{candidate}.json").is_file() or not (
            run_root / "provenance/deterministic_checks" / f"{candidate}.json"
        ).is_file():
            raise RuntimeError(f"generation stage incomplete for {candidate}")
    requests = _filter_request_id(build_solver_requests(run_root, round_index), request_id)
    item_lookup = _item_lookup(eligible_candidates(run_root, round_index))
    base_schema = _schema(run_root / "frozen/schemas/solver_response.schema.json")
    template = (run_root / "frozen/prompts/learner_solver.txt").read_text(encoding="utf-8")

    def task(request: Mapping[str, Any]) -> int:
        schema = _dynamic_schema(
            base_schema,
            {"batch_id": request["request_id"], "replicate": request["replicate"]},
        )
        count = len(request["input"]["learner_views"])
        schema["properties"]["responses"]["minItems"] = count
        schema["properties"]["responses"]["maxItems"] = count
        values = dict(request["input"])
        values["output_schema"] = schema
        prompt = render(template, values)
        result = run_audited_request(
            run_root,
            request,
            prompt,
            schema,
            config["learner_solver_stress_test"]["model"],
            config["learner_solver_stress_test"]["reasoning_effort"],
            run_root / "raw/solver" / request["request_id"],
            lambda output: _solver_expected(output, request),
        )
        for row in result["responses"]:
            item = item_lookup[row["item_id"]]
            accepted = {normalize_response(value) for value in item["scoring"]["accepted_responses"]}
            enriched = {
                **row,
                "batch_id": request["request_id"],
                "replicate": request["replicate"],
                "keyed_match": normalize_response(row["submitted_response"]) in accepted,
                "reasonable_unkeyed_responses": [
                    value
                    for value in row["other_reasonable_responses"]
                    if normalize_response(value) not in accepted
                ],
            }
            write_frozen_json(
                run_root / "parsed/solver" / f"{row['solver_attempt_id']}.json",
                enriched,
                "parsed solver attempt",
            )
        return count

    counts = _parallel(requests, workers, task)
    refresh_call_ledger(run_root)
    return {"round": round_index, "calls": len(requests), "attempts": sum(counts)}


def solver_rows_for_family(run_root: Path, family: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in family["items"]:
        for replicate in (1, 2):
            path = run_root / "parsed/solver" / f"{item['candidate_item_id']}_solver_r{replicate}.json"
            if path.is_file():
                rows.append(read_json(path))
    return rows


def solver_gate(run_root: Path, family: Mapping[str, Any]) -> dict[str, Any]:
    rows = solver_rows_for_family(run_root, family)
    by_item: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_item.setdefault(row["item_id"], []).append(row)
    failed: list[str] = []
    pending: list[str] = []
    for item in family["items"]:
        item_id = item["candidate_item_id"]
        attempts = by_item.get(item_id, [])
        if len(attempts) != 2:
            failed.append(f"{item_id}:two_solver_replicates")
            continue
        if sum(bool(row["keyed_match"]) for row in attempts) < 1:
            failed.append(f"{item_id}:minimum_keyed_matches")
        if any(not row["task_understood"] or not row["response_mechanism_clear"] for row in attempts):
            failed.append(f"{item_id}:task_not_understood")
        if any(row["major_ambiguity"] for row in attempts):
            failed.append(f"{item_id}:major_ambiguity")
        if any(row["reasonable_unkeyed_responses"] for row in attempts):
            pending.append(f"{item_id}:reasonable_unkeyed_response")
    return {"passed": not failed, "failed": failed, "pending_measurement_review": pending}


def _critic_family_view(
    role: str,
    family: Mapping[str, Any],
    spec: Mapping[str, Any],
    run_root: Path,
    kcs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    if role == "platform_product":
        return {
            "family_id": family["family_id"],
            "candidate_id": family["candidate_id"],
            "items": [
                {**learner_view(item), "scoring_view": item["scoring"]}
                for item in family["items"]
            ],
        }
    cell = spec["cell"]
    view = {
        "family_id": family["family_id"],
        "candidate_id": family["candidate_id"],
        "grammar_cell": cell["features"],
        "source_support": {"source_ids": cell["source_ids"]},
        "generator_kcs": [
            {"id": kc_id, "name": kcs[kc_id]["name"], "description": kcs[kc_id]["description"]}
            for kc_id in cell["generator_kc_ids"]
        ],
        "q_row": cell["q_row"],
        "candidate_family": family,
    }
    if role == "measurement":
        view["solver_attempts"] = solver_rows_for_family(run_root, family)
    return view


def build_critic_requests(run_root: Path, round_index: int) -> list[dict[str, Any]]:
    _, config, selected = validate_run(run_root)
    specs = {row["family_id"]: row for row in family_specs(config, selected)}
    kcs = load_kcs()
    eligible = [family for family in eligible_candidates(run_root, round_index) if solver_gate(run_root, family)["passed"]]
    maximum = int(config["independent_validation"]["maximum_families_per_call"])
    requests: list[dict[str, Any]] = []
    for role in ROLES:
        ordered = sorted(eligible, key=lambda family: family["family_id"])
        for batch_index, start in enumerate(range(0, len(ordered), maximum), 1):
            batch = ordered[start : start + maximum]
            batch_id = f"critic_r{round_index:02d}_{role}_b{batch_index:02d}"
            views = [
                _critic_family_view(role, family, specs[family["family_id"]], run_root, kcs)
                for family in batch
            ]
            input_data: dict[str, Any] = {
                "identifiers": {"batch_id": batch_id, "role": role, "candidate_round": round_index},
                "intended_cefr": config["design"]["intended_proficiency"]["cefr"],
                "criterion_contract": {
                    "item_criteria": config["independent_validation"]["roles"][role]["exact_item_criteria"],
                    "family_criteria": config["independent_validation"]["roles"][role]["exact_family_criteria"],
                    "must_pass": config["independent_validation"]["roles"][role]["must_pass"],
                },
            }
            if role == "platform_product":
                input_data["platform_views"] = views
            else:
                input_data["candidate_families"] = views
            requests.append(
                {
                    "request_id": batch_id,
                    "stage": "validation",
                    "role": role,
                    "candidate_round": round_index,
                    "family_ids": [family["family_id"] for family in batch],
                    "candidate_ids": [family["candidate_id"] for family in batch],
                    "input": input_data,
                }
            )
    write_frozen_jsonl(
        run_root / f"plans/critic_requests_round_{round_index:02d}.jsonl",
        requests,
        f"round {round_index} critic requests",
    )
    return requests


def _critic_expected(
    value: Mapping[str, Any], request: Mapping[str, Any], config: Mapping[str, Any], families: Mapping[str, Mapping[str, Any]]
) -> None:
    role = request["role"]
    if value.get("role") != role or value.get("batch_id") != request["request_id"]:
        raise ValueError("critic batch envelope mismatch")
    rows = value.get("families", [])
    if [row.get("family_id") for row in rows] != request["family_ids"]:
        raise ValueError("critic family coverage/order mismatch")
    if [row.get("candidate_id") for row in rows] != request["candidate_ids"]:
        raise ValueError("critic candidate coverage/order mismatch")
    contract = config["independent_validation"]["roles"][role]
    for row in rows:
        family = families[row["family_id"]]
        expected_items = [item["candidate_item_id"] for item in family["items"]]
        if [item["item_id"] for item in row["item_judgments"]] != expected_items:
            raise ValueError("critic item coverage/order mismatch")
        for item in row["item_judgments"]:
            if [criterion["criterion"] for criterion in item["criteria"]] != contract["exact_item_criteria"]:
                raise ValueError("critic item criteria mismatch")
        if [criterion["criterion"] for criterion in row["family_judgments"]] != contract["exact_family_criteria"]:
            raise ValueError("critic family criteria mismatch")


def run_critics(
    run_root: Path,
    round_index: int,
    workers: int,
    request_id: str | None = None,
) -> dict[str, Any]:
    _, config, _ = validate_run(run_root)
    for family in eligible_candidates(run_root, round_index):
        if len(solver_rows_for_family(run_root, family)) != 8:
            raise RuntimeError(f"solver stage incomplete for {family['candidate_id']}")
    requests = _filter_request_id(build_critic_requests(run_root, round_index), request_id)
    families = {family["family_id"]: family for family in eligible_candidates(run_root, round_index)}
    base_schema = _schema(run_root / "frozen/schemas/critic_response.schema.json")

    def task(request: Mapping[str, Any]) -> int:
        role = request["role"]
        schema = _dynamic_schema(base_schema, {"role": role, "batch_id": request["request_id"]})
        count = len(request["family_ids"])
        schema["properties"]["families"]["minItems"] = count
        schema["properties"]["families"]["maxItems"] = count
        values = dict(request["input"])
        values["output_schema"] = schema
        template = (run_root / "frozen" / config["independent_validation"]["roles"][role]["prompt"]).read_text(encoding="utf-8")
        prompt = render(template, values)
        result = run_audited_request(
            run_root,
            request,
            prompt,
            schema,
            config["independent_validation"]["model"],
            config["independent_validation"]["reasoning_effort"],
            run_root / "raw/validation" / role / request["request_id"],
            lambda output: _critic_expected(output, request, config, families),
        )
        for row in result["families"]:
            write_frozen_json(
                run_root / "parsed/validation" / role / f"{row['candidate_id']}.json",
                {"role": role, "batch_id": request["request_id"], **row},
                "parsed critic family judgment",
            )
        return count

    counts = _parallel(requests, workers, task)
    refresh_call_ledger(run_root)
    return {"round": round_index, "calls": len(requests), "family_role_judgments": sum(counts)}


def critic_gate(run_root: Path, family: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    failed: list[str] = []
    for role in ROLES:
        path = run_root / "parsed/validation" / role / f"{family['candidate_id']}.json"
        if not path.is_file():
            failed.append(f"{role}:missing")
            continue
        row = read_json(path)
        if not row["overall_accept"]:
            failed.append(f"{role}:overall_reject")
        criteria = [
            criterion
            for item in row["item_judgments"]
            for criterion in item["criteria"]
        ] + list(row["family_judgments"])
        if any(criterion["severity"] == "major_concern" for criterion in criteria):
            failed.append(f"{role}:major_concern")
        if any(criterion["blocking"] for criterion in criteria):
            failed.append(f"{role}:blocking")
        must_pass = set(config["independent_validation"]["roles"][role]["must_pass"])
        observed = {criterion["criterion"]: criterion["severity"] for criterion in criteria}
        for criterion in sorted(must_pass):
            if observed.get(criterion) != "pass":
                failed.append(f"{role}:must_pass:{criterion}")
    return {"passed": not failed, "failed": sorted(set(failed))}


def _content_tokens(value: str, stopwords: set[str]) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z]+", value.casefold())
        if token not in stopwords
    }


def variant_diversity_gate(
    family: Mapping[str, Any], accepted_sibling: Mapping[str, Any] | None, config: Mapping[str, Any]
) -> list[str]:
    if accepted_sibling is None:
        return []
    failed: list[str] = []
    left = family["semantic_frame"]
    right = accepted_sibling["semantic_frame"]
    if left["main_verb_lemma"].strip().casefold() == right["main_verb_lemma"].strip().casefold():
        failed.append("semantic_variant:distinct_main_verb_lemma")
    stopwords = set(config["deterministic_checks"]["semantic_variant_diversity"]["stopword_list"])
    a = _content_tokens(left["situation_summary"], stopwords)
    b = _content_tokens(right["situation_summary"], stopwords)
    jaccard = len(a & b) / len(a | b) if a | b else 1.0
    if jaccard > config["deterministic_checks"]["semantic_variant_diversity"]["maximum_lowercase_content_token_jaccard"]:
        failed.append("semantic_variant:context_token_jaccard")
    return failed


def curate_round(run_root: Path, round_index: int) -> dict[str, Any]:
    _, config, selected = validate_run(run_root)
    decision_schema = _schema(run_root / "frozen/schemas/curation_decision.schema.json")
    specs = family_specs(config, selected)
    existing_rows = read_jsonl(run_root / "curation/family_decisions.jsonl") if (run_root / "curation/family_decisions.jsonl").is_file() else []
    existing_by_family = {row["family_id"]: row for row in existing_rows if row["decision"] == "accept"}
    existing_keys = {(row["family_id"], row["candidate_round"]) for row in existing_rows}
    new_rows: list[dict[str, Any]] = []
    accepted_family_objects: dict[str, dict[str, Any]] = {
        family_id: read_json(run_root / "parsed/generation" / f"{row['candidate_id']}.json")
        for family_id, row in existing_by_family.items()
    }
    for spec in specs:
        if spec["family_id"] in existing_by_family:
            continue
        if (spec["family_id"], round_index) in existing_keys:
            continue
        missing_prior = [
            prior
            for prior in range(1, round_index)
            if (spec["family_id"], prior) not in existing_keys
        ]
        if missing_prior:
            raise RuntimeError(
                f"cannot curate {spec['family_id']} round {round_index} before "
                f"rounds {missing_prior}"
            )
        candidate = candidate_id(spec["family_id"], round_index)
        family_path = run_root / "parsed/generation" / f"{candidate}.json"
        check_path = run_root / "provenance/deterministic_checks" / f"{candidate}.json"
        if not family_path.is_file() or not check_path.is_file():
            raise RuntimeError(f"generation stage incomplete for {candidate}")
        failed: list[str] = []
        deterministic_pass = family_path.is_file() and check_path.is_file() and read_json(check_path)["passed"]
        family = read_json(family_path) if family_path.is_file() else None
        if not deterministic_pass:
            failed.append("deterministic_checks")
        solver = solver_gate(run_root, family) if deterministic_pass and family else {"passed": False, "failed": ["not_run"], "pending_measurement_review": []}
        if deterministic_pass and len(solver_rows_for_family(run_root, family)) != 8:
            raise RuntimeError(f"solver stage incomplete for {candidate}")
        if not solver["passed"]:
            failed.extend(f"solver:{value}" for value in solver["failed"])
        critics = critic_gate(run_root, family, config) if solver["passed"] and family else {"passed": False, "failed": ["not_run"]}
        if solver["passed"] and any(
            not (run_root / "parsed/validation" / role / f"{candidate}.json").is_file()
            for role in ROLES
        ):
            raise RuntimeError(f"critic stage incomplete for {candidate}")
        if not critics["passed"]:
            failed.extend(f"critic:{value}" for value in critics["failed"])
        if solver.get("pending_measurement_review") and critics["passed"]:
            # A passing accepted-response-coverage judgment is the preregistered
            # adjudication; retain the alternatives in evidence rather than
            # silently adding them to the key.
            pass
        if family and spec["grammar_regime"] == "seen":
            sibling_id = (
                spec["family_id"].replace("_sv01", "_sv02")
                if spec["semantic_variant_index"] == 1
                else spec["family_id"].replace("_sv02", "_sv01")
            )
            diversity_failures = variant_diversity_gate(family, accepted_family_objects.get(sibling_id), config)
            failed.extend(diversity_failures)
        accepted = not failed
        decision = {
            "family_id": spec["family_id"],
            "candidate_id": candidate,
            "candidate_round": round_index,
            "decision": "accept" if accepted else "reject",
            "deterministic_checks_pass": bool(deterministic_pass),
            "solver_gates_pass": bool(solver["passed"]),
            "critic_gates_pass": bool(critics["passed"]),
            "failed_gates": sorted(set(failed)),
            "selected_as_earliest_passing": accepted,
        }
        validate_schema(decision, decision_schema, "curation decision")
        new_rows.append(decision)
        if accepted and family:
            accepted_family_objects[spec["family_id"]] = family
    combined = [*existing_rows, *new_rows]
    path = run_root / "curation/family_decisions.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    if new_rows:
        with path.open("a", encoding="utf-8") as stream:
            for row in new_rows:
                stream.write(canonical_json(row) + "\n")
        rejection_path = run_root / "curation/rejections.jsonl"
        with rejection_path.open("a", encoding="utf-8") as stream:
            for row in new_rows:
                if row["decision"] == "reject":
                    stream.write(canonical_json(row) + "\n")
    return {
        "round": round_index,
        "new_accepts": sum(row["decision"] == "accept" for row in new_rows),
        "new_rejections": sum(row["decision"] == "reject" for row in new_rows),
        "accepted_total": len({row["family_id"] for row in combined if row["decision"] == "accept"}),
    }


def _final_item(
    raw: Mapping[str, Any], family: Mapping[str, Any], spec: Mapping[str, Any], config: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "item_id": slot_item_id(family["family_id"], raw["format"], config),
        "family_id": family["family_id"],
        "cell_id": spec["cell_id"],
        "semantic_variant_index": spec["semantic_variant_index"],
        "format": raw["format"],
        "response_mode": raw["response_mode"],
        "instruction": raw["instruction"],
        "context": raw["context"],
        "format_payload": raw["format_payload"],
        "scoring": raw["scoring"],
        "canonical_target_sentence": family["canonical_target_sentence"],
        "semantic_frame": family["semantic_frame"],
        "grammar_regime": spec["grammar_regime"],
        "acquisition_updates": spec["acquisition_updates"],
        "generator_kc_ids": spec["cell"]["generator_kc_ids"],
        "q_row": spec["cell"]["q_row"],
        "validation_status": "hard_gates_passed",
        "provenance": {
            "protocol_id": config["protocol_id"],
            "source_candidate_id": family["candidate_id"],
            "source_candidate_item_id": raw["candidate_item_id"],
            "selected_candidate_round": family["candidate_round"],
            "selection_rule": "earliest_whole_family_passing_all_gates",
        },
    }


def freeze_bank(run_root: Path) -> dict[str, Any]:
    plan, config, selected = validate_run(run_root)
    decisions = read_jsonl(run_root / "curation/family_decisions.jsonl")
    accepted = {}
    for row in decisions:
        if row["decision"] == "accept":
            if row["family_id"] in accepted:
                raise ValueError(f"multiple accepted rounds for {row['family_id']}")
            accepted[row["family_id"]] = row
    specs = {row["family_id"]: row for row in family_specs(config, selected)}
    if set(accepted) != set(specs):
        missing = sorted(set(specs) - set(accepted))
        raise RuntimeError(f"cannot freeze: {len(missing)} families unresolved: {missing[:5]}")
    families: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    for family_id in [row["family_id"] for row in family_specs(config, selected)]:
        decision = accepted[family_id]
        family = read_json(run_root / "parsed/generation" / f"{decision['candidate_id']}.json")
        spec = specs[family_id]
        families.append(
            {
                "family_id": family_id,
                "cell_id": spec["cell_id"],
                "grammar_regime": spec["grammar_regime"],
                "semantic_variant_index": spec["semantic_variant_index"],
                "canonical_target_sentence": family["canonical_target_sentence"],
                "semantic_frame": family["semantic_frame"],
                "generator_kc_ids": spec["cell"]["generator_kc_ids"],
                "q_row": spec["cell"]["q_row"],
                "selected_candidate_id": family["candidate_id"],
                "selected_candidate_round": family["candidate_round"],
                "item_ids": [slot_item_id(family_id, item_format, config) for item_format in FORMATS],
                "validation_status": "hard_gates_passed",
            }
        )
        items.extend(_final_item(item, family, spec, config) for item in family["items"])
    if len(families) != 38 or len(items) != 152:
        raise ValueError("freeze scale mismatch")
    curated_schema = _schema(run_root / "frozen/schemas/curated_item.schema.json")
    for item in items:
        validate_schema(item, curated_schema, f"curated item {item['item_id']}")
    for spec in specs.values():
        if spec["grammar_regime"] != "seen" or spec["semantic_variant_index"] != 2:
            continue
        sibling_id = spec["family_id"].replace("_sv02", "_sv01")
        current = next(row for row in families if row["family_id"] == spec["family_id"])
        sibling = next(row for row in families if row["family_id"] == sibling_id)
        failures = variant_diversity_gate(current, sibling, config)
        if failures:
            raise ValueError(f"accepted semantic variants fail diversity: {failures}")
    write_frozen_jsonl(run_root / "bank/families.jsonl", families, "frozen families")
    write_frozen_jsonl(run_root / "bank/items.jsonl", items, "frozen items")
    q_path = run_root / "bank/q_matrix.csv"
    q_lines = [",".join(["item_id", *selected["kc_order"]])]
    q_lines.extend(
        ",".join([row["item_id"], *map(str, row["q_row"])]) for row in items
    )
    write_frozen_text(q_path, "\n".join(q_lines) + "\n", "frozen Q matrix")
    manifest = {
        "dataset_id": "grammar_kt_measurement_bank_v0_confirmatory",
        "status": "FROZEN_AUTOMATED_VALIDATION_COMPLETE_HUMAN_VALIDATION_PENDING",
        "protocol_id": config["protocol_id"],
        "run_id": run_root.name,
        "source_dataset": "grammar_kt_full_v1",
        "source_dataset_manifest_sha256": plan["inputs"]["v1_manifest"]["sha256"],
        "selected_cells_sha256": plan["inputs"]["selected_cells"]["sha256"],
        "counts": {"families": 38, "items": 152, "formats": 4, "generator_kcs": 18},
        "scientific_boundary": {
            "automated_critics_are_human_evidence": False,
            "platform_deployment_validated": False,
            "learner_outcomes_used_in_construction": False,
            "q_rows_copied_from_frozen_cell_projection": True,
        },
        "artifacts": {},
    }
    for name in ("families.jsonl", "items.jsonl", "q_matrix.csv"):
        path = run_root / "bank" / name
        manifest["artifacts"][name] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    write_frozen_json(run_root / "bank/manifest.json", manifest, "bank manifest")
    verify_bank(run_root)
    return manifest


def package_evidence(run_root: Path) -> dict[str, Any]:
    validate_run(run_root)
    records = refresh_call_ledger(run_root)
    rows: list[dict[str, Any]] = []
    for record in records:
        evidence = run_root / record["evidence_path"]
        payload: dict[str, Any] = {"call_record": record, "files": {}}
        for name in (
            "input.json", "rendered_prompt.txt", "model_settings.json",
            "output_schema.json", "raw_output.txt", "cli_stderr.txt",
            "call_metadata.json", "parsed_result.json",
        ):
            path = evidence / name
            if path.is_file():
                content = path.read_text(encoding="utf-8")
                payload["files"][name] = {"sha256": sha256_file(path), "content": content}
        rows.append(payload)
    bundle = run_root / "provenance/call_evidence_bundle.jsonl"
    write_frozen_text(
        bundle,
        "".join(canonical_json(row) + "\n" for row in rows),
        "call evidence bundle",
    )
    manifest = {
        "calls_or_attempts": len(rows),
        "bundle": str(bundle.relative_to(run_root)),
        "sha256": sha256_file(bundle),
        "bytes": bundle.stat().st_size,
    }
    write_frozen_json(run_root / "provenance/call_evidence_manifest.json", manifest, "call evidence manifest")
    return manifest


def verify_bank(run_root: Path) -> dict[str, Any]:
    plan, config, selected = validate_run(run_root)
    manifest = read_json(run_root / "bank/manifest.json")
    for name, metadata in manifest["artifacts"].items():
        path = run_root / "bank" / name
        if sha256_file(path) != metadata["sha256"] or path.stat().st_size != metadata["bytes"]:
            raise ValueError(f"bank artifact changed: {name}")
    items = read_jsonl(run_root / "bank/items.jsonl")
    families = read_jsonl(run_root / "bank/families.jsonl")
    if len(items) != 152 or len(families) != 38:
        raise ValueError("frozen bank scale mismatch")
    if len({row["item_id"] for row in items}) != 152 or len({row["family_id"] for row in families}) != 38:
        raise ValueError("duplicate bank IDs")
    curated_schema = _schema(run_root / "frozen/schemas/curated_item.schema.json")
    for row in items:
        validate_schema(row, curated_schema, f"curated item {row.get('item_id')}")
    specs = {row["family_id"]: row for row in family_specs(config, selected)}
    decisions = read_jsonl(run_root / "curation/family_decisions.jsonl")
    accepts = {row["family_id"]: row for row in decisions if row["decision"] == "accept"}
    if set(accepts) != set(specs):
        raise ValueError("curation ledger does not contain exactly 38 accepts")
    for family_id, decision in accepts.items():
        earlier = [
            row for row in decisions
            if row["family_id"] == family_id and row["candidate_round"] < decision["candidate_round"]
        ]
        if len(earlier) != decision["candidate_round"] - 1 or any(row["decision"] != "reject" for row in earlier):
            raise ValueError(f"earliest-passing rule not evidenced: {family_id}")
        family = read_json(run_root / "parsed/generation" / f"{decision['candidate_id']}.json")
        checks = read_json(run_root / "provenance/deterministic_checks" / f"{decision['candidate_id']}.json")
        if not checks["passed"] or not solver_gate(run_root, family)["passed"] or not critic_gate(run_root, family, config)["passed"]:
            raise ValueError(f"accepted family no longer passes evidence gates: {family_id}")
    counts = Counter((row["family_id"], row["format"]) for row in items)
    if any(counts[(family_id, item_format)] != 1 for family_id in specs for item_format in FORMATS):
        raise ValueError("bank is not exactly crossed")
    for row in items:
        spec = specs[row["family_id"]]
        if row["q_row"] != spec["cell"]["q_row"] or row["generator_kc_ids"] != spec["cell"]["generator_kc_ids"]:
            raise ValueError(f"Q projection changed: {row['item_id']}")
        if row["grammar_regime"] != spec["grammar_regime"] or row["acquisition_updates"] != spec["acquisition_updates"]:
            raise ValueError(f"regime/update policy changed: {row['item_id']}")
        if row["validation_status"] != "hard_gates_passed":
            raise ValueError(f"unvalidated item in frozen bank: {row['item_id']}")
    expected_items: list[dict[str, Any]] = []
    expected_families: list[dict[str, Any]] = []
    for family_id in [row["family_id"] for row in family_specs(config, selected)]:
        decision = accepts[family_id]
        source = read_json(run_root / "parsed/generation" / f"{decision['candidate_id']}.json")
        spec = specs[family_id]
        expected_items.extend(_final_item(item, source, spec, config) for item in source["items"])
        expected_families.append(
            {
                "family_id": family_id,
                "cell_id": spec["cell_id"],
                "grammar_regime": spec["grammar_regime"],
                "semantic_variant_index": spec["semantic_variant_index"],
                "canonical_target_sentence": source["canonical_target_sentence"],
                "semantic_frame": source["semantic_frame"],
                "generator_kc_ids": spec["cell"]["generator_kc_ids"],
                "q_row": spec["cell"]["q_row"],
                "selected_candidate_id": source["candidate_id"],
                "selected_candidate_round": source["candidate_round"],
                "item_ids": [slot_item_id(family_id, item_format, config) for item_format in FORMATS],
                "validation_status": "hard_gates_passed",
            }
        )
    if items != expected_items or families != expected_families:
        raise ValueError("frozen bank is not an exact deterministic projection of accepted families")
    with (run_root / "bank/q_matrix.csv").open(encoding="utf-8", newline="") as stream:
        q_rows = list(csv.DictReader(stream))
    if [row["item_id"] for row in q_rows] != [row["item_id"] for row in items]:
        raise ValueError("Q CSV item order mismatch")
    for csv_row, item in zip(q_rows, items):
        if [int(csv_row[kc]) for kc in selected["kc_order"]] != item["q_row"]:
            raise ValueError(f"Q CSV mismatch: {item['item_id']}")
    if _exact_rank([row["q_row"] for row in items if row["grammar_regime"] == "seen"]) != 18:
        raise ValueError("frozen seen-item Q matrix lost full rank")
    return {
        "verified": True,
        "run_id": run_root.name,
        "families": len(families),
        "items": len(items),
        "seen_q_rank": 18,
        "manifest_sha256": sha256_file(run_root / "bank/manifest.json"),
        "v1_manifest_sha256": plan["inputs"]["v1_manifest"]["sha256"],
    }


def _run_root(run_id: str, runs_root: Path) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", run_id):
        raise ValueError("run ID must be a short filename-safe identifier")
    return runs_root / run_id


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--runs-root", type=Path, default=DEFAULT_RUNS)
    sub = cli.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--run-id", required=True)
    plan.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    plan.add_argument("--selected-cells", type=Path, default=DEFAULT_SELECTED)
    for name in ("generate", "solve", "critic"):
        stage = sub.add_parser(name)
        stage.add_argument("--run-id", required=True)
        stage.add_argument("--round", type=int, choices=(1, 2, 3), required=True)
        stage.add_argument("--workers", type=int, default=4)
        stage.add_argument(
            "--request-id",
            help="execute one exact planned request as a resumable provider preflight",
        )
    curate = sub.add_parser("curate")
    curate.add_argument("--run-id", required=True)
    curate.add_argument("--round", type=int, choices=(1, 2, 3), required=True)
    for name in ("freeze", "verify", "package-evidence"):
        stage = sub.add_parser(name)
        stage.add_argument("--run-id", required=True)
    return cli


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    run_root = _run_root(args.run_id, args.runs_root.resolve())
    if args.command == "plan":
        result = create_plan(run_root, args.config.resolve(), args.selected_cells.resolve())
    elif args.command == "generate":
        result = run_generation(run_root, args.round, args.workers, args.request_id)
    elif args.command == "solve":
        result = run_solver(run_root, args.round, args.workers, args.request_id)
    elif args.command == "critic":
        result = run_critics(run_root, args.round, args.workers, args.request_id)
    elif args.command == "curate":
        result = curate_round(run_root, args.round)
    elif args.command == "freeze":
        result = freeze_bank(run_root)
    elif args.command == "package-evidence":
        result = package_evidence(run_root)
    else:
        result = verify_bank(run_root)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
