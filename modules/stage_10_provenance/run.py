"""Build the small typed lineage graph used by the current experiment."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from shared.utils.contracts import validate_jsonl
from shared.utils.io import ROOT, display_path, read_json, read_jsonl, sha256_file, utc_now, write_json, write_jsonl
from shared.utils.manifests import write_stage_manifest
from shared.utils.research import prepare_stage_directory


def provenance_edge(kind: str, source: str, target: str, evidence: dict[str, Any]) -> dict[str, Any]:
    basis = json.dumps([kind, source, target, evidence], sort_keys=True, separators=(",", ":"))
    return {
        "provenance_edge_id": "PROV_" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16].upper(),
        "edge_type": kind,
        "source_node": source,
        "target_node": target,
        "evidence": evidence,
    }


def build_graph(
    mapping_provenance: list[dict[str, Any]],
    source_edges: list[dict[str, Any]],
    items: list[dict[str, Any]],
    q_edges: list[dict[str, Any]],
    interactions: list[dict[str, Any]],
    methodology: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    methodology = methodology or {}
    mapping_by_source = {row["egp_id"]: row for row in mapping_provenance}
    q_by_item: dict[str, list[dict[str, Any]]] = defaultdict(list)
    events_by_item: dict[str, list[str]] = defaultdict(list)
    sources_by_cell: dict[str, set[str]] = defaultdict(set)
    for row in q_edges:
        q_by_item[row["item_id"]].append(row)
    for row in interactions:
        events_by_item[row["item_id"]].append(row["event_id"])
    for row in source_edges:
        sources_by_cell[row["canonical_cell_id"]].add(row["egp_id"])

    edges: list[dict[str, Any]] = []
    for egp_id, row in sorted(mapping_by_source.items()):
        phase1 = f"PHASE1:{row['primary_unit_id']}"
        edges.append(
            provenance_edge(
                "SOURCE_TO_PHASE1",
                f"EGP:{egp_id}",
                phase1,
                {"sha256": row["phase1_sha256"], "methodology": methodology.get("normalization")},
            )
        )
        if row["final_phase"] == 2:
            edges.append(
                provenance_edge(
                    "PHASE1_TO_PHASE2",
                    phase1,
                    f"PHASE2:{row['primary_unit_id']}",
                    {"sha256": row["phase2_sha256"]},
                )
            )
    for row in source_edges:
        source = mapping_by_source[row["egp_id"]]
        final_node = f"PHASE{source['final_phase']}:{source['primary_unit_id']}"
        edges.append(
            provenance_edge(
                "FINAL_MAPPING_TO_CELL",
                final_node,
                row["canonical_cell_id"],
                {
                    "egp_id": row["egp_id"],
                    "source_cell_index": row["source_cell_index"],
                    "source_mapping_result": row["source_mapping_result"],
                    "methodology": methodology.get("canonical"),
                },
            )
        )
    for item in items:
        realization_id = item["realization_spec"]["realization_id"]
        edges.append(
            provenance_edge(
                "CELL_TO_REALIZATION",
                item["canonical_cell_id"],
                realization_id,
                {
                    "source_descriptor_id": item["realization_spec"]["source_descriptor_id"],
                    "realization_version": item["provenance"]["realization_version"],
                    "methodology": methodology.get("realization"),
                },
            )
        )
        edges.append(
            provenance_edge(
                "REALIZATION_TO_ITEM",
                realization_id,
                item["item_id"],
                {
                    "item_family": item["item_family"],
                    "item_method_version": item["provenance"]["item_method_version"],
                    "methodology": methodology.get("items"),
                },
            )
        )
        for q_edge in q_by_item[item["item_id"]]:
            edges.append(
                provenance_edge(
                    "ITEM_TO_KC",
                    item["item_id"],
                    q_edge["kc_id"],
                    {
                        "q_edge_id": q_edge["edge_id"],
                        "activation_rule": q_edge["activation_rule"],
                        "manual_post_hoc": False,
                        "kc_methodology": methodology.get("kc"),
                        "qmatrix_methodology": methodology.get("qmatrix"),
                    },
                )
            )
        for event_id in events_by_item[item["item_id"]]:
            edges.append(
                provenance_edge(
                    "ITEM_TO_INTERACTION",
                    item["item_id"],
                    event_id,
                    {"dataset": "KT_DATASET_v1", "methodology": methodology.get("simulation")},
                )
            )

    errors: list[str] = []
    item_audit = []
    selected: dict[str, dict[str, Any]] = {}
    for item in sorted(items, key=lambda row: row["item_id"]):
        selected.setdefault(item["primary_kc_id"], item)
    event_counts = {len(events_by_item[item["item_id"]]) for item in items}
    expected_events_per_item = next(iter(event_counts)) if len(event_counts) == 1 else None
    for kc_id, item in sorted(selected.items()):
        row_errors = []
        if not set(item["source_descriptor_ids"]) <= sources_by_cell[item["canonical_cell_id"]]:
            row_errors.append("item source set not supported by source-cell edges")
        if {row["kc_id"] for row in q_by_item[item["item_id"]]} != set(item["all_kc_ids"]):
            row_errors.append("item and Q-matrix KC sets differ")
        if expected_events_per_item is None or len(events_by_item[item["item_id"]]) != expected_events_per_item:
            row_errors.append("interaction count is not constant across items")
        errors.extend(f"{item['item_id']}: {message}" for message in row_errors)
        item_audit.append(
            {
                "primary_kc_id": kc_id,
                "item_id": item["item_id"],
                "canonical_cell_id": item["canonical_cell_id"],
                "source_descriptor_count": len(item["source_descriptor_ids"]),
                "q_edge_count": len(q_by_item[item["item_id"]]),
                "interaction_count": len(events_by_item[item["item_id"]]),
                "status": "PASS" if not row_errors else "FAIL",
                "errors": row_errors,
            }
        )
    ordered = sorted(edges, key=lambda row: row["provenance_edge_id"])
    if len({row["provenance_edge_id"] for row in ordered}) != len(ordered):
        errors.append("duplicate provenance edge IDs")
    edge_type_counts: dict[str, int] = defaultdict(int)
    for row in ordered:
        edge_type_counts[row["edge_type"]] += 1
    audit = {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "edge_count": len(ordered),
        "edge_type_counts": dict(sorted(edge_type_counts.items())),
        "expected_interactions_per_item": expected_events_per_item,
        "stratified_item_audit": item_audit,
        "automated_lineage_check_not_human_validation": True,
    }
    return ordered, audit


def run_stage(run_dir: Path, config: dict[str, Any], experiment_manifest: Path, command: list[str]) -> None:
    started = utc_now()
    output = run_dir / "provenance"
    prepare_stage_directory(output)
    source_path = run_dir / "source" / "source_subset.jsonl"
    mappings_path = run_dir / "normalization" / "final_mappings.jsonl"
    mapping_path = run_dir / "normalization" / "mapping_provenance.jsonl"
    source_edges_path = run_dir / "canonical" / "source_cell_edges.jsonl"
    realizations_path = run_dir / "realization" / "realizations.jsonl"
    items_path = run_dir / "items" / "validation" / "accepted_items.jsonl"
    q_edges_path = run_dir / "qmatrix" / "item_kc_edges.jsonl"
    interactions_path = run_dir / "simulation" / "observable_interactions.jsonl"
    source_ids = {row["egp_id"] for row in read_jsonl(source_path)}
    mapping_ids = {row["egp_id"] for row in read_jsonl(mappings_path)}
    if mapping_ids != source_ids:
        raise RuntimeError("provenance input source and final-mapping IDs differ")
    # Reading the realization output makes the declared graph boundary explicit
    # even though item-level realization IDs live in ItemSpec records.
    read_jsonl(realizations_path)
    methodology = {}
    methodology_manifests = []
    for stage in ("source", "normalization", "canonical", "realization", "kc", "items", "qmatrix", "simulation"):
        manifest_path = run_dir / stage / "manifest.json"
        methodology_manifests.append(manifest_path)
        manifest = read_json(manifest_path)
        fingerprint_basis = manifest.get("fingerprint_basis", {})
        methodology[stage] = {
            "manifest_path": display_path(manifest_path),
            "manifest_sha256": sha256_file(manifest_path),
            "stage_fingerprint": manifest.get("stage_fingerprint"),
            "module": manifest.get("module"),
            "version": manifest.get("version"),
            "resolved_configuration": fingerprint_basis.get("configuration"),
            "scientific_resources": fingerprint_basis.get("scientific_resources", manifest.get("configs", [])),
            "implementation": fingerprint_basis.get("implementation", manifest.get("code", [])),
        }
    edges, audit = build_graph(
        read_jsonl(mapping_path),
        read_jsonl(source_edges_path),
        read_jsonl(items_path),
        read_jsonl(q_edges_path),
        read_jsonl(interactions_path),
        methodology,
    )
    if audit["status"] != "PASS":
        raise RuntimeError(f"provenance audit failed: {audit['errors'][:5]}")
    edges_path = output / "provenance_edges.jsonl"
    audit_path = output / "provenance_audit.json"
    methodology_path = output / "methodology.json"
    write_jsonl(edges_path, edges)
    write_json(audit_path, audit)
    write_json(methodology_path, methodology)
    provenance_schema = ROOT / "modules/stage_10_provenance/schemas/provenance_edge.schema.json"
    validate_jsonl(edges_path, provenance_schema, label="provenance output ProvenanceEdge")
    write_stage_manifest(
        output,
        module="provenance",
        version=config["version"],
        started_utc=started,
        command=command,
        inputs=[
            source_path, mappings_path, mapping_path, source_edges_path,
            realizations_path, items_path, q_edges_path, interactions_path,
            *methodology_manifests,
        ],
        configs=[experiment_manifest, provenance_schema],
        code=[Path(__file__)],
        outputs=[edges_path, audit_path, methodology_path],
        details={"provenance_edges": len(edges), "typed_graph": True, "status": audit["status"]},
    )
