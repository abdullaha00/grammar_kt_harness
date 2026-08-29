#!/usr/bin/env python3
"""Matched live audit of medium/high/xhigh effort in the three LM stages.

This is an explicit research procedure, not a generic experiment framework.
It freezes challenge-enriched normalisation and validation cohorts, interleaves
effort conditions, retains CLI token/latency evidence, and generates the active
N=3 item block over every final GrammarCell.  Generation is judged only after
the validation effort has been selected and passed with ``--judge-effort``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any, Callable

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.generate import generate_item_candidate
from grammar_kt.io import (
    read_jsonl,
    read_text,
    read_yaml,
    render,
    write_json,
    write_jsonl,
)
from grammar_kt.normalise import (
    PHASE1_FIELDS,
    _validate_mapping,
    _validate_phase2_transition,
)
from grammar_kt.validate_items import answer_span_consistency, validate_items


EFFORTS = ("medium", "high", "xhigh")
EFFORT_ORDER = {effort: index for index, effort in enumerate(EFFORTS)}
SEED = 20260828
DEFAULT_OUTPUT = ROOT / "reports/backend_thinking/artifacts/live_v1"
DATASET = ROOT / "data/grammar_kt_medium_v1"
NORMALISATION_TRANSITIONS = (
    ROOT / "reports/phase4/artifacts/normalisation/legacy_transitions.jsonl"
)
VALIDATION_SOURCE = (
    ROOT / "reports/phase4/artifacts/validation_reliability"
)

NORMALISATION_COMPLETE_IDS = (
    "1741163713626x133661684035994100",  # present simple affirmative
    "1741163712739x998605611367738000",  # past simple negative
    "1741163713121x303053781636601900",  # present progressive negative
    "1741163712747x475008652441932600",  # present perfect negative
)
NORMALISATION_PARTIAL_IDS = (
    "1741163712321x444348941700378800",  # past progressive questions
    "1741163712334x456379754309706560",  # past perfect questions
    "1741163712052x892253245373132200",  # passive with modals
    "1741163712049x547897454512315650",  # modal perfect passive
)
NORMALISATION_OUT_OF_SCOPE_IDS = (
    "1741163715029x648850706024519700",  # tags
    "1741163713626x199664325289681020",  # if clauses
    "1741163712747x212368838412682500",  # inversion
    "1741163712048x834192566226660200",  # passive infinitive
    "1741163708343x784452436860678700",  # interrogative + adverb
)
GENERATION_CELL_IDS = tuple(f"cell_{index:03d}" for index in range(1, 25))
CORRECTION_ITEM_IDS = {
    "candidate_cell_003_01",
    "candidate_cell_005_01",
    "candidate_cell_017_06",
    "candidate_cell_018_01",
    "candidate_cell_018_03",
    "candidate_cell_019_03",
}
TOKEN_PATTERN = re.compile(r"tokens used\s*\n([0-9,]+)", re.IGNORECASE)
CODEX_VERSION = subprocess.run(
    ["codex", "--version"],
    text=True,
    capture_output=True,
    check=True,
).stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _stable(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _mapping_signature(mapping: dict[str, Any] | None) -> str | None:
    """Canonical structural signature; ignore note prose and harmless ordering."""

    if mapping is None:
        return None
    cells = []
    for cell in mapping["cells"]:
        cells.append(
            {
                name: sorted(value) if isinstance(value, list) else value
                for name, value in sorted(cell.items())
            }
        )
    return _stable(
        {
            "result": mapping["result"],
            "cells": sorted((_stable(cell) for cell in cells)),
            "phase2_eligible": sorted(mapping["phase2_eligible"]),
        }
    )


def _call_totals(evidence_dir: Path) -> dict[str, Any]:
    metadata = [_json(path) for path in evidence_dir.glob("**/call_metadata.json")]
    return {
        "model_calls": len(metadata),
        "tokens_used": sum(row.get("tokens_used") or 0 for row in metadata),
        "model_runtime_seconds": sum(row.get("runtime_seconds") or 0.0 for row in metadata),
        "model_call_failures": sum(row.get("returncode") != 0 for row in metadata),
    }


def audited_model_call(
    prompt: str,
    *,
    model: str,
    reasoning_effort: str,
    input_data: dict[str, Any],
    stage: str,
    call_key: str,
    evidence_dir: Path | None = None,
) -> dict[str, Any]:
    """Mirror the active Codex call while retaining usage, stderr, and failures."""

    if evidence_dir is None:
        raise ValueError("backend-thinking audit requires an evidence directory")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    write_json(evidence_dir / "input.json", input_data)
    (evidence_dir / "rendered_prompt.txt").write_text(prompt, encoding="utf-8")
    write_json(
        evidence_dir / "model_settings.json",
        {
            "model": model,
            "reasoning_effort": reasoning_effort,
            "stage": stage,
            "call_key": call_key,
            "codex_version": CODEX_VERSION,
        },
    )
    command = [
        "codex",
        "exec",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--model",
        model,
        "--config",
        f'model_reasoning_effort="{reasoning_effort}"',
        "-",
    ]
    started = time.monotonic()
    result = subprocess.run(
        command,
        # Isolate the model from retained labels and prior results in the
        # repository. The complete scientific input is already in ``prompt``.
        cwd=evidence_dir,
        input=prompt,
        text=True,
        capture_output=True,
        check=False,
    )
    runtime = time.monotonic() - started
    raw = result.stdout.strip()
    (evidence_dir / "raw_output.txt").write_text(raw + "\n", encoding="utf-8")
    (evidence_dir / "cli_stderr.txt").write_text(result.stderr, encoding="utf-8")
    token_matches = TOKEN_PATTERN.findall(result.stderr)
    write_json(
        evidence_dir / "call_metadata.json",
        {
            "returncode": result.returncode,
            "runtime_seconds": runtime,
            "tokens_used": int(token_matches[-1].replace(",", "")) if token_matches else None,
            "token_metric": "codex_cli_total_tokens_used",
            "command": command,
        },
    )
    if result.returncode != 0:
        raise RuntimeError(f"codex exec failed with return code {result.returncode}")
    parsed = json.loads(raw)
    write_json(evidence_dir / "parsed_result.json", parsed)
    return parsed


def _parallel(
    tasks: list[dict[str, Any]],
    function: Callable[[dict[str, Any]], dict[str, Any]],
    workers: int,
    label: str,
) -> list[dict[str, Any]]:
    if workers < 1:
        raise ValueError("workers must be positive")
    results: list[dict[str, Any] | None] = [None] * len(tasks)
    if workers == 1:
        for index, task in enumerate(tasks):
            results[index] = function(task)
            if (index + 1) % 5 == 0 or index + 1 == len(tasks):
                print(f"{label}: {index + 1}/{len(tasks)}", flush=True)
        return [row for row in results if row is not None]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(function, task): index for index, task in enumerate(tasks)}
        completed = 0
        for future in as_completed(futures):
            results[futures[future]] = future.result()
            completed += 1
            if completed % 5 == 0 or completed == len(tasks):
                print(f"{label}: {completed}/{len(tasks)}", flush=True)
    return [row for row in results if row is not None]


def _select_validation_cohort() -> list[dict[str, Any]]:
    candidates = {row["item_id"]: row for row in read_jsonl(DATASET / "items/curated_candidates.jsonl")}
    judgments = {row["item_id"]: row for row in read_jsonl(DATASET / "items/curated_validation.jsonl")}
    eligible = []
    for item_id, candidate in candidates.items():
        judgment = judgments[item_id]
        if str(judgment.get("rejection_stage") or "").startswith("deterministic"):
            continue
        eligible.append(
            {
                "item_id": item_id,
                "cell_id": candidate["cell_id"],
                "format": candidate["format"],
                "prompt": candidate["prompt"],
                "target_answer": candidate["target_answer"],
                "accepted_answers": candidate["accepted_answers"],
                "retained_accepted": judgment["accepted"],
                "retained_failed_criteria": sorted(
                    name
                    for name, result in judgment.get("judgments", {}).items()
                    if not result["passed"]
                ),
                "packaging_correction": item_id in CORRECTION_ITEM_IDS,
            }
        )

    selected = [row for row in eligible if row["item_id"] in CORRECTION_ITEM_IDS]
    selected_ids = {row["item_id"] for row in selected}
    target_by_label = {True: 18, False: 18}
    for label in (True, False):
        while sum(row["retained_accepted"] == label for row in selected) < target_by_label[label]:
            covered_cells = Counter(row["cell_id"] for row in selected)
            covered_failures = Counter(
                criterion for row in selected for criterion in row["retained_failed_criteria"]
            )
            pool = [
                row for row in eligible
                if row["retained_accepted"] == label and row["item_id"] not in selected_ids
            ]
            if not pool:
                raise ValueError("validation cohort cannot meet the balanced target")
            pool.sort(
                key=lambda row: (
                    covered_cells[row["cell_id"]] > 0,
                    -sum(covered_failures[name] == 0 for name in row["retained_failed_criteria"]),
                    covered_cells[row["cell_id"]],
                    row["item_id"],
                )
            )
            chosen = pool[0]
            selected.append(chosen)
            selected_ids.add(chosen["item_id"])
    selected.sort(key=lambda row: row["item_id"])
    if len(selected) != 36 or sum(row["retained_accepted"] for row in selected) != 18:
        raise ValueError("validation cohort must be 18 accepted and 18 rejected")
    return selected


def _adversarial_validation_safety_set() -> list[dict[str, Any]]:
    """Authored negative controls for criteria absent from retained rejects."""

    rows = [
        (
            "target_fidelity_1", "cell_003",
            "Write the sentence about Mia's routine: ______",
            "Mia did not walk to work yesterday.",
            ["Mia did not walk to work yesterday."],
            ["target_fidelity"],
        ),
        (
            "target_fidelity_2", "cell_019",
            "Write the sentence about Ava and the letter: ______",
            "Ava mails the letter every Monday.",
            ["Ava mails the letter every Monday."],
            ["target_fidelity"],
        ),
        (
            "grammaticality_1", "cell_003",
            "Describe Mia's daily walk: ______",
            "Mia walk to school every day.",
            ["Mia walk to school every day."],
            ["grammaticality"],
        ),
        (
            "grammaticality_2", "cell_019",
            "Report what happened to the letters yesterday: ______",
            "The letters was sent yesterday.",
            ["The letters was sent yesterday."],
            ["grammaticality"],
        ),
        (
            "lexical_simplicity_1", "cell_003",
            "Describe the scholar's customary conduct: ______",
            "The sesquipedalian logomachist tergiversates quotidianly.",
            ["The sesquipedalian logomachist tergiversates quotidianly."],
            ["non_target_language_simplicity"],
        ),
        (
            "lexical_simplicity_2", "cell_019",
            "State what happened to the abstruse tract: ______",
            "The antidisestablishmentarian tract was promulgated yesternight.",
            ["The antidisestablishmentarian tract was promulgated yesternight."],
            ["non_target_language_simplicity"],
        ),
        (
            "answer_leakage_1", "cell_008",
            "The complete answer is ‘Mia is reading the book.’ Copy it here: ______",
            "Mia is reading the book.",
            ["Mia is reading the book."],
            ["no_answer_leakage"],
        ),
        (
            "answer_leakage_2", "cell_020",
            "Use the displayed answer ‘The room is cleaned every day.’ Response: ______",
            "The room is cleaned every day.",
            ["The room is cleaned every day."],
            ["no_answer_leakage"],
        ),
        (
            "extraneous_grammar_1", "cell_003",
            "Had the counterfactual protasis not undergone ellipsis, supply the matrix-clause consequence: ______",
            "Mia closes the window.",
            ["Mia closes the window."],
            ["no_extraneous_grammar"],
        ),
        (
            "extraneous_grammar_2", "cell_019",
            "Resolve the garden-path relative and then render its presupposed event as a passive: ______",
            "The report was filed yesterday.",
            ["The report was filed yesterday."],
            ["no_extraneous_grammar"],
        ),
        (
            "world_knowledge_1", "cell_003",
            "Without looking it up, write the present-tense fact naming Kazakhstan's capital: ______",
            "Astana is the capital of Kazakhstan.",
            ["Astana is the capital of Kazakhstan."],
            ["no_world_knowledge"],
        ),
        (
            "world_knowledge_2", "cell_019",
            "Recall the medieval event and complete the historical fact: ______",
            "Magna Carta was sealed at Runnymede in 1215.",
            ["Magna Carta was sealed at Runnymede in 1215."],
            ["no_world_knowledge"],
        ),
    ]
    return [
        {
            "item_id": f"adversarial_{name}",
            "cell_id": cell_id,
            "format": "controlled_production",
            "prompt": prompt,
            "target_answer": target_answer,
            "accepted_answers": accepted_answers,
            "retained_accepted": False,
            "retained_failed_criteria": expected_failures,
            "packaging_correction": False,
            "adversarial_safety": True,
            "reference_source": "authored_adversarial_negative_control",
        }
        for name, cell_id, prompt, target_answer, accepted_answers, expected_failures in rows
    ]


def prepare(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_rows = read_jsonl(DATASET / "source/descriptors.jsonl")
    source_by_id = {row["source_id"]: row for row in source_rows}
    retained_mappings = read_jsonl(DATASET / "normalisation/mappings.jsonl")
    mapping_by_id = {row["source_id"]: row for row in retained_mappings}
    eligible_ids = [row["source_id"] for row in retained_mappings if row["phase2_eligible"]]
    unresolved_ids = [row["source_id"] for row in retained_mappings if row["result"] == "unresolved"]
    normalisation_ids = [
        *eligible_ids,
        *unresolved_ids,
        *NORMALISATION_OUT_OF_SCOPE_IDS,
        *NORMALISATION_COMPLETE_IDS,
        *NORMALISATION_PARTIAL_IDS,
    ]
    if len(normalisation_ids) != 24 or len(set(normalisation_ids)) != 24:
        raise ValueError("normalisation cohort must contain 24 unique descriptors")
    normalisation_cohort = [
        {
            "cohort_order": order,
            "stratum": (
                "phase2_eligible" if source_id in eligible_ids else
                "unresolved" if source_id in unresolved_ids else
                "out_of_scope" if source_id in NORMALISATION_OUT_OF_SCOPE_IDS else
                "complete_noneligible" if source_id in NORMALISATION_COMPLETE_IDS else
                "partial_noneligible"
            ),
            "descriptor": source_by_id[source_id],
            "retained_mapping": mapping_by_id[source_id],
        }
        for order, source_id in enumerate(normalisation_ids, 1)
    ]
    write_jsonl(output_dir / "cohorts/normalisation_phase1.jsonl", normalisation_cohort)

    transition_rows = [
        row for row in read_jsonl(NORMALISATION_TRANSITIONS)
        if row["duplicate_of"] is None and row["phase1"]["phase2_eligible"]
    ]
    if len(transition_rows) != 9:
        raise ValueError("normalisation Phase-2 cohort must contain nine fixed transitions")
    phase2_cohort = []
    for order, row in enumerate(transition_rows, 1):
        source = source_by_id[row["source_id"]]
        phase2_cohort.append(
            {
                "cohort_order": order,
                "source_id": row["source_id"],
                "descriptor": {name: source[name] for name in PHASE1_FIELDS},
                "examples": source["examples"],
                "fixed_phase1_mapping": row["phase1"],
                "retained_phase2_mapping": row["phase2"],
            }
        )
    write_jsonl(output_dir / "cohorts/normalisation_phase2.jsonl", phase2_cohort)

    cells = [
        row for row in read_jsonl(DATASET / "canonical/cells.jsonl")
        if row["cell_id"] in set(GENERATION_CELL_IDS)
    ]
    cells.sort(key=lambda row: row["cell_id"])
    if [row["cell_id"] for row in cells] != list(GENERATION_CELL_IDS):
        raise ValueError("generation cohort must contain all 24 final GrammarCells")
    write_jsonl(output_dir / "cohorts/generation_cells.jsonl", cells)
    cells_by_id = {row["cell_id"]: row for row in cells}

    validation_cohort = _select_validation_cohort()
    write_jsonl(output_dir / "cohorts/validation_items_with_retained_labels.jsonl", validation_cohort)
    validation_safety = _adversarial_validation_safety_set()
    write_jsonl(output_dir / "supplementary/validation_adversarial_safety.jsonl", validation_safety)
    blinded_validation = []
    validation_mapping = []
    shuffled = [*validation_cohort, *validation_safety]
    random.Random(SEED).shuffle(shuffled)
    for order, row in enumerate(shuffled, 1):
        blind_id = f"validation_review_{order:03d}"
        blinded_validation.append(
            {
                "review_id": blind_id,
                "target_cell": cells_by_id[row["cell_id"]]["features"],
                **{
                    key: row[key]
                    for key in (
                        "format",
                        "prompt",
                        "target_answer",
                        "accepted_answers",
                    )
                },
            }
        )
        validation_mapping.append(
            {
                "review_id": blind_id,
                "item_id": row["item_id"],
                "retained_accepted": row["retained_accepted"],
                "retained_failed_criteria": row["retained_failed_criteria"],
                "packaging_correction": row["packaging_correction"],
                "adversarial_safety": row.get("adversarial_safety", False),
                "reference_source": row.get(
                    "reference_source", "retained_medium_curation"
                ),
            }
        )
    write_jsonl(output_dir / "review_packets/validation_items.jsonl", blinded_validation)
    write_jsonl(output_dir / "private_mappings/validation_review_map.jsonl", validation_mapping)
    phase1_results_path = output_dir / "normalisation/phase1/results.jsonl"
    phase2_results_path = output_dir / "normalisation/phase2/results.jsonl"
    if phase1_results_path.exists() and phase2_results_path.exists():
        make_normalisation_review_packet(
            output_dir,
            read_jsonl(phase1_results_path),
            read_jsonl(phase2_results_path),
        )

    hashes = {}
    declaration_paths = [
        ROOT / "modules/grammar/resource/egp/normalisation/phase1.txt",
        ROOT / "modules/grammar/resource/egp/normalisation/phase2.txt",
        ROOT / "modules/grammar/resource/egp/normalisation/rulebook.md",
        ROOT / "modules/grammar/canonical/schema.yaml",
        ROOT / "modules/items/generation/prompt.txt",
        ROOT / "modules/items/generation/rulebook.md",
        ROOT / "modules/items/generation/design.yaml",
        ROOT / "modules/items/generation/formats/controlled_production.yaml",
        ROOT / "modules/items/validation/prompt.txt",
        ROOT / "modules/items/validation/criteria.yaml",
    ]
    for path in declaration_paths:
        hashes[str(path.relative_to(ROOT))] = _sha256(path)
    for path in sorted((output_dir / "cohorts").glob("*.jsonl")):
        hashes[str(path.relative_to(output_dir))] = _sha256(path)
    manifest = {
        "experiment_id": "BACKEND-THINKING-001",
        "date": date.today().isoformat(),
        "status": "prepared",
        "claim_boundary": (
            "Fresh matched live-model effort audit. Provider sampling seeds and model "
            "snapshots are unavailable; two replicates estimate ordinary call variability. "
            "Research-agent reviews are not human or expert gold labels."
        ),
        "efforts": list(EFFORTS),
        "models": {
            "normalisation": "gpt-5.6-sol",
            "generation": "gpt-5.6-sol",
            "validation": "gpt-5.6-terra",
        },
        "replicates": {"normalisation": 2, "validation": 2, "generation": 1},
        "scale": {
            "normalisation_phase1_descriptors": 24,
            "normalisation_phase2_fixed_transitions": 9,
            "validation_items": 36,
            "generation_cells": 24,
            "generation_candidates_per_cell": 3,
        },
        "supplementary_scale": {
            "validation_adversarial_safety_items": len(validation_safety),
        },
        "supplementary_hashes": {
            "supplementary/validation_adversarial_safety.jsonl": _sha256(
                output_dir / "supplementary/validation_adversarial_safety.jsonl"
            ),
        },
        "seed_use": {
            "seed": SEED,
            "uses": ["cohort blinding", "interleaved call ordering", "bootstrap"],
            "provider_sampling_seed_available": False,
        },
        "selection_rule": {
            "principle": "lowest admissible effort non-inferior to the best quality setting",
            "normalisation_margin": 0.05,
            "validation_margin": 0.05,
            "generation_margin": 0.05,
            "generation_coverage_tolerance_cells": 1,
            "critical_error_gate": True,
        },
        "declaration_hashes": hashes,
        "codex_version": CODEX_VERSION,
    }
    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists():
        previous = _json(manifest_path)
        for key in ("experiment_id", "efforts", "models", "replicates", "scale", "declaration_hashes"):
            if previous.get(key) != manifest.get(key):
                raise RuntimeError(f"incompatible retained audit manifest field: {key}")
        manifest["status"] = previous.get("status", "prepared")
        manifest["exact_commands"] = previous.get("exact_commands", [])
        if "generation_judge" in previous:
            manifest["generation_judge"] = previous["generation_judge"]
        for key in ("completion", "operational_settings", "result_hashes"):
            if key in previous:
                manifest[key] = previous[key]
    write_json(manifest_path, manifest)
    return manifest


def _task_order(tasks: list[dict[str, Any]], salt: str) -> list[dict[str, Any]]:
    ordered = tasks.copy()
    random.Random(f"{SEED}:{salt}").shuffle(ordered)
    return ordered


def run_normalisation(output_dir: Path, workers: int) -> None:
    grammar_schema = read_yaml(ROOT / "modules/grammar/canonical/schema.yaml")
    phase1_prompt = read_text(ROOT / "modules/grammar/resource/egp/normalisation/phase1.txt")
    phase2_prompt = read_text(ROOT / "modules/grammar/resource/egp/normalisation/phase2.txt")
    rulebook = read_text(ROOT / "modules/grammar/resource/egp/normalisation/rulebook.md")
    phase1_cohort = read_jsonl(output_dir / "cohorts/normalisation_phase1.jsonl")
    phase2_cohort = read_jsonl(output_dir / "cohorts/normalisation_phase2.jsonl")

    phase1_tasks = _task_order(
        [
            {"effort": effort, "replicate": replicate, "row": row}
            for row in phase1_cohort
            for effort in EFFORTS
            for replicate in (1, 2)
        ],
        "normalisation-phase1",
    )

    def phase1_task(task: dict[str, Any]) -> dict[str, Any]:
        effort = task["effort"]
        replicate = task["replicate"]
        cohort_row = task["row"]
        resource = cohort_row["descriptor"]
        source_id = resource["source_id"]
        result_path = output_dir / f"normalisation/phase1/results/{effort}/r{replicate}/{source_id}.json"
        if result_path.exists():
            return _json(result_path)
        evidence = output_dir / f"normalisation/phase1/evidence/{effort}/r{replicate}/{source_id}"
        descriptor = {name: resource[name] for name in PHASE1_FIELDS}
        prompt = render(
            phase1_prompt,
            {"descriptor": descriptor, "canonical_schema": grammar_schema, "rulebook": rulebook},
        )
        started = time.monotonic()
        mapping = None
        error = None
        try:
            mapping = audited_model_call(
                prompt,
                model="gpt-5.6-sol",
                reasoning_effort=effort,
                input_data={"descriptor": descriptor},
                stage="normalisation.phase1",
                call_key=source_id,
                evidence_dir=evidence,
            )
            _validate_mapping(mapping, source_id, grammar_schema)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        row = {
            "source_id": source_id,
            "stratum": cohort_row["stratum"],
            "effort": effort,
            "replicate": replicate,
            "success": error is None,
            "error": error,
            "mapping": mapping,
            "retained_mapping": cohort_row["retained_mapping"],
            "task_runtime_seconds": time.monotonic() - started,
            **_call_totals(evidence),
        }
        write_json(result_path, row)
        return row

    phase1_results = _parallel(phase1_tasks, phase1_task, workers, "normalisation phase1")
    write_jsonl(output_dir / "normalisation/phase1/results.jsonl", phase1_results)

    phase2_tasks = _task_order(
        [
            {"effort": effort, "replicate": replicate, "row": row}
            for row in phase2_cohort
            for effort in EFFORTS
            for replicate in (1, 2)
        ],
        "normalisation-phase2",
    )

    def phase2_task(task: dict[str, Any]) -> dict[str, Any]:
        effort = task["effort"]
        replicate = task["replicate"]
        cohort_row = task["row"]
        source_id = cohort_row["source_id"]
        result_path = output_dir / f"normalisation/phase2/results/{effort}/r{replicate}/{source_id}.json"
        if result_path.exists():
            return _json(result_path)
        evidence = output_dir / f"normalisation/phase2/evidence/{effort}/r{replicate}/{source_id}"
        prompt = render(
            phase2_prompt,
            {
                "descriptor": cohort_row["descriptor"],
                "phase1_mapping": cohort_row["fixed_phase1_mapping"],
                "examples": cohort_row["examples"],
                "canonical_schema": grammar_schema,
                "rulebook": rulebook,
            },
        )
        input_data = {
            "descriptor": cohort_row["descriptor"],
            "phase1_mapping": cohort_row["fixed_phase1_mapping"],
            "examples": cohort_row["examples"],
        }
        started = time.monotonic()
        mapping = None
        error = None
        try:
            mapping = audited_model_call(
                prompt,
                model="gpt-5.6-sol",
                reasoning_effort=effort,
                input_data=input_data,
                stage="normalisation.phase2",
                call_key=source_id,
                evidence_dir=evidence,
            )
            _validate_mapping(mapping, source_id, grammar_schema, allow_resolved_eligibility=True)
            _validate_phase2_transition(cohort_row["fixed_phase1_mapping"], mapping, grammar_schema)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        row = {
            "source_id": source_id,
            "effort": effort,
            "replicate": replicate,
            "success": error is None,
            "error": error,
            "mapping": mapping,
            "fixed_phase1_mapping": cohort_row["fixed_phase1_mapping"],
            "retained_phase2_mapping": cohort_row["retained_phase2_mapping"],
            "task_runtime_seconds": time.monotonic() - started,
            **_call_totals(evidence),
        }
        write_json(result_path, row)
        return row

    phase2_results = _parallel(phase2_tasks, phase2_task, workers, "normalisation phase2")
    write_jsonl(output_dir / "normalisation/phase2/results.jsonl", phase2_results)
    make_normalisation_review_packet(output_dir, phase1_results, phase2_results)


def make_normalisation_review_packet(
    output_dir: Path,
    phase1_results: list[dict[str, Any]],
    phase2_results: list[dict[str, Any]],
) -> None:
    cohort = {row["descriptor"]["source_id"]: row for row in read_jsonl(output_dir / "cohorts/normalisation_phase1.jsonl")}
    phase2_cohort = {row["source_id"]: row for row in read_jsonl(output_dir / "cohorts/normalisation_phase2.jsonl")}
    entries = []
    private = []
    for stage, rows in (("phase1", phase1_results), ("phase2", phase2_results)):
        for row in rows:
            review_source = cohort[row["source_id"]]["descriptor"]
            review_id = hashlib.sha256(
                f"{SEED}:{stage}:{row['source_id']}:{row['effort']}:{row['replicate']}".encode()
            ).hexdigest()[:12]
            entries.append(
                {
                    "review_id": f"normalisation_{review_id}",
                    "stage": stage,
                    "descriptor": {
                        name: review_source[name]
                        for name in (
                            (*PHASE1_FIELDS, "examples")
                            if stage == "phase2"
                            else PHASE1_FIELDS
                        )
                    },
                    "fixed_phase1_mapping": (
                        phase2_cohort[row["source_id"]]["fixed_phase1_mapping"]
                        if stage == "phase2"
                        else None
                    ),
                    "candidate_mapping": row["mapping"],
                    "contract_success": row["success"],
                    "contract_error": row["error"],
                }
            )
            private.append(
                {
                    "review_id": f"normalisation_{review_id}",
                    "stage": stage,
                    "source_id": row["source_id"],
                    "effort": row["effort"],
                    "replicate": row["replicate"],
                }
            )
    random.Random(f"{SEED}:normalisation-review").shuffle(entries)
    write_jsonl(output_dir / "review_packets/normalisation_outputs.jsonl", entries)
    write_jsonl(output_dir / "private_mappings/normalisation_review_map.jsonl", private)


def run_validation(output_dir: Path, workers: int) -> None:
    cells = read_jsonl(DATASET / "canonical/cells.jsonl")
    candidates = [
        *read_jsonl(output_dir / "cohorts/validation_items_with_retained_labels.jsonl"),
        *read_jsonl(output_dir / "supplementary/validation_adversarial_safety.jsonl"),
    ]
    prompt = read_text(ROOT / "modules/items/validation/prompt.txt")
    criteria = read_yaml(ROOT / "modules/items/validation/criteria.yaml")
    tasks = _task_order(
        [
            {"effort": effort, "replicate": replicate, "candidate": candidate}
            for candidate in candidates
            for effort in EFFORTS
            for replicate in (1, 2)
        ],
        "validation",
    )

    def task_function(task: dict[str, Any]) -> dict[str, Any]:
        effort = task["effort"]
        replicate = task["replicate"]
        source_candidate = task["candidate"]
        item_id = source_candidate["item_id"]
        audit_id = "validation_live_" + hashlib.sha256(
            f"{SEED}:{item_id}".encode()
        ).hexdigest()[:12]
        result_path = output_dir / f"validation/results/{effort}/r{replicate}/{item_id}.json"
        if result_path.exists():
            return _json(result_path)
        evidence = output_dir / f"validation/evidence/{effort}/r{replicate}/{audit_id}"
        candidate = {
            key: source_candidate[key]
            for key in ("cell_id", "format", "prompt", "target_answer", "accepted_answers")
        }
        candidate["item_id"] = audit_id
        started = time.monotonic()
        judgments = None
        accepted = False
        error = None
        try:
            accepted_rows, judgment_rows = validate_items(
                [candidate],
                cells,
                prompt,
                criteria,
                model="gpt-5.6-terra",
                reasoning_effort=effort,
                model_call=audited_model_call,
                evidence_dir=evidence,
            )
            judgments = judgment_rows[0]
            accepted = bool(accepted_rows)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        row = {
            "item_id": item_id,
            "audit_id": audit_id,
            "cell_id": candidate["cell_id"],
            "effort": effort,
            "replicate": replicate,
            "success": error is None,
            "error": error,
            "accepted": accepted,
            "judgment": judgments,
            "retained_accepted": source_candidate["retained_accepted"],
            "retained_failed_criteria": source_candidate["retained_failed_criteria"],
            "packaging_correction": source_candidate["packaging_correction"],
            "adversarial_safety": source_candidate.get("adversarial_safety", False),
            "reference_source": source_candidate.get(
                "reference_source", "retained_medium_curation"
            ),
            "task_runtime_seconds": time.monotonic() - started,
            **_call_totals(evidence),
        }
        write_json(result_path, row)
        return row

    results = _parallel(tasks, task_function, workers, "validation")
    write_jsonl(output_dir / "validation/results.jsonl", results)


def run_generation(output_dir: Path, workers: int, judge_effort: str | None) -> None:
    cells = read_jsonl(output_dir / "cohorts/generation_cells.jsonl")
    prompt = read_text(ROOT / "modules/items/generation/prompt.txt")
    rulebook = read_text(ROOT / "modules/items/generation/rulebook.md")
    design = read_yaml(ROOT / "modules/items/generation/design.yaml")
    item_format = read_yaml(ROOT / "modules/items/generation/formats/controlled_production.yaml")
    tasks = _task_order(
        [
            {"effort": effort, "cell": cell, "candidate_index": candidate_index}
            for cell in cells
            for effort in EFFORTS
            for candidate_index in (1, 2, 3)
        ],
        "generation",
    )

    def generation_task(task: dict[str, Any]) -> dict[str, Any]:
        effort = task["effort"]
        cell = task["cell"]
        index = task["candidate_index"]
        result_path = output_dir / f"generation/results/{effort}/{cell['cell_id']}_{index:02d}.json"
        if result_path.exists():
            return _json(result_path)
        evidence = output_dir / f"generation/evidence/{effort}/{cell['cell_id']}_{index:02d}"
        started = time.monotonic()
        candidate = None
        error = None
        try:
            candidate = generate_item_candidate(
                cell,
                prompt,
                rulebook,
                design,
                item_format,
                candidate_index=index,
                model="gpt-5.6-sol",
                reasoning_effort=effort,
                model_call=audited_model_call,
                evidence_dir=evidence,
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        span_passed = None
        span_note = None
        if candidate is not None:
            span_passed, span_note = answer_span_consistency(candidate)
        row = {
            "experiment_item_id": f"generation_{effort}_{cell['cell_id']}_{index:02d}",
            "cell_id": cell["cell_id"],
            "candidate_index": index,
            "effort": effort,
            "success": error is None,
            "error": error,
            "answer_span_passed": span_passed,
            "answer_span_note": span_note,
            "candidate": candidate,
            "task_runtime_seconds": time.monotonic() - started,
            **_call_totals(evidence),
        }
        write_json(result_path, row)
        return row

    generation_results = _parallel(tasks, generation_task, workers, "generation")
    write_jsonl(output_dir / "generation/results.jsonl", generation_results)
    make_generation_review_packet(output_dir, generation_results)
    if judge_effort is not None:
        run_generation_judgment(output_dir, generation_results, cells, workers, judge_effort)


def make_generation_review_packet(output_dir: Path, generation_results: list[dict[str, Any]]) -> None:
    cells = {row["cell_id"]: row for row in read_jsonl(output_dir / "cohorts/generation_cells.jsonl")}
    entries = []
    private = []
    for row in generation_results:
        if row["candidate_index"] != 1 or row["candidate"] is None:
            continue
        review_id = hashlib.sha256(f"{SEED}:{row['experiment_item_id']}".encode()).hexdigest()[:12]
        candidate = row["candidate"]
        entries.append(
            {
                "review_id": f"generation_{review_id}",
                "target_cell": cells[row["cell_id"]]["features"],
                "format": candidate["format"],
                "prompt": candidate["prompt"],
                "target_answer": candidate["target_answer"],
                "accepted_answers": candidate["accepted_answers"],
            }
        )
        private.append(
            {
                "review_id": f"generation_{review_id}",
                "experiment_item_id": row["experiment_item_id"],
                "effort": row["effort"],
                "cell_id": row["cell_id"],
                "candidate_index": row["candidate_index"],
            }
        )
    random.Random(f"{SEED}:generation-review").shuffle(entries)
    write_jsonl(output_dir / "review_packets/generation_position1.jsonl", entries)
    write_jsonl(output_dir / "private_mappings/generation_review_map.jsonl", private)


def run_generation_judgment(
    output_dir: Path,
    generation_results: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    workers: int,
    judge_effort: str,
) -> None:
    selection_path = output_dir / "validation/selection.json"
    if not selection_path.exists():
        raise RuntimeError(
            "freeze validation/selection.json before judging generation conditions"
        )
    selection = _json(selection_path)
    if selection.get("generation_judge_effort") != judge_effort:
        raise RuntimeError(
            "--judge-effort does not match the frozen validation selection: "
            f"{selection.get('generation_judge_effort')!r}"
        )
    manifest = _json(output_dir / "manifest.json")
    retained_judge = manifest.get("generation_judge")
    proposed_judge = {
        "model": "gpt-5.6-terra",
        "reasoning_effort": judge_effort,
    }
    if retained_judge is not None and retained_judge != proposed_judge:
        raise RuntimeError(
            "generation judgments are already frozen with a different judge: "
            f"{retained_judge}"
        )
    manifest["generation_judge"] = proposed_judge
    write_json(output_dir / "manifest.json", manifest)

    prompt = read_text(ROOT / "modules/items/validation/prompt.txt")
    criteria = read_yaml(ROOT / "modules/items/validation/criteria.yaml")
    successful = [row for row in generation_results if row["success"] and row["candidate"] is not None]
    shuffled = successful.copy()
    random.Random(f"{SEED}:generation-judge").shuffle(shuffled)
    blind_map = []
    tasks = []
    for order, row in enumerate(shuffled, 1):
        blind_id = f"generation_judge_{order:04d}"
        candidate = dict(row["candidate"])
        candidate["item_id"] = blind_id
        tasks.append({"blind_id": blind_id, "candidate": candidate, "source": row})
        blind_map.append(
            {
                "blind_id": blind_id,
                "experiment_item_id": row["experiment_item_id"],
                "effort": row["effort"],
                "cell_id": row["cell_id"],
                "candidate_index": row["candidate_index"],
            }
        )
    write_jsonl(output_dir / "private_mappings/generation_judge_map.jsonl", blind_map)

    def judge_task(task: dict[str, Any]) -> dict[str, Any]:
        blind_id = task["blind_id"]
        result_path = output_dir / f"generation/judgment/results/{judge_effort}/{blind_id}.json"
        if result_path.exists():
            return _json(result_path)
        evidence = output_dir / f"generation/judgment/evidence/{judge_effort}/{blind_id}"
        started = time.monotonic()
        judgment = None
        accepted = False
        error = None
        try:
            accepted_rows, judgment_rows = validate_items(
                [task["candidate"]],
                cells,
                prompt,
                criteria,
                model="gpt-5.6-terra",
                reasoning_effort=judge_effort,
                model_call=audited_model_call,
                evidence_dir=evidence,
            )
            judgment = judgment_rows[0]
            accepted = bool(accepted_rows)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        row = {
            "blind_id": blind_id,
            "experiment_item_id": task["source"]["experiment_item_id"],
            "generation_effort": task["source"]["effort"],
            "cell_id": task["source"]["cell_id"],
            "candidate_index": task["source"]["candidate_index"],
            "judge_effort": judge_effort,
            "success": error is None,
            "error": error,
            "accepted": accepted,
            "judgment": judgment,
            "task_runtime_seconds": time.monotonic() - started,
            **_call_totals(evidence),
        }
        write_json(result_path, row)
        return row

    judgments = _parallel(tasks, judge_task, workers, "generation judgment")
    write_jsonl(output_dir / "generation/judgment/results.jsonl", judgments)


def _percentile(values: list[float], percentile: float) -> float | None:
    return float(np.percentile(values, percentile)) if values else None


def _agreement(left: list[bool], right: list[bool]) -> float | None:
    return sum(a == b for a, b in zip(left, right)) / len(left) if left else None


def analyze(output_dir: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "experiment_id": "BACKEND-THINKING-001",
        "analysis_date": date.today().isoformat(),
        "claim_boundary": (
            "Automated structural, agreement, retained-reference, efficiency, and "
            "fixed-judge summaries. Blinded reviewer adjudication is merged separately."
        ),
    }
    normalisation = {}
    phase1_path = output_dir / "normalisation/phase1/results.jsonl"
    phase2_path = output_dir / "normalisation/phase2/results.jsonl"
    if phase1_path.exists() and phase2_path.exists():
        phase1 = read_jsonl(phase1_path)
        phase2 = read_jsonl(phase2_path)
        historical_phase1 = {
            row["source_id"]: row["fixed_phase1_mapping"]
            for row in read_jsonl(output_dir / "cohorts/normalisation_phase2.jsonl")
        }
        for effort in EFFORTS:
            p1 = [row for row in phase1 if row["effort"] == effort]
            p2 = [row for row in phase2 if row["effort"] == effort]
            p1_pairs = [
                (
                    next(r for r in p1 if r["source_id"] == source_id and r["replicate"] == 1),
                    next(r for r in p1 if r["source_id"] == source_id and r["replicate"] == 2),
                )
                for source_id in sorted({row["source_id"] for row in p1})
            ]
            p1_successful_pairs = [
                pair for pair in p1_pairs if pair[0]["success"] and pair[1]["success"]
            ]
            p2_pairs = [
                (
                    next(r for r in p2 if r["source_id"] == source_id and r["replicate"] == 1),
                    next(r for r in p2 if r["source_id"] == source_id and r["replicate"] == 2),
                )
                for source_id in sorted({row["source_id"] for row in p2})
            ]
            p2_successful_pairs = [
                pair for pair in p2_pairs if pair[0]["success"] and pair[1]["success"]
            ]
            normalisation[effort] = {
                "phase1_calls": len(p1),
                "phase1_contract_success": sum(row["success"] for row in p1),
                "phase1_historical_status_agreement_drift_only": sum(
                    row["success"]
                    and row["mapping"]["result"]
                    == historical_phase1.get(row["source_id"], row["retained_mapping"])["result"]
                    for row in p1
                ),
                "phase1_historical_structure_agreement_drift_only": sum(
                    row["success"]
                    and _mapping_signature(row["mapping"])
                    == _mapping_signature(
                        historical_phase1.get(row["source_id"], row["retained_mapping"])
                    )
                    for row in p1
                ),
                "phase1_repeat_successful_pairs": len(p1_successful_pairs),
                "phase1_repeat_structural_agreement": sum(
                    _mapping_signature(left["mapping"])
                    == _mapping_signature(right["mapping"])
                    for left, right in p1_successful_pairs
                ),
                "phase2_calls": len(p2),
                "phase2_contract_and_transition_success": sum(row["success"] for row in p2),
                "phase2_retained_status_agreement_drift_only": sum(
                    row["success"] and row["mapping"]["result"] == row["retained_phase2_mapping"]["result"]
                    for row in p2
                ),
                "phase2_repeat_successful_pairs": len(p2_successful_pairs),
                "phase2_repeat_structural_agreement": sum(
                    _mapping_signature(left["mapping"])
                    == _mapping_signature(right["mapping"])
                    for left, right in p2_successful_pairs
                ),
                "total_tokens": sum(row["tokens_used"] for row in [*p1, *p2]),
                "median_call_seconds": _percentile([row["model_runtime_seconds"] for row in [*p1, *p2]], 50),
                "p90_call_seconds": _percentile([row["model_runtime_seconds"] for row in [*p1, *p2]], 90),
            }
        summary["normalisation"] = normalisation

    validation_path = output_dir / "validation/results.jsonl"
    if validation_path.exists():
        rows = read_jsonl(validation_path)
        validation = {}
        for effort in EFFORTS:
            subset = [row for row in rows if row["effort"] == effort]
            repeat_pairs = [
                (
                    next(r for r in subset if r["item_id"] == item_id and r["replicate"] == 1),
                    next(r for r in subset if r["item_id"] == item_id and r["replicate"] == 2),
                )
                for item_id in sorted({row["item_id"] for row in subset})
            ]
            successful_pairs = [
                pair for pair in repeat_pairs if pair[0]["success"] and pair[1]["success"]
            ]
            validation[effort] = {
                "calls": len(subset),
                "valid_outputs": sum(row["success"] for row in subset),
                "retained_accept_agreement_drift_only": sum(
                    row["success"] and row["accepted"] == row["retained_accepted"] for row in subset
                ),
                "accepted": sum(row["accepted"] for row in subset),
                "adversarial_safety_calls": sum(row["adversarial_safety"] for row in subset),
                "adversarial_safety_false_accepts": sum(
                    row["success"] and row["adversarial_safety"] and row["accepted"]
                    for row in subset
                ),
                "repeat_successful_pairs": len(successful_pairs),
                "repeat_accept_agreement": sum(
                    left["accepted"] == right["accepted"]
                    for left, right in successful_pairs
                ),
                "total_tokens": sum(row["tokens_used"] for row in subset),
                "median_call_seconds": _percentile([row["model_runtime_seconds"] for row in subset], 50),
                "p90_call_seconds": _percentile([row["model_runtime_seconds"] for row in subset], 90),
            }
        pairwise = {}
        for left_index, left in enumerate(EFFORTS):
            for right in EFFORTS[left_index + 1 :]:
                left_map = {(row["item_id"], row["replicate"]): row for row in rows if row["effort"] == left and row["success"]}
                right_map = {(row["item_id"], row["replicate"]): row for row in rows if row["effort"] == right and row["success"]}
                keys = sorted(set(left_map) & set(right_map))
                pairwise[f"{left}_vs_{right}"] = {
                    "n": len(keys),
                    "accept_agreement": _agreement(
                        [left_map[key]["accepted"] for key in keys],
                        [right_map[key]["accepted"] for key in keys],
                    ),
                }
        summary["validation"] = validation
        summary["validation_pairwise"] = pairwise

    generation_path = output_dir / "generation/results.jsonl"
    judgment_path = output_dir / "generation/judgment/results.jsonl"
    if generation_path.exists():
        generated = read_jsonl(generation_path)
        judgments = read_jsonl(judgment_path) if judgment_path.exists() else []
        judgment_by_id = {row["experiment_item_id"]: row for row in judgments}
        generation = {}
        for effort in EFFORTS:
            subset = [row for row in generated if row["effort"] == effort]
            accepted = [
                judgment_by_id[row["experiment_item_id"]]["accepted"]
                for row in subset
                if row["experiment_item_id"] in judgment_by_id
                and judgment_by_id[row["experiment_item_id"]]["success"]
            ]
            cells_covered = {
                row["cell_id"]
                for row in subset
                if row["experiment_item_id"] in judgment_by_id
                and judgment_by_id[row["experiment_item_id"]]["success"]
                and judgment_by_id[row["experiment_item_id"]]["accepted"]
            }
            generation[effort] = {
                "calls": len(subset),
                "valid_payloads": sum(row["success"] for row in subset),
                "answer_span_passes": sum(row["answer_span_passed"] is not False for row in subset if row["success"]),
                "fixed_judge_successes": len(accepted),
                "fixed_judge_failures": sum(
                    row["experiment_item_id"] in judgment_by_id
                    and not judgment_by_id[row["experiment_item_id"]]["success"]
                    for row in subset
                ),
                "fixed_judge_accepts": sum(accepted),
                "fixed_judge_acceptance_rate_among_successful": (
                    sum(accepted) / len(accepted) if accepted else None
                ),
                "N3_cell_coverage": len(cells_covered),
                "total_generation_tokens": sum(row["tokens_used"] for row in subset),
                "median_generation_seconds": _percentile([row["model_runtime_seconds"] for row in subset], 50),
                "p90_generation_seconds": _percentile([row["model_runtime_seconds"] for row in subset], 90),
            }
        summary["generation"] = generation
        if judgments:
            summary["generation_judge"] = {
                "effort": judgments[0]["judge_effort"],
                "calls": len(judgments),
                "valid_outputs": sum(row["success"] for row in judgments),
                "total_tokens": sum(row["tokens_used"] for row in judgments),
                "median_seconds": _percentile([row["model_runtime_seconds"] for row in judgments], 50),
            }
    write_json(output_dir / "automated_summary.json", summary)
    return summary


def _record_command(output_dir: Path) -> None:
    manifest = _json(output_dir / "manifest.json")
    command = " ".join([sys.executable, *sys.argv])
    commands = manifest.setdefault("exact_commands", [])
    if command not in commands:
        commands.append(command)
    write_json(output_dir / "manifest.json", manifest)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        choices=("prepare", "normalisation", "validation", "generation", "analyze"),
        required=True,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--judge-effort", choices=EFFORTS)
    args = parser.parse_args()
    if args.stage not in {"prepare", "analyze"} and shutil.which("codex") is None:
        parser.error("codex CLI is required for live model calls")
    if args.stage != "generation" and args.judge_effort is not None:
        parser.error("--judge-effort is only valid with --stage generation")
    return args


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    manifest_path = output_dir / "manifest.json"
    if args.stage == "prepare" or not manifest_path.exists():
        prepare(output_dir)
    _record_command(output_dir)
    if args.stage == "normalisation":
        run_normalisation(output_dir, args.workers)
    elif args.stage == "validation":
        run_validation(output_dir, args.workers)
    elif args.stage == "generation":
        run_generation(output_dir, args.workers, args.judge_effort)
    elif args.stage == "analyze":
        print(json.dumps(analyze(output_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
