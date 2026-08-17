"""Cross-stage contract checks for a completed harness run."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from jsonschema.validators import validator_for

from modules.canonical.run import stable_cell_id
from shared.utils.io import DIMENSIONS, ROOT, read_json, read_jsonl, repo_path, utc_now
from shared.utils.manifests import verify_descriptor


STAGES = ("source", "normalization", "canonical", "realization", "kc", "items", "qmatrix", "simulation", "kt", "provenance")
FORBIDDEN_OBSERVABLE = {
    "profile", "pre_mastery", "post_mastery", "response_probability", "random_draw",
    "target_answer", "accepted_answers", "prompt", "definition", "activation_rule",
}


def _manifest_errors(run_dir: Path) -> list[str]:
    errors: list[str] = []
    manifests = sorted(run_dir.rglob("manifest.json"))
    if not manifests:
        return ["no stage manifests found"]
    for path in manifests:
        try:
            value = read_json(path)
        except Exception as error:
            errors.append(f"{path}: cannot read manifest: {error}")
            continue
        for field in ("module", "version", "command", "inputs", "configs", "code", "outputs", "validation_status"):
            if field not in value:
                errors.append(f"{path}: missing {field}")
        for category in ("inputs", "configs", "code", "outputs"):
            for record in value.get(category, []):
                problem = verify_descriptor(record)
                if problem:
                    errors.append(f"{path}: {problem}")
        if value.get("validation_status") != "PASS":
            errors.append(f"{path}: validation status is not PASS")
    return errors


def verify_manifests(run_dir: Path) -> list[str]:
    """Public lightweight check used before immutable-stage reuse."""
    return _manifest_errors(run_dir.resolve())


def _schema_errors(path: Path, schema_path: Path, label: str) -> list[str]:
    schema = read_json(schema_path)
    validator_class = validator_for(schema)
    validator_class.check_schema(schema)
    validator = validator_class(schema)
    errors: list[str] = []
    for index, row in enumerate(read_jsonl(path), 1):
        for error in validator.iter_errors(row):
            errors.append(f"{label} row {index}: {error.message}")
            if len(errors) >= 100:
                return errors
    return errors


def _read_q(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = reader.fieldnames or []
    if not fields or fields[0] != "item_id":
        raise ValueError("Q-matrix first column must be item_id")
    return fields[1:], rows


def validate_run(run_dir: Path, *, compare_reference: bool = True) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    errors = _manifest_errors(run_dir)
    warnings: list[str] = []
    required = {
        "experiment_manifest": run_dir / "experiment_manifest.json",
        "source": run_dir / "source" / "source_subset.jsonl",
        "source_units": run_dir / "source" / "annotation_units.jsonl",
        "phase1": run_dir / "normalization" / "phase1.jsonl",
        "phase2": run_dir / "normalization" / "phase2.jsonl",
        "mappings": run_dir / "normalization" / "final_mappings.jsonl",
        "mapping_provenance": run_dir / "normalization" / "mapping_provenance.jsonl",
        "normalization_duplicates": run_dir / "normalization" / "duplicate_diagnostics.jsonl",
        "schema_failures": run_dir / "normalization" / "schema_failures.jsonl",
        "cells": run_dir / "canonical" / "canonical_cells.jsonl",
        "source_edges": run_dir / "canonical" / "source_cell_edges.jsonl",
        "realizations": run_dir / "realization" / "realizations.jsonl",
        "kc_inventory": run_dir / "kc" / "kc_inventory.jsonl",
        "projection": run_dir / "kc" / "cell_kc_projection.jsonl",
        "candidates": run_dir / "items" / "generation" / "candidate_items.jsonl",
        "item_units": run_dir / "items" / "generation" / "validation_units.jsonl",
        "accepted": run_dir / "items" / "validation" / "accepted_items.jsonl",
        "rejected": run_dir / "items" / "validation" / "rejected_items.jsonl",
        "item_duplicates": run_dir / "items" / "validation" / "duplicate_diagnostics.jsonl",
        "q_matrix": run_dir / "qmatrix" / "q_matrix.csv",
        "q_edges": run_dir / "qmatrix" / "item_kc_edges.jsonl",
        "observable": run_dir / "simulation" / "observable_interactions.jsonl",
        "oracle": run_dir / "simulation" / "oracle_interactions.jsonl",
        "learners_file": run_dir / "simulation" / "learners.jsonl",
        "metrics": run_dir / "kt" / "metrics.json",
        "provenance": run_dir / "provenance" / "provenance_edges.jsonl",
        "provenance_audit": run_dir / "provenance" / "provenance_audit.json",
    }
    required.update({f"{stage}_manifest": run_dir / stage / "manifest.json" for stage in STAGES})
    required["item_generation_manifest"] = run_dir / "items" / "generation" / "manifest.json"
    required["item_validation_manifest"] = run_dir / "items" / "validation" / "manifest.json"
    missing = [f"missing required output {name}: {path}" for name, path in required.items() if not path.is_file()]
    errors.extend(missing)
    if missing:
        return {
            "status": "FAIL", "completed": False, "validated_utc": utc_now(),
            "run": str(run_dir), "errors": errors, "warnings": warnings, "counts": {},
        }

    experiment_record = read_json(required["experiment_manifest"])
    config = experiment_record.get("resolved_config", experiment_record)
    source = read_jsonl(required["source"])
    source_units = read_jsonl(required["source_units"])
    phase1 = read_jsonl(required["phase1"])
    phase2 = read_jsonl(required["phase2"])
    mappings = read_jsonl(required["mappings"])
    mapping_provenance = read_jsonl(required["mapping_provenance"])
    normalization_duplicates = read_jsonl(required["normalization_duplicates"])
    cells = read_jsonl(required["cells"])
    source_edges = read_jsonl(required["source_edges"])
    realizations = read_jsonl(required["realizations"])
    cards = read_jsonl(required["kc_inventory"])
    projections = read_jsonl(required["projection"])
    candidates = read_jsonl(required["candidates"])
    item_units = read_jsonl(required["item_units"])
    accepted = read_jsonl(required["accepted"])
    rejected = read_jsonl(required["rejected"])
    item_duplicates = read_jsonl(required["item_duplicates"])
    q_edges = read_jsonl(required["q_edges"])
    observed = read_jsonl(required["observable"])
    oracle = read_jsonl(required["oracle"])
    learners = read_jsonl(required["learners_file"])
    provenance = read_jsonl(required["provenance"])

    schema_jobs = (
        (required["source"], ROOT / "shared/schemas/source_record.schema.json", "source"),
        (required["mappings"], repo_path(config["normalization"]["output_schema"]), "mapping"),
        (required["accepted"], ROOT / "shared/schemas/item.schema.json", "accepted item"),
        (required["observable"], ROOT / "shared/schemas/interaction.schema.json", "observable interaction"),
        (required["provenance"], ROOT / "shared/schemas/provenance_edge.schema.json", "provenance edge"),
    )
    for data_path, schema_path, label in schema_jobs:
        errors.extend(_schema_errors(data_path, schema_path, label))

    source_ids = {row["egp_id"] for row in source}
    if len(source_ids) != len(source):
        errors.append("source descriptor IDs are not unique")
    mapping_ids = {row["egp_id"] for row in mappings}
    if mapping_ids != source_ids:
        errors.append("normalization mapping IDs differ from source IDs")
    if {row["egp_id"] for row in mapping_provenance} != source_ids:
        errors.append("mapping provenance IDs differ from source IDs")
    expected_normalization_duplicates = sum(row["duplicate_of"] is not None for row in source_units)
    if len(normalization_duplicates) != expected_normalization_duplicates:
        errors.append(
            f"normalization duplicate diagnostics number {len(normalization_duplicates)}; "
            f"annotation units declare {expected_normalization_duplicates}"
        )

    cell_by_id: dict[str, dict[str, Any]] = {}
    for row in cells:
        cell = row.get("cell", {})
        if set(cell) != set(DIMENSIONS) or not all(isinstance(cell.get(key), str) for key in DIMENSIONS):
            errors.append(f"{row.get('canonical_cell_id')}: canonical cell is not six scalar values")
            continue
        expected_id = stable_cell_id(cell)
        if row["canonical_cell_id"] != expected_id:
            errors.append(f"{row['canonical_cell_id']}: unstable canonical cell ID; expected {expected_id}")
        cell_by_id[row["canonical_cell_id"]] = cell
    if len(cell_by_id) != len(cells):
        errors.append("canonical cell IDs are not unique")
    for edge in source_edges:
        if edge["egp_id"] not in source_ids or edge["canonical_cell_id"] not in cell_by_id:
            errors.append(f"{edge.get('edge_id')}: broken source-cell foreign key")
        if edge.get("source_mapping_result") != "complete":
            errors.append(f"{edge.get('edge_id')}: non-complete mapping expanded")

    realization_schema = repo_path(config["realization"]["schema"])
    realization_validator_class = validator_for(read_json(realization_schema))
    realization_validator = realization_validator_class(read_json(realization_schema))
    for row in realizations:
        spec = row.get("spec", {})
        for error in realization_validator.iter_errors(spec):
            errors.append(f"realization {spec.get('realization_id')}: {error.message}")
        if spec.get("canonical_cell_id") not in cell_by_id or spec.get("source_descriptor_id") not in source_ids:
            errors.append(f"realization {spec.get('realization_id')}: broken cell/source foreign key")

    kc_ids = {row["kc_id"] for row in cards}
    if len(kc_ids) != len(cards):
        errors.append("KC IDs are not unique")
    projection_by_cell = {row["canonical_cell_id"]: row["kc_ids"] for row in projections}
    if set(projection_by_cell) != set(cell_by_id):
        errors.append("KC projection does not cover exactly the canonical cells")
    for cell_id, active in projection_by_cell.items():
        if not active or not set(active) <= kc_ids:
            errors.append(f"{cell_id}: empty or unknown KC activation")

    candidate_ids = {row["item_id"] for row in candidates}
    accepted_by_id = {row["item_id"]: row for row in accepted}
    rejected_ids = {row["item"]["item_id"] for row in rejected}
    if set(accepted_by_id) & rejected_ids or set(accepted_by_id) | rejected_ids != candidate_ids:
        errors.append("accepted/rejected items do not partition candidates")
    expected_item_duplicates = sum(row["duplicate_of"] is not None for row in item_units)
    if len(item_duplicates) != expected_item_duplicates:
        errors.append(
            f"item duplicate diagnostics number {len(item_duplicates)}; "
            f"validation units declare {expected_item_duplicates}"
        )
    for item in accepted:
        if item["canonical_cell_id"] not in cell_by_id or not set(item["source_descriptor_ids"]) <= source_ids:
            errors.append(f"{item['item_id']}: broken item cell/source foreign key")
        if item["all_kc_ids"] != projection_by_cell.get(item["canonical_cell_id"]):
            errors.append(f"{item['item_id']}: stored KC labels differ from cell projection")

    q_kcs, q_rows = _read_q(required["q_matrix"])
    q_by_item: dict[str, set[str]] = defaultdict(set)
    for edge in q_edges:
        q_by_item[edge["item_id"]].add(edge["kc_id"])
        if edge["item_id"] not in accepted_by_id or edge["kc_id"] not in kc_ids:
            errors.append(f"{edge.get('edge_id')}: broken item/KC foreign key")
    if set(q_kcs) != kc_ids or len(q_kcs) != len(kc_ids):
        errors.append("Q-matrix columns differ from KC inventory")
    if {row["item_id"] for row in q_rows} != set(accepted_by_id):
        errors.append("Q-matrix rows differ from accepted item IDs")
    for row in q_rows:
        matrix_active = {kc for kc in q_kcs if row[kc] == "1"}
        if any(row[kc] not in {"0", "1"} for kc in q_kcs):
            errors.append(f"{row['item_id']}: Q row contains a nonbinary value")
        if matrix_active != q_by_item[row["item_id"]] or matrix_active != set(accepted_by_id[row["item_id"]]["all_kc_ids"]):
            errors.append(f"{row['item_id']}: item, Q edge, and Q row KC sets differ")

    event_ids = set()
    by_learner: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in observed:
        if row["event_id"] in event_ids:
            errors.append(f"duplicate event ID: {row['event_id']}")
        event_ids.add(row["event_id"])
        by_learner[row["learner_id"]].append(row)
        leaked = FORBIDDEN_OBSERVABLE & set(row)
        if leaked:
            errors.append(f"{row['event_id']}: observable oracle/content leakage {sorted(leaked)}")
        item = accepted_by_id.get(row["item_id"])
        if item is None or row["canonical_cell_id"] != item["canonical_cell_id"] or set(row["kc_ids"]) != q_by_item[row["item_id"]]:
            errors.append(f"{row['event_id']}: interaction item/cell/KC foreign key mismatch")
        if set(row["opportunity_indices"]) != set(row["kc_ids"]):
            errors.append(f"{row['event_id']}: opportunity-index keys differ from active KCs")
    learner_ids = {row["learner_id"] for row in learners}
    if set(by_learner) != learner_ids:
        errors.append("learner table IDs differ from observable learner IDs")
    event_counts = set()
    for learner_id, rows in by_learner.items():
        rows.sort(key=lambda row: row["sequence_index"])
        event_counts.add(len(rows))
        if [row["sequence_index"] for row in rows] != list(range(1, len(rows) + 1)):
            errors.append(f"{learner_id}: sequence indices are not contiguous")
        if any(rows[index]["timestamp"] >= rows[index + 1]["timestamp"] for index in range(len(rows) - 1)):
            errors.append(f"{learner_id}: chronology is not strictly increasing")
        if not all(Counter(row["item_id"] for row in rows)[item_id] >= 2 for item_id in accepted_by_id):
            errors.append(f"{learner_id}: fewer than two opportunities for an item")
    oracle_ids = {row["event_id"] for row in oracle}
    if oracle_ids != event_ids or len(oracle_ids) != len(oracle):
        errors.append("oracle and observable event IDs do not align one-to-one")

    edge_types: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in provenance:
        edge_types[edge["edge_type"]].append(edge)
    expected_types = {
        "SOURCE_TO_PHASE1", "FINAL_MAPPING_TO_CELL",
        "CELL_TO_REALIZATION", "REALIZATION_TO_ITEM", "ITEM_TO_KC", "ITEM_TO_INTERACTION",
    }
    if any(row["final_phase"] == 2 for row in mapping_provenance):
        expected_types.add("PHASE1_TO_PHASE2")
    if set(edge_types) != expected_types:
        errors.append(f"provenance edge types differ: {sorted(set(edge_types) ^ expected_types)}")
    if {edge["source_node"].removeprefix("EGP:") for edge in edge_types["SOURCE_TO_PHASE1"]} != source_ids:
        errors.append("provenance source-to-Phase-1 coverage mismatch")
    prov_q = {(edge["source_node"], edge["target_node"]) for edge in edge_types["ITEM_TO_KC"]}
    if prov_q != {(edge["item_id"], edge["kc_id"]) for edge in q_edges}:
        errors.append("provenance item-to-KC edges differ from Q edges")
    prov_events = {(edge["source_node"], edge["target_node"]) for edge in edge_types["ITEM_TO_INTERACTION"]}
    if prov_events != {(row["item_id"], row["event_id"]) for row in observed}:
        errors.append("provenance item-to-interaction edges differ from observable data")
    provenance_audit = read_json(required["provenance_audit"])
    if provenance_audit.get("status") != "PASS" or provenance_audit.get("edge_count") != len(provenance):
        errors.append("provenance audit status/count mismatch")

    result_counts = Counter(row["result"] for row in mappings)
    counts = {
        "unique_source_descriptors": len(source_ids),
        "phase1_units": len(phase1),
        "complete_mappings": result_counts["complete"],
        "partial_mappings": result_counts["partial"],
        "out_of_scope": result_counts["out_of_scope"],
        "unresolved": result_counts["unresolved"],
        "schema_failures": len(read_jsonl(required["schema_failures"])),
        "source_cell_edges": len(source_edges),
        "canonical_cells": len(cells),
        "kcs": len(cards),
        "accepted_items": len(accepted),
        "q_rows": len(q_rows),
        "q_columns": len(q_kcs),
        "q_edges": len(q_edges),
        "learners": len(learners),
        "events_per_learner": next(iter(event_counts)) if len(event_counts) == 1 else None,
        "interactions": len(observed),
        "provenance_edges": len(provenance),
    }
    reference_differences: dict[str, dict[str, Any]] = {}
    if compare_reference and config.get("experiment_id") == "current" and config.get("reference"):
        expected = read_json(repo_path(config["reference"]))
        for key, expected_value in expected.items():
            if counts.get(key) != expected_value:
                reference_differences[key] = {"expected": expected_value, "observed": counts.get(key)}
        if reference_differences:
            errors.append(f"reference headline counts differ: {reference_differences}")
        sanity_path = ROOT / "reference/current/kt_sanity.json"
        if sanity_path.is_file():
            sanity = read_json(sanity_path)
            metrics = read_json(required["metrics"])
            for name in ("empirical", "bkt", "logistic"):
                if name in metrics.get("techniques", {}):
                    observed_auc = metrics["techniques"][name]["test"]["auc"]
                    if abs(observed_auc - sanity[name]) > sanity["tolerance"]:
                        warnings.append(
                            f"{name} test AUC {observed_auc:.6f} is outside the approximate "
                            f"reference tolerance around {sanity[name]:.6f}"
                        )
    return {
        "status": "PASS" if not errors else "FAIL",
        "completed": not errors,
        "validated_utc": utc_now(),
        "run": str(run_dir),
        "experiment_id": config.get("experiment_id"),
        "errors": errors,
        "warnings": warnings,
        "counts": counts,
        "reference_count_differences": reference_differences,
        "claims": {
            "synthetic_interactions_are_simulator_truth": True,
            "kt_metrics_are_technical_sanity_only": True,
            "automated_item_checks_are_not_human_validation": True,
        },
    }
