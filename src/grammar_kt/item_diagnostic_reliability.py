"""Agreement reporting for repeated independent item diagnostics."""

from __future__ import annotations

from typing import Any


def analyse_repeated_diagnostics(
    units: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
    acceptance: dict[str, bool],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    by_uid = {row["validation_unit_id"]: row for row in diagnostics}
    flag_fields = sorted(acceptance)
    comparisons = []
    for alternate_unit in units:
        primary_uid = alternate_unit.get("duplicate_of")
        if primary_uid is None:
            continue
        alternate_uid = alternate_unit["validation_unit_id"]
        if primary_uid not in by_uid or alternate_uid not in by_uid:
            raise RuntimeError(f"repeated item diagnostic pair is incomplete: {alternate_uid}")
        primary = by_uid[primary_uid]["result"]
        alternate = by_uid[alternate_uid]["result"]
        agreement = {field: primary[field] == alternate[field] for field in flag_fields}
        primary_gate = all(primary[field] == expected for field, expected in acceptance.items())
        alternate_gate = all(alternate[field] == expected for field, expected in acceptance.items())
        comparisons.append(
            {
                "item_id": alternate_unit["item_id"],
                "primary_validation_unit_id": primary_uid,
                "alternate_validation_unit_id": alternate_uid,
                "primary_flag_vector": {field: primary[field] for field in flag_fields},
                "alternate_flag_vector": {field: alternate[field] for field in flag_fields},
                "field_agreement": agreement,
                "exact_flag_vector_agreement": all(agreement.values()),
                "primary_acceptance_gate_pass": primary_gate,
                "alternate_acceptance_gate_pass": alternate_gate,
                "could_change_final_acceptance": primary_gate != alternate_gate,
            }
        )

    def rate(numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    disagreeing = [row for row in comparisons if not row["exact_flag_vector_agreement"]]
    acceptance_sensitive = [row for row in comparisons if row["could_change_final_acceptance"]]
    report = {
        "model_check_role": "acceptance_gate",
        "reference_behavior": (
            "The primary model diagnostic is an acceptance gate after deterministic validation. "
            "Repeated diagnostics are reliability evidence and do not replace the primary decision."
        ),
        "future_condition_not_applied": "treat the model check as diagnostic evidence only",
        "repeated_pairs": len(comparisons),
        "exact_flag_vector": {
            "agreements": sum(row["exact_flag_vector_agreement"] for row in comparisons),
            "agreement_rate": rate(sum(row["exact_flag_vector_agreement"] for row in comparisons), len(comparisons)),
        },
        "field_agreement": {
            field: {
                "agreements": sum(row["field_agreement"][field] for row in comparisons),
                "agreement_rate": rate(sum(row["field_agreement"][field] for row in comparisons), len(comparisons)),
            }
            for field in flag_fields
        },
        "item_ids_with_disagreement": sorted(row["item_id"] for row in disagreeing),
        "acceptance_sensitive_disagreements": {
            "count": len(acceptance_sensitive),
            "item_ids": sorted(row["item_id"] for row in acceptance_sensitive),
        },
    }
    return report, comparisons
