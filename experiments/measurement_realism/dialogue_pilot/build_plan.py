#!/usr/bin/env python3
"""Build the deterministic four-cell, five-format continuum pilot plan.

This script reads only the outcome-free matched-format cell selection and the
local preregistered protocol files. It makes no model calls and never writes to
the protected full-v1 dataset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]
PROTOCOL_ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE = (
    ROOT / "experiments/measurement_realism/design/format_selection/selected_cells.json"
)

SELECTION_SPECS: tuple[tuple[str, str, int, str], ...] = (
    (
        "simple",
        "finite_present_anchor",
        1,
        "One-KC finite-present anchor: a common, minimally compositional selected seen row.",
    ),
    (
        "multi_kc",
        "past_perfect_contrast",
        2,
        "An ordinary two-KC aspect-plus-finite contrast between the simple anchor and more heavily stacked rows.",
    ),
    (
        "question",
        "present_perfect_polar_contrast",
        3,
        "A common polar-question contrast with reusable aspect and finite-form dependencies.",
    ),
    (
        "rare_complex",
        "non_subject_wh_rare_cell",
        3,
        "The sole selected non-subject-WH cell, deliberately testing the narrowest rare clause-operation support.",
    ),
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


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


def write_frozen(path: Path, payload: str, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") != payload:
        raise FileExistsError(f"refusing to overwrite changed {label}: {path}")
    path.write_text(payload, encoding="utf-8")


def read_config(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("dialogue pilot config must be an object")
    return value


def build(source_path: Path, config_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source = json.loads(source_path.read_text(encoding="utf-8"))
    config = read_config(config_path)
    seen = source.get("seen_cells")
    if not isinstance(seen, list) or len(seen) != 18:
        raise ValueError("canonical source must contain the 18-cell seen cohort")
    if any(row.get("acquisition_updates") is not True for row in seen):
        raise ValueError("dialogue pilot selection must use seen acquisition cells")
    by_role = {str(row["selection_role"]): row for row in seen}
    if len(by_role) != len(seen):
        raise ValueError("canonical source contains duplicate selection roles")

    formats = list(config["formats"]["order"])
    expected_formats = [
        "constrained_cloze",
        "sentence_transformation",
        "contextual_production",
        "dialogue_completion",
        "open_dialogue",
    ]
    if formats != expected_formats:
        raise ValueError("format continuum order changed")
    configured_roles = config["selection"]["exact_roles"]
    selected_rows: list[dict[str, Any]] = []
    requests: list[dict[str, Any]] = []
    selected_cell_ids: set[str] = set()
    for order, (stratum, selection_role, q_width, rationale) in enumerate(
        SELECTION_SPECS, start=1
    ):
        if configured_roles.get(stratum) != selection_role:
            raise ValueError(f"config selection role changed for {stratum}")
        if selection_role not in by_role:
            raise ValueError(f"missing canonical role: {selection_role}")
        source_row = by_role[selection_role]
        if int(source_row["q_cardinality"]) != q_width:
            raise ValueError(f"Q width changed for {selection_role}")
        cell_id = str(source_row["cell_id"])
        if cell_id in selected_cell_ids:
            raise ValueError("pilot strata must select four distinct cells")
        selected_cell_ids.add(cell_id)
        family_id = f"ecp_{stratum}_{cell_id}"
        opportunity_slots = [
            {
                "opportunity_id": f"{family_id}_{format_id}",
                "format": format_id,
                "continuum_order": index,
            }
            for index, format_id in enumerate(formats, start=1)
        ]
        selected = {
            "selection_order": order,
            "pilot_stratum": stratum,
            "selection_role": selection_role,
            "selection_rationale": rationale,
            "family_id": family_id,
            "cell_id": cell_id,
            "grammar_regime": source_row["grammar_regime"],
            "grammar_cell": dict(source_row["features"]),
            "active_generator_kc_ids": list(source_row["generator_kc_ids"]),
            "q_cardinality": int(source_row["q_cardinality"]),
            "q_row": list(source_row["q_row"]),
            "source_ids": list(source_row["source_ids"]),
            "source_support_count": int(source_row["source_support_count"]),
            "reference_item": {
                "item_id": source_row["reference_item_id"],
                "prompt": source_row["reference_prompt"],
                "target_answer": source_row["reference_target_answer"],
                "accepted_answers": list(source_row["reference_accepted_answers"]),
                "audit": dict(source_row["item_audit"]),
                "reuse_policy": source_row["reference_stem_reuse"],
            },
            "opportunity_slots": opportunity_slots,
        }
        selected_rows.append(selected)
        requests.append(
            {
                "request_schema": "dialogue_continuum_generation_request_v1",
                "family_id": family_id,
                "pilot_stratum": stratum,
                "cell_id": cell_id,
                "grammar_cell": dict(source_row["features"]),
                "active_generator_kc_ids": list(source_row["generator_kc_ids"]),
                "q_row": list(source_row["q_row"]),
                "reference_item": selected["reference_item"],
                "formats": opportunity_slots,
                "matching_contract": dict(config["matching"]),
                "format_contracts": dict(config["formats"]["contracts"]),
                "prompt_template": config["generation"]["prompt"],
                "output_schema": config["generation"]["output_schema"],
                "live_call_authorized": False,
            }
        )

    if [row["q_cardinality"] for row in selected_rows] != [1, 2, 3, 3]:
        raise ValueError("pilot structural strata changed")
    plan = {
        "pilot_id": config["pilot_id"],
        "status": "FROZEN_NO_CALL_CONTINUUM_PLAN",
        "source_selection": {
            "path": relative(source_path),
            "sha256": file_sha256(source_path),
            "cohort": "full_rank_18_seen_acquisition",
        },
        "scientific_boundary": dict(config["scientific_boundary"]),
        "format_order": formats,
        "critic_roles": list(config["critique"]["roles"]),
        "counts": {
            "cells": len(selected_rows),
            "formats_per_cell": len(formats),
            "planned_opportunities": len(selected_rows) * len(formats),
            "planned_critic_judgments": len(selected_rows)
            * len(formats)
            * len(config["critique"]["roles"]),
        },
        "selection_method": {
            "kind": "exact_selection_role_lookup_from_outcome_free_full_rank_cohort",
            "strata_in_order": [row["pilot_stratum"] for row in selected_rows],
            "outcomes_read": False,
            "private_oracle_trajectories_read": False,
            "tie_break": config["selection"]["stable_tie_break"],
        },
        "selected_cells": selected_rows,
        "analysis_contract": dict(config["analysis"]),
        "human_expert_validation": dict(config["human_expert_validation"]),
    }
    return plan, requests


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--config", type=Path, default=PROTOCOL_ROOT / "config.yaml")
    parser.add_argument("--output-dir", type=Path, default=PROTOCOL_ROOT)
    args = parser.parse_args()

    plan, requests = build(args.source, args.config)
    selected_payload = json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    request_payload = "".join(canonical_json(row) + "\n" for row in requests)
    selected_path = args.output_dir / "selected_cells.json"
    requests_path = args.output_dir / "generation_requests.jsonl"
    write_frozen(selected_path, selected_payload, "selected cells")
    write_frozen(requests_path, request_payload, "generation requests")

    static_inputs = {
        "canonical_selection": args.source,
        "config": args.config,
        "generation_prompt": PROTOCOL_ROOT / "prompts/generate_continuum_family.txt",
        "critic_prompt": PROTOCOL_ROOT / "prompts/critic_continuum.txt",
        "family_schema": PROTOCOL_ROOT / "schemas/generated_family.schema.json",
        "critic_schema": PROTOCOL_ROOT / "schemas/critic_judgment.schema.json",
        "preregistration": PROTOCOL_ROOT / "preregistration.md",
        "human_validation_protocol": (
            PROTOCOL_ROOT / "human_expert_validation_protocol.md"
        ),
        "analysis_script": PROTOCOL_ROOT / "analyze_dialogue_pilot.py",
        "builder": Path(__file__).resolve(),
    }
    manifest = {
        "pilot_id": plan["pilot_id"],
        "status": "FROZEN_NO_CALL_CONTINUUM_PLAN",
        "live_model_calls_made": 0,
        "human_judgments_collected": 0,
        "full_v1_mutated": False,
        "inputs": {
            key: {
                "path": relative(path),
                "sha256": file_sha256(path),
                "bytes": path.stat().st_size,
            }
            for key, path in sorted(static_inputs.items())
        },
        "outputs": {
            "selected_cells": {
                "path": "selected_cells.json",
                "sha256": sha256_bytes(selected_payload.encode("utf-8")),
                "bytes": len(selected_payload.encode("utf-8")),
                "cells": 4,
            },
            "generation_requests": {
                "path": "generation_requests.jsonl",
                "sha256": sha256_bytes(request_payload.encode("utf-8")),
                "bytes": len(request_payload.encode("utf-8")),
                "rows": 4,
            },
        },
        "forbidden_inputs": [
            "learner interactions",
            "private mastery trajectories",
            "response probabilities",
            "KT predictions or discovery selections",
        ],
        "replay_command": (
            ".venv/bin/python "
            "experiments/measurement_realism/dialogue_pilot/build_plan.py"
        ),
    }
    manifest_payload = json.dumps(
        manifest, ensure_ascii=False, indent=2, sort_keys=True
    ) + "\n"
    write_frozen(args.output_dir / "manifest.json", manifest_payload, "plan manifest")
    print(
        canonical_json(
            {
                "status": manifest["status"],
                "cells": 4,
                "planned_opportunities": 20,
                "live_model_calls_made": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
