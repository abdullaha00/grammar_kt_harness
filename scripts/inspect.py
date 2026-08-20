#!/usr/bin/env python3
"""Inspect one unit from an existing run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Prevent this file from shadowing Python's standard inspect module in dependencies.
sys.path.remove(str(Path(__file__).resolve().parent))

from grammar_kt.io import ROOT, read_json, read_jsonl


def one(rows: list[dict[str, Any]], key: str, value: str) -> dict[str, Any]:
    try:
        return next(row for row in rows if row.get(key) == value)
    except StopIteration as error:
        raise KeyError(f"{value} not found by {key}") from error


def inspect_normalisation(run: Path, identifier: str) -> dict[str, Any]:
    for result_path in (run / "normalisation" / "units").glob("*/result.json"):
        result = read_json(result_path)
        if result.get("input", {}).get("egp_id") == identifier or result_path.parent.name == identifier:
            phases = {}
            for phase in ("phase1", "phase2"):
                directory = result_path.parent / phase
                if not directory.is_dir():
                    continue
                selected = read_json(directory / "result.json")["selected_attempt"]
                attempt = directory / f"attempt-{selected:02d}"
                phases[phase] = {
                    "input": read_json(attempt / "input.json"),
                    "rendered_prompt": (attempt / "rendered_prompt.txt").read_text(encoding="utf-8"),
                    "invocation": read_json(attempt / "invocation.json"),
                    "raw_output": (attempt / "raw_output.txt").read_text(encoding="utf-8"),
                    "parsed_output": read_json(attempt / "parsed_output.json"),
                    "validation": read_json(attempt / "validation.json"),
                }
            return {"result": result, "phases": phases}
    raise KeyError(identifier)


def inspect_kc(run: Path, identifier: str) -> dict[str, Any]:
    projections = read_jsonl(run / "kc" / "item_kc_projection.jsonl")
    matches = [
        row for row in projections
        if row["item_id"] == identifier or row["canonical_cell_id"] == identifier
    ]
    if not matches:
        raise KeyError(identifier)
    return {
        "frozen_policy": read_json(run / "kc_selection" / "selected_policy.json"),
        "authoritative_projection_unit": "accepted concrete item realization",
        "item_projections": matches,
    }


def inspect_item(run: Path, identifier: str) -> dict[str, Any]:
    candidates = read_jsonl(run / "items" / "generation" / "candidate_items.jsonl")
    item = one(candidates, "item_id", identifier)
    result = one(read_jsonl(run / "items" / "validation" / "validation_results.jsonl"), "item_id", identifier)
    generation_input = read_json(run / "items" / "generation" / "units" / identifier / "input.json")
    diagnostics = [row for row in read_jsonl(run / "items" / "validation" / "diagnostics.jsonl") if row["item_id"] == identifier]
    evidence = []
    for diagnostic in diagnostics:
        number = diagnostic["successful_attempt"]
        if number is None:
            continue
        attempt = run / "items" / "validation" / "model_units" / diagnostic["validation_unit_id"] / f"attempt-{number:02d}"
        evidence.append({
            "validation_unit_id": diagnostic["validation_unit_id"],
            "input": read_json(attempt / "input.json"),
            "rendered_prompt": (attempt / "rendered_prompt.txt").read_text(encoding="utf-8"),
            "invocation": read_json(attempt / "invocation.json"),
            "raw_output": (attempt / "raw_output.txt").read_text(encoding="utf-8"),
            "parsed_output": read_json(attempt / "parsed_output.json"),
            "validation": read_json(attempt / "validation.json"),
        })
    return {"generation_input": generation_input, "generated_item": item, "validation_result": result, "model_diagnostics": diagnostics, "model_evidence": evidence}


def inspect_kt(run: Path, identifier: str) -> dict[str, Any]:
    event = one(read_jsonl(run / "simulation" / "base_events.jsonl"), "event_id", identifier)
    item = one(
        read_jsonl(run / "items" / "validation" / "accepted_items.jsonl"),
        "item_id",
        event["item_id"],
    )
    cell = one(
        read_jsonl(run / "canonical" / "canonical_cells.jsonl"),
        "canonical_cell_id",
        event["canonical_cell_id"],
    )
    oracle_projection = one(
        read_jsonl(run / "simulation" / "oracle_item_projection.jsonl"),
        "item_id",
        event["item_id"],
    )
    oracle_event = one(
        read_jsonl(run / "simulation" / "oracle_interactions.jsonl"),
        "event_id",
        identifier,
    )
    item_projection = one(
        read_jsonl(run / "kc" / "item_kc_projection.jsonl"),
        "item_id",
        event["item_id"],
    )
    projected = one(
        read_jsonl(run / "kt" / "projected_interactions.jsonl"),
        "event_id",
        identifier,
    )
    prediction = one(read_jsonl(run / "kt" / "predictions.jsonl"), "event_id", identifier)
    return {
        "fixed_data_boundary": {
            "item_and_realisation_evidence": item,
            "canonical_cell": cell,
            "base_event": event,
            "oracle_item_projection": oracle_projection,
            "oracle_event_private_to_simulator": oracle_event,
        },
        "candidate_representation_boundary": {
            "item_kc_projection": item_projection,
            "projected_kt_interaction": projected,
            "prediction": prediction,
        },
        "oracle_used_by_kt": False,
    }


def inspect_probe(run: Path, identifier: str) -> dict[str, Any]:
    simulation_directory = run / "simulation/compositional"
    probe_events = read_jsonl(
        simulation_directory / "compositional_probe_events.jsonl"
    ) + read_jsonl(simulation_directory / "novel_feature_probe_events.jsonl")
    event = one(probe_events, "event_id", identifier)
    item = one(
        read_jsonl(run / "items/validation/accepted_items.jsonl"),
        "item_id",
        event["item_id"],
    )
    cell = one(
        read_jsonl(run / "canonical/canonical_cells.jsonl"),
        "canonical_cell_id",
        event["canonical_cell_id"],
    )
    oracle_item = one(
        read_jsonl(run / "simulation/oracle_item_projection.jsonl"),
        "item_id",
        event["item_id"],
    )
    private_oracle = one(
        read_jsonl(simulation_directory / "oracle_probe_evidence.jsonl"),
        "event_id",
        identifier,
    )
    item_projection = one(
        read_jsonl(run / "kc/item_kc_projection.jsonl"),
        "item_id",
        event["item_id"],
    )
    projected_probe = one(
        read_jsonl(run / "kt/compositional/probe_projection.jsonl"),
        "event_id",
        identifier,
    )
    candidate_state = one(
        read_jsonl(run / "kt/compositional/learner_frozen_candidate_state.jsonl"),
        "learner_id",
        event["learner_id"],
    )
    prediction = one(
        read_jsonl(run / "kt/compositional/predictions.jsonl"),
        "event_id",
        identifier,
    )
    active_state = {
        kc_id: {
            "development_attempts": candidate_state["kc_attempts"].get(kc_id, 0),
            "development_correct": candidate_state["kc_correct"].get(kc_id, 0),
            "frozen_bkt_mastery": candidate_state["bkt_mastery"].get(kc_id),
            "development_supported": kc_id
            in projected_probe["development_supported_kc_ids"],
            "cold": kc_id in projected_probe["cold_kc_ids"],
        }
        for kc_id in projected_probe["kc_ids"]
    }
    return {
        "fixed_probe_boundary": {
            "item_and_realisation_evidence": item,
            "canonical_cell": cell,
            "canonical_split": event["canonical_split"],
            "fixed_observable_probe_outcome": event,
        },
        "private_data_generating_evidence_not_consumed_by_kt": {
            "oracle_item_projection": oracle_item,
            "oracle_probe_evidence": private_oracle,
            "warning": "private structural-oracle evidence is debugging information, not model input",
        },
        "candidate_representation_boundary": {
            "item_kc_projection": item_projection,
            "development_support_and_frozen_history": projected_probe,
            "active_kc_frozen_state": active_state,
            "learner_global_development_state": {
                "attempts": candidate_state["development_attempts"],
                "correct": candidate_state["development_correct"],
            },
            "prediction": prediction,
        },
        "invariants": {
            "oracle_used_by_kt": False,
            "probe_updated_oracle_state": private_oracle["oracle_update_applied"],
            "probe_updated_candidate_state": candidate_state["probe_updates_applied"],
        },
    }


def inspect_qmatrix(run: Path, identifier: str) -> dict[str, Any]:
    projection = one(
        read_jsonl(run / "kc" / "item_kc_projection.jsonl"),
        "item_id",
        identifier,
    )
    edges = [
        row
        for row in read_jsonl(run / "qmatrix" / "item_kc_edges.jsonl")
        if row["item_id"] == identifier
    ]
    return {
        "item_id": identifier,
        "kc_ids": projection["kc_ids"],
        "projection": projection,
        "edges": edges,
        "reason": "derived by applying the frozen KC policy to this accepted item realization",
    }


def inspect_trace(run: Path, identifier: str) -> dict[str, Any]:
    """Reconstruct an item or fixed-event lineage by joining saved stable IDs."""

    candidates = read_jsonl(run / "items" / "generation" / "candidate_items.jsonl")
    base_events = read_jsonl(run / "simulation" / "base_events.jsonl")
    event = next((row for row in base_events if row["event_id"] == identifier), None)
    item_id = event["item_id"] if event else identifier
    item = one(candidates, "item_id", item_id)
    cell_id = item["canonical_cell_id"]
    canonical_cell = one(read_jsonl(run / "canonical" / "canonical_cells.jsonl"), "canonical_cell_id", cell_id)
    source_edges = [
        row
        for row in read_jsonl(run / "canonical" / "source_cell_edges.jsonl")
        if row["canonical_cell_id"] == cell_id
    ]
    source_ids = {row["egp_id"] for row in source_edges}
    source_descriptors = [
        row
        for row in read_jsonl(run / "source" / "source_subset.jsonl")
        if row["egp_id"] in source_ids
    ]
    mappings = [
        row
        for row in read_jsonl(run / "normalisation" / "final_mappings.jsonl")
        if row["egp_id"] in source_ids
    ]
    realisations = [
        row
        for row in read_jsonl(run / "realisation" / "realisations.jsonl")
        if row["spec"]["canonical_cell_id"] == cell_id
    ]
    item_projection = one(
        read_jsonl(run / "kc" / "item_kc_projection.jsonl"),
        "item_id",
        item_id,
    )
    q_edges = [
        row
        for row in read_jsonl(run / "qmatrix" / "item_kc_edges.jsonl")
        if row["item_id"] == item_id
    ]
    interactions = [row for row in base_events if row["item_id"] == item_id]
    oracle_item_projection = one(
        read_jsonl(run / "simulation" / "oracle_item_projection.jsonl"),
        "item_id",
        item_id,
    )
    projected_interactions = [
        row for row in read_jsonl(run / "kt" / "projected_interactions.jsonl")
        if row["item_id"] == item_id
    ]
    return {
        "source_descriptors": source_descriptors,
        "normalisation_mappings": mappings,
        "canonical_cell": canonical_cell,
        "source_cell_edges": source_edges,
        "supporting_realisations": realisations,
        "item": item,
        "fixed_simulation": {
            "oracle_item_projection": oracle_item_projection,
            "base_event": event,
            "item_events": {"count": len(interactions), "first_five": interactions[:5]},
        },
        "candidate_ontology": {
            "item_kc_projection": item_projection,
            "q_edges": q_edges,
            "projected_event": next(
                (row for row in projected_interactions if event and row["event_id"] == event["event_id"]),
                None,
            ),
            "item_projected_events": {
                "count": len(projected_interactions),
                "first_five": projected_interactions[:5],
            },
        },
        "oracle_model_boundary": "KT reads base events plus candidate KC projection; it never reads oracle artifacts",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect one saved experimental unit.")
    parser.add_argument("kind", choices=("normalisation", "kc", "item", "qmatrix", "event", "kt", "probe", "trace"))
    parser.add_argument("identifier")
    parser.add_argument("--run", default="base")
    args = parser.parse_args()
    run = Path(args.run)
    if not run.is_dir():
        run = ROOT / "runs" / args.run
    if args.kind == "normalisation":
        result = inspect_normalisation(run, args.identifier)
    elif args.kind == "kc":
        result = inspect_kc(run, args.identifier)
    elif args.kind == "item":
        result = inspect_item(run, args.identifier)
    elif args.kind == "qmatrix":
        result = inspect_qmatrix(run, args.identifier)
    elif args.kind in {"event", "kt"}:
        result = inspect_kt(run, args.identifier)
    elif args.kind == "probe":
        result = inspect_probe(run, args.identifier)
    else:
        result = inspect_trace(run, args.identifier)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
