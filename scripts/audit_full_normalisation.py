#!/usr/bin/env python3
"""Audit full-source normalisation without publishing restricted source text.

The input source stream may contain descriptor text because it lives in the
private construction evidence directory.  This script uses only source IDs and
the declared categorical fields in its output.  In particular, mapping ``note``
values and technical error messages are never copied into the audit artifact.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.canonicalise import validate_cell
from grammar_kt.full_normalisation import sha256_file
from grammar_kt.io import read_jsonl, read_yaml, write_json
from grammar_kt.normalise import (
    _validate_mapping,
    _validate_phase2_transition,
)


RESULT_ORDER = ("complete", "partial", "unresolved", "out_of_scope")
CATEGORY_FIELDS = ("cefr", "supercategory", "subcategory")
SAFE_CODE = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")


def _fraction(numerator: int, denominator: int) -> dict[str, int | float | None]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": round(numerator / denominator, 6) if denominator else None,
    }


def _ordered_result_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(row["result"] for row in rows)
    return {result: counts.get(result, 0) for result in RESULT_ORDER}


def _result_summary(
    rows: list[dict[str, Any]], source_denominator: int
) -> dict[str, Any]:
    counts = _ordered_result_counts(rows)
    mapped = len(rows)
    return {
        "mapped_denominator": mapped,
        "source_denominator": source_denominator,
        "counts": counts,
        "rates_among_mapped": {
            result: _fraction(count, mapped) for result, count in counts.items()
        },
        "rates_of_source_inventory": {
            result: _fraction(count, source_denominator)
            for result, count in counts.items()
        },
    }


def _index_source(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    required = {"source_id", *CATEGORY_FIELDS, "examples"}
    for row in rows:
        source_id = row.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError("typed source contains a missing or invalid source_id")
        if source_id in indexed:
            raise ValueError(f"typed source contains duplicate source_id: {source_id}")
        missing = required - set(row)
        if missing:
            raise ValueError(
                f"typed source {source_id} lacks required audit fields: {sorted(missing)}"
            )
        indexed[source_id] = row
    return indexed


def _load_mapping_stream(
    path: Path, label: str
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], set[str]]:
    """Read direct mappings or mapping-bearing checkpoint records.

    A checkpoint record may have ``status`` and a nullable ``mapping``.  The
    record still contributes to technical coverage when its mapping is null.
    """

    mappings: dict[str, dict[str, Any]] = {}
    statuses: list[dict[str, Any]] = []
    record_ids: set[str] = set()
    for row in read_jsonl(path):
        source_id = row.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError(f"{label} contains a missing or invalid source_id")
        if source_id in record_ids:
            raise ValueError(f"{label} contains duplicate source_id: {source_id}")
        record_ids.add(source_id)

        if "result" in row and "cells" in row:
            mapping = row
        elif "mapping" in row:
            mapping = row["mapping"]
            statuses.append(row)
            if mapping is not None and mapping.get("source_id") != source_id:
                raise ValueError(
                    f"{label} checkpoint source_id differs from nested mapping: "
                    f"{source_id}"
                )
        else:
            raise ValueError(
                f"{label} row {source_id} is neither a mapping nor a mapping checkpoint"
            )
        if mapping is not None:
            mappings[source_id] = mapping
    return mappings, statuses, record_ids


def _load_status_stream(path: Path, label: str) -> list[dict[str, Any]]:
    rows = read_jsonl(path)
    seen: set[str] = set()
    for row in rows:
        source_id = row.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError(f"{label} contains a missing or invalid source_id")
        if source_id in seen:
            raise ValueError(f"{label} contains duplicate source_id: {source_id}")
        seen.add(source_id)
    return rows


def _safe_counter(values: Iterable[Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for raw in values:
        value = str(raw)
        counts[value if SAFE_CODE.fullmatch(value) else "other_unpublished"] += 1
    return dict(sorted(counts.items()))


def _technical_summary(
    rows: list[dict[str, Any]], allowed_ids: set[str], label: str
) -> dict[str, Any] | None:
    if not rows:
        return None
    ids = {row["source_id"] for row in rows}
    unexpected = ids - allowed_ids
    if unexpected:
        raise ValueError(
            f"{label} contains {len(unexpected)} source IDs outside its declared cohort"
        )
    runtimes = [
        float(row["runtime_seconds"])
        for row in rows
        if isinstance(row.get("runtime_seconds"), (int, float))
    ]
    errors = [
        error
        for row in rows
        for error in row.get("errors", [])
        if isinstance(error, dict)
    ]
    return {
        "recorded_rows": len(rows),
        "cohort_denominator": len(allowed_ids),
        "coverage": _fraction(len(ids), len(allowed_ids)),
        "status_counts": _safe_counter(
            row.get("status", "status_missing") for row in rows
        ),
        "attempt_count_distribution": _safe_counter(
            row.get("attempt_count", "attempt_count_missing") for row in rows
        ),
        "rows_with_retries": sum(
            isinstance(row.get("attempt_count"), int)
            and row["attempt_count"] > 1
            for row in rows
        ),
        "error_type_counts": _safe_counter(
            error.get("error_type", "error_type_missing") for error in errors
        ),
        "error_messages_published": False,
        "runtime_seconds": {
            "observed_denominator": len(runtimes),
            "total": round(sum(runtimes), 6),
            "mean": round(sum(runtimes) / len(runtimes), 6)
            if runtimes
            else None,
            "minimum": round(min(runtimes), 6) if runtimes else None,
            "maximum": round(max(runtimes), 6) if runtimes else None,
        },
    }


def _normalise_value(value: Any) -> Any:
    if isinstance(value, list):
        return sorted(value)
    return value


def _cell_signature(cell: dict[str, Any], dimensions: list[str]) -> str:
    return json.dumps(
        {name: _normalise_value(cell[name]) for name in dimensions},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _mapping_cell_multiset(
    mapping: dict[str, Any], dimensions: list[str]
) -> tuple[str, ...]:
    return tuple(sorted(_cell_signature(cell, dimensions) for cell in mapping["cells"]))


def _uncertain_dimensions(
    mapping: dict[str, Any], dimensions: list[str]
) -> tuple[str, ...]:
    return tuple(
        name
        for name in dimensions
        if any(cell[name] is None or isinstance(cell[name], list) for cell in mapping["cells"])
    )


def _signature_label(values: Iterable[str]) -> str:
    values = tuple(values)
    return "+".join(values) if values else "none"


def _branch_summary(
    rows: list[dict[str, Any]], dimensions: list[str]
) -> dict[str, Any]:
    by_result = {
        result: sum(len(row["cells"]) for row in rows if row["result"] == result)
        for result in RESULT_ORDER
    }
    branch_counts = Counter(len(row["cells"]) for row in rows)
    exact_branches = sum(
        all(cell[name] is not None and not isinstance(cell[name], list) for name in dimensions)
        for row in rows
        for cell in row["cells"]
    )
    duplicate_multisets = sum(
        len(_mapping_cell_multiset(row, dimensions))
        != len(set(_mapping_cell_multiset(row, dimensions)))
        for row in rows
    )
    exact_signatures = {
        _cell_signature(cell, dimensions)
        for row in rows
        for cell in row["cells"]
        if all(cell[name] is not None and not isinstance(cell[name], list) for name in dimensions)
    }
    return {
        "mapping_denominator": len(rows),
        "total_branches": sum(by_result.values()),
        "branches_by_result": by_result,
        "branch_count_distribution": {
            str(count): frequency for count, frequency in sorted(branch_counts.items())
        },
        "mappings_with_multiple_branches": sum(len(row["cells"]) > 1 for row in rows),
        "mappings_with_duplicate_branches": duplicate_multisets,
        "exact_branches": exact_branches,
        "uncertain_branches": sum(by_result.values()) - exact_branches,
        "unique_exact_feature_cells": len(exact_signatures),
    }


def _eligibility_summary(
    rows: list[dict[str, Any]], source_by_id: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    partial = [row for row in rows if row["result"] == "partial"]
    eligible = [row for row in partial if row["phase2_eligible"]]
    eligible_with_examples = [
        row for row in eligible if bool(source_by_id[row["source_id"]]["examples"])
    ]
    signatures = Counter(
        _signature_label(row["phase2_eligible"]) for row in eligible
    )
    return {
        "all_mappings_denominator": len(rows),
        "partial_mappings_denominator": len(partial),
        "eligible_partial": _fraction(len(eligible), len(partial)),
        "eligible_partial_of_all_mappings": _fraction(len(eligible), len(rows)),
        "eligible_with_examples": len(eligible_with_examples),
        "eligible_without_examples": len(eligible) - len(eligible_with_examples),
        "eligible_dimension_signatures": dict(sorted(signatures.items())),
    }


def _category_summary(
    rows: list[dict[str, Any]], source_by_id: dict[str, dict[str, Any]], field: str
) -> dict[str, Any]:
    rows_by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_counts = Counter(str(row[field]) for row in source_by_id.values())
    for row in rows:
        rows_by_category[str(source_by_id[row["source_id"]][field])].append(row)

    output = {}
    for category in sorted(source_counts):
        category_rows = rows_by_category[category]
        mapped = len(category_rows)
        counts = _ordered_result_counts(category_rows)
        partial = sum(row["result"] == "partial" for row in category_rows)
        eligible = sum(
            row["result"] == "partial" and bool(row["phase2_eligible"])
            for row in category_rows
        )
        output[category] = {
            "source_rows": source_counts[category],
            "mapped_rows": mapped,
            "mapping_coverage": _fraction(mapped, source_counts[category]),
            "result_counts": counts,
            "result_rates_among_mapped": {
                result: _fraction(count, mapped) for result, count in counts.items()
            },
            "partial_denominator": partial,
            "phase2_eligible": eligible,
            "phase2_eligibility_among_partial": _fraction(eligible, partial),
            "branches": sum(len(row["cells"]) for row in category_rows),
        }
    return output


def _failure_groups(
    rows: list[dict[str, Any]],
    source_by_id: dict[str, dict[str, Any]],
    dimensions: list[str],
) -> dict[str, Any]:
    failures = [row for row in rows if row["result"] in {"partial", "unresolved"}]
    return {
        "grouping_basis": [
            "mapping_result",
            "source_cefr",
            "source_supercategory",
            "source_subcategory",
            "uncertain_dimensions",
            "phase2_eligible_dimensions",
        ],
        "structured_reason_code_available": False,
        "denominator_partial_or_unresolved": len(failures),
        "by_result": _ordered_result_counts(failures),
        "by_cefr": dict(
            sorted(Counter(str(source_by_id[row["source_id"]]["cefr"]) for row in failures).items())
        ),
        "by_supercategory": dict(
            sorted(
                Counter(
                    str(source_by_id[row["source_id"]]["supercategory"])
                    for row in failures
                ).items()
            )
        ),
        "by_subcategory": dict(
            sorted(
                Counter(
                    str(source_by_id[row["source_id"]]["subcategory"])
                    for row in failures
                ).items()
            )
        ),
        "by_uncertain_dimension_signature": dict(
            sorted(
                Counter(
                    _signature_label(_uncertain_dimensions(row, dimensions))
                    for row in failures
                ).items()
            )
        ),
        "by_phase2_eligible_dimension_signature": dict(
            sorted(
                Counter(
                    _signature_label(row["phase2_eligible"]) for row in failures
                ).items()
            )
        ),
        "rows_with_nonempty_note_suppressed": sum(bool(row.get("note")) for row in failures),
        "free_text_notes_published": False,
    }


def _stage_summary(
    rows: list[dict[str, Any]],
    source_by_id: dict[str, dict[str, Any]],
    dimensions: list[str],
) -> dict[str, Any]:
    return {
        "results": _result_summary(rows, len(source_by_id)),
        "eligibility": _eligibility_summary(rows, source_by_id),
        "branches": _branch_summary(rows, dimensions),
        "by_cefr": _category_summary(rows, source_by_id, "cefr"),
        "by_supercategory": _category_summary(rows, source_by_id, "supercategory"),
        "by_subcategory": _category_summary(rows, source_by_id, "subcategory"),
        "partial_unresolved_groups": _failure_groups(rows, source_by_id, dimensions),
    }


def _assert_id_coverage(
    record_ids: set[str],
    expected_ids: set[str],
    label: str,
    *,
    allow_incomplete: bool,
) -> dict[str, Any]:
    unexpected = record_ids - expected_ids
    if unexpected:
        raise ValueError(
            f"{label} contains {len(unexpected)} source IDs outside the expected set"
        )
    missing = expected_ids - record_ids
    if missing and not allow_incomplete:
        raise ValueError(
            f"{label} source-ID set mismatch: {len(missing)} expected IDs are missing"
        )
    return {
        "expected_source_ids": len(expected_ids),
        "recorded_source_ids": len(record_ids),
        "missing_source_ids": len(missing),
        "unexpected_source_ids": 0,
        "coverage": _fraction(len(record_ids), len(expected_ids)),
        "complete": not missing,
    }


def _transition_summary(
    phase1_by_id: dict[str, dict[str, Any]],
    phase2_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    transitions = Counter(
        f"{phase1_by_id[source_id]['result']}->{mapping['result']}"
        for source_id, mapping in phase2_by_id.items()
    )
    branch_changes = Counter()
    initial_total = 0
    final_total = 0
    for source_id, mapping in phase2_by_id.items():
        initial = len(phase1_by_id[source_id]["cells"])
        final = len(mapping["cells"])
        initial_total += initial
        final_total += final
        if final > initial:
            branch_changes["expanded"] += 1
        elif final < initial:
            branch_changes["contracted"] += 1
        else:
            branch_changes["unchanged"] += 1
    denominator = len(phase2_by_id)
    completed = sum(row["result"] == "complete" for row in phase2_by_id.values())
    return {
        "valid_transition_denominator": denominator,
        "result_transitions": dict(sorted(transitions.items())),
        "resolved_to_complete": _fraction(completed, denominator),
        "branch_expansion": {
            "initial_branches": initial_total,
            "final_branches": final_total,
            "net_branches": final_total - initial_total,
            "final_to_initial_ratio": round(final_total / initial_total, 6)
            if initial_total
            else None,
            "descriptor_change_counts": {
                key: branch_changes.get(key, 0)
                for key in ("expanded", "unchanged", "contracted")
            },
        },
    }


def _canonical_audit(
    cells_path: Path | None,
    relations_path: Path | None,
    final_rows: list[dict[str, Any]],
    source_ids: set[str],
    schema: dict[str, Any],
) -> dict[str, Any] | None:
    if cells_path is None and relations_path is None:
        return None
    if cells_path is None and relations_path is not None:
        raise ValueError("source-cell relations cannot be audited without canonical cells")

    assert cells_path is not None
    dimensions = list(schema["dimension_order"])
    cells = read_jsonl(cells_path)
    by_id: dict[str, dict[str, Any]] = {}
    by_signature: dict[str, dict[str, Any]] = {}
    for row in cells:
        cell_id = row.get("cell_id")
        if not isinstance(cell_id, str) or not cell_id:
            raise ValueError("canonical cells contain a missing or invalid cell_id")
        if cell_id in by_id:
            raise ValueError(f"canonical cells contain duplicate cell_id: {cell_id}")
        features = row.get("features")
        if not isinstance(features, dict):
            raise ValueError(f"canonical cell {cell_id} lacks a feature mapping")
        validate_cell(features, schema)
        signature = _cell_signature(features, dimensions)
        if signature in by_signature:
            raise ValueError("canonical cells contain duplicate feature tuples")
        contributing_ids = row.get("source_ids", [])
        if (
            not isinstance(contributing_ids, list)
            or len(contributing_ids) != len(set(contributing_ids))
            or not set(contributing_ids) <= source_ids
        ):
            raise ValueError(f"canonical cell {cell_id} has invalid source_ids")
        by_id[cell_id] = row
        by_signature[signature] = row

    expected_support: dict[str, set[str]] = defaultdict(set)
    expected_relations: set[tuple[str, str, int]] = set()
    unlinked_expected_branches = 0
    for mapping in final_rows:
        if mapping["result"] != "complete":
            continue
        for branch_index, raw_cell in enumerate(mapping["cells"]):
            signature = _cell_signature(raw_cell, dimensions)
            expected_support[signature].add(mapping["source_id"])
            if signature in by_signature:
                expected_relations.add(
                    (
                        mapping["source_id"],
                        by_signature[signature]["cell_id"],
                        branch_index,
                    )
                )
            else:
                unlinked_expected_branches += 1

    artifact_signatures = set(by_signature)
    expected_signatures = set(expected_support)
    support_matches = sum(
        set(row.get("source_ids", [])) == expected_support.get(signature, set())
        for signature, row in by_signature.items()
    )
    result: dict[str, Any] = {
        "canonical_cells": len(cells),
        "expected_unique_complete_feature_cells": len(expected_signatures),
        "feature_set_match": artifact_signatures == expected_signatures,
        "artifact_only_feature_cells": len(artifact_signatures - expected_signatures),
        "mapping_only_feature_cells": len(expected_signatures - artifact_signatures),
        "cell_source_support_matches": support_matches,
        "cell_source_support_denominator": len(cells),
        "all_cell_source_support_matches": support_matches == len(cells),
        "canonical_value_support": {
            dimension: dict(
                sorted(Counter(row["features"][dimension] for row in cells).items())
            )
            for dimension in dimensions
        },
    }

    if relations_path is not None:
        relations = read_jsonl(relations_path)
        actual_relations: set[tuple[str, str, int]] = set()
        for row in relations:
            source_id = row.get("source_id")
            cell_id = row.get("cell_id")
            branch_index = row.get("source_branch_index")
            if source_id not in source_ids:
                raise ValueError("source-cell relations contain an unknown source_id")
            if cell_id not in by_id:
                raise ValueError("source-cell relations contain an unknown cell_id")
            if not isinstance(branch_index, int) or branch_index < 0:
                raise ValueError("source-cell relations contain an invalid branch index")
            key = (source_id, cell_id, branch_index)
            if key in actual_relations:
                raise ValueError("source-cell relations contain a duplicate relation")
            actual_relations.add(key)
        result["source_cell_relations"] = {
            "artifact_relations": len(actual_relations),
            "expected_relations": len(expected_relations),
            "unlinked_expected_branches": unlinked_expected_branches,
            "relation_set_match": actual_relations == expected_relations,
            "artifact_only_relations": len(actual_relations - expected_relations),
            "mapping_only_relations": len(expected_relations - actual_relations),
        }
    return result


def _agreement(
    primary: dict[str, dict[str, Any]],
    repeat: dict[str, dict[str, Any]],
    dimensions: list[str],
) -> dict[str, Any]:
    shared = sorted(set(primary) & set(repeat))
    result_matches = sum(primary[key]["result"] == repeat[key]["result"] for key in shared)
    eligibility_matches = sum(
        primary[key]["phase2_eligible"] == repeat[key]["phase2_eligible"]
        for key in shared
    )
    cell_matches = sum(
        _mapping_cell_multiset(primary[key], dimensions)
        == _mapping_cell_multiset(repeat[key], dimensions)
        for key in shared
    )
    with_cells = [
        key for key in shared if primary[key]["cells"] or repeat[key]["cells"]
    ]
    complete_both = [
        key
        for key in shared
        if primary[key]["result"] == repeat[key]["result"] == "complete"
    ]
    result_by_primary = {}
    for result in RESULT_ORDER:
        cohort = [key for key in shared if primary[key]["result"] == result]
        matches = sum(repeat[key]["result"] == result for key in cohort)
        result_by_primary[result] = _fraction(matches, len(cohort))

    dimension_agreement = {}
    for dimension in dimensions:
        def signature(mapping: dict[str, Any]) -> tuple[str, ...]:
            return tuple(
                sorted(
                    json.dumps(_normalise_value(cell[dimension]), sort_keys=True)
                    for cell in mapping["cells"]
                )
            )

        matches = sum(signature(primary[key]) == signature(repeat[key]) for key in with_cells)
        dimension_agreement[dimension] = _fraction(matches, len(with_cells))

    return {
        "comparison_is_source_id_paired": True,
        "branch_order_ignored": True,
        "shared_source_ids": len(shared),
        "primary_source_ids": len(primary),
        "repeat_source_ids": len(repeat),
        "result_exact_agreement": _fraction(result_matches, len(shared)),
        "result_agreement_by_primary_result": result_by_primary,
        "phase2_eligibility_exact_agreement": _fraction(
            eligibility_matches, len(shared)
        ),
        "feature_cell_multiset_exact_agreement_all_shared": _fraction(
            cell_matches, len(shared)
        ),
        "feature_cell_multiset_exact_agreement_with_any_cells": _fraction(
            sum(
                _mapping_cell_multiset(primary[key], dimensions)
                == _mapping_cell_multiset(repeat[key], dimensions)
                for key in with_cells
            ),
            len(with_cells),
        ),
        "exact_complete_cell_set_agreement": _fraction(
            sum(
                _mapping_cell_multiset(primary[key], dimensions)
                == _mapping_cell_multiset(repeat[key], dimensions)
                for key in complete_both
            ),
            len(complete_both),
        ),
        "feature_multiset_agreement_by_dimension_with_any_cells": dimension_agreement,
    }


def audit_full_normalisation(
    *,
    source_path: Path,
    phase1_path: Path,
    schema_path: Path,
    phase2_path: Path | None = None,
    phase1_attempts_path: Path | None = None,
    phase2_attempts_path: Path | None = None,
    cells_path: Path | None = None,
    relations_path: Path | None = None,
    repeat_mappings_path: Path | None = None,
    allow_incomplete: bool = False,
) -> dict[str, Any]:
    """Return aggregate-only diagnostics and fail on identity corruption."""

    schema = read_yaml(schema_path)
    dimensions = list(schema["dimension_order"])
    if len(dimensions) != len(set(dimensions)):
        raise ValueError("grammar schema dimension_order contains duplicates")
    source_rows = read_jsonl(source_path)
    source_by_id = _index_source(source_rows)
    source_ids = set(source_by_id)

    phase1, embedded_phase1_status, phase1_record_ids = _load_mapping_stream(
        phase1_path, "Phase-1 stream"
    )
    phase1_coverage = _assert_id_coverage(
        phase1_record_ids,
        source_ids,
        "Phase-1 stream",
        allow_incomplete=allow_incomplete,
    )
    for source_id, mapping in phase1.items():
        _validate_mapping(mapping, source_id, schema)

    expected_phase2_ids = {
        source_id
        for source_id, mapping in phase1.items()
        if mapping["result"] == "partial"
        and bool(mapping["phase2_eligible"])
        and bool(source_by_id[source_id]["examples"])
    }
    phase2: dict[str, dict[str, Any]] = {}
    embedded_phase2_status: list[dict[str, Any]] = []
    phase2_record_ids: set[str] = set()
    phase2_coverage = None
    if phase2_path is not None:
        phase2, embedded_phase2_status, phase2_record_ids = _load_mapping_stream(
            phase2_path, "Phase-2 stream"
        )
        phase2_coverage = _assert_id_coverage(
            phase2_record_ids,
            expected_phase2_ids,
            "Phase-2 stream",
            allow_incomplete=allow_incomplete,
        )
        for source_id, mapping in phase2.items():
            _validate_mapping(
                mapping,
                source_id,
                schema,
                allow_resolved_eligibility=True,
            )
            _validate_phase2_transition(phase1[source_id], mapping, schema)

    final_by_id = dict(phase1)
    final_by_id.update(phase2)
    final_rows = [final_by_id[source_id] for source_id in source_by_id if source_id in final_by_id]

    phase1_attempts = (
        _load_status_stream(phase1_attempts_path, "Phase-1 attempts")
        if phase1_attempts_path is not None
        else embedded_phase1_status
    )
    phase2_attempts = (
        _load_status_stream(phase2_attempts_path, "Phase-2 attempts")
        if phase2_attempts_path is not None
        else embedded_phase2_status
    )

    output: dict[str, Any] = {
        "audit_schema": "full_normalisation_audit_v1",
        "privacy": {
            "aggregate_only": True,
            "source_descriptor_text_published": False,
            "mapping_notes_published": False,
            "technical_error_messages_published": False,
            "published_source_metadata": list(CATEGORY_FIELDS),
        },
        "grammar_schema": {
            "schema_id": schema.get("schema_id"),
            "dimensions": dimensions,
        },
        "input_hashes": {
            "typed_source_sha256": sha256_file(source_path),
            "phase1_mappings_sha256": sha256_file(phase1_path),
            "phase2_mappings_sha256": sha256_file(phase2_path)
            if phase2_path is not None
            else None,
            "canonical_cells_sha256": sha256_file(cells_path)
            if cells_path is not None
            else None,
            "source_cell_relations_sha256": sha256_file(relations_path)
            if relations_path is not None
            else None,
            "repeat_mappings_sha256": sha256_file(repeat_mappings_path)
            if repeat_mappings_path is not None
            else None,
        },
        "source_coverage": {
            "typed_source_rows": len(source_rows),
            "unique_source_ids": len(source_ids),
            "phase1": phase1_coverage,
            "phase1_valid_mappings": _fraction(len(phase1), len(source_ids)),
            "phase2_expected_eligible_cohort": len(expected_phase2_ids),
            "phase2": phase2_coverage,
            "phase2_valid_mappings": _fraction(len(phase2), len(expected_phase2_ids))
            if phase2_path is not None
            else None,
        },
        "phase1": _stage_summary(list(phase1.values()), source_by_id, dimensions),
        "phase1_technical_status": _technical_summary(
            phase1_attempts, source_ids, "Phase-1 attempts"
        ),
        "phase2": None,
        "final": {
            "status": (
                "phase1_only"
                if phase2_path is None
                else (
                    "phase2_applied"
                    if phase2_coverage is not None and phase2_coverage["complete"]
                    else "phase2_partially_applied"
                )
            ),
            **_stage_summary(final_rows, source_by_id, dimensions),
        },
        "canonical": _canonical_audit(
            cells_path,
            relations_path,
            final_rows,
            source_ids,
            schema,
        ),
        "repeated_annotation": None,
        "invariants": {
            "source_ids_unique": True,
            "phase1_ids_known": True,
            "phase1_contract_valid": True,
            "phase1_has_valid_mapping_for_every_source": len(phase1) == len(source_ids),
            "phase2_ids_equal_declared_cohort": phase2_coverage["complete"]
            if phase2_coverage is not None
            else None,
            "phase2_has_valid_mapping_for_every_eligible_source": (
                len(phase2) == len(expected_phase2_ids)
                if phase2_path is not None
                else None
            ),
            "phase2_transitions_valid": True if phase2_path is not None else None,
        },
    }

    if phase2_path is not None:
        output["phase2"] = {
            "coverage": phase2_coverage,
            "transitions": _transition_summary(phase1, phase2),
            "mapping_results": _stage_summary(
                list(phase2.values()), source_by_id, dimensions
            ),
            "technical_status": _technical_summary(
                phase2_attempts, expected_phase2_ids, "Phase-2 attempts"
            ),
        }

    if repeat_mappings_path is not None:
        repeat, _repeat_status, repeat_record_ids = _load_mapping_stream(
            repeat_mappings_path, "Repeated-annotation stream"
        )
        repeat_coverage = _assert_id_coverage(
            repeat_record_ids,
            set(phase1_record_ids),
            "Repeated-annotation stream",
            allow_incomplete=allow_incomplete,
        )
        for source_id, mapping in repeat.items():
            _validate_mapping(
                mapping,
                source_id,
                schema,
                allow_resolved_eligibility=True,
            )
        output["repeated_annotation"] = {
            "coverage": repeat_coverage,
            **_agreement(phase1, repeat, dimensions),
        }

    return output


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Private typed source JSONL")
    parser.add_argument("--phase1", type=Path, required=True, help="Phase-1 mapping JSONL")
    parser.add_argument(
        "--schema",
        type=Path,
        default=ROOT / "modules/grammar/canonical/schema.yaml",
    )
    parser.add_argument("--phase2", type=Path)
    parser.add_argument("--phase1-attempts", type=Path)
    parser.add_argument("--phase2-attempts", type=Path)
    parser.add_argument("--cells", type=Path)
    parser.add_argument("--relations", type=Path)
    parser.add_argument("--repeat-mappings", type=Path)
    parser.add_argument("--allow-incomplete", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    arguments = _parse_args()
    result = audit_full_normalisation(
        source_path=arguments.source,
        phase1_path=arguments.phase1,
        schema_path=arguments.schema,
        phase2_path=arguments.phase2,
        phase1_attempts_path=arguments.phase1_attempts,
        phase2_attempts_path=arguments.phase2_attempts,
        cells_path=arguments.cells,
        relations_path=arguments.relations,
        repeat_mappings_path=arguments.repeat_mappings,
        allow_incomplete=arguments.allow_incomplete,
    )
    write_json(arguments.output, result)


if __name__ == "__main__":
    main()
