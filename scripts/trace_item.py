#!/usr/bin/env python3
"""Print one accepted item's source-to-interaction lineage."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.utils.io import display_path, read_json, read_jsonl, sha256_file
from shared.utils.manifests import describe


def _one(rows: list[dict[str, Any]], key: str, value: str) -> dict[str, Any] | None:
    return next((row for row in rows if row.get(key) == value), None)


def _indexed_mappings(run_dir: Path, phase: int) -> dict[str, dict[str, Any]]:
    values = read_jsonl(run_dir / "normalization" / f"phase{phase}.jsonl")
    index = read_jsonl(run_dir / "normalization" / f"phase{phase}_index.jsonl")
    if len(values) != len(index):
        raise RuntimeError(f"Phase {phase} values/index length mismatch")
    return {
        meta["unit_id"]: {"index": meta, "mapping": mapping}
        for meta, mapping in zip(index, values, strict=True)
    }


def _model_evidence(path: Path) -> dict[str, Any] | None:
    if not path.is_dir():
        return None
    result = {
        "directory": display_path(path),
        "input": read_json(path / "input.json"),
        "invocation": read_json(path / "invocation.json"),
        "validation": read_json(path / "validation.json"),
    }
    for name in ("rendered_prompt.txt", "raw_output.txt", "parsed_output.json"):
        candidate = path / name
        result[name] = {
            "path": display_path(candidate),
            "sha256": sha256_file(candidate),
        }
    return result


def _legacy_model_evidence(
    *,
    prompt: Path,
    invocation: Path,
    raw: Path,
    parsed: Path,
    validation: Path | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "layout": "legacy_accepted_reference_read_only",
        "rendered_prompt.txt": describe(prompt),
        "invocation": read_json(invocation),
        "raw_output.txt": describe(raw),
        "parsed_output.json": describe(parsed),
        "parsed_output": read_json(parsed),
    }
    if validation is not None and validation.is_file():
        result["validation"] = read_json(validation)
    return result


def _legacy_indexed_mappings(run_dir: Path, phase: int) -> dict[str, dict[str, Any]]:
    root = run_dir / "normalization" / f"phase{phase}"
    values = read_jsonl(root / "mappings.jsonl")
    index = read_jsonl(root / "unit_index.jsonl")
    if len(values) != len(index):
        raise RuntimeError(f"legacy Phase {phase} values/index length mismatch")
    return {
        meta["unit_id"]: {"index": meta, "mapping": mapping}
        for meta, mapping in zip(index, values, strict=True)
    }


def _legacy_trace(run_dir: Path, item_id: str, interaction_limit: int) -> dict[str, Any]:
    item = _one(read_jsonl(run_dir / "items/validated/items_v1.jsonl"), "item_id", item_id)
    if item is None:
        raise SystemExit(f"accepted item not found: {item_id}")
    source_by_id = {
        row["egp_id"]: row
        for row in read_jsonl(run_dir / "input/source_sample/selected_source.jsonl")
    }
    final_by_id = {
        row["egp_id"]: row
        for row in read_jsonl(run_dir / "normalization/source_mappings.jsonl")
    }
    mapping_prov = {
        row["egp_id"]: row
        for row in read_jsonl(run_dir / "normalization/source_mapping_provenance.jsonl")
    }
    phase1 = _legacy_indexed_mappings(run_dir, 1)
    phase2 = _legacy_indexed_mappings(run_dir, 2)
    source_trace = []
    for egp_id in item["source_descriptor_ids"]:
        provenance = mapping_prov[egp_id]
        unit_id = provenance["primary_unit_id"]
        phase1_root = run_dir / "normalization/phase1"
        phase2_root = run_dir / "normalization/phase2"
        log1 = run_dir / "logs/normalization/phase1"
        log2 = run_dir / "logs/normalization/phase2"
        first_evidence = _legacy_model_evidence(
            prompt=log1 / f"{unit_id}.attempt-01.prompt.txt",
            invocation=log1 / f"{unit_id}.attempt-01.json",
            raw=phase1_root / f"raw/{unit_id}.attempt-01.txt",
            parsed=phase1_root / f"parsed/{unit_id}.json",
            validation=log1 / f"{unit_id}.validation.json",
        )
        second_evidence = None
        if unit_id in phase2:
            second_evidence = _legacy_model_evidence(
                prompt=log2 / f"{unit_id}.attempt-01.prompt.txt",
                invocation=log2 / f"{unit_id}.attempt-01.json",
                raw=phase2_root / f"raw/{unit_id}.attempt-01.txt",
                parsed=phase2_root / f"parsed/{unit_id}.json",
                validation=log2 / f"{unit_id}.validation.json",
            )
        source_trace.append(
            {
                "source_descriptor": source_by_id[egp_id],
                "phase1": phase1[unit_id],
                "phase1_model_evidence": first_evidence,
                "phase2": phase2.get(unit_id),
                "phase2_model_evidence": second_evidence,
                "final_mapping": final_by_id[egp_id],
            }
        )
    cell = _one(
        read_jsonl(run_dir / "normalization/canonical_cells/cells.jsonl"),
        "canonical_cell_id",
        item["canonical_cell_id"],
    )
    cell_edges = [
        row for row in read_jsonl(run_dir / "normalization/canonical_cells/source_edges.jsonl")
        if row["canonical_cell_id"] == item["canonical_cell_id"]
    ]
    realizations = [
        row for row in read_jsonl(run_dir / "realization/outputs/realizations_v1.jsonl")
        if row["spec"]["canonical_cell_id"] == item["canonical_cell_id"]
    ]
    opportunity = _one(
        read_jsonl(run_dir / "kc/inventory/OPPORTUNITY_PROJECTION_v1.jsonl"),
        "opportunity_id",
        item["provenance"]["opportunity_id"],
    )
    q_edges = [
        row for row in read_jsonl(run_dir / "qmatrix/outputs/item_kc_edges.jsonl")
        if row["item_id"] == item_id
    ]
    interactions = [
        row for row in read_jsonl(run_dir / "simulation/interactions/interactions_v1.jsonl")
        if row["item_id"] == item_id
    ]
    validation_unit = next(
        row["validation_unit_id"]
        for row in read_jsonl(run_dir / "items/pilots/v0_1/validation_units.jsonl")
        if row["item_id"] == item_id and row["duplicate_of"] is None
    )
    diagnostic_log = run_dir / "logs/items/model_validation_items_v0_1"
    diagnostic_root = run_dir / "items/pilots/v0_1/model_validation"
    item_diagnostic = _legacy_model_evidence(
        prompt=diagnostic_log / f"{validation_unit}.attempt-01.prompt.txt",
        invocation=diagnostic_log / f"{validation_unit}.attempt-01.json",
        raw=diagnostic_root / f"raw/{validation_unit}.attempt-01.txt",
        parsed=diagnostic_root / f"parsed/{validation_unit}.json",
    )
    candidate = _one(
        read_jsonl(run_dir / "items/pilots/v0_1/candidates.jsonl"),
        "item_id",
        item_id,
    )
    item_diagnostic["input"] = candidate
    methodology_files = [
        run_dir / "manifests/E2E_V1_STACK.sha256",
        run_dir / "manifests/NORMALIZATION_FREEZE.sha256",
        run_dir / "manifests/REALIZATION_OUTPUTS_v1.sha256",
        run_dir / "manifests/KC_OUTPUTS_v1.sha256",
        run_dir / "manifests/ITEM_OUTPUTS_v1.sha256",
        run_dir / "manifests/QMATRIX_OUTPUTS_v1.sha256",
        run_dir / "manifests/SIMULATION_KT_OUTPUTS_v1.sha256",
    ]
    return {
        "item_id": item_id,
        "evidence_layout": "legacy_accepted_reference_read_only",
        "chain": {
            "source_descriptors_to_normalization": source_trace,
            "canonical_cell": cell,
            "source_cell_edges": cell_edges,
            "base_realizations_for_cell": realizations,
            "kc_opportunity": opportunity,
            "item_realization_spec": item["realization_spec"],
            "accepted_item": item,
            "item_generation_evidence": {
                "candidate": candidate,
                "opportunity": opportunity,
            },
            "item_validation_evidence": item["validator_results"],
            "item_model_diagnostic": item_diagnostic,
            "item_kc_edges": q_edges,
            "selected_observable_interactions": interactions[: max(0, interaction_limit)],
            "total_observable_interactions_for_item": len(interactions),
            "methodology_references": [describe(path) for path in methodology_files],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("item_id")
    parser.add_argument("--run", required=True, help="run ID under runs/ or a run-directory path")
    parser.add_argument("--interaction-limit", type=int, default=5)
    args = parser.parse_args()
    run_dir = Path(args.run)
    if not run_dir.is_absolute() and len(run_dir.parts) == 1:
        run_dir = ROOT / "runs" / run_dir
    run_dir = run_dir.resolve()
    if not (run_dir / "items/validation/accepted_items.jsonl").is_file():
        legacy = run_dir / "items/validated/items_v1.jsonl"
        if legacy.is_file():
            print(
                json.dumps(
                    _legacy_trace(run_dir, args.item_id, args.interaction_limit),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
    items = read_jsonl(run_dir / "items" / "validation" / "accepted_items.jsonl")
    item = _one(items, "item_id", args.item_id)
    if item is None:
        raise SystemExit(f"accepted item not found: {args.item_id}")

    source_by_id = {row["egp_id"]: row for row in read_jsonl(run_dir / "source" / "source_subset.jsonl")}
    final_by_id = {row["egp_id"]: row for row in read_jsonl(run_dir / "normalization" / "final_mappings.jsonl")}
    mapping_prov = {row["egp_id"]: row for row in read_jsonl(run_dir / "normalization" / "mapping_provenance.jsonl")}
    phase1 = _indexed_mappings(run_dir, 1)
    phase2 = _indexed_mappings(run_dir, 2)
    cell = _one(read_jsonl(run_dir / "canonical" / "canonical_cells.jsonl"), "canonical_cell_id", item["canonical_cell_id"])
    cell_edges = [
        row for row in read_jsonl(run_dir / "canonical" / "source_cell_edges.jsonl")
        if row["canonical_cell_id"] == item["canonical_cell_id"]
    ]
    base_realizations = [
        row for row in read_jsonl(run_dir / "realization" / "realizations.jsonl")
        if row["spec"]["canonical_cell_id"] == item["canonical_cell_id"]
    ]
    q_edges = [
        row for row in read_jsonl(run_dir / "qmatrix" / "item_kc_edges.jsonl")
        if row["item_id"] == item["item_id"]
    ]
    interactions = [
        row for row in read_jsonl(run_dir / "simulation" / "observable_interactions.jsonl")
        if row["item_id"] == item["item_id"]
    ]
    source_trace = []
    for egp_id in item["source_descriptor_ids"]:
        provenance = mapping_prov[egp_id]
        unit_id = provenance["primary_unit_id"]
        source_trace.append(
            {
                "source_descriptor": source_by_id[egp_id],
                "phase1": phase1[unit_id],
                "phase1_model_evidence": _model_evidence(
                    run_dir / "normalization" / "units" / unit_id / "phase1"
                ),
                "phase2": phase2.get(unit_id),
                "phase2_model_evidence": _model_evidence(
                    run_dir / "normalization" / "units" / unit_id / "phase2"
                ),
                "final_mapping": final_by_id[egp_id],
            }
        )
    validation_units = read_jsonl(run_dir / "items" / "generation" / "validation_units.jsonl")
    diagnostic_unit = next(
        (
            row["validation_unit_id"] for row in validation_units
            if row["item_id"] == item["item_id"] and row["duplicate_of"] is None
        ),
        None,
    )
    methodology_path = run_dir / "provenance" / "methodology.json"
    result = {
        "item_id": item["item_id"],
        "chain": {
            "source_descriptors_to_normalization": source_trace,
            "canonical_cell": cell,
            "source_cell_edges": cell_edges,
            "base_realizations_for_cell": base_realizations,
            "item_realization_spec": item["realization_spec"],
            "accepted_item": item,
            "item_generation_evidence": {
                name: read_json(
                    run_dir / "items" / "generation" / "units" / item["item_id"] / filename
                )
                for name, filename in (
                    ("input", "input.json"),
                    ("procedure", "procedure.json"),
                    ("generated_item", "generated_item.json"),
                )
            },
            "item_validation_evidence": read_json(
                run_dir / "items" / "validation" / "units" / f"{item['item_id']}.json"
            ),
            "item_model_diagnostic": (
                _model_evidence(run_dir / "items" / "units" / diagnostic_unit)
                if diagnostic_unit else None
            ),
            "item_kc_edges": q_edges,
            "selected_observable_interactions": interactions[: max(0, args.interaction_limit)],
            "total_observable_interactions_for_item": len(interactions),
            "methodology_references": read_json(methodology_path) if methodology_path.is_file() else None,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
