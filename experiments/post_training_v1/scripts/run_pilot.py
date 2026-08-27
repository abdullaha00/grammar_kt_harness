#!/usr/bin/env python3
"""Collect and evaluate active-pipeline generation supervision.

The script deliberately orchestrates public active module functions rather
than copying generation or validation logic. Every sampling unit has its own
evidence directory and resumable result record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import subprocess
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import FeatureUnion

from grammar_kt.folds import assignment_for_cells, load_fold
from grammar_kt.generation.generators import generate_items
from grammar_kt.generation.validation import validate_items
from grammar_kt.io import ROOT, read_json, read_jsonl, read_yaml, sha256_file, utc_now, write_json, write_jsonl
from grammar_kt.measurement.opportunities import build_measurement_opportunities, opportunity_bank_fingerprint


HERE = ROOT / "experiments" / "post_training_v1"
DEFAULT_CONFIG = HERE / "configs" / "pilot_v1.json"
DATA = HERE / "data" / "pilot_v1"
RESULTS = HERE / "results" / "pilot_v1"
TOKEN_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


def _json_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _git_state() -> dict[str, Any]:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True))
    return {"commit_sha": commit, "dirty": dirty}


def _format_for(opportunity_id: str, config: dict[str, Any]) -> str:
    value = int(hashlib.sha256(f"{config['seed']}:{opportunity_id}".encode()).hexdigest(), 16)
    return (
        "dialogue"
        if value % int(config["dialogue_hash_modulus"]) == int(config["dialogue_hash_remainder"])
        else "standalone"
    )


def _selection_key(row: dict[str, Any]) -> tuple[Any, ...]:
    conditions = row["structural_conditions"]
    subtype = conditions["imperative_subtype"]
    return (
        conditions["predicate_class"] != "lexical_transitive",
        not (conditions["subject_person"] == 3 and conditions["subject_number"] == "singular"),
        conditions["wh_role"] is not None,
        subtype not in {None, "ordinary"},
        row["measurement_opportunity_id"],
    )


def prepare(config: dict[str, Any]) -> None:
    cells = read_jsonl(ROOT / config["canonical_cells"])
    all_opportunities = build_measurement_opportunities(cells)
    by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in all_opportunities:
        by_cell[row["canonical_cell_id"]].append(row)
    selected: list[dict[str, Any]] = []
    limit = int(config["max_opportunities_per_cell"])
    for cell_id in sorted(by_cell):
        selected.extend(sorted(by_cell[cell_id], key=_selection_key)[:limit])
    assignments = assignment_for_cells(cells, load_fold(config["fold_manifest"]))
    enriched = []
    for row in selected:
        canonical_split = assignments[row["canonical_cell_id"]]
        enriched.append(
            {
                **row,
                "post_training_split": "train" if canonical_split == "development" else "test",
                "canonical_split": canonical_split,
                "item_format": _format_for(row["measurement_opportunity_id"], config),
            }
        )
    DATA.mkdir(parents=True, exist_ok=True)
    write_jsonl(DATA / "opportunities.jsonl", enriched, sort_keys=False)
    write_json(
        DATA / "manifest.json",
        {
            "experiment_id": config["experiment_id"],
            "prepared_utc": utc_now(),
            "pre_candidate_selection": True,
            "selection_rule": "up to two per canonical cell by preregistered structural priority",
            "split_policy": "frozen reference_v0 canonical-cell split",
            "format_policy": "SHA-256(seed, opportunity_id) modulo configured modulus",
            "config_sha256": sha256_file(DEFAULT_CONFIG),
            "source_canonical_sha256": sha256_file(ROOT / config["canonical_cells"]),
            "all_opportunity_bank_sha256": opportunity_bank_fingerprint(all_opportunities),
            "selected_opportunity_bank_sha256": opportunity_bank_fingerprint(
                [{k: v for k, v in row.items() if k not in {"post_training_split", "canonical_split", "item_format"}} for row in enriched]
            ),
            "counts": {
                "canonical_cells": len(cells),
                "all_opportunities": len(all_opportunities),
                "selected_opportunities": len(enriched),
                "train_opportunities": sum(row["post_training_split"] == "train" for row in enriched),
                "test_opportunities": sum(row["post_training_split"] == "test" for row in enriched),
                "standalone_opportunities": sum(row["item_format"] == "standalone" for row in enriched),
                "dialogue_opportunities": sum(row["item_format"] == "dialogue" for row in enriched),
            },
            "git": _git_state(),
        },
    )
    print(json.dumps(read_json(DATA / "manifest.json"), indent=2, sort_keys=True))


def _intrinsic_opportunity(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row[key]
        for key in (
            "measurement_opportunity_id",
            "canonical_cell_id",
            "cell",
            "structural_conditions",
            "expected_operations",
            "source_descriptor_ids",
            "coverage_reasons",
        )
    }


def _attempt_id(opportunity_id: str, sample_index: int, item_format: str, revision: int) -> str:
    digest = hashlib.sha256(f"active_post_training_v1:r{revision}:{opportunity_id}:{sample_index}:{item_format}".encode()).hexdigest()[:16].upper()
    return f"ATTEMPT_{digest}"


def _run_attempt(row: dict[str, Any], sample_index: int, config: dict[str, Any]) -> dict[str, Any]:
    opportunity = _intrinsic_opportunity(row)
    revision = int(config.get("collection_revision", 1))
    attempt_id = _attempt_id(row["measurement_opportunity_id"], sample_index, row["item_format"], revision)
    unit_result = DATA / "attempt_records" / f"{attempt_id}.json"
    if unit_result.is_file():
        return read_json(unit_result)
    item_format = row["item_format"]
    generator_path = ROOT / "modules" / "generation" / "generators" / f"llm_{item_format}_v0.yaml"
    generator = read_yaml(generator_path)
    generator["backend_config"] = config["generator_backend"]
    generator["max_attempts"] = 1
    generation_root = DATA / "evidence" / "generation" / attempt_id
    started = time.monotonic()
    generated = generate_items([opportunity], generator, evidence_root=generation_root)
    base = {
        "attempt_id": attempt_id,
        "sample_index": sample_index,
        "collection_revision": revision,
        "measurement_opportunity_id": row["measurement_opportunity_id"],
        "canonical_cell_id": row["canonical_cell_id"],
        "canonical_split": row["canonical_split"],
        "post_training_split": row["post_training_split"],
        "item_format": item_format,
        "generation_evidence": str(generation_root.relative_to(ROOT)),
        "generation_model": config["generator_backend"]["model"],
        "validator_model": config["validator_backend"]["model"],
    }
    if not generated["candidates"]:
        result = {
            **base,
            "status": "generation_failure",
            "generation_rejection": generated["rejections"][0],
            "candidate": None,
            "structurally_valid": False,
            "validation_reasons": [],
            "runtime_seconds": time.monotonic() - started,
        }
    else:
        candidate = generated["candidates"][0]
        validator = {
            "evaluator_id": "blind_reconstruction_v0",
            "structural_backend_config": config["validator_backend"],
            "quality_backend_config": config["validator_backend"],
            "known_generators": ["llm_standalone_v0", "llm_dialogue_v0"],
            "max_attempts": 1,
            "repeat_first_n": 0,
        }
        validation_root = DATA / "evidence" / "validation" / attempt_id
        validated = validate_items([candidate], [opportunity], validator, evidence_root=validation_root)
        if validated["accepted"]:
            final_candidate = validated["accepted"][0]
            reasons: list[str] = []
            accepted = True
        else:
            rejected = validated["rejected"][0]
            final_candidate = rejected["item"]
            reasons = rejected["reasons"]
            accepted = False
        result = {
            **base,
            "status": "validated",
            "candidate": final_candidate,
            "structurally_valid": accepted,
            "validation_reasons": reasons,
            "validation_report": validated["report"],
            "validation_evidence": str(validation_root.relative_to(ROOT)),
            "runtime_seconds": time.monotonic() - started,
        }
    unit_result.parent.mkdir(parents=True, exist_ok=True)
    write_json(unit_result, result)
    return result


def collect(config: dict[str, Any]) -> None:
    if not (DATA / "opportunities.jsonl").is_file():
        raise RuntimeError("run prepare before collect")
    opportunities = read_jsonl(DATA / "opportunities.jsonl")
    jobs = [
        (row, sample_index)
        for row in opportunities
        for sample_index in range(1, int(config["samples_per_opportunity"]) + 1)
    ]
    results = []
    with ThreadPoolExecutor(max_workers=int(config["workers"])) as pool:
        futures = {pool.submit(_run_attempt, row, sample, config): (row, sample) for row, sample in jobs}
        for number, future in enumerate(as_completed(futures), 1):
            row, sample = futures[future]
            result = future.result()
            results.append(result)
            print(
                f"[{number}/{len(jobs)}] {row['measurement_opportunity_id']} "
                f"sample={sample} status={result['status']} valid={result['structurally_valid']}",
                flush=True,
            )
    results.sort(key=lambda x: (x["measurement_opportunity_id"], x["sample_index"]))
    write_jsonl(DATA / "candidate_attempts.jsonl", results, sort_keys=False)
    write_json(
        DATA / "collection_manifest.json",
        {
            "experiment_id": config["experiment_id"],
            "collected_utc": utc_now(),
            "attempts": len(results),
            "generation_failures": sum(row["status"] == "generation_failure" for row in results),
            "schema_valid_candidates": sum(row["candidate"] is not None for row in results),
            "structurally_valid": sum(row["structurally_valid"] for row in results),
            "total_runtime_seconds_sum": sum(row["runtime_seconds"] for row in results),
            "config": config,
            "git": _git_state(),
            "exact_command": "PYTHONPATH=src .venv/bin/python experiments/post_training_v1/scripts/run_pilot.py collect",
            "cost_information": "Codex research backend exposes no monetary/token cost in invocation metadata; wall-clock runtime is retained per attempt.",
        },
    )


def _revalidate_attempt(row: dict[str, Any], opportunity: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    if row["candidate"] is None:
        return row
    if row["measurement_opportunity_id"] in set(config.get("excluded_opportunity_ids", [])):
        return {**row, "scientifically_excluded": True}
    revision = int(config.get("validation_revision", 2))
    unit_result = DATA / f"revalidation_records_v{revision}" / f"{row['attempt_id']}.json"
    if unit_result.is_file():
        return read_json(unit_result)
    validator = {
        "evaluator_id": f"blind_reconstruction_v0_closed_ontology_v{revision}",
        "structural_backend_config": config["validator_backend"],
        "quality_backend_config": config["validator_backend"],
        "known_generators": ["llm_standalone_v0", "llm_dialogue_v0"],
        "max_attempts": 1,
        "repeat_first_n": 0,
    }
    validation_root = DATA / "evidence" / f"validation_v{revision}" / row["attempt_id"]
    validated = validate_items([row["candidate"]], [_intrinsic_opportunity(opportunity)], validator, evidence_root=validation_root)
    if validated["accepted"]:
        candidate = validated["accepted"][0]
        reasons: list[str] = []
        accepted = True
    else:
        rejected = validated["rejected"][0]
        candidate = rejected["item"]
        reasons = rejected["reasons"]
        accepted = False
    result = {
        **row,
        "candidate": candidate,
        "structurally_valid": accepted,
        "validation_reasons": reasons,
        "validation_report": validated["report"],
        "previous_validation_evidence": row.get("validation_evidence"),
        "validation_evidence": str(validation_root.relative_to(ROOT)),
        "validation_revision": revision,
    }
    unit_result.parent.mkdir(parents=True, exist_ok=True)
    write_json(unit_result, result)
    return result


def revalidate(config: dict[str, Any]) -> None:
    attempts = read_jsonl(DATA / "candidate_attempts.jsonl")
    opportunities = {row["measurement_opportunity_id"]: row for row in read_jsonl(DATA / "opportunities.jsonl")}
    revision = int(config.get("validation_revision", 2))
    old_path = DATA / f"candidate_attempts_validation_v{revision-1}_before_revision_{revision}.jsonl"
    if not old_path.exists():
        write_jsonl(old_path, attempts, sort_keys=False)
    results = []
    with ThreadPoolExecutor(max_workers=int(config["workers"])) as pool:
        futures = {
            pool.submit(_revalidate_attempt, row, opportunities[row["measurement_opportunity_id"]], config): row
            for row in attempts
        }
        for number, future in enumerate(as_completed(futures), 1):
            result = future.result()
            results.append(result)
            print(f"[{number}/{len(attempts)}] {result['attempt_id']} valid={result['structurally_valid']}", flush=True)
    results.sort(key=lambda x: (x["measurement_opportunity_id"], x["sample_index"]))
    write_jsonl(DATA / "candidate_attempts.jsonl", results, sort_keys=False)
    write_json(
        DATA / f"revalidation_manifest_v{revision}.json",
        {
            "revalidated_utc": utc_now(),
            "candidates": sum(row["candidate"] is not None for row in results),
            "accepted": sum(row["structurally_valid"] for row in results),
            "validation_revision": revision,
            "reason": "closed operation labels plus explicit canonical tense/agreement conventions",
            "intended_target_still_hidden": True,
            "original_judgments_retained": str(old_path.relative_to(ROOT)),
            "exact_command": "PYTHONPATH=src .venv/bin/python experiments/post_training_v1/scripts/run_pilot.py revalidate",
        },
    )


def _quality_pass(candidate: dict[str, Any]) -> bool:
    q = candidate.get("quality_diagnostics", {})
    return bool(q) and q.get("naturalness", 0) >= 3 and q.get("pedagogical_suitability", 0) >= 3 and not q.get("answer_ambiguity", True)


def _taxonomy(row: dict[str, Any]) -> tuple[str, list[str]]:
    if row["status"] == "generation_failure" or row["candidate"] is None:
        return "F_format_or_API_failure", ["generation_failure"]
    candidate = row["candidate"]
    reasons = row["validation_reasons"]
    dimensions = sorted(
        {
            match.group(1)
            for reason in reasons
            if (match := re.search(r"blind reconstruction ([a-z_]+)_mismatch", reason))
        }
    )
    quality = candidate.get("quality_diagnostics", {})
    if row["structurally_valid"]:
        return ("A_valid_target_realization" if _quality_pass(candidate) else "E_quality_failure"), dimensions
    if not candidate.get("validated_structure"):
        return "F_format_or_API_failure", dimensions
    if quality.get("answer_ambiguity"):
        return "C_ambiguous_measurement", dimensions
    if "cell" in dimensions and quality.get("naturalness", 0) >= 3:
        return "B_fluent_wrong_target", dimensions
    return "D_structurally_unsupported", dimensions


def _candidate_text(candidate: dict[str, Any]) -> str:
    return json.dumps(
        {"content": candidate["content"], "target_answer": candidate["target_answer"], "accepted_answers": candidate["accepted_answers"]},
        ensure_ascii=False,
        sort_keys=True,
    )


def _candidate_view(row: dict[str, Any]) -> dict[str, Any]:
    candidate = row["candidate"]
    return {
        "attempt_id": row["attempt_id"],
        "item_id": candidate["item_id"],
        "item_family": candidate["item_family"],
        "content": candidate["content"],
        "target_answer": candidate["target_answer"],
        "accepted_answers": candidate["accepted_answers"],
    }


def _provenance(row: dict[str, Any]) -> dict[str, Any]:
    candidate = row["candidate"]
    return {
        "attempt_id": row["attempt_id"],
        "item_id": candidate["item_id"],
        "canonical_cell_id": row["canonical_cell_id"],
        "canonical_split": row["canonical_split"],
        "post_training_split": row["post_training_split"],
        "sample_index": row["sample_index"],
        "generation_model": row["generation_model"],
        "validator_model": row["validator_model"],
        "generation_evidence": row["generation_evidence"],
        "validation_evidence": row.get("validation_evidence"),
    }


def _validation_view(row: dict[str, Any], category: str, dimensions: list[str]) -> dict[str, Any]:
    candidate = row["candidate"]
    return {
        "structurally_valid": row["structurally_valid"],
        "taxonomy": category,
        "mismatch_dimensions": dimensions,
        "reasons": row["validation_reasons"],
        "blind_reconstruction": candidate["validated_structure"],
        "quality_diagnostics": candidate["quality_diagnostics"],
    }


def _usage_summary(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    roots = [
        DATA / "evidence" / "generation" / row["attempt_id"]
        for row in attempts
    ] + [
        DATA / "evidence" / "validation_v3" / row["attempt_id"]
        for row in attempts
        if row["candidate"] is not None and not row.get("scientifically_excluded")
    ]
    usage: Counter[str] = Counter()
    invocations = 0
    invocation_wall_seconds = 0.0
    for root in roots:
        if not root.is_dir():
            continue
        for invocation in root.rglob("invocation.json"):
            metadata = read_json(invocation)
            invocations += 1
            try:
                from datetime import datetime
                invocation_wall_seconds += (
                    datetime.fromisoformat(metadata["finished_utc"])
                    - datetime.fromisoformat(metadata["started_utc"])
                ).total_seconds()
            except (KeyError, TypeError, ValueError):
                pass
            events = invocation.with_name("events.jsonl")
            if not events.is_file():
                continue
            for line in events.read_text(encoding="utf-8").splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for key, value in event.get("usage", {}).items():
                    if isinstance(value, int):
                        usage[key] += value
    return {
        "invocations": invocations,
        "summed_invocation_wall_seconds": invocation_wall_seconds,
        "reported_token_usage": dict(sorted(usage.items())),
        "monetary_cost": None,
        "cost_note": "The Codex research backend records token usage but exposes no monetary charge schedule for these invocations.",
    }


def analyse(config: dict[str, Any]) -> None:
    attempts = read_jsonl(DATA / "candidate_attempts.jsonl")
    excluded_opportunity_ids = set(config.get("excluded_opportunity_ids", []))
    opportunities = {row["measurement_opportunity_id"]: row for row in read_jsonl(DATA / "opportunities.jsonl")}
    categories: Counter[str] = Counter()
    eligible_categories: Counter[str] = Counter()
    mismatch_dimensions: Counter[str] = Counter()
    annotated: dict[str, tuple[str, list[str]]] = {}
    verifier = []
    for row in attempts:
        category, dimensions = _taxonomy(row)
        annotated[row["attempt_id"]] = (category, dimensions)
        categories[category] += 1
        if row["measurement_opportunity_id"] in excluded_opportunity_ids:
            continue
        eligible_categories[category] += 1
        if category in {"B_fluent_wrong_target", "C_ambiguous_measurement", "D_structurally_unsupported"}:
            mismatch_dimensions.update(dimensions)
        if row["candidate"] is None or not row["candidate"].get("validated_structure"):
            continue
        context = _intrinsic_opportunity(opportunities[row["measurement_opportunity_id"]])
        verifier.append(
            {
                "record_type": "generation_verifier",
                "context": {"measurement_opportunity": context},
                "candidate": _candidate_view(row),
                "labels": _validation_view(row, category, dimensions),
                "provenance": _provenance(row),
            }
        )
    by_opportunity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in attempts:
        by_opportunity[row["measurement_opportunity_id"]].append(row)
    preferences = []
    possible_pairs = 0
    for opportunity_id, rows in sorted(by_opportunity.items()):
        if opportunity_id in excluded_opportunity_ids:
            continue
        chosen = [row for row in rows if row["candidate"] is not None and row["structurally_valid"] and _quality_pass(row["candidate"])]
        rejected = [
            row for row in rows
            if row["candidate"] is not None
            and not row["structurally_valid"]
            and annotated[row["attempt_id"]][0] in {"B_fluent_wrong_target", "C_ambiguous_measurement", "D_structurally_unsupported"}
            and row["candidate"].get("validated_structure")
            and row["candidate"].get("quality_diagnostics", {}).get("naturalness", 0) >= 3
        ]
        possible_pairs += sum(
            1 for left in rows for right in rows
            if left["structurally_valid"]
            and right["candidate"] is not None
            and right["candidate"].get("validated_structure")
            and not right["structurally_valid"]
        )
        context = _intrinsic_opportunity(opportunities[opportunity_id])
        for good in chosen:
            for bad in rejected:
                category, dimensions = annotated[bad["attempt_id"]]
                preferences.append(
                    {
                        "record_type": "generation_preference",
                        "context": {"measurement_opportunity": context},
                        "chosen": _candidate_view(good),
                        "rejected": _candidate_view(bad),
                        "preference": {
                            "reason": "chosen preserves the fixed measurement target; rejected is a plausible structural near miss",
                            "rejected_taxonomy": category,
                            "structural_dimensions": {dimension: "mismatch" for dimension in dimensions},
                            "label_source": "active blind structural reconstruction",
                        },
                        "validation": {
                            "chosen": _validation_view(good, *annotated[good["attempt_id"]]),
                            "rejected": _validation_view(bad, category, dimensions),
                        },
                        "provenance": {
                            "chosen": _provenance(good),
                            "rejected": _provenance(bad),
                            "split_unit": good["canonical_cell_id"],
                            "post_training_split": good["post_training_split"],
                        },
                    }
                )
    write_jsonl(DATA / "generation_verifier.jsonl", verifier, sort_keys=False)
    write_jsonl(DATA / "generation_preference.jsonl", preferences, sort_keys=False)
    surface_counts = Counter(_candidate_text(row["candidate"]) for row in attempts if row["candidate"] is not None)
    tokens = [token.lower() for row in attempts if row["candidate"] is not None for token in TOKEN_RE.findall(_candidate_text(row["candidate"]))]
    bigrams = list(zip(tokens, tokens[1:]))
    mixed = [
        opportunity_id for opportunity_id, rows in by_opportunity.items()
        if any(row["structurally_valid"] for row in rows) and any(not row["structurally_valid"] for row in rows)
    ]
    educational_mixed = [
        opportunity_id for opportunity_id, rows in by_opportunity.items()
        if opportunity_id not in excluded_opportunity_ids
        and any(row["structurally_valid"] for row in rows)
        and any(
            row["candidate"] is not None
            and row["candidate"].get("validated_structure")
            and not row["structurally_valid"]
            for row in rows
        )
    ]
    eligible_attempts = [row for row in attempts if row["measurement_opportunity_id"] not in excluded_opportunity_ids]
    feature_coverage = {
        field: dict(sorted(Counter(opportunities[row["measurement_opportunity_id"]]["cell"][field] for row in attempts).items()))
        for field in ("tense", "aspect", "voice", "polarity", "clause", "modal")
    }
    summary = {
        "experiment_id": config["experiment_id"],
        "counts": {
            "measurement_opportunities": len(by_opportunity),
            "generated_attempts": len(attempts),
            "schema_valid_candidates": sum(row["candidate"] is not None for row in attempts),
            "accepted": sum(row["structurally_valid"] for row in attempts),
            "rejected": sum(not row["structurally_valid"] for row in attempts),
            "generation_failures": sum(row["status"] == "generation_failure" for row in attempts),
            "mixed_validity_opportunities": len(mixed),
            "mixed_educational_validity_opportunities": len(educational_mixed),
            "possible_accepted_rejected_pairs": possible_pairs,
            "eligible_nontrivial_preference_pairs": len(preferences),
            "verifier_records": len(verifier),
            "excluded_measurement_opportunities": len(excluded_opportunity_ids),
            "excluded_candidate_attempts": sum(row["measurement_opportunity_id"] in excluded_opportunity_ids for row in attempts),
            "exact_duplicate_candidate_instances": sum(value - 1 for value in surface_counts.values() if value > 1),
            "unique_candidate_surfaces": len(surface_counts),
        },
        "acceptance_rate": sum(row["structurally_valid"] for row in attempts) / len(attempts),
        "release_eligible_acceptance_rate_all_attempts": sum(row["structurally_valid"] for row in eligible_attempts) / len(eligible_attempts),
        "release_eligible_structural_acceptance_rate_schema_valid": (
            sum(row["structurally_valid"] for row in eligible_attempts)
            / sum(row["candidate"] is not None for row in eligible_attempts)
        ),
        "raw_taxonomy": dict(sorted(categories.items())),
        "release_eligible_taxonomy": dict(sorted(eligible_categories.items())),
        "rejection_dimensions": dict(sorted(mismatch_dimensions.items())),
        "formats": {
            key: {
                "attempts": len(rows),
                "accepted": sum(row["structurally_valid"] for row in rows),
                "acceptance_rate": sum(row["structurally_valid"] for row in rows) / len(rows),
            }
            for key in ("standalone", "dialogue")
            if (rows := [row for row in attempts if row["item_format"] == key])
        },
        "splits": dict(sorted(Counter(row["post_training_split"] for row in attempts).items())),
        "canonical_splits": dict(sorted(Counter(row["canonical_split"] for row in attempts).items())),
        "feature_coverage": feature_coverage,
        "lexical_diversity": {
            "tokens": len(tokens),
            "types": len(set(tokens)),
            "type_token_ratio": len(set(tokens)) / len(tokens) if tokens else None,
            "bigrams": len(bigrams),
            "distinct_bigram_ratio": len(set(bigrams)) / len(bigrams) if bigrams else None,
        },
        "readiness_preregistered_automatic_gates": {
            "at_least_20_pairs": len(preferences) >= 20,
            "at_least_3_error_dimensions": len(mismatch_dimensions) >= 3,
            "at_least_10_mixed_opportunities": len(educational_mixed) >= 10,
            "manual_audit_pass": False,
        },
        "leakage_check": {
            "split_unit": "canonical_cell_id",
            "cell_overlap": sorted(
                {row["canonical_cell_id"] for row in attempts if row["post_training_split"] == "train"}
                & {row["canonical_cell_id"] for row in attempts if row["post_training_split"] == "test"}
            ),
            "opportunity_overlap": [],
            "policy": "all attempts and derived pairs inherit the frozen canonical-cell split",
        },
        "scientific_exclusions": {
            "measurement_opportunity_ids": sorted(excluded_opportunity_ids),
            "reason": "generation used the pre-fix erroneous lets_not do_support target; raw attempts remain retained but cannot support training/evaluation",
        },
        "model_usage": _usage_summary(attempts),
        "exact_command": "PYTHONPATH=src .venv/bin/python experiments/post_training_v1/scripts/run_pilot.py analyse",
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    write_json(RESULTS / "candidate_pool_summary.json", summary)
    audit_sample = []
    strata: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in preferences:
        strata[row["preference"]["rejected_taxonomy"]].append(row)
    rng = random.Random(int(config["seed"]))
    while len(audit_sample) < min(30, len(preferences)) and any(strata.values()):
        for key in sorted(strata):
            if strata[key] and len(audit_sample) < min(30, len(preferences)):
                picked = rng.randrange(len(strata[key]))
                row = strata[key].pop(picked)
                audit_sample.append(
                    {
                        "audit_id": f"AUDIT_{len(audit_sample)+1:03d}",
                        "context": row["context"],
                        "candidate_a": row["chosen"],
                        "candidate_b": row["rejected"],
                        "system_label_hidden_for_audit": True,
                        "author_judgment": {"preferred": None, "label_correct": None, "rejected_plausible": None, "note": ""},
                        "source_attempt_ids": [row["chosen"]["attempt_id"], row["rejected"]["attempt_id"]],
                    }
                )
    write_json(RESULTS / "manual_audit_sample.json", audit_sample)
    print(json.dumps(summary, indent=2, sort_keys=True))


def _context_tokens(opportunity: dict[str, Any], candidate_text: str) -> str:
    raw_tokens = [token.lower() for token in TOKEN_RE.findall(candidate_text)]
    features = [f"cell_{key}_{value}" for key, value in opportunity["cell"].items()]
    conditions = opportunity["structural_conditions"]
    features.extend(f"cond_{key}_{value}" for key, value in conditions.items())
    features.extend(f"op_{value}" for value in opportunity["expected_operations"] or ["none"])
    interactions = [f"{feature}__tok_{token}" for feature in features for token in raw_tokens]
    return " ".join(raw_tokens + features + interactions)


def _vectorizer() -> FeatureUnion:
    return FeatureUnion(
        [
            ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True, token_pattern=r"(?u)\b\S+\b")),
            ("char", TfidfVectorizer(analyzer="char", ngram_range=(3, 5), min_df=2, sublinear_tf=True, max_features=30000)),
        ]
    )


def _render_record(row: dict[str, Any], contextual: bool) -> str:
    text = _candidate_text(row["candidate"])
    opportunity = row["context"]["measurement_opportunity"]
    return _context_tokens(opportunity, text) if contextual else text


def _safe_auc(labels: Iterable[int], scores: Iterable[float]) -> float | None:
    labels = list(labels)
    return float(roc_auc_score(labels, list(scores))) if len(set(labels)) == 2 else None


def _fit_model(train: list[dict[str, Any]], contextual: bool, seed: int) -> tuple[Any, Any, float, list[dict[str, Any]]]:
    labels = np.asarray([int(row["labels"]["structurally_valid"]) for row in train])
    groups = np.asarray([row["provenance"]["canonical_cell_id"] for row in train])
    texts = [_render_record(row, contextual) for row in train]
    candidate_cs = [0.1, 1.0, 10.0]
    folds = min(5, len(set(groups)))
    cv_rows = []
    for c_value in candidate_cs:
        fold_scores = []
        for train_index, valid_index in GroupKFold(n_splits=folds).split(texts, labels, groups):
            if len(set(labels[train_index])) < 2:
                continue
            vectorizer = _vectorizer()
            x_train = vectorizer.fit_transform([texts[index] for index in train_index])
            classifier = LogisticRegression(C=c_value, class_weight="balanced", max_iter=2000, random_state=seed)
            classifier.fit(x_train, labels[train_index])
            predictions = classifier.predict(vectorizer.transform([texts[index] for index in valid_index]))
            fold_scores.append(float(balanced_accuracy_score(labels[valid_index], predictions)))
        cv_rows.append({"C": c_value, "fold_balanced_accuracy": fold_scores, "mean": float(np.mean(fold_scores)) if fold_scores else None})
    eligible = [row for row in cv_rows if row["mean"] is not None]
    selected_c = max(eligible, key=lambda row: (row["mean"], -row["C"]))["C"] if eligible else 1.0
    vectorizer = _vectorizer()
    matrix = vectorizer.fit_transform(texts)
    classifier = LogisticRegression(C=selected_c, class_weight="balanced", max_iter=2000, random_state=seed)
    classifier.fit(matrix, labels)
    return vectorizer, classifier, selected_c, cv_rows


def _bootstrap_difference(rows: list[dict[str, Any]], samples: int, seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    differences = []
    for _ in range(samples):
        draw = [rows[rng.randrange(len(rows))] for _ in rows]
        differences.append(float(np.mean([row["learned"] - row["first"] for row in draw])))
    return {
        "point_difference": float(np.mean([row["learned"] - row["first"] for row in rows])),
        "ci95": [float(np.quantile(differences, 0.025)), float(np.quantile(differences, 0.975))],
        "resamples": samples,
        "cluster_unit": "measurement_opportunity_id",
    }


def evaluate(config: dict[str, Any]) -> None:
    verifier = read_jsonl(DATA / "generation_verifier.jsonl")
    preferences = read_jsonl(DATA / "generation_preference.jsonl")
    train = [row for row in verifier if row["provenance"]["post_training_split"] == "train"]
    test = [row for row in verifier if row["provenance"]["post_training_split"] == "test"]
    if len({row["labels"]["structurally_valid"] for row in train}) < 2:
        result = {
            "experiment_id": config["experiment_id"],
            "hypothesis_frozen_before_collection": True,
            "status": "NOT_RUN_INSUFFICIENT_CLASS_VARIATION",
            "reason": "After ontology repair and the scientific exclusion, every export-eligible schema-valid candidate is structurally valid; no negative training or evaluation class remains.",
            "class_counts": {
                "train": dict(sorted(Counter(str(row["labels"]["structurally_valid"]) for row in train).items())),
                "test": dict(sorted(Counter(str(row["labels"]["structurally_valid"]) for row in test).items())),
            },
            "records": {"train": len(train), "test": len(test), "preferences": len(preferences)},
            "preregistered_decision_criteria": {
                "pairwise_accuracy_above_chance": False,
                "reranker_above_first": False,
                "reranker_above_random": False,
                "bootstrap_ci_excludes_zero": False,
            },
            "demonstrated_downstream_gain": False,
            "interpretation": "The pilot cannot test learned ranking utility. Adding generation/API failures as negatives would violate the protocol and create a trivial task.",
            "exact_command": "PYTHONPATH=src .venv/bin/python experiments/post_training_v1/scripts/run_pilot.py evaluate",
        }
        RESULTS.mkdir(parents=True, exist_ok=True)
        write_json(RESULTS / "utility_experiment.json", result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    model_results = {}
    scores_by_model: dict[str, dict[str, float]] = {}
    for name, contextual in (("candidate_only", False), ("context_plus_candidate", True)):
        vectorizer, classifier, selected_c, cv = _fit_model(train, contextual, int(config["seed"]))
        test_text = [_render_record(row, contextual) for row in test]
        scores = classifier.predict_proba(vectorizer.transform(test_text))[:, 1]
        predictions = (scores >= 0.5).astype(int)
        labels = np.asarray([int(row["labels"]["structurally_valid"]) for row in test])
        scores_by_model[name] = {row["candidate"]["attempt_id"]: float(score) for row, score in zip(test, scores)}
        model_results[name] = {
            "method": "word(1,2)+char(3,5) TF-IDF with balanced logistic regression",
            "context_interaction_features": contextual,
            "selected_C": selected_c,
            "development_group_cv": cv,
            "test": {
                "records": len(test),
                "accuracy": float(accuracy_score(labels, predictions)),
                "balanced_accuracy": float(balanced_accuracy_score(labels, predictions)),
                "auroc": _safe_auc(labels, scores),
                "brier": float(brier_score_loss(labels, scores)),
                "confusion_matrix_labels_0_1": confusion_matrix(labels, predictions, labels=[0, 1]).tolist(),
            },
        }
    test_preferences = [row for row in preferences if row["provenance"]["post_training_split"] == "test"]
    for name, score_map in scores_by_model.items():
        comparable = [row for row in test_preferences if row["chosen"]["attempt_id"] in score_map and row["rejected"]["attempt_id"] in score_map]
        wins = [score_map[row["chosen"]["attempt_id"]] > score_map[row["rejected"]["attempt_id"]] for row in comparable]
        ties = [score_map[row["chosen"]["attempt_id"]] == score_map[row["rejected"]["attempt_id"]] for row in comparable]
        model_results[name]["heldout_pairwise"] = {
            "pairs": len(comparable),
            "accuracy_strict": sum(wins) / len(wins) if wins else None,
            "ties": sum(ties),
        }
    by_opportunity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in test:
        by_opportunity[row["context"]["measurement_opportunity"]["measurement_opportunity_id"]].append(row)
    rng = random.Random(int(config["seed"]))
    opportunity_rows = []
    random_rates = []
    for opportunity_id, rows in sorted(by_opportunity.items()):
        rows.sort(key=lambda row: row["provenance"]["sample_index"])
        first = int(rows[0]["labels"]["structurally_valid"])
        learned_row = max(rows, key=lambda row: scores_by_model["context_plus_candidate"][row["candidate"]["attempt_id"]])
        candidate_only_row = max(rows, key=lambda row: scores_by_model["candidate_only"][row["candidate"]["attempt_id"]])
        quality_row = max(rows, key=lambda row: row["labels"]["quality_diagnostics"].get("naturalness", -1))
        opportunity_rows.append(
            {
                "measurement_opportunity_id": opportunity_id,
                "canonical_cell_id": rows[0]["provenance"]["canonical_cell_id"],
                "canonical_split": rows[0]["provenance"]["canonical_split"],
                "item_format": rows[0]["candidate"]["item_family"],
                "candidates": len(rows),
                "first": first,
                "random_expected": float(np.mean([int(row["labels"]["structurally_valid"]) for row in rows])),
                "naturalness_only": int(quality_row["labels"]["structurally_valid"]),
                "candidate_only": int(candidate_only_row["labels"]["structurally_valid"]),
                "learned": int(learned_row["labels"]["structurally_valid"]),
                "selected_attempt_id": learned_row["candidate"]["attempt_id"],
            }
        )
    for _ in range(int(config["random_choice_resamples"])):
        random_rates.append(float(np.mean([int(rng.choice(rows)["labels"]["structurally_valid"]) for rows in by_opportunity.values()])))
    rates = {
        "opportunities": len(opportunity_rows),
        "first_candidate": float(np.mean([row["first"] for row in opportunity_rows])),
        "random_choice_expected": float(np.mean([row["random_expected"] for row in opportunity_rows])),
        "random_choice_monte_carlo_ci95": [float(np.quantile(random_rates, 0.025)), float(np.quantile(random_rates, 0.975))],
        "naturalness_only": float(np.mean([row["naturalness_only"] for row in opportunity_rows])),
        "candidate_only_verifier": float(np.mean([row["candidate_only"] for row in opportunity_rows])),
        "grammar_kt_context_verifier": float(np.mean([row["learned"] for row in opportunity_rows])),
    }
    bootstrap = _bootstrap_difference(opportunity_rows, int(config["bootstrap_resamples"]), int(config["seed"]))
    pair_accuracy = model_results["context_plus_candidate"]["heldout_pairwise"]["accuracy_strict"]
    criteria = {
        "pairwise_accuracy_above_chance": pair_accuracy is not None and pair_accuracy > 0.5,
        "reranker_above_first": rates["grammar_kt_context_verifier"] > rates["first_candidate"],
        "reranker_above_random": rates["grammar_kt_context_verifier"] > rates["random_choice_expected"],
        "bootstrap_ci_excludes_zero": bootstrap["ci95"][0] > 0,
    }
    result = {
        "experiment_id": config["experiment_id"],
        "hypothesis_frozen_before_collection": True,
        "split": {
            "unit": "canonical_cell_id",
            "train_cells": sorted({row["provenance"]["canonical_cell_id"] for row in train}),
            "test_cells": sorted({row["provenance"]["canonical_cell_id"] for row in test}),
            "overlap": sorted(
                {row["provenance"]["canonical_cell_id"] for row in train}
                & {row["provenance"]["canonical_cell_id"] for row in test}
            ),
        },
        "models": model_results,
        "best_of_3": rates,
        "best_of_3_by_opportunity": opportunity_rows,
        "cluster_bootstrap_learned_minus_first": bootstrap,
        "preregistered_decision_criteria": criteria,
        "demonstrated_downstream_gain": all(criteria.values()),
        "exact_command": "PYTHONPATH=src .venv/bin/python experiments/post_training_v1/scripts/run_pilot.py evaluate",
        "runtime_note": "CPU-only scikit-learn model; collection runtime and model invocations are in data manifests/evidence.",
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    write_json(RESULTS / "utility_experiment.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("command", choices=("prepare", "collect", "revalidate", "analyse", "evaluate"))
    args = parser.parse_args()
    config = read_json(args.config)
    globals()[args.command](config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
