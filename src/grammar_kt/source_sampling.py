"""Deterministic execution of a declared EGP source-sampling design."""

from __future__ import annotations

import random
from collections import Counter
from pathlib import Path
from typing import Any

from .io import read_jsonl, sha256_file, write_json, write_jsonl


def _matches(record: dict[str, Any], conditions: dict[str, Any]) -> bool:
    for field, expected in conditions.items():
        values = expected if isinstance(expected, list) else [expected]
        if record.get(field) not in values:
            return False
    return True


def sample_records(
    records: list[dict[str, Any]], design: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Filter, stratify, and select with declared deterministic tie-breaking."""

    allowed = design.get("allowed", {})
    excluded = design.get("excluded", {})
    eligible = [
        row
        for row in records
        if _matches(row, allowed) and not (excluded and _matches(row, excluded))
    ]
    ordering = design.get("ordering", ["egp_id"])
    if not isinstance(ordering, list) or not ordering:
        raise ValueError("sampling design requires deterministic ordering fields")
    eligible.sort(key=lambda row: tuple(str(row.get(field, "")) for field in ordering))

    strata = design.get("strata", [])
    if not isinstance(strata, list) or not strata:
        raise ValueError("sampling design requires at least one declared stratum")
    selected: list[dict[str, Any]] = []
    metadata: list[dict[str, Any]] = []
    audits = []
    assigned: set[str] = set()
    seed = design.get("seed")
    for index, stratum in enumerate(strata):
        stratum_id = stratum["stratum_id"]
        candidates = [
            row
            for row in eligible
            if row["egp_id"] not in assigned and _matches(row, stratum.get("match", {}))
        ]
        if seed is not None:
            rng = random.Random(f"{seed}|{index}|{stratum_id}")
            rng.shuffle(candidates)
        minimum = int(stratum.get("minimum", 0))
        if len(candidates) < minimum:
            raise RuntimeError(
                f"stratum {stratum_id} has {len(candidates)} eligible records; minimum={minimum}"
            )
        quota = stratum.get("quota")
        if quota is not None and int(quota) < minimum:
            raise ValueError(
                f"stratum {stratum_id} quota={quota} is below minimum={minimum}"
            )
        chosen = candidates if quota is None else candidates[: int(quota)]
        for rank, row in enumerate(chosen, 1):
            assigned.add(row["egp_id"])
            selected.append(row)
            metadata.append(
                {
                    "egp_id": row["egp_id"],
                    "selection_stratum": stratum_id,
                    "within_stratum_rank": rank,
                    "selection_rule": stratum.get("rationale"),
                }
            )
        audits.append(
            {
                "stratum_id": stratum_id,
                "eligible": len(candidates),
                "minimum": minimum,
                "quota": quota,
                "selected": len(chosen),
            }
        )
    audit = {
        "design_id": design["design_id"],
        "source_records": len(records),
        "eligible_after_scope_filters": len(eligible),
        "selected_descriptors": len(selected),
        "ordering": ordering,
        "seed": seed,
        "strata": audits,
        "unselected_eligible": len(eligible) - len(assigned),
        "selected_by_supercategory": dict(
            sorted(
                Counter(
                    str(row.get("supercategory") or "UNSPECIFIED")
                    for row in selected
                ).items()
            )
        ),
    }
    return selected, metadata, audit


def execute_sampling(
    source_path: Path,
    *,
    expected_sha256: str,
    design: dict[str, Any],
    output: Path,
) -> dict[str, Any]:
    actual = sha256_file(source_path)
    if actual != expected_sha256:
        raise RuntimeError("external EGP source SHA-256 differs from the declared sampling input")
    records = read_jsonl(source_path)
    selected, metadata, audit = sample_records(records, design)
    audit["source_sha256"] = actual
    output.mkdir(parents=True, exist_ok=False)
    (output / "sample_ids.txt").write_text(
        "".join(f"{row['egp_id']}\n" for row in selected), encoding="utf-8"
    )
    write_jsonl(output / "sample_metadata.jsonl", metadata, sort_keys=False)
    write_json(output / "sampling_audit.json", audit)
    return audit
