"""Full-source, stage-separated EGP normalisation helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .canonicalise import validate_cell
from .io import ModelCall, render
from .normalise import (
    PHASE1_FIELDS,
    _validate_mapping,
    _validate_phase2_transition,
)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def adapt_full_egp_source(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Translate the consult-only raw snapshot to the typed source boundary."""

    adapted = []
    for row in rows:
        adapted.append(
            {
                "source_id": row["egp_id"],
                "supercategory": row["supercategory"],
                "subcategory": row["subcategory"],
                "guideword": row["guideword"],
                "can_do": row["can_do"],
                "examples": row["examples"],
                "cefr": row["cefr_band"],
            }
        )
    ids = [row["source_id"] for row in adapted]
    if len(ids) != len(set(ids)):
        raise ValueError("full EGP source contains duplicate identifiers")
    return adapted


def normalise_phase1_record(
    resource: dict[str, Any],
    phase1_prompt: str,
    rulebook: str,
    grammar_schema: dict[str, Any],
    *,
    model: str,
    reasoning_effort: str,
    model_call: ModelCall,
    evidence_dir: Path,
) -> dict[str, Any]:
    """Run and validate only Phase 1 for one typed descriptor."""

    source_id = resource["source_id"]
    descriptor = {name: resource[name] for name in PHASE1_FIELDS}
    prompt = render(
        phase1_prompt,
        {
            "descriptor": descriptor,
            "canonical_schema": grammar_schema,
            "rulebook": rulebook,
        },
    )
    mapping = model_call(
        prompt,
        model=model,
        reasoning_effort=reasoning_effort,
        input_data={"descriptor": descriptor},
        stage="normalisation.phase1",
        call_key=source_id,
        evidence_dir=evidence_dir,
    )
    _validate_mapping(mapping, source_id, grammar_schema)
    return mapping


def normalise_phase2_record(
    resource: dict[str, Any],
    phase1_mapping: dict[str, Any],
    phase2_prompt: str,
    rulebook: str,
    grammar_schema: dict[str, Any],
    *,
    model: str,
    reasoning_effort: str,
    model_call: ModelCall,
    evidence_dir: Path,
) -> dict[str, Any]:
    """Run and validate branch-preserving Phase 2 for one eligible descriptor."""

    if phase1_mapping["result"] != "partial" or not phase1_mapping[
        "phase2_eligible"
    ]:
        raise ValueError("Phase 2 received an ineligible Phase-1 mapping")
    if not resource["examples"]:
        raise ValueError("Phase 2 received an eligible descriptor without examples")
    source_id = resource["source_id"]
    descriptor = {name: resource[name] for name in PHASE1_FIELDS}
    prompt = render(
        phase2_prompt,
        {
            "descriptor": descriptor,
            "phase1_mapping": phase1_mapping,
            "examples": resource["examples"],
            "canonical_schema": grammar_schema,
            "rulebook": rulebook,
        },
    )
    mapping = model_call(
        prompt,
        model=model,
        reasoning_effort=reasoning_effort,
        input_data={
            "descriptor": descriptor,
            "phase1_mapping": phase1_mapping,
            "examples": resource["examples"],
        },
        stage="normalisation.phase2",
        call_key=source_id,
        evidence_dir=evidence_dir,
    )
    _validate_mapping(
        mapping,
        source_id,
        grammar_schema,
        allow_resolved_eligibility=True,
    )
    _validate_phase2_transition(phase1_mapping, mapping, grammar_schema)
    return mapping


def stable_canonicalise(
    mappings: list[dict[str, Any]], grammar_schema: dict[str, Any]
) -> list[dict[str, Any]]:
    """Canonicalise complete mappings with feature-derived stable cell IDs."""

    dimensions = list(grammar_schema["dimension_order"])
    unique: dict[tuple[str, ...], set[str]] = {}
    for mapping in mappings:
        if mapping["result"] != "complete":
            continue
        for raw_cell in mapping["cells"]:
            features = {name: raw_cell[name] for name in dimensions}
            validate_cell(features, grammar_schema)
            key = tuple(features[name] for name in dimensions)
            unique.setdefault(key, set()).add(mapping["source_id"])

    cells = []
    used_ids: dict[str, tuple[str, ...]] = {}
    for key in sorted(unique):
        features = dict(zip(dimensions, key, strict=True))
        payload = json.dumps(
            features, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        cell_id = "gc_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        if cell_id in used_ids and used_ids[cell_id] != key:
            raise ValueError("GrammarCell hash collision")
        used_ids[cell_id] = key
        cells.append(
            {
                "cell_id": cell_id,
                "features": features,
                "source_ids": sorted(unique[key]),
            }
        )
    return cells


def source_cell_relations(
    mappings: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    grammar_schema: dict[str, Any],
) -> list[dict[str, Any]]:
    """Create opaque source-to-cell provenance without source text."""

    dimensions = list(grammar_schema["dimension_order"])
    cell_by_key = {
        tuple(row["features"][name] for name in dimensions): row["cell_id"]
        for row in cells
    }
    rows = []
    for mapping in mappings:
        if mapping["result"] != "complete":
            continue
        for branch_index, raw_cell in enumerate(mapping["cells"]):
            key = tuple(raw_cell[name] for name in dimensions)
            rows.append(
                {
                    "source_id": mapping["source_id"],
                    "cell_id": cell_by_key[key],
                    "source_branch_index": branch_index,
                }
            )
    return sorted(
        rows,
        key=lambda row: (
            row["source_id"],
            row["source_branch_index"],
            row["cell_id"],
        ),
    )
