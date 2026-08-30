#!/usr/bin/env python3
"""Run an outcome-blind, activation-canonicalised KC induction stress test.

The proposer sees only the frozen GrammarCell universe, source-support counts,
and an executable predicate grammar.  Existing K*, Q*, items, and learner data
are withheld until all proposals are frozen.  Analysis then compares activation
vectors rather than names.  The result is evidence about methodological
stability and underdetermination, not a selected psychological ontology.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Mapping, Sequence

import jsonschema
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from grammar_kt.io import read_yaml
from grammar_kt.model_evidence import audited_model_call


DEFAULT_DATASET = ROOT / "data/grammar_kt_full_v1"
DEFAULT_CONFIG = ROOT / "modules/measurement_realism/kc_induction.yaml"
DEFAULT_PROMPT = ROOT / "modules/measurement_realism/prompts/kc_induction.txt"
DEFAULT_SCHEMA = ROOT / "modules/measurement_realism/schemas/kc_induction.schema.json"
DEFAULT_OUTPUT = ROOT / "experiments/measurement_realism/kc_induction_v1"
DEFAULT_EVIDENCE = ROOT / "runs/measurement_realism/kc_induction_v1"


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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_frozen(path: Path, payload: str, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise FileExistsError(f"refusing to overwrite changed {label}: {path}")
        return
    path.write_text(payload, encoding="utf-8")


def write_frozen_json(path: Path, value: Any, label: str) -> None:
    write_frozen(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n", label)


def repository_head() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _load_public_inputs(dataset: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "FROZEN_BASELINE_COMPLETE":
        raise ValueError("KC induction requires the frozen full-v1 reference")
    schema = read_yaml(ROOT / "modules/grammar/canonical/schema.yaml")
    dimensions = schema["dimensions"]
    dimension_order = list(schema["dimension_order"])
    canonical_schema = {
        "schema_id": schema["schema_id"],
        "dimension_order": dimension_order,
        "dimensions": {
            name: {
                "allowed_values": list(dimensions[name]["allowed_values"]),
                "interpretation": dimensions[name]["interpretation"],
            }
            for name in dimension_order
        },
    }
    cells = sorted(
        read_jsonl(dataset / "grammar/cells.jsonl"), key=lambda row: row["cell_id"]
    )
    visible_cells = [
        {
            "cell_id": row["cell_id"],
            "features": row["features"],
            "source_support_count": len(row["source_ids"]),
        }
        for row in cells
    ]
    if len(visible_cells) != 75:
        raise ValueError("frozen GrammarCell count changed")
    return canonical_schema, visible_cells


def _input_manifest(dataset: Path, config: Path, prompt: Path, schema: Path) -> dict[str, Any]:
    paths = {
        "dataset_manifest": dataset / "manifest.json",
        "cells": dataset / "grammar/cells.jsonl",
        "canonical_schema": ROOT / "modules/grammar/canonical/schema.yaml",
        "config": config,
        "prompt": prompt,
        "output_schema": schema,
        "script": Path(__file__).resolve(),
        "audited_backend": ROOT / "src/grammar_kt/model_evidence.py",
    }
    return {
        name: {
            "path": str(path.relative_to(ROOT)),
            "sha256": file_sha256(path),
            "bytes": path.stat().st_size,
        }
        for name, path in paths.items()
    }


def _render_prompt(
    template: str,
    *,
    replicate_id: str,
    config: Mapping[str, Any],
    canonical_schema: Mapping[str, Any],
    cells: Sequence[Mapping[str, Any]],
    output_schema: Mapping[str, Any],
) -> str:
    replacements = {
        "{{minimum_kcs}}": str(config["proposal_count"]["minimum"]),
        "{{maximum_kcs}}": str(config["proposal_count"]["maximum"]),
        "{{replicate_id}}": replicate_id,
        "{{canonical_schema}}": canonical_json(canonical_schema),
        "{{cells}}": canonical_json(list(cells)),
        "{{output_schema}}": canonical_json(output_schema),
    }
    rendered = template
    for marker, value in replacements.items():
        if marker not in rendered:
            raise ValueError(f"prompt marker missing: {marker}")
        rendered = rendered.replace(marker, value)
    if re.search(r"\{\{[a-z][a-z0-9_]*\}\}", rendered):
        raise ValueError("unresolved prompt placeholder")
    return rendered


def plan(
    dataset: Path,
    config_path: Path,
    prompt_path: Path,
    schema_path: Path,
    output: Path,
) -> dict[str, Any]:
    config = read_yaml(config_path)
    if config.get("status") != "preregistered_before_model_calls":
        raise ValueError("KC induction config is not preregistered")
    output_schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(output_schema)
    canonical_schema, cells = _load_public_inputs(dataset)
    frozen_input = {
        "canonical_schema": canonical_schema,
        "cells": cells,
    }
    input_payload = canonical_json(frozen_input) + "\n"
    write_frozen(output / "proposal_input.json", input_payload, "proposal input")
    replicate_ids = [
        f"independent_{index:02d}"
        for index in range(1, int(config["independent_replicates"]) + 1)
    ]
    requests = []
    template = prompt_path.read_text(encoding="utf-8")
    for replicate_id in replicate_ids:
        rendered = _render_prompt(
            template,
            replicate_id=replicate_id,
            config=config,
            canonical_schema=canonical_schema,
            cells=cells,
            output_schema=output_schema,
        )
        requests.append(
            {
                "replicate_id": replicate_id,
                "prompt_sha256": sha256_bytes(rendered.encode("utf-8")),
                "prompt_bytes": len(rendered.encode("utf-8")),
            }
        )
    request_payload = "".join(canonical_json(row) + "\n" for row in requests)
    write_frozen(output / "proposal_requests.jsonl", request_payload, "proposal requests")
    study_plan = {
        "study_id": config["study_id"],
        "status": "PREREGISTERED_BEFORE_MODEL_CALLS",
        "evidence_type": "independent_non_human_outcome_blind_kc_hypothesis_induction",
        "human_or_expert_gold": False,
        "replicate_ids": replicate_ids,
        "model": config["model"],
        "proposal_count": config["proposal_count"],
        "canonicalisation": config["canonicalisation"],
        "scientific_boundary": {
            "visible": config["inputs_visible_to_proposer"],
            "hidden_until_evaluation": config["inputs_hidden_until_evaluation"],
            "claim": config["claim_boundary"],
        },
        "scale": {"cells": len(cells), "dimensions": len(canonical_schema["dimension_order"])},
        "input": {
            "path": "proposal_input.json",
            "sha256": sha256_bytes(input_payload.encode("utf-8")),
        },
        "requests": {
            "path": "proposal_requests.jsonl",
            "sha256": sha256_bytes(request_payload.encode("utf-8")),
            "count": len(requests),
        },
        "inputs": _input_manifest(dataset, config_path, prompt_path, schema_path),
        "repository_head_at_plan": repository_head(),
        "commands": {
            "plan": ".venv/bin/python scripts/experiments/measurement_realism_kc_induction.py plan",
            "run": ".venv/bin/python scripts/experiments/measurement_realism_kc_induction.py run --workers 3",
            "analyse": ".venv/bin/python scripts/experiments/measurement_realism_kc_induction.py analyse",
        },
    }
    write_frozen_json(output / "study_plan.json", study_plan, "study plan")
    return study_plan


def _validate_plan(
    dataset: Path,
    config_path: Path,
    prompt_path: Path,
    schema_path: Path,
    output: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    study_plan = json.loads((output / "study_plan.json").read_text(encoding="utf-8"))
    if study_plan.get("status") != "PREREGISTERED_BEFORE_MODEL_CALLS":
        raise ValueError("invalid KC induction plan status")
    if study_plan["inputs"] != _input_manifest(dataset, config_path, prompt_path, schema_path):
        raise ValueError("KC induction inputs changed after planning")
    input_path = output / study_plan["input"]["path"]
    if file_sha256(input_path) != study_plan["input"]["sha256"]:
        raise ValueError("KC induction proposal input changed")
    request_path = output / study_plan["requests"]["path"]
    if file_sha256(request_path) != study_plan["requests"]["sha256"]:
        raise ValueError("KC induction requests changed")
    config = read_yaml(config_path)
    output_schema = json.loads(schema_path.read_text(encoding="utf-8"))
    frozen_input = json.loads(input_path.read_text(encoding="utf-8"))
    requests = read_jsonl(request_path)
    return study_plan, config, output_schema, requests


def _validate_predicates(
    result: Mapping[str, Any],
    *,
    replicate_id: str,
    config: Mapping[str, Any],
    schema: Mapping[str, Any],
    canonical_schema: Mapping[str, Any],
) -> None:
    jsonschema.validate(result, schema)
    if result["replicate_id"] != replicate_id:
        raise ValueError("replicate ID mismatch")
    hypotheses = result["hypotheses"]
    expected_min = int(config["proposal_count"]["minimum"])
    expected_max = int(config["proposal_count"]["maximum"])
    if not expected_min <= len(hypotheses) <= expected_max:
        raise ValueError("proposal count outside preregistered bounds")
    proposal_ids = [row["proposal_id"] for row in hypotheses]
    if len(proposal_ids) != len(set(proposal_ids)):
        raise ValueError("duplicate proposal IDs")
    allowed = {
        name: set(value["allowed_values"])
        for name, value in canonical_schema["dimensions"].items()
    }
    for hypothesis in hypotheses:
        for clause in hypothesis["activation"]["any_of"]:
            if not any(clause["all_of"].values()):
                raise ValueError("predicate clause cannot be entirely unconstrained")
            for dimension, values in clause["all_of"].items():
                if dimension not in allowed:
                    raise ValueError(f"unknown predicate dimension: {dimension}")
                if not set(values) <= allowed[dimension]:
                    raise ValueError(f"unknown value in predicate dimension {dimension}")


def run(
    dataset: Path,
    config_path: Path,
    prompt_path: Path,
    schema_path: Path,
    output: Path,
    evidence: Path,
    workers: int,
) -> dict[str, Any]:
    study_plan, config, output_schema, requests = _validate_plan(
        dataset, config_path, prompt_path, schema_path, output
    )
    frozen_input = json.loads((output / "proposal_input.json").read_text(encoding="utf-8"))
    template = prompt_path.read_text(encoding="utf-8")

    def one(request: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
        replicate_id = request["replicate_id"]
        rendered = _render_prompt(
            template,
            replicate_id=replicate_id,
            config=config,
            canonical_schema=frozen_input["canonical_schema"],
            cells=frozen_input["cells"],
            output_schema=output_schema,
        )
        if sha256_bytes(rendered.encode("utf-8")) != request["prompt_sha256"]:
            raise ValueError("rendered prompt changed after plan")
        evidence_dir = evidence / replicate_id
        if (evidence_dir / "parsed_result.json").is_file():
            result = json.loads((evidence_dir / "parsed_result.json").read_text(encoding="utf-8"))
        else:
            if evidence_dir.exists():
                raise FileExistsError(f"incomplete call evidence requires audit: {evidence_dir}")
            result = audited_model_call(
                rendered,
                model=config["model"]["name"],
                reasoning_effort=config["model"]["reasoning_effort"],
                input_data={
                    "replicate_id": replicate_id,
                    "visible_input": frozen_input,
                    "prompt_sha256": request["prompt_sha256"],
                },
                stage="kc_hypothesis_induction",
                call_key=replicate_id,
                evidence_dir=evidence_dir,
                output_schema=output_schema,
            )
        _validate_predicates(
            result,
            replicate_id=replicate_id,
            config=config,
            schema=output_schema,
            canonical_schema=frozen_input["canonical_schema"],
        )
        print(json.dumps({"completed": replicate_id}), flush=True)
        return replicate_id, result

    results: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(one, request): request for request in requests}
        for future in as_completed(futures):
            replicate_id, result = future.result()
            results[replicate_id] = result
    ordered = [results[replicate_id] for replicate_id in study_plan["replicate_ids"]]
    proposal_payload = "".join(canonical_json(row) + "\n" for row in ordered)
    write_frozen(output / "raw_proposals.jsonl", proposal_payload, "raw proposals")

    bundle_rows = []
    for replicate_id in study_plan["replicate_ids"]:
        call_dir = evidence / replicate_id
        bundle_rows.append(
            {
                "replicate_id": replicate_id,
                "input": json.loads((call_dir / "input.json").read_text(encoding="utf-8")),
                "rendered_prompt": (call_dir / "rendered_prompt.txt").read_text(encoding="utf-8"),
                "model_settings": json.loads((call_dir / "model_settings.json").read_text(encoding="utf-8")),
                "output_schema": json.loads((call_dir / "output_schema.json").read_text(encoding="utf-8")),
                "raw_output": (call_dir / "raw_output.txt").read_text(encoding="utf-8"),
                "stderr": (call_dir / "cli_stderr.txt").read_text(encoding="utf-8"),
                "call_metadata": json.loads((call_dir / "call_metadata.json").read_text(encoding="utf-8")),
                "parsed_result": json.loads((call_dir / "parsed_result.json").read_text(encoding="utf-8")),
            }
        )
    bundle_payload = "".join(canonical_json(row) + "\n" for row in bundle_rows)
    write_frozen(output / "call_evidence_bundle.jsonl", bundle_payload, "call evidence bundle")
    run_manifest = {
        "study_id": study_plan["study_id"],
        "status": "MODEL_PROPOSALS_FROZEN_BEFORE_KSTAR_EVALUATION",
        "calls": len(bundle_rows),
        "raw_proposals_sha256": sha256_bytes(proposal_payload.encode("utf-8")),
        "call_evidence_bundle_sha256": sha256_bytes(bundle_payload.encode("utf-8")),
        "token_total": sum(
            int(row["call_metadata"].get("tokens_used") or 0) for row in bundle_rows
        ),
    }
    write_frozen_json(output / "run_manifest.json", run_manifest, "run manifest")
    return run_manifest


def _activates(features: Mapping[str, str], activation: Mapping[str, Any]) -> bool:
    return any(
        all(
            not values or features[dimension] in values
            for dimension, values in clause["all_of"].items()
        )
        for clause in activation["any_of"]
    )


def _kstar_cell_signatures(dataset: Path, cell_ids: Sequence[str]) -> dict[str, tuple[int, ...]]:
    items = read_jsonl(dataset / "items/items.jsonl")
    cell_by_item = {row["item_id"]: row["cell_id"] for row in items}
    with (dataset / "q_matrix.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
        kc_ids = [name for name in rows[0] if name != "item_id"]
    q_by_cell: dict[str, tuple[int, ...]] = {}
    for row in rows:
        cell_id = cell_by_item[row["item_id"]]
        q = tuple(int(row[kc_id]) for kc_id in kc_ids)
        if cell_id in q_by_cell and q_by_cell[cell_id] != q:
            raise ValueError("Q* is not deterministic by GrammarCell")
        q_by_cell[cell_id] = q
    if set(q_by_cell) != set(cell_ids):
        raise ValueError("Q* cell universe differs from proposal universe")
    return {
        kc_id: tuple(q_by_cell[cell_id][index] for cell_id in cell_ids)
        for index, kc_id in enumerate(kc_ids)
    }


def analyse(dataset: Path, output: Path) -> dict[str, Any]:
    plan = json.loads((output / "study_plan.json").read_text(encoding="utf-8"))
    run_manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
    proposal_path = output / "raw_proposals.jsonl"
    if file_sha256(proposal_path) != run_manifest["raw_proposals_sha256"]:
        raise ValueError("frozen proposals changed before K* evaluation")
    frozen_input = json.loads((output / "proposal_input.json").read_text(encoding="utf-8"))
    cells = frozen_input["cells"]
    cell_ids = [row["cell_id"] for row in cells]
    features = [row["features"] for row in cells]
    proposals = read_jsonl(proposal_path)
    kstar = _kstar_cell_signatures(dataset, cell_ids)
    kstar_by_signature = {signature: kc_id for kc_id, signature in kstar.items()}

    replicate_results = []
    signature_sets: dict[str, set[str]] = {}
    ledger = []
    for result in proposals:
        replicate_id = result["replicate_id"]
        columns = []
        unique_signatures: dict[str, tuple[int, ...]] = {}
        duplicate_groups: dict[str, list[str]] = {}
        exact_matches = []
        for hypothesis in result["hypotheses"]:
            signature = tuple(
                int(_activates(row, hypothesis["activation"])) for row in features
            )
            if not any(signature):
                raise ValueError(f"empty activation: {replicate_id}/{hypothesis['proposal_id']}")
            signature_hash = sha256_bytes(bytes(signature))
            columns.append(signature)
            duplicate_groups.setdefault(signature_hash, []).append(hypothesis["proposal_id"])
            unique_signatures.setdefault(signature_hash, signature)
            matched = kstar_by_signature.get(signature)
            if matched:
                exact_matches.append(
                    {"proposal_id": hypothesis["proposal_id"], "generator_kc_id": matched}
                )
            ledger.append(
                {
                    "replicate_id": replicate_id,
                    "proposal_id": hypothesis["proposal_id"],
                    "name": hypothesis["name"],
                    "hypothesis_type": hypothesis["hypothesis_type"],
                    "support_cells": int(sum(signature)),
                    "activation_signature_sha256": signature_hash,
                    "exact_frozen_kstar_signature_match": matched,
                    "activation": hypothesis["activation"],
                    "pedagogical_interpretation": hypothesis["pedagogical_interpretation"],
                    "limitation_or_needed_evidence": hypothesis["limitation_or_needed_evidence"],
                }
            )
        matrix = np.asarray(columns, dtype=float).T
        unique_matrix = np.asarray(list(unique_signatures.values()), dtype=float).T
        signature_sets[replicate_id] = set(unique_signatures)
        replicate_results.append(
            {
                "replicate_id": replicate_id,
                "raw_hypotheses": len(columns),
                "unique_activation_hypotheses": len(unique_signatures),
                "duplicate_activation_groups": [
                    {"signature_sha256": key, "proposal_ids": ids}
                    for key, ids in sorted(duplicate_groups.items())
                    if len(ids) > 1
                ],
                "raw_q_rank": int(np.linalg.matrix_rank(matrix)),
                "unique_q_rank": int(np.linalg.matrix_rank(unique_matrix)),
                "full_column_rank_after_canonicalisation": int(np.linalg.matrix_rank(unique_matrix))
                == len(unique_signatures),
                "support_cells": {
                    "minimum": int(unique_matrix.sum(axis=0).min()),
                    "median": float(np.median(unique_matrix.sum(axis=0))),
                    "maximum": int(unique_matrix.sum(axis=0).max()),
                },
                "exact_kstar_activation_matches": exact_matches,
                "exact_kstar_match_count": len({row["generator_kc_id"] for row in exact_matches}),
                "ontology_level_limitations": result["ontology_level_limitations"],
            }
        )
    pairwise = []
    replicate_ids = plan["replicate_ids"]
    for left_index, left in enumerate(replicate_ids):
        for right in replicate_ids[left_index + 1 :]:
            intersection = signature_sets[left] & signature_sets[right]
            union = signature_sets[left] | signature_sets[right]
            pairwise.append(
                {
                    "left": left,
                    "right": right,
                    "shared_activation_hypotheses": len(intersection),
                    "union_activation_hypotheses": len(union),
                    "jaccard": len(intersection) / len(union) if union else 1.0,
                }
            )
    all_shared = set.intersection(*(signature_sets[key] for key in replicate_ids))
    union_all = set.union(*(signature_sets[key] for key in replicate_ids))
    ledger_payload = "".join(canonical_json(row) + "\n" for row in ledger)
    write_frozen(output / "activation_ledger.jsonl", ledger_payload, "activation ledger")
    summary = {
        "study_id": plan["study_id"],
        "status": "ANALYSED_AFTER_PROPOSALS_FROZEN",
        "evidence_boundary": {
            "automated_proposers": len(proposals),
            "human_or_expert_gold": False,
            "interpretation": "Activation stability and structural diagnostics only; no ontology is selected.",
        },
        "replicates": replicate_results,
        "pairwise_activation_set_agreement": pairwise,
        "activation_hypotheses_shared_by_all_replicates": len(all_shared),
        "activation_hypotheses_in_union": len(union_all),
        "frozen_kstar_columns": len(kstar),
        "kstar_columns_recovered_by_any_exact_activation": len(
            {
                row["exact_frozen_kstar_signature_match"]
                for row in ledger
                if row["exact_frozen_kstar_signature_match"]
            }
        ),
        "methodological_conclusion_rule": {
            "high_agreement": "Convergence by activation supports reproducibility, not human truth.",
            "low_agreement": "Divergence demonstrates ontology underdetermination from GrammarCells alone.",
            "rank": "Rank is reported as geometry and never used as a semantic selection score.",
        },
        "activation_ledger": {
            "path": "activation_ledger.jsonl",
            "rows": len(ledger),
            "sha256": sha256_bytes(ledger_payload.encode("utf-8")),
        },
    }
    write_frozen_json(output / "results.json", summary, "KC induction results")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("plan", "run", "analyse", "all"))
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--workers", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command in {"plan", "all"}:
        print(json.dumps(plan(args.dataset, args.config, args.prompt, args.schema, args.output), indent=2))
    if args.command in {"run", "all"}:
        print(
            json.dumps(
                run(
                    args.dataset,
                    args.config,
                    args.prompt,
                    args.schema,
                    args.output,
                    args.evidence,
                    args.workers,
                ),
                indent=2,
            )
        )
    if args.command in {"analyse", "all"}:
        print(json.dumps(analyse(args.dataset, args.output), indent=2))


if __name__ == "__main__":
    main()
