#!/usr/bin/env python3
"""Replay the retained 139-descriptor normalisation evidence offline.

The historical model outputs predate the explicit ``phase2_eligible`` field.
This script translates their machine-readable note prefix into that field for
audit only; it does not relabel or replace the retained raw evidence and makes
no model calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.io import read_jsonl, read_yaml, write_json, write_jsonl
from grammar_kt.normalise import _validate_mapping, _validate_phase2_transition


DEFAULT_RUN = ROOT / "runs/base_seed_20260820"
DEFAULT_OUTPUT = ROOT / "reports/phase4/artifacts/normalisation"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _legacy_eligibility(mapping: dict[str, Any], order: list[str]) -> list[str]:
    note = mapping.get("note") or ""
    prefix = "phase2 eligible: "
    if not note.startswith(prefix):
        return []
    declaration = note.removeprefix(prefix).split(";", 1)[0].strip()
    names = [] if declaration == "none" else declaration.split(",")
    selected = {name.strip() for name in names if name.strip()}
    return [name for name in order if name in selected]


def _adapt_legacy_mapping(
    mapping: dict[str, Any], order: list[str], *, inherited: list[str] | None = None
) -> dict[str, Any]:
    source_id = mapping.get("source_id", mapping.get("egp_id"))
    return {
        "source_id": source_id,
        "result": mapping["result"],
        "cells": mapping["cells"],
        "phase2_eligible": (
            inherited
            if inherited is not None
            else _legacy_eligibility(mapping, order)
        ),
        "note": mapping.get("note"),
    }


def _check(action: Callable[[], None]) -> dict[str, Any]:
    try:
        action()
    except (KeyError, TypeError, ValueError) as error:
        return {"passed": False, "error": str(error)}
    return {"passed": True, "error": None}


def _base_cell(**changes: Any) -> dict[str, Any]:
    return {
        "tense": "present",
        "aspect": "none",
        "voice": "active",
        "polarity": "positive",
        "clause": "declarative",
        "modal": "none",
    } | changes


def _mapping(cells: list[dict[str, Any]], result: str) -> dict[str, Any]:
    return {
        "source_id": "adversarial_control",
        "result": result,
        "cells": cells,
        "phase2_eligible": ["tense"],
        "note": "offline adversarial control",
    }


def _adversarial_controls(schema: dict[str, Any]) -> dict[str, Any]:
    one_branch = _mapping(
        [_base_cell(tense=["present", "past"])], "partial"
    )
    correlated = _mapping(
        [
            _base_cell(tense=["present", "past"]),
            _base_cell(
                tense=["present", "past"],
                voice="passive",
                polarity="negative",
            ),
        ],
        "partial",
    )
    cases = {
        "valid_narrowing": _mapping([_base_cell(tense="past")], "complete"),
        "changed_exact_field": _mapping(
            [_base_cell(tense="past", voice="passive")], "complete"
        ),
        "broadened_eligible_field": _mapping(
            [_base_cell(tense=None)], "partial"
        ),
        "cross_branch_recombination": _mapping(
            [
                _base_cell(tense="present", polarity="negative"),
                _base_cell(tense="past", voice="passive"),
            ],
            "complete",
        ),
        "dropped_branch": _mapping([_base_cell()], "complete"),
    }
    parents = {
        "valid_narrowing": one_branch,
        "changed_exact_field": one_branch,
        "broadened_eligible_field": one_branch,
        "cross_branch_recombination": correlated,
        "dropped_branch": correlated,
    }
    expected = {
        "valid_narrowing": True,
        "changed_exact_field": False,
        "broadened_eligible_field": False,
        "cross_branch_recombination": False,
        "dropped_branch": False,
    }
    results = []
    for case_id, second in cases.items():
        check = _check(
            lambda first=parents[case_id], final=second: (
                _validate_phase2_transition(first, final, schema)
            )
        )
        results.append(
            {
                "case_id": case_id,
                "expected_pass": expected[case_id],
                "observed_pass": check["passed"],
                "expectation_met": check["passed"] == expected[case_id],
                "error": check["error"],
            }
        )

    exact_but_eligible = _mapping(
        [_base_cell(polarity=None)], "partial"
    )
    eligibility_check = _check(
        lambda: _validate_mapping(
            exact_but_eligible,
            exact_but_eligible["source_id"],
            schema,
        )
    )
    results.append(
        {
            "case_id": "eligibility_names_exact_dimension",
            "expected_pass": False,
            "observed_pass": eligibility_check["passed"],
            "expectation_met": not eligibility_check["passed"],
            "error": eligibility_check["error"],
        }
    )
    return {
        "offline": True,
        "controls": results,
        "all_expectations_met": all(row["expectation_met"] for row in results),
    }


def _retain_selection_manifest(run_dir: Path, output_dir: Path) -> dict[str, Any]:
    metadata_path = run_dir / "source/sample_metadata.jsonl"
    subset_path = run_dir / "source/source_subset.jsonl"
    if not metadata_path.exists() or not subset_path.exists():
        return {"available": False}

    metadata = read_jsonl(metadata_path)
    subset = read_jsonl(subset_path)
    metadata_ids = [row["egp_id"] for row in metadata]
    subset_ids = [row["egp_id"] for row in subset]
    if len(metadata) != 139 or metadata_ids != subset_ids:
        raise ValueError(
            "retained source selection must contain the same ordered 139 IDs"
        )
    target = output_dir / "selection_manifest.jsonl"
    write_jsonl(target, metadata)
    return {
        "available": True,
        "rows": len(metadata),
        "unique_source_ids": len(set(metadata_ids)),
        "source_path": str(metadata_path.relative_to(ROOT)),
        "source_sha256": _sha256(metadata_path),
        "retained_path": str(target.relative_to(ROOT)),
        "retained_sha256": _sha256(target),
        "ordered_ids_match_source_subset": True,
    }


def run_audit(run_dir: Path, output_dir: Path) -> dict[str, Any]:
    schema = read_yaml(ROOT / "modules/grammar/canonical/schema.yaml")
    order = schema["dimension_order"]
    annotation_path = run_dir / "source/annotation_units.jsonl"
    annotation_units = {
        row["unit_id"]: row for row in read_jsonl(annotation_path)
    }

    transition_rows = []
    final_by_unit: dict[str, dict[str, Any]] = {}
    for unit_dir in sorted((run_dir / "normalisation/units").glob("u*")):
        result_path = unit_dir / "result.json"
        if not result_path.exists():
            continue
        retained = json.loads(result_path.read_text(encoding="utf-8"))
        unit_id = unit_dir.name
        raw_first = retained["phase1"]
        raw_second = retained.get("phase2")
        first = _adapt_legacy_mapping(raw_first, order)
        final_by_unit[unit_id] = _adapt_legacy_mapping(
            retained["output"], order, inherited=first["phase2_eligible"]
        )
        if raw_second is None:
            continue
        second = _adapt_legacy_mapping(
            raw_second, order, inherited=first["phase2_eligible"]
        )
        phase1_check = _check(
            lambda mapping=first: _validate_mapping(
                mapping, mapping["source_id"], schema
            )
        )
        phase2_check = _check(
            lambda mapping=second: _validate_mapping(
                mapping,
                mapping["source_id"],
                schema,
                allow_resolved_eligibility=True,
            )
        )
        transition_check = _check(
            lambda initial=first, final=second: _validate_phase2_transition(
                initial, final, schema
            )
        )
        annotation = annotation_units[unit_id]
        transition_rows.append(
            {
                "unit_id": unit_id,
                "source_id": first["source_id"],
                "duplicate_of": annotation["duplicate_of"],
                "phase1": first,
                "phase2": second,
                "phase1_contract": phase1_check,
                "phase2_contract": phase2_check,
                "transition_contract": transition_check,
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    transitions_path = output_dir / "legacy_transitions.jsonl"
    write_jsonl(transitions_path, transition_rows)
    manifest = _retain_selection_manifest(run_dir, output_dir)

    primary_units = [
        row for row in annotation_units.values() if row["duplicate_of"] is None
    ]
    primary_final = [final_by_unit[row["unit_id"]] for row in primary_units]
    repeated = [
        row for row in annotation_units.values() if row["duplicate_of"] is not None
    ]
    repeat_agreements = []
    for row in repeated:
        original = final_by_unit[row["duplicate_of"]]
        duplicate = final_by_unit[row["unit_id"]]
        repeat_agreements.append(
            {
                "unit_id": row["unit_id"],
                "duplicate_of": row["duplicate_of"],
                "source_id": row["egp_id"],
                "exact_mapping_agreement": duplicate == original,
                "result_agreement": duplicate["result"] == original["result"],
            }
        )

    primary_transition_rows = [
        row for row in transition_rows if row["duplicate_of"] is None
    ]
    invocation_settings = set()
    for invocation_path in (run_dir / "normalisation/units").glob(
        "u*/phase*/attempt-*/invocation.json"
    ):
        invocation = json.loads(invocation_path.read_text(encoding="utf-8"))
        invocation_settings.add(
            (
                invocation.get("backend"),
                invocation.get("model"),
                invocation.get("reasoning_effort"),
                invocation.get("model_snapshot_pinned"),
                invocation.get("decoding_parameters_pinned"),
            )
        )
    replay_summary = {
        "experiment_id": "P4-NORMALISATION-OFFLINE-001",
        "claim_boundary": (
            "Offline replay of retained 2026-08-20 model outputs; no fresh "
            "annotation, model call, or independent quality adjudication."
        ),
        "legacy_run": str(run_dir.relative_to(ROOT)),
        "legacy_source_selection": manifest,
        "annotation_units": len(annotation_units),
        "primary_descriptors": len(primary_units),
        "repeated_annotations": len(repeated),
        "legacy_model_settings": [
            {
                "backend": setting[0],
                "model": setting[1],
                "reasoning_effort": setting[2],
                "model_snapshot_pinned": setting[3],
                "decoding_parameters_pinned": setting[4],
            }
            for setting in sorted(invocation_settings)
        ],
        "seed": None,
        "primary_final_result_counts": dict(
            sorted(Counter(row["result"] for row in primary_final).items())
        ),
        "primary_phase2_calls": len(primary_transition_rows),
        "primary_phase2_result_transitions": dict(
            sorted(
                Counter(
                    f"{row['phase1']['result']}->{row['phase2']['result']}"
                    for row in primary_transition_rows
                ).items()
            )
        ),
        "primary_phase2_complete_yield": sum(
            row["phase1"]["result"] == "partial"
            and row["phase2"]["result"] == "complete"
            for row in primary_transition_rows
        ),
        "explicit_nonempty_eligibility_primary": sum(
            bool(row["phase1"]["phase2_eligible"])
            for row in primary_transition_rows
        ),
        "phase1_contract_pass_primary": sum(
            row["phase1_contract"]["passed"] for row in primary_transition_rows
        ),
        "phase2_contract_pass_primary": sum(
            row["phase2_contract"]["passed"] for row in primary_transition_rows
        ),
        "transition_contract_pass_primary": sum(
            row["transition_contract"]["passed"]
            for row in primary_transition_rows
        ),
        "transition_contract_failure_examples": [
            {
                "unit_id": row["unit_id"],
                "source_id": row["source_id"],
                "error": row["transition_contract"]["error"],
            }
            for row in primary_transition_rows
            if not row["transition_contract"]["passed"]
        ][:10],
        "repeat_exact_mapping_agreements": sum(
            row["exact_mapping_agreement"] for row in repeat_agreements
        ),
        "repeat_result_agreements": sum(
            row["result_agreement"] for row in repeat_agreements
        ),
        "repeat_comparisons": repeat_agreements,
        "artifacts": {
            "legacy_transitions": str(transitions_path.relative_to(ROOT)),
            "legacy_transitions_sha256": _sha256(transitions_path),
        },
    }
    write_json(output_dir / "replay_summary.json", replay_summary)
    adversarial = _adversarial_controls(schema)
    write_json(output_dir / "adversarial_controls.json", adversarial)
    return replay_summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy-run", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    summary = run_audit(args.legacy_run.resolve(), args.output_dir.resolve())
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
