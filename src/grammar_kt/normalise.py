"""Stage 1: two-phase EGP normalisation into resource-neutral mappings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tqdm.auto import tqdm

from .io import ModelCall, call_model, render


RESULTS = {"complete", "partial", "out_of_scope", "unresolved"}
PHASE1_FIELDS = ("source_id", "supercategory", "subcategory", "guideword", "can_do")
MAPPING_FIELDS = {"source_id", "result", "cells", "phase2_eligible", "note"}


def _validate_mapping(
    mapping: dict[str, Any],
    source_id: str,
    schema: dict[str, Any],
    *,
    allow_resolved_eligibility: bool = False,
) -> None:
    if set(mapping) != MAPPING_FIELDS:
        raise ValueError(
            f"{source_id}: normalisation fields must be {sorted(MAPPING_FIELDS)}"
        )
    if mapping["source_id"] != source_id or mapping["result"] not in RESULTS:
        raise ValueError(f"invalid normalisation result for {source_id}")

    dimensions = schema["dimensions"]
    eligible = mapping["phase2_eligible"]
    if (
        not isinstance(eligible, list)
        or any(not isinstance(name, str) for name in eligible)
        or len(eligible) != len(set(eligible))
        or not set(eligible) <= set(dimensions)
    ):
        raise ValueError(f"{source_id}: invalid phase2_eligible dimensions")
    declared_order = [
        name for name in schema["dimension_order"] if name in set(eligible)
    ]
    if eligible != declared_order:
        raise ValueError(
            f"{source_id}: phase2_eligible must follow canonical dimension order"
        )

    if mapping["result"] in {"out_of_scope", "unresolved"}:
        if mapping["cells"]:
            raise ValueError(f"{mapping['result']} mappings cannot contain cells")
        if eligible and not allow_resolved_eligibility:
            raise ValueError(
                f"{source_id}: Phase-1 {mapping['result']} mapping cannot be "
                "Phase-2 eligible"
            )
        return

    has_uncertainty = False
    uncertain_dimensions: set[str] = set()
    for cell in mapping["cells"]:
        if set(cell) != set(dimensions):
            raise ValueError(f"{source_id}: normalised cell has wrong dimensions")
        for name, value in cell.items():
            allowed = set(dimensions[name]["allowed_values"])
            if value is None:
                has_uncertainty = True
                uncertain_dimensions.add(name)
            elif isinstance(value, list):
                has_uncertainty = True
                uncertain_dimensions.add(name)
                if not value or not set(value) <= allowed:
                    raise ValueError(f"{source_id}: invalid bounded values for {name}")
            elif value not in allowed:
                raise ValueError(f"{source_id}: invalid {name}={value}")
    if mapping["result"] == "complete" and (has_uncertainty or not mapping["cells"]):
        raise ValueError(f"{source_id}: complete mapping must contain exact cells")
    eligibility_is_invalid = eligible and not set(eligible) <= uncertain_dimensions
    if not allow_resolved_eligibility and eligibility_is_invalid:
        invalid = sorted(set(eligible) - uncertain_dimensions)
        raise ValueError(
            f"{source_id}: phase2_eligible dimensions are not uncertain: {invalid}"
        )
    if mapping["result"] == "partial":
        if not has_uncertainty:
            raise ValueError(f"{source_id}: partial mapping must retain uncertainty")


def _value_domain(value: Any, allowed_values: list[str]) -> set[str]:
    if value is None:
        return set(allowed_values)
    if isinstance(value, list):
        return set(value)
    return {value}


def _is_branch_narrowing(
    first_cell: dict[str, Any],
    second_cell: dict[str, Any],
    eligible: set[str],
    schema: dict[str, Any],
) -> bool:
    for field in schema["dimension_order"]:
        first_value = first_cell[field]
        second_value = second_cell[field]
        if field not in eligible:
            if second_value != first_value:
                return False
            continue
        allowed = schema["dimensions"][field]["allowed_values"]
        if not _value_domain(second_value, allowed) <= _value_domain(
            first_value, allowed
        ):
            return False
    return True


def _validate_phase2_transition(
    first: dict[str, Any],
    second: dict[str, Any],
    schema: dict[str, Any],
) -> None:
    if second["phase2_eligible"] != first["phase2_eligible"]:
        raise ValueError("Phase 2 changed phase2_eligible provenance")
    if second["result"] == "unresolved":
        return
    if second["result"] == "out_of_scope":
        raise ValueError(
            "Phase 2 cannot reclassify an in-scope branch as out_of_scope"
        )

    eligible = set(first["phase2_eligible"])
    compatible_parents: list[list[int]] = []
    for second_cell in second["cells"]:
        parents = [
            index
            for index, first_cell in enumerate(first["cells"])
            if _is_branch_narrowing(first_cell, second_cell, eligible, schema)
        ]
        if not parents:
            raise ValueError(
                "Phase 2 produced a broadened, recombined, or otherwise invalid branch"
            )
        compatible_parents.append(parents)

    covered = {parent for parents in compatible_parents for parent in parents}
    missing = sorted(set(range(len(first["cells"]))) - covered)
    if missing:
        raise ValueError(f"Phase 2 dropped Phase-1 branches: {missing}")


def normalise(
    resources: list[dict[str, Any]],
    phase1_prompt: str,
    phase2_prompt: str,
    rulebook: str,
    grammar_schema: dict[str, Any],
    *,
    model: str,
    reasoning_effort: str,
    model_call: ModelCall = call_model,
    evidence_dir: Path | None = None,
    show_progress: bool = False,
) -> list[dict[str, Any]]:
    """Normalise typed descriptors in source order using the declared two phases."""

    mappings = []

    resource_rows = tqdm(
        resources,
        desc="Normalising descriptors",
        disable=not show_progress,
        unit="descriptor",
    )
    for resource in resource_rows:
        source_id = resource["source_id"]
        phase1_descriptor = {name: resource[name] for name in PHASE1_FIELDS}
        prompt = render(
            phase1_prompt,
            {
                "descriptor": phase1_descriptor,
                "canonical_schema": grammar_schema,
                "rulebook": rulebook,
            },
        )
        first = model_call(
            prompt,
            model=model,
            reasoning_effort=reasoning_effort,
            input_data={"descriptor": phase1_descriptor},
            stage="normalisation.phase1",
            call_key=source_id,
            evidence_dir=(
                evidence_dir / "calls" / f"{source_id}_phase1"
                if evidence_dir
                else None
            ),
        )
        _validate_mapping(first, source_id, grammar_schema)

        final = first
        eligible = first["phase2_eligible"]
        if first["result"] == "partial" and eligible and resource["examples"]:
            prompt = render(
                phase2_prompt,
                {
                    "descriptor": phase1_descriptor,
                    "phase1_mapping": first,
                    "examples": resource["examples"],
                    "canonical_schema": grammar_schema,
                    "rulebook": rulebook,
                },
            )
            final = model_call(
                prompt,
                model=model,
                reasoning_effort=reasoning_effort,
                input_data={
                    "descriptor": phase1_descriptor,
                    "phase1_mapping": first,
                    "examples": resource["examples"],
                },
                stage="normalisation.phase2",
                call_key=source_id,
                evidence_dir=(
                    evidence_dir / "calls" / f"{source_id}_phase2"
                    if evidence_dir
                    else None
                ),
            )
            _validate_mapping(
                final,
                source_id,
                grammar_schema,
                allow_resolved_eligibility=True,
            )
            _validate_phase2_transition(first, final, grammar_schema)
        mappings.append(final)
    return mappings
