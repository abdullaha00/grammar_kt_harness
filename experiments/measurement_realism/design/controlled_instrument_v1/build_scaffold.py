#!/usr/bin/env python3
"""Build the deterministic, non-release controlled-instrument scaffold.

The slot rows are derived only from the frozen 18+2 cell selection. Rejected or
accepted candidate wording from the matched-bank run is never read into slot
construction. The failed-run ledger is read solely to retain the reason this
separate structural scenario exists.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import jsonschema
import numpy as np


ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
SELECTED = (
    ROOT
    / "experiments/measurement_realism/design/format_selection/selected_cells.json"
)
SCHEMA = HERE / "controlled_instrument.schema.json"
OUTPUT = HERE / "instrument.jsonl"
MANIFEST = HERE / "manifest.json"
FAILED_DECISIONS = (
    ROOT
    / "experiments/measurement_realism/design/bank_protocol/runs/"
    "matched_bank_v0_2_20260830/curation/family_decisions.jsonl"
)
FORMATS = (
    ("constrained_cloze", "clz"),
    ("dialogue_completion", "dlg"),
    ("multiple_choice", "mcq"),
    ("sentence_transformation", "xfm"),
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semantic_hash(rows: Iterable[Any]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(canonical_json(row).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_exact(path: Path, payload: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != payload:
        raise FileExistsError(f"refusing to overwrite changed frozen artifact: {path}")
    path.write_text(payload, encoding="utf-8")


def role_code(regime: str) -> str:
    return {
        "seen": "seen",
        "unseen_combination": "ucomb",
        "unseen_value": "uval",
    }[regime]


def build_rows(selected: dict[str, Any]) -> list[dict[str, Any]]:
    selection_prefix = sha256_file(SELECTED)[:12]
    rows = []
    for cell in [*selected["seen_cells"], *selected["held_out_cells"]]:
        regime = cell["grammar_regime"]
        replicates = (1, 2) if regime == "seen" else (1,)
        for replicate in replicates:
            family_id = (
                f"cis1_{selection_prefix}_{role_code(regime)}_"
                f"{cell['cell_id']}_r{replicate:02d}"
            )
            for format_label, format_code in FORMATS:
                rows.append(
                    {
                        "schema_version": "controlled_instrument_slot_v1",
                        "slot_id": f"{family_id}_{format_code}",
                        "family_id": family_id,
                        "cell_id": cell["cell_id"],
                        "replicate_index": replicate,
                        "format_label": format_label,
                        "grammar_regime": regime,
                        "acquisition_updates": regime == "seen",
                        "generator_kc_ids": list(cell["generator_kc_ids"]),
                        "q_row": list(cell["q_row"]),
                        "instrument_status": "STRUCTURAL_PLACEHOLDER_ONLY",
                        "release_eligible": False,
                        "placeholder_metadata": {
                            "learner_prompt_present": False,
                            "target_answer_present": False,
                            "accepted_response_space_present": False,
                            "format_is_label_only": True,
                            "learner_facing_validity": "NOT_ASSESSED",
                            "platform_deployability": "NOT_ASSESSED",
                            "permitted_use": "CONTROLLED_SIMULATOR_SCENARIO_ONLY",
                        },
                        "provenance": {
                            "construction": "deterministic_from_selected_cell_and_crossing",
                            "selected_cells_sha256": sha256_file(SELECTED),
                            "candidate_item_content_used": False,
                            "learner_outcomes_used": False,
                        },
                    }
                )
    return sorted(rows, key=lambda row: row["slot_id"])


def validate_rows(rows: list[dict[str, Any]], selected: dict[str, Any]) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    for index, row in enumerate(rows):
        errors = sorted(validator.iter_errors(row), key=lambda error: list(error.path))
        if errors:
            raise ValueError(f"slot {index} violates schema: {errors[0].message}")
    if len(rows) != 152 or len({row["slot_id"] for row in rows}) != 152:
        raise ValueError("controlled scaffold must contain 152 unique slots")
    if len({row["family_id"] for row in rows}) != 38:
        raise ValueError("controlled scaffold must contain 38 families")
    counts = Counter((row["family_id"], row["format_label"]) for row in rows)
    if any(value != 1 for value in counts.values()) or len(counts) != 38 * 4:
        raise ValueError("every family must cross each of four format labels once")
    selected_by_id = {
        row["cell_id"]: row
        for row in [*selected["seen_cells"], *selected["held_out_cells"]]
    }
    for row in rows:
        cell = selected_by_id[row["cell_id"]]
        if (
            row["grammar_regime"] != cell["grammar_regime"]
            or row["q_row"] != cell["q_row"]
            or row["generator_kc_ids"] != cell["generator_kc_ids"]
        ):
            raise ValueError(f"slot changed selected-cell truth: {row['slot_id']}")
    seen_rows = {
        row["cell_id"]: row["q_row"]
        for row in rows
        if row["grammar_regime"] == "seen"
    }
    if len(seen_rows) != 18 or int(np.linalg.matrix_rank(list(seen_rows.values()))) != 18:
        raise ValueError("controlled scaffold seen-cell Q must retain rank 18")


def failed_run_summary() -> dict[str, Any]:
    decisions = read_jsonl(FAILED_DECISIONS)
    accepted = sorted(
        {row["family_id"] for row in decisions if row["decision"] == "accept"}
    )
    return {
        "status": "CURATED_BANK_INCOMPLETE_NOT_FREEZABLE",
        "decision_ledger_path": str(FAILED_DECISIONS.relative_to(ROOT)),
        "decision_ledger_sha256": sha256_file(FAILED_DECISIONS),
        "decision_rows": len(decisions),
        "families_attempted": len({row["family_id"] for row in decisions}),
        "accepted_families": len(accepted),
        "required_families": 38,
        "round_decision_counts": dict(
            sorted(Counter(str(row["candidate_round"]) for row in decisions).items())
        ),
        "accepted_family_ids_retained_as_content": False,
        "rejected_candidate_content_reused": False,
    }


def main() -> None:
    selected = json.loads(SELECTED.read_text(encoding="utf-8"))
    rows = build_rows(selected)
    validate_rows(rows, selected)
    payload = "".join(canonical_json(row) + "\n" for row in rows)
    write_exact(OUTPUT, payload)
    manifest = {
        "schema_version": "controlled_instrument_manifest_v1",
        "scenario_status": "FROZEN_STRUCTURE_ONLY_BEFORE_RESPONSES",
        "release_eligible": False,
        "learner_facing_item_bank": False,
        "measurement_validity_claimed": False,
        "platform_plausibility_claimed": False,
        "construction_uses_learner_outcomes": False,
        "construction_uses_generated_candidate_content": False,
        "counts": {
            "slots": len(rows),
            "families": len({row["family_id"] for row in rows}),
            "seen_slots": sum(row["grammar_regime"] == "seen" for row in rows),
            "probe_only_slots": sum(row["grammar_regime"] != "seen" for row in rows),
            "formats": dict(sorted(Counter(row["format_label"] for row in rows).items())),
            "seen_cell_q_rank": 18,
        },
        "inputs": {
            "selected_cells": {
                "path": str(SELECTED.relative_to(ROOT)),
                "sha256": sha256_file(SELECTED),
            },
            "schema": {
                "path": str(SCHEMA.relative_to(ROOT)),
                "sha256": sha256_file(SCHEMA),
            },
            "builder": {
                "path": str(Path(__file__).resolve().relative_to(ROOT)),
                "sha256": sha256_file(Path(__file__).resolve()),
            },
        },
        "instrument": {
            "path": str(OUTPUT.relative_to(ROOT)),
            "sha256": sha256_file(OUTPUT),
            "semantic_sha256": semantic_hash(rows),
        },
        "curated_bank_failure_evidence": failed_run_summary(),
        "claim_boundary": (
            "Format names are experimental nuisance labels only. Rows contain no "
            "learner-facing prompt, target answer, accepted response set, semantic "
            "content, or evidence of deployability."
        ),
    }
    write_exact(
        MANIFEST,
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )
    print(canonical_json({"slots": len(rows), "manifest": str(MANIFEST)}))


if __name__ == "__main__":
    main()

